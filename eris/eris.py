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

""" This module implements resource monitor and control agent """

from __future__ import print_function
from __future__ import division

import os
import sys

import time
import traceback

import docker
import numpy as np

from argparse import ArgumentParser, FileType
from datetime import datetime
try:
    from os import cpu_count
except ImportError:
    from multiprocessing import cpu_count
from threading import Thread

from container import Container, Contention
from cpuquota import CpuQuota
from llcoccup import LlcOccup
from mresource import Resource
from naivectrl import NaiveController
from prometheus import PrometheusClient
from pgos import Pgos
from analyze.analyzer import Metric, Analyzer, ThreshType

__version__ = 0.8


class Context(object):
    """ This class encapsulate all configuration and args """

    def __init__(self):
        self._docker_client = None
        self._prometheus = None
        self.pgos = None
        self.pgos_inited = False
        self.shutdown = False
        self.args = None
        self.sysmax_util = 0
        self.lc_set = {}
        self.be_set = {}
        self.cpuq = None
        self.llc = None
        self.controllers = {}
        self.util_cons = dict()
        self.metric_cons = dict()
        self.analyzer = None
        self.cgroup_driver = 'cgroupfs'

    @property
    def docker_client(self):
        if self._docker_client is None:
            self._docker_client = docker.from_env(version='auto')
        return self._docker_client

    @property
    def prometheus(self):
        if self._prometheus is None:
            self._prometheus = PrometheusClient()
        return self._prometheus


def detect_contender(metric_cons, contention_type, container_contended):
    resource_delta_max = -np.Inf
    suspect = "unknown"

    for cid, container in metric_cons.items():
        delta = 0
        if cid == container_contended.cid:
            continue
        if contention_type == Contention.LLC:
            delta = container.get_llcoccupany_delta()
        elif contention_type == Contention.MEM_BW:
            delta = container.get_latest_mbt()
        elif contention_type == Contention.TDP:
            delta = container.get_freq_delta()

        if delta > 0 and delta > resource_delta_max:
            resource_delta_max = delta
            suspect = container.name

    print('Contention %s for container %s: Suspect is %s' %
          (contention_type, container_contended.name, suspect))


def set_metrics(ctx, timestamp, data):
    """
    This function collect metrics from pgos tool and trigger resource
    contention detection and control
        ctx - agent context
        data - metrics data collected from pgos
    """
    for cid, metric in data:
        container = ctx.metric_cons[cid]
        container.metrics.update(metric)

    contention = {
        Contention.LLC: False,
        Contention.MEM_BW: False,
        Contention.UNKN: False
    }
    contention_map = {}
    bes = []
    lcs = []
    findbe = False
    for cid, con in ctx.metric_cons.items():
        key = con.cid if ctx.args.key_cid else con.name
        metrics = con.get_full_metrics(timestamp, ctx.args.metric_interval)
        if metrics:
            if ctx.args.detect:
                con.update_metrics_history()

            if ctx.args.record:
                with open(Analyzer.METRIC_FILE, 'a') as metricf:
                    metricf.write(str(con))

                if ctx.args.enable_prometheus:
                    ctx.prometheus.send_metrics(con.name, con.utils,
                                                metrics[Metric.CYC],
                                                metrics[Metric.L3MISS],
                                                metrics[Metric.INST],
                                                metrics[Metric.CPI],
                                                metrics[Metric.L3MPKI],
                                                metrics[Metric.MSPKI],
                                                metrics[Metric.NF],
                                                metrics[Metric.MBR] +
                                                metrics[Metric.MBL],
                                                metrics[Metric.L3OCC])

        if key in ctx.lc_set:
            if ctx.args.exclusive_cat:
                lcs.append(con)
            if metrics:
                if ctx.args.detect:
                    contend_res = con.contention_detect()
                    if_contended = False

                    if contend_res:
                        if_contended = True
                        for contend in contend_res:
                            contention[contend] = True

                    tdp_contend = con.tdp_contention_detect()
                    if tdp_contend is not None:
                        if_contended = True
                        contention[tdp_contend] = True

                    if if_contended:
                        contention_map[con] = contention.copy()

        if key in ctx.be_set:
            findbe = True
            bes.append(con)

    if ctx.args.detect:
        for container_contended, contention_list in contention_map.items():
            for contention_type, contention_type_if_happened\
                    in contention_list.items():
                if contention_type_if_happened and\
                   contention_type != Contention.UNKN:
                    detect_contender(ctx.metric_cons, contention_type,
                                     container_contended)
    if findbe and ctx.args.control:
        for contention, flag in contention.items():
            if contention in ctx.controllers:
                ctx.controllers[contention].update(bes, lcs, flag, False)


