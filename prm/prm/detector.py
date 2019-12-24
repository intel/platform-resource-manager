# Copyright (C) 2018 Intel Corporation
#  
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#  
# http://www.apache.org/licenses/LICENSE-2.0
#  
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.
#  
#
# SPDX-License-Identifier: Apache-2.0
import logging
import json
import numpy as np
from typing import List

from wca import detectors
from wca.platforms import Platform
from wca.detectors import ContentionAnomaly, ContendedResource, TasksData
from wca.metrics import Metric as WCAMetric

from prm.container import Container
from prm.analyze.analyzer import Metric, Analyzer, ThreshType
from prm.model_distribution.db import ModelDatabase, correct_key_characters
from prm.utils import (extract_tasks_data, TasksLabels, TasksResources,
                       TasksMeasurements)

log = logging.getLogger(__name__)


class ContentionDetector(detectors.AnomalyDetector):
    WL_META_FILE = 'workload.json'

    def __init__(
        self,
        database: ModelDatabase,
        action_delay: float,
        agg_period: float = 20,
        model_pull_cycle: float = 180,
        metric_file: str = Analyzer.METRIC_FILE
    ):
        log.debug('action_delay: %i, agg_period: %i, model_pull_cycle: %i',
                  action_delay, agg_period, model_pull_cycle)
        self.metric_file = metric_file
        self.agg_cnt = int(agg_period) / int(action_delay) \
            if int(agg_period) % int(action_delay) == 0 else 1

        self.counter = 0
        self.agg = False
        self.container_map = dict()
        self.ucols = ['time', 'cid', 'name', Metric.UTIL]
        self.mcols = ['time', 'cid', 'name', 'cpu_model', 'vcpu_count',
                      Metric.CYC, Metric.INST,
                      Metric.L3MISS, Metric.L3OCC, Metric.MB, Metric.CPI,
                      Metric.L3MPKI, Metric.NF, Metric.UTIL, Metric.MSPKI]
        self.workload_meta = {}
        self.analyzer = Analyzer()
        if database:
            self.database = database
            self.model_pull_cycle = model_pull_cycle
            self.threshs = {}
            self.cycle = 0

    def _init_data_file(self, data_file, cols):
        headline = None
        try:
            with open(data_file, 'r') as dtf:
                headline = dtf.readline()
        except Exception:
            log.debug('cannot open %r for reading - ignore', data_file)
        if headline != ','.join(cols) + '\n':
            with open(data_file, 'w') as dtf:
                dtf.write(','.join(cols) + '\n')

    def _detect_contenders(self, con: Container, resource: ContendedResource):
        contenders = []
        if resource == ContendedResource.UNKN:
            return contenders

        resource_delta_max = -np.Inf
        contender_id = None
        for cid, container in self.container_map.items():
            delta = 0
            if con.cid == cid:
                continue
            if resource == ContendedResource.LLC:
                delta = container.get_llcoccupany_delta()
            elif resource == ContendedResource.MEMORY_BW:
                delta = container.get_latest_mbt()
            elif resource == ContendedResource.TDP:
                delta = container.get_freq_delta()

            if delta > 0 and delta > resource_delta_max:
                resource_delta_max = delta
                contender_id = container.cid

        if contender_id:
            contenders.append(contender_id)

        return contenders

    def _append_anomaly(self, anomalies, res, cid, contenders, wca_metrics):
        anomaly = ContentionAnomaly(
                resource=res,
                contended_task_id=cid,
                contending_task_ids=contenders,
                metrics=wca_metrics
            )
        anomalies.append(anomaly)

    def _get_thresholds(self, app: str, thresh_type: ThreshType):
        thresh = {}
        vcpus = str(self.workload_meta[app]['cpus'])
        if self.threshs and app in self.threshs and vcpus in self.threshs[app]:
            thresh = self.threshs[app][vcpus][thresh_type.value]
        return thresh

    def _detect_one_task(self, con: Container, app: str):
        anomalies = []
        if not con.get_metrics():
            return anomalies

        cid = con.cid
        thresh = self._get_thresholds(app, ThreshType.METRICS)
        if thresh:
            contends, wca_metrics = con.contention_detect(thresh)
            log.debug('cid=%r contends=%r', cid, contends)
            log.debug('cid=%r threshold metrics=%r', cid, wca_metrics)
            for contend in contends:
                contenders = self._detect_contenders(con, contend)
                self._append_anomaly(anomalies, contend, cid, contenders,
                                     wca_metrics)
        thresh_tdp = self._get_thresholds(app, ThreshType.TDP)
        if thresh_tdp:
            tdp_contend, wca_metrics = con.tdp_contention_detect(thresh_tdp)
            if tdp_contend:
                contenders = self._detect_contenders(con, tdp_contend)
                self._append_anomaly(anomalies, tdp_contend, cid, contenders,
                                     wca_metrics)

        return anomalies

    def _get_container_from_taskid(self, cid):
        if cid in self.container_map:
            container = self.container_map[cid]
        else:
            container = Container(cid)
            self.container_map[cid] = container
        return container

    def _remove_finished_tasks(self, cidset: set):
        for cid in self.container_map.copy():
            if cid not in cidset:
                del self.container_map[cid]

    def _cid_to_app(self, cid, tasks_labels: TasksLabels):
        """
        Maps container id to a string key identifying statistical model instance.
        """
        if 'application' in tasks_labels[cid]:
            app = tasks_labels[cid]['application']
            if 'application_version_name' in tasks_labels[cid] and\
               tasks_labels[cid]['application_version_name']:
                return app + '.' + tasks_labels[cid]['application_version_name']
            else:
                return app
        else:
            log.warn('no label "application" '
                     'passed to detect function by wca for container: {}'.format(cid))

        return None

    def _is_be_app(self, cid, tasks_labels: TasksLabels):
        if 'type' in tasks_labels[cid] and tasks_labels[cid]['type'] == 'best_efforts':
            return True

        return False

    def _get_headroom_metrics(self, assign_cpus, lcutil, sysutil):
        util_max = self.analyzer.get_lcutilmax()
        if util_max < lcutil:
            self.analyzer.update_lcutilmax(lcutil)
            util_max = lcutil
        capacity = assign_cpus * 100
        return [WCAMetric(name=Metric.LCCAPACITY, value=capacity),
                WCAMetric(name=Metric.LCMAX, value=util_max),
                WCAMetric(name=Metric.SYSUTIL, value=sysutil)]

    def _get_threshold_metrics(self):
        """Encode threshold objects as WCA metrics.
        In contrast to *_threshold metrics from Container,
        all utilization partitions are exposed for all workloads.
        """
        metrics = []
        # Only when debugging is enabled.
        if log.getEffectiveLevel() == logging.DEBUG:
            for cid, threshold in self.analyzer.threshold.items():
                if cid == 'lcutilmax':
                    metrics.append(
                        WCAMetric(name='threshold_lcutilmax', value=threshold)
                    )
                    continue
                if 'tdp' in threshold and 'bar' in threshold['tdp']:
                    metrics.extend([
                        WCAMetric(
                            name='threshold_tdp_bar',
                            value=threshold['tdp']['bar'],
                            labels=dict(cid=cid)),
                        WCAMetric(
                            name='threshold_tdp_util',
                            value=threshold['tdp']['util'],
                            labels=dict(cid=cid)),
                    ])
                if 'thresh' in threshold:
                    for d in threshold['thresh']:
                        metrics.extend([
                            WCAMetric(
                                name='threshold_cpi',
                                labels=dict(start=str(int(d['util_start'])),
                                            end=str(int(d['util_end'])),
                                            cid=cid),
                                value=d['cpi']),
                            WCAMetric(
                                name='threshold_mpki',
                                labels=dict(start=str(int(d['util_start'])),
                                            end=str(int(d['util_end'])),
                                            cid=cid),
                                value=(d['mpki'])),
                            WCAMetric(
                                name='threshold_mb',
                                labels=dict(start=str(int(d['util_start'])),
                                            end=str(int(d['util_end'])),
                                            cid=cid),
                                value=(d['mb'])),
                        ])

        return metrics

    def _record_utils(self, time, utils):
        row = [str(time), '', 'lcs']
        for i in range(3, len(self.ucols)):
            row.append(str(utils))
        with open(Analyzer.UTIL_FILE, 'a') as utilf:
            utilf.write(','.join(row) + '\n')

    def _record_metrics(self, time, cid, name, cpu_model, vcpus, metrics):
        row = [str(time), cid, name, cpu_model, str(vcpus)]
        for i in range(5, len(self.mcols)):
            row.append(str(metrics[self.mcols[i]]))
        with open(self.metric_file, 'a') as metricf:
            metricf.write(','.join(row) + '\n')

    def _update_workload_meta(self):
        with open(ContentionDetector.WL_META_FILE, 'w') as wlf:
            wlf.write(json.dumps(self.workload_meta))

    def _get_task_resources(self, tasks_resources: TasksResources,
                            tasks_labels: TasksLabels):
        assigned_cpus = 0
        cidset = set()
        for cid, resources in tasks_resources.items():
            cidset.add(cid)
            if not self._is_be_app(cid, tasks_labels):
                assigned_cpus += resources['cpus']
            app = self._cid_to_app(cid, tasks_labels)
            if app:
                self.workload_meta[app] = resources

        self._update_workload_meta()

        self._remove_finished_tasks(cidset)
        return assigned_cpus

    def _process_measurements(
        self,
        tasks_measurements: TasksMeasurements,
        tasks_labels: TasksLabels,
        metric_list: List[WCAMetric],
        timestamp: float,
        assigned_cpus: float,
        cpu_model: str
    ):
        sysutil = 0
        lcutil = 0
        for cid, measurements in tasks_measurements.items():
            app = self._cid_to_app(cid, tasks_labels)
            container = self._get_container_from_taskid(cid)
            container.update_measurement(timestamp, measurements, self.agg)
            if not self._is_be_app(cid, tasks_labels):
                lcutil += container.util
            sysutil += container.util
            if self.agg:
                metrics = container.get_metrics()
                log.debug('cid=%r container metrics=%r', cid, metrics)
                if metrics and app:
                    vcpus = self.workload_meta[app]['cpus']
                    wca_metrics = container.get_wca_metrics(app, vcpus)
                    metric_list.extend(wca_metrics)
                    # always try to init header column considering log rotate
                    self._init_data_file(self.metric_file, self.mcols)
                    self._record_metrics(timestamp, cid, app,
                                         correct_key_characters(cpu_model),
                                         vcpus, metrics)

        metric_list.extend(self._get_headroom_metrics(assigned_cpus, lcutil, sysutil))

    def detect(
            self,
            platform: Platform,
            tasks_data: TasksData):

        tasks_resources, tasks_labels, \
                tasks_measurements, tasks_allocations = extract_tasks_data(tasks_data)

        log.debug('prm detect called...')
        log.debug('task_labels=%r', tasks_labels)

        self.counter += 1
        if self.counter == self.agg_cnt:
            self.counter = 0
            self.agg = True
        else:
            self.agg = False

        assigned_cpus = self._get_task_resources(tasks_resources, tasks_labels)

        metric_list = []
        metric_list.extend(self._get_threshold_metrics())
        self._process_measurements(tasks_measurements, tasks_labels, metric_list,
                                   platform.timestamp, assigned_cpus, platform.cpu_model)

        anomaly_list = []
        if self.agg:
            if self.database and self.cycle == 0:
                try:
                    threshs = self.database.get(platform.cpu_model)
                    self.threshs = json.loads(threshs)
                    if self.threshs:
                        log.debug('pulled model thresholds=%r', self.threshs)
                    else:
                        log.warn('No model is pulled from model database!')
                except Exception:
                    log.exception('error in pulling model from database')
            self.cycle += 1
            if self.cycle == self.model_pull_cycle:
                self.cycle = 0

            for container in self.container_map.values():
                app = self._cid_to_app(container.cid, tasks_labels)
                if app:
                    anomalies = self._detect_one_task(container, app)
                    anomaly_list.extend(anomalies)
            if anomaly_list:
                log.debug('anomalies: %r', anomaly_list)
        if metric_list:
            log.debug('metrics: %r', metric_list)
        return anomaly_list, metric_list
