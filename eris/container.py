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

from __future__ import print_function
from __future__ import division

import time
import multiprocessing

from collections import deque
from itertools import islice
from enum import Enum
from os.path import join as path_join
from analyze.analyzer import Metric


class Contention(Enum):
    """ This enumeration defines resource contention type """
    UNKN = 1
    CPU_CYC = 2
    LLC = 3
    MEM_BW = 4
    TDP = 5


class Container(object):
    """
    This class is the abstraction of one task, container metrics and
    contention detection method are encapsulated in this module
    """

    def __init__(
            self, cgroup_driver, cid, name, pids, verbose,
            thresh=[], tdp_thresh=[], history_depth=5):
        self.cid = cid
        self.name = name
        self.pids = pids
        self.cpu_usage = 0
        self.system_usage = 0
        self.utils = 0
        self.timestamp = 0.0
        self.thresh = thresh
        self.tdp_thresh = tdp_thresh
        self.verbose = verbose
        self.metrics = dict()
        self.history_depth = history_depth + 1
        self.metrics_history = deque([], self.history_depth)
        self.cpusets = []
        if cgroup_driver == 'systemd':
            self.con_path = 'docker-' + cid + '.scope'
            self.parent_path = 'system.slice/'
        else:
            self.con_path = cid
            self.parent_path = 'docker/'

    def __str__(self):
        metrics = self.metrics
        cols = [
            metrics['time'],
            self.cid,
            self.name,
            metrics[Metric.INST],
            metrics[Metric.CYC],
            metrics[Metric.CPI],
            metrics[Metric.L3MPKI],
            metrics[Metric.L3MISS],
            metrics[Metric.NF],
            self.utils,
            metrics[Metric.L3OCC],
            metrics[Metric.MBL],
            metrics[Metric.MBR],
            metrics[Metric.L2STALL],
            metrics[Metric.MEMSTALL],
            metrics[Metric.L2SPKI],
            metrics[Metric.MSPKI],
        ]
        return ','.join(str(col) for col in cols) + '\n'

    def update_metrics(self, row_tuple):
        key_mappings = [('time', str), (Metric.INST, int), (Metric.CYC, int),
                        (Metric.CPI, float), (Metric.L3MPKI, float),
                        (Metric.L3MISS, int), (Metric.NF, float),
                        (Metric.L3OCC, int), (Metric.MBL, float),
                        (Metric.MBR, float), (Metric.L2STALL, int),
                        (Metric.MEMSTALL, int), (Metric.L2SPKI, float),
                        (Metric.MSPKI, float)]
        for key, converter in key_mappings:
            self.metrics[key] = converter(row_tuple[1][key])
        self.utils = float(row_tuple[1][Metric.UTIL])
        self.update_metrics_history()

    def get_history_delta_by_type(self, column_name):
        length = len(self.metrics_history)
        if length == 0:
            return 0
        if length == 1:
            return self.metrics_history[0][column_name]
        data_sum = sum(m[column_name] for m in
                       list(islice(self.metrics_history, length - 1)))
        data_avg = float(data_sum) / (length - 1)
        data_delta = self.metrics_history[-1][column_name] - data_avg
        return data_delta

    def get_llcoccupany_delta(self):
        return self.get_history_delta_by_type(Metric.L3OCC)

    def get_freq_delta(self):
        return self.get_history_delta_by_type(Metric.NF)

    def get_latest_mbt(self):
        mbl = self.metrics.get(Metric.MBL, 0)
        mbr = self.metrics.get(Metric.MBR, 0)

        return mbl + mbr

    def get_full_metrics(self, timestamp, interval):
        """ retrieve container platform metrics """
        self.update_cpu_usage()
        metrics = self.metrics
        if self.metrics:
            metrics['time'] = timestamp
            if metrics[Metric.INST] == 0:
                metrics[Metric.CPI] = 0
                metrics[Metric.L3MPKI] = 0
                metrics[Metric.L2SPKI] = 0
                metrics[Metric.MSPKI] = 0
            else:
                metrics[Metric.CPI] = metrics[Metric.CYC] /\
                    metrics[Metric.INST]
                metrics[Metric.L3MPKI] = metrics[Metric.L3MISS] * 1000 /\
                    metrics[Metric.INST]
                metrics[Metric.L2SPKI] = metrics[Metric.L2STALL] * 1000 /\
                    metrics[Metric.INST]
                metrics[Metric.MSPKI] = metrics[Metric.MEMSTALL] * 1000 /\
                    metrics[Metric.INST]
            if self.utils == 0:
                metrics[Metric.NF] = 0
            else:
                metrics[Metric.NF] = int(metrics[Metric.CYC] / interval /
                                         10000 / self.utils)
        return metrics

    def update_pids(self, pids):
        """
        update process ids of one Container
            pids - pid list of Container
        """
        self.pids = pids
    
    def update_cpu_usage(self):
        """ calculate cpu usage of container """
        try:
            total_usage = 0
            system_usage = 0
            cpu_util = 0.0
            cur = time.time() * 1e9

            with open("/proc/stat") as f:
                stats = [int(e) for e in f.readline().split()[1:]]
                system_usage = sum(stats) * 1e9 / 100

            cgroup_stat = path_join('/sys/fs/cgroup/cpu', self.parent_path,
                                  self.con_path, 'cpuacct.usage')
            
            with open(cgroup_stat, 'r') as fi:
                total_usage = int(fi.read().strip())

            cpu_delta = total_usage - self.cpu_usage
            system_delta = system_usage - self.system_usage
            cpu_no = multiprocessing.cpu_count()

            if cpu_delta > 0 and system_delta > 0:
                cpu_util = (float(cpu_delta) / system_delta) * cpu_no * 100
            
            self.timestamp = cur 
            self.utils = cpu_util
            self.cpu_usage = total_usage
            self.system_usage = system_usage
        except (ValueError, IOError):
            pass

    def update_metrics_history(self):
        '''
        add metric data to metrics history
        metrics history only contains the most recent metrics data, defined by
        self.historyDepth if histroy metrics data length exceeds the
        self.historyDepth, the oldest data will be erased
        '''
        self.metrics_history.append(self.metrics.copy())

    def __detect_in_bin(self, thresh):
        metrics = self.metrics
        contend_res = []
        if metrics[Metric.CPI] > thresh['cpi']:
            unk_res = True
            if metrics[Metric.L3MPKI] > thresh['mpki']:
                print('Last Level Cache contention is detected at %s' %
                      metrics['time'])
                print('Latency critical container %s, CPI = %f, threshold =\
%f, MPKI = %f, threshold = %f, L2SPKI = %f, threshold = %f' %
                      (self.name, metrics[Metric.CPI], thresh['cpi'],
                       metrics[Metric.L3MPKI], thresh['mpki'],
                       metrics[Metric.L2SPKI], thresh['l2spki']))
                unk_res = False
                contend_res.append(Contention.LLC)
            if metrics[Metric.MBL] + metrics[Metric.MBR] < thresh['mb'] or\
               metrics[Metric.MSPKI] > thresh['mspki']:
                print('Memory Bandwidth contention detected at %s' %
                      metrics['time'])
                print('Latency critical container %s, CPI = %f, threshold =\
%f, MBL = %f, MBR = %f, threshold = %f, MSPKI = %f, threshold = %f' %
                      (self.name, metrics[Metric.CPI], thresh['cpi'],
                       metrics[Metric.MBL], metrics[Metric.MBR], thresh['mb'],
                       metrics[Metric.MSPKI], thresh['mspki']))
                unk_res = False
                contend_res.append(Contention.MEM_BW)
            if unk_res:
                print('Performance is impacted at %s' %
                      metrics['time'])
                print('Latency critical container %s, CPI = %f, threshold =\
%f' % (self.name, metrics[Metric.CPI], thresh['cpi']))
                contend_res.append(Contention.UNKN)

        return contend_res

    def tdp_contention_detect(self):
        """ detect TDP contention in container """
        if not self.tdp_thresh:
            return None

        if self.verbose:
            print(self.utils, self.metrics[Metric.NF], self.tdp_thresh['util'],
                  self.tdp_thresh['bar'])

        if self.utils >= self.tdp_thresh['util'] and\
           self.metrics[Metric.NF] < self.tdp_thresh['bar']:
            print('TDP Contention Alert!')
            return Contention.TDP

        return None

    def contention_detect(self):
        """ detect resouce contention after find proper utilization bin """
        if not self.thresh:
            return []

        for i in range(0, len(self.thresh)):
            thresh = self.thresh[i]
            if self.utils < thresh['util_start']:
                if i == 0:
                    return []

                return self.__detect_in_bin(self.thresh[i - 1])

            if self.utils >= thresh['util_start']:
                if self.utils < thresh['util_end'] or\
                   i == len(self.thresh) - 1:
                    return self.__detect_in_bin(thresh)
