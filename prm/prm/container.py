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

"""
This module implements resource contention detection on one workload
"""

import logging
from datetime import datetime
from collections import deque
from wca.metrics import Metric as WCAMetric
from wca.metrics import Measurements, MetricName
from wca.detectors import ContendedResource
from prm.analyze.analyzer import Metric

log = logging.getLogger(__name__)


class Container:
    """
    This class is the abstraction of one task, container metrics and
    contention detection method are encapsulated in this module
    """

    def __init__(self, cid, history_depth=5):
        self.cid = cid
        self.metrics = dict()
        self.measurements = None
        self.timestamp = 0
        self.cpu_usage = 0
        self.util = 0
        self.usg_tt = 0
        self.total_llc_occu = 0
        self.llc_cnt = 0
        self.history_depth = history_depth + 1
        self.metrics_history = deque([], self.history_depth)

    '''
    add metric data to metrics history
    metrics history only contains the most recent metrics data, defined by
    self.historyDepth if histroy metrics data length exceeds the
    self.historyDepth, the oldest data will be erased
    '''
    def _update_metrics_history(self):
        self.metrics_history.append(self.metrics.copy())

    def _get_history_delta_by_Type(self, columnname):
        length = len(self.metrics_history)
        if length == 0:
            return 0

        if length == 1:
            return self.metrics_history[length - 1][columnname]

        data_sum = 0

        for x in range(length - 1):
            data_sum = data_sum + self.metrics_history[x][columnname]

        data_delta = self.metrics_history[length - 1][columnname] -\
            data_sum / (length - 1)

        return data_delta

    def get_llcoccupany_delta(self):
        return self._get_history_delta_by_Type(Metric.L3OCC)

    def get_freq_delta(self):
        return self._get_history_delta_by_Type(Metric.NF)

    def get_latest_mbt(self):
        if Metric.MB not in self.metrics:
            return 0
        return self.metrics[Metric.MB]

    def get_metrics(self):
        """ retrieve container platform metrics """
        return self.metrics

    def get_wca_metrics(self, app, vcpu):
        metrics = []
        if self.metrics:
            for met, val in self.metrics.items():
                label_dict = dict(
                    task_id=self.cid
                )
                if app:
                    label_dict['application'] = app
                    label_dict['initial_task_cpu_assignment'] = str(vcpu)

                metric = WCAMetric(
                    name=met,
                    value=val,
                    labels=label_dict
                )
                metrics.append(metric)
        return metrics

    def update_measurement(self, timestamp: float,
                           measurements: Measurements, agg: bool):
        """
        update measurements in current cycle and calculate metrics
        """

        def delta(name):
            dlt = measurements[name] - self.measurements[name]
            return dlt if dlt > 0 else 0

        if self.cpu_usage != 0:
            self.util = (measurements[MetricName.TASK_CPU_USAGE_SECONDS] -
                         self.cpu_usage) * 100 / ((timestamp - self.usg_tt) * 1e9)
        self.cpu_usage = measurements[MetricName.TASK_CPU_USAGE_SECONDS]
        self.usg_tt = timestamp

        if measurements.get(MetricName.TASK_LLC_OCCUPANCY_BYTES, 0) > 0:
            self.total_llc_occu += measurements[MetricName.TASK_LLC_OCCUPANCY_BYTES]
            self.llc_cnt += 1
        if self.measurements and agg:
            metrics = self.metrics
            delta_t = timestamp - self.timestamp
            metrics[Metric.CYC] = delta(MetricName.TASK_CYCLES)
            metrics[Metric.INST] = delta(MetricName.TASK_INSTRUCTIONS)
            metrics[Metric.L3MISS] = delta(MetricName.TASK_CACHE_MISSES)
            # TODO: Check!
            metrics[Metric.MEMSTALL] = delta(MetricName.TASK_STALLED_MEM_LOADS)
            if self.llc_cnt == 0:
                metrics[Metric.L3OCC] = 0
            else:
                metrics[Metric.L3OCC] = self.total_llc_occu / self.llc_cnt / 1024
            self.total_llc_occu = 0
            self.llc_cnt = 0
            if metrics[Metric.INST] == 0:
                metrics[Metric.CPI] = 0
                metrics[Metric.L3MPKI] = 0
            else:
                metrics[Metric.CPI] = metrics[Metric.CYC] /\
                    metrics[Metric.INST]
                metrics[Metric.L3MPKI] = metrics[Metric.L3MISS] * 1000 /\
                    metrics[Metric.INST]
                metrics[Metric.MSPKI] = metrics[Metric.MEMSTALL] * 1000 /\
                    metrics[Metric.INST]
            metrics[Metric.UTIL] = delta(MetricName.TASK_CPU_USAGE_SECONDS) * 100 / (delta_t * 1e9)
            if measurements.get(MetricName.TASK_MEM_BANDWIDTH_BYTES, 0) > 0:
                metrics[Metric.MB] = (measurements[MetricName.TASK_MEM_BANDWIDTH_BYTES] -
                                      self.measurements.get(
                                          MetricName.TASK_MEM_BANDWIDTH_BYTES, 0)) /\
                    1024 / 1024 / delta_t
            if metrics[Metric.UTIL] == 0:
                metrics[Metric.NF] = 0
            else:
                metrics[Metric.NF] = metrics[Metric.CYC] / delta_t / 10000 /\
                    metrics[Metric.UTIL]
            self._update_metrics_history()

        if not self.measurements or agg:
            self.measurements = measurements
            self.timestamp = timestamp

    def _append_metrics(self, metrics, mname, mvalue):
        metric = WCAMetric(
                name=mname,
                value=mvalue,
                labels=dict(
                    task_id=self.cid,
                )
            )
        metrics.append(metric)

    def _detect_in_bin(self, thresh):
        wca_metrics = []
        cond_res = []
        metrics = self.metrics
        unknown_reason = True
        if metrics[Metric.CPI] > thresh['cpi']:
            self._append_metrics(wca_metrics, Metric.CPI,
                                 metrics[Metric.CPI])
            self._append_metrics(wca_metrics, 'cpi_threshold', thresh['cpi'])

            if metrics[Metric.L3MPKI] > thresh['mpki']:
                log.info('Last Level Cache contention is detected:')
                log.info('Latency critical container %s CPI = %f MPKI = %f \n',
                         self.cid, metrics[Metric.CPI], metrics[Metric.L3MPKI])
                self._append_metrics(wca_metrics, Metric.L3MPKI,
                                     metrics[Metric.L3MPKI])
                self._append_metrics(wca_metrics, 'mpki_threshold',
                                     thresh['mpki'])
                cond_res.append(ContendedResource.LLC)
                unknown_reason = False

            if metrics[Metric.MSPKI] > thresh['mspki']:
                log.info('Memory Bandwidth contention detected:')
                log.info('Latency critical container %s CPI = %f MSPKI = %f \n',
                         self.cid, metrics[Metric.CPI], metrics[Metric.MSPKI])
                self._append_metrics(wca_metrics, Metric.MSPKI,
                                     metrics[Metric.MSPKI])
                self._append_metrics(wca_metrics, 'mspki_threshold',
                                     thresh['mspki'])
                cond_res.append(ContendedResource.MEMORY_BW)
                unknown_reason = False

            if unknown_reason:
                log.info('Performance is impacted by unknown reason:')
                log.info('Latency critical container %s CPI exceeds threshold = %f',
                         self.cid, metrics[Metric.CPI])
                cond_res.append(ContendedResource.UNKN)

            return cond_res, wca_metrics

        return [], wca_metrics

    def tdp_contention_detect(self, tdp_thresh):
        """ detect TDP contention in container """
        wca_metrics = []
        if not tdp_thresh:
            return None, wca_metrics

        metrics = self.metrics
        log.debug('Current utilization = %f, frequency = %f, tdp utilization\
                  threshold = %f, tdp frequency bar = %f', metrics[Metric.UTIL],
                  metrics[Metric.NF], tdp_thresh['util'], tdp_thresh['bar'])

        if metrics[Metric.UTIL] >= tdp_thresh['util'] and\
           self.metrics[Metric.NF] < tdp_thresh['bar']:
            log.info('TDP Contention Alert!')
            self._append_metrics(wca_metrics, Metric.NF, metrics[Metric.NF])
            self._append_metrics(wca_metrics, 'nf_threshold',
                                 tdp_thresh['bar'])
            self._append_metrics(wca_metrics, Metric.UTIL,
                                 metrics[Metric.UTIL])
            self._append_metrics(wca_metrics, 'util_threshold',
                                 tdp_thresh['util'])

            return ContendedResource.TDP, wca_metrics

        return None, wca_metrics

    def contention_detect(self, threshs):
        """ detect resouce contention after find proper utilization bin """
        if not threshs:
            return [], []

        metrics = self.metrics
        for i in range(0, len(threshs)):
            thresh = threshs[i]
            if metrics[Metric.UTIL] < thresh['util_start']:
                if i == 0:
                    return [], []

                return self._detect_in_bin(threshs[i - 1])

            if metrics[Metric.UTIL] >= thresh['util_start']:
                if metrics[Metric.UTIL] < thresh['util_end'] or i == len(threshs) - 1:
                    return self._detect_in_bin(thresh)

    def __str__(self):
        metrics = self.metrics
        return datetime.fromtimestamp(self.timestamp).isoformat() + ',' +\
            self.cid + ',' + str(metrics[Metric.INST]) +\
            ',' + str(metrics[Metric.CYC]) + ',' +\
            str(metrics[Metric.CPI]) + ',' + str(metrics[Metric.L3MPKI]) +\
            ',' + str(metrics[Metric.L3MISS]) + ',' +\
            str(metrics[Metric.NF]) + ',' + str(metrics[Metric.UTIL]) +\
            ',' + str(metrics[Metric.L3OCC]) + ',' +\
            str(metrics[Metric.MB]) + ',' + str(metrics[Metric.MSPKI]) + '\n'