def remove_finished_containers(cids, consmap):
    """
    remove finished containers from cached container map
        cids - container id list from docker
        mon_cons - cached container map
    """
    for cid in consmap.copy():
        if cid not in cids:
            del consmap[cid]


def list_tids(pid):
    tids = []
    try:
        tids = os.listdir('/proc/' + pid + '/task')
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return tids


def list_pids(container):
    """
    list all process id of one container
        container - container object listed from Docker
    """
    procs = container.top()['Processes']
    pids = [pid[1] for pid in procs] if procs else []
    return [tid for pid in pids
            for tid in list_tids(pid)] if pids else []


def mon_util_cycle(ctx):
    """
    CPU utilization monitor timer function
        ctx - agent context
    """
    findbe = False
    lc_utils = 0
    be_utils = 0
    date = datetime.now().isoformat()
    bes = []
    newbe = False
    containers = ctx.docker_client.containers.list()
    remove_finished_containers({c.id for c in containers}, ctx.util_cons)

    for container in containers:
        cid = container.id
        name = container.name
        pids = list_pids(container)
        key = cid if ctx.args.key_cid else name
        if cid in ctx.util_cons:
            con = ctx.util_cons[cid]
        else:
            con = Container(ctx.cgroup_driver, cid, name, pids,
                            ctx.args.verbose)
            ctx.util_cons[cid] = con
            if ctx.args.control:
                if key in ctx.be_set:
                    newbe = True
                    ctx.cpuq.set_share(con, CpuQuota.CPU_SHARE_BE)
                else:
                    ctx.cpuq.set_share(con, CpuQuota.CPU_SHARE_LC)
        con.update_cpu_usage()
        if ctx.args.record:
            with open(Analyzer.UTIL_FILE, 'a') as utilf:
                utilf.write(date + ',' + cid + ',' + name +
                            ',' + str(con.utils) + '\n')

        if key in ctx.lc_set:
            lc_utils = lc_utils + con.utils

        if key in ctx.be_set:
            findbe = True
            be_utils = be_utils + con.utils
            bes.append(con)

    loadavg = os.getloadavg()[0]
    if ctx.args.record:
        with open(Analyzer.UTIL_FILE, 'a') as utilf:
            utilf.write(date + ',,lcs,' + str(lc_utils) + '\n')
            utilf.write(date + ',,loadavg1m,' + str(loadavg) + '\n')

    if lc_utils > ctx.sysmax_util:
        ctx.sysmax_util = lc_utils
        ctx.analyzer.update_lcutilmax(lc_utils)
        if ctx.args.control:
            ctx.cpuq.update_max_sys_util(lc_utils)

    if newbe:
        ctx.cpuq.budgeting(bes, [])

    if findbe and ctx.args.control:
        exceed, hold = ctx.cpuq.detect_margin_exceed(lc_utils, be_utils)
        if not ctx.args.enable_hold:
            hold = False
        ctx.controllers[Contention.CPU_CYC].update(bes, [], exceed, hold)


def mon_metric_cycle(ctx):
    """
    Platform metrics monitor timer function
        ctx - agent context
    """
    containers = ctx.docker_client.containers.list()
    cgroups = []
    bes = []
    lcs = []
    newcon = False
    newbe = False
    remove_finished_containers({c.id for c in containers}, ctx.metric_cons)

    for container in containers:
        cid = container.id
        name = container.name
        pids = list_pids(container)
        key = cid if ctx.args.key_cid else name
        if cid in ctx.metric_cons:
            con = ctx.metric_cons[cid]
            con.update_pids(pids)
        else:
            thresh = ctx.analyzer.get_thresh(key, ThreshType.METRICS)
            tdp_thresh = ctx.analyzer.get_thresh(key, ThreshType.TDP)
            con = Container(ctx.cgroup_driver, cid, name, pids,
                            ctx.args.verbose, thresh, tdp_thresh)
            ctx.metric_cons[cid] = con
            con.update_cpu_usage()
            if ctx.args.control and not ctx.args.disable_cat:
                newcon = True
                if key in ctx.be_set:
                    newbe = True
        if key in ctx.lc_set:
            if ctx.args.exclusive_cat:
                lcs.append(con)
        if key in ctx.be_set:
            bes.append(con)
        cgroups.append((cid, '/sys/fs/cgroup/perf_event/' +
                        con.parent_path + con.con_path))
    if newbe or newcon and bes and ctx.args.exclusive_cat:
        ctx.llc.budgeting(bes, lcs)

    if cgroups:
        timestamp, data = ctx.pgos.collect(cgroups)
        if data:
            set_metrics(ctx, timestamp, data)


def monitor(func, ctx, interval):
    """
    wrap schedule timer function
        ctx - agent context
        interval - timer interval
    """
    next_time = time.time()
    while not ctx.shutdown:
        func(ctx)
        while True:
            next_time += interval
            delta = next_time - time.time()
            if delta > 0:
                break
        time.sleep(delta)


def init_wlset(ctx):
    """
    Initialize workload set for both LC and BE
        ctx - agent context
    """
    lcs = []
    bes = []
    for key, meta in ctx.analyzer.get_wl_meta().items():
        if meta['type'] == 'best_efforts':
            bes.append(key)
        else:
            lcs.append(key)
    ctx.lc_set = set(lcs)
    ctx.be_set = set(bes)
    if ctx.args.verbose:
        print(ctx.lc_set)
        print(ctx.be_set)


def init_sysmax(ctx):
    """
    Initialize historical LC tasks maximal utilization from model file
        ctx - agent context
    """
    ctx.sysmax_util = ctx.analyzer.get_lcutilmax()
    if ctx.sysmax_util == 0:
        ctx.sysmax_util = cpu_count() * 100
    if ctx.args.verbose:
        print(ctx.sysmax_util)


def detect_cgroup_driver():
    """
    Detect docker cgroup parent dir based on cgroup driver type
    """
    client = docker.from_env()
    dockinfo = client.info()
    cgroup_driver = dockinfo['CgroupDriver']
    return cgroup_driver


def parse_arguments():
    """ agent command line arguments parse function """

    parser = ArgumentParser(description='eris agent monitor\
                            container CPU utilization and platform\
                            metrics, detect potential resource\
                            contention and regulate \
                            task resource usages')
    parser.add_argument('workload_conf_file', help='workload configuration\
                        file describes each task name, type, id, request cpu\
                        count', type=FileType('rt'), default='workload.json')
    parser.add_argument('-v', '--verbose', help='increase output verbosity',
                        action='store_true')
    parser.add_argument('-g', '--collect-metrics', help='collect platform\
                        performance metrics (CPI, MPKI, etc..)',
                        action='store_true')
    parser.add_argument('-d', '--detect', help='detect resource contention\
                        between containers', action='store_true')
    parser.add_argument('-c', '--control', help='regulate best-efforts task\
                        resource usages', action='store_true')
    parser.add_argument('-r', '--record', help='record container CPU\
                        utilizaton and platform metrics in csv file',
                        action='store_true')
    parser.add_argument('-i', '--key-cid', help='use container id in workload\
                        configuration file as key id', action='store_true')
    parser.add_argument('-e', '--enable-hold', help='keep container resource\
                        usage in current level while the usage is close but\
                        not exceed throttle threshold ', action='store_true')
    parser.add_argument('-n', '--disable-cat', help='disable CAT control while\
                        in resource regulation', action='store_true')
    parser.add_argument('-x', '--exclusive-cat', help='use exclusive CAT control while\
                        in resource regulation', action='store_true')
    parser.add_argument('-p', '--enable-prometheus', help='allow eris send\
                        metrics to Prometheus', action='store_true')
    parser.add_argument('-u', '--util-interval', help='CPU utilization monitor\
                        interval', type=int, choices=range(1, 11), default=2)
    parser.add_argument('-m', '--metric-interval', help='platform metrics\
                        monitor interval', type=int, choices=range(2, 61),
                        default=20)
    parser.add_argument('-l', '--llc-cycles', help='cycle number in LLC\
                        controller', type=int, default=6)
    parser.add_argument('-q', '--quota-cycles', help='cycle number in CPU CFS\
                        quota controller', type=int, default=7)
    parser.add_argument('-k', '--margin-ratio', help='margin ratio related to\
                        one logical processor used in CPU cycle regulation',
                        type=float, default=0.5)
    parser.add_argument('-t', '--thresh-file', help='threshold model file build\
                        from analyze.py tool', default=Analyzer.THRESH_FILE)

    args = parser.parse_args()
    if args.verbose:
        print(args)
    return args

def init_data_file(ctx, data_file, cols):
    headline = None
    try:
        with open(data_file, 'r') as dtf:
            headline = dtf.readline()
    except Exception:
        if ctx.args.verbose:
            traceback.print_exc(file=sys.stdout)
    if headline != ','.join(cols) + '\n':
        with open(data_file, 'w') as dtf:
            dtf.write(','.join(cols) + '\n')

def main():
    """ Script entry point. """
    ctx = Context()
    ctx.args = parse_arguments()
    ctx.cgroup_driver = detect_cgroup_driver()
    ctx.analyzer = Analyzer(ctx.args.workload_conf_file,
                            ctx.args.thresh_file)
    init_wlset(ctx)
    init_sysmax(ctx)

    if ctx.args.enable_prometheus:
        ctx.prometheus.start()

    if ctx.args.control:
        ctx.cpuq = CpuQuota(ctx.sysmax_util, ctx.args.margin_ratio,
                            ctx.args.verbose)
        quota_controller = NaiveController(ctx.cpuq, ctx.args.quota_cycles)
        ctx.llc = LlcOccup(Resource.BUGET_LEV_MIN, ctx.args.exclusive_cat)
        llc_controller = NaiveController(ctx.llc, ctx.args.llc_cycles)
        if ctx.args.disable_cat:
            ctx.llc = LlcOccup(Resource.BUGET_LEV_FULL, exclusive=False)
            ctx.controllers = {Contention.CPU_CYC: quota_controller}
        else:
            ctx.controllers = {Contention.CPU_CYC: quota_controller,
                               Contention.LLC: llc_controller}
    if ctx.args.record:
        cols = ['time', 'cid', 'name', Metric.UTIL]
        init_data_file(ctx, Analyzer.UTIL_FILE, cols)
    threads = [Thread(target=monitor, args=(mon_util_cycle,
                                            ctx, ctx.args.util_interval))]

    if ctx.args.collect_metrics:
        if ctx.args.record:
            cols = ['time', 'cid', 'name', Metric.INST, Metric.CYC,
                    Metric.CPI, Metric.L3MPKI, Metric.L3MISS, Metric.NF,
                    Metric.UTIL, Metric.L3OCC, Metric.MBL, Metric.MBR,
                    Metric.L2STALL, Metric.MEMSTALL, Metric.L2SPKI,
                    Metric.MSPKI]
            init_data_file(ctx, Analyzer.METRIC_FILE, cols)
        ctx.pgos = Pgos(cpu_count(), ctx.args.metric_interval * 1000 - 1500)
        ret = ctx.pgos.init_pgos()
        if ret != 0:
            print('error in libpgos init, error code: ' + str(ret))
        else:
            ctx.pgos_inited = True
        threads.append(Thread(target=monitor,
                              args=(mon_metric_cycle,
                                    ctx, ctx.args.metric_interval)))

    for thread in threads:
        thread.start()

    print('eris agent version', __version__, 'is started!')

    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print('Shutdown eris agent ...exiting')
        if ctx.pgos_inited:
            ctx.pgos.fin_pgos()
        ctx.shutdown = True
    except Exception:
        traceback.print_exc(file=sys.stdout)

    sys.exit(0)


if __name__ == '__main__':
    main()
