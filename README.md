# Intel® Platform Resource Manager

*Note: This is Alpha code for evaluation purposes.*

Intel® Platform Resource Manager (Intel® PRM) is a suite of software packages
to help you to co-locate best-efforts jobs with latency-critical jobs on a node
and in a cluster. The suite contains the following:

- Agent ([eris agent](#eris-agent)) to monitor and control platform resources
  (CPU Cycle, Last Level Cache, Memory Bandwidth, etc.) on each node.
- Analysis tool ([analyze tool](#analyze-tool)) to build a model for platform
  resource contention detection.


## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment setup](#environment-setup)
- [Command line arguments](#command-line-arguments)
    - [eris agent](#eris-agent)
    - [analyze tool](#analyze-tool)
- [Typical usage](#typical-usage)
- [Contribution](#contribution)

## Prerequisites

 - Python 3.6.x
 - Python lib: numpy, pandas, scipy, scikit-learn, docker, prometheus-client
 - Golang compiler
 - gcc
 - git
 - Docker

## Environment setup
Assuming all requirements are installed and configured properly, follow the steps below to set up a working environment.

1.  Install the `intel-cmt-cat` tool with the commands:

     ```
     git clone https://github.com/intel/intel-cmt-cat
     cd intel-cmt-cat
     make
     sudo make install PREFIX=/usr
     ```

2.  Build the Intel® Platform Resource Manager with the commands:

     ```
     git clone https://github.com/intel/platform-resource-manager
     cd platform-resource-manager
     ./setup.sh
     cd eris
     ```

3.  Prepare the workload configuration file.

    To use the Intel® PRM tool, you must provide a workload configuration
    `json` file in advance. Each row in the file describes name, id, type (Best-Effort, Latency-Critical), request CPU count of one task (Container).

The following is an example file demonstrating the file format.

```json
{
    "cassandra_workload": {
        "cpus": 10,
        "type": "latency_critical"
    },
    "django_workload": {
        "cpus": 8,
        "type": "latency_critical"
    },
    "memcache_workload_1": {
        "cpus": 2,
        "type": "latency_critical"
    },
    "memcache_workload_2": {
        "cpus": 2,
        "type": "latency_critical"
    },
    "memcache_workload_3": {
        "cpus": 2,
        "type": "latency_critical"
    },
    "stress-ng": {
        "cpus": 2,
        "type": "best_efforts"
    },
    "tensorflow_training": {
        "cpus": 1,
        "type": "best_efforts"
    }
}
```

## Command line arguments

This section lists command line arguments for the eris agent and the analyze tool.

### eris agent

    usage: eris.py [-h] [-v] [-g] [-d] [-c] [-r] [-i] [-e] [-n] [-p]
                   [-u UTIL_INTERVAL] [-m METRIC_INTERVAL] [-l LLC_CYCLES]
                   [-q QUOTA_CYCLES] [-k MARGIN_RATIO] [-t THRESH_FILE]
                   workload_conf_file

    eris agent monitor container CPU utilization and platform metrics, detect
    potential resource contention and regulate task resource usages

    positional arguments:
      workload_conf_file    workload configuration file describes each task name,
                            type, id, request cpu count

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         increase output verbosity
      -g, --collect-metrics
                            collect platform performance metrics (CPI, MPKI,
                            etc..)
      -d, --detect          detect resource contention between containers
      -c, --control         regulate best-efforts task resource usages
      -r, --record          record container CPU utilizaton and platform metrics
                            in csv file
      -i, --key-cid         use container id in workload configuration file as key
                            id
      -e, --enable-hold     keep container resource usage in current level while
                            the usage is close but not exceed throttle threshold
      -n, --disable-cat     disable CAT control while in resource regulation
      -x, --exclusive-cat   use exclusive CAT control while in resource regulation
      -p, --enable_prometheus
                            allow eris send metrics to prometheus
      -u UTIL_INTERVAL, --util-interval UTIL_INTERVAL
                            CPU utilization monitor interval (1, 10)
      -m METRIC_INTERVAL, --metric-interval METRIC_INTERVAL (2, 60)
                            platform metrics monitor interval
      -l LLC_CYCLES, --llc-cycles LLC_CYCLES
                            cycle number in LLC controller
      -q QUOTA_CYCLES, --quota-cycles QUOTA_CYCLES
                            cycle number in CPU CFS quota controller
      -k MARGIN_RATIO, --margin-ratio MARGIN_RATIO
                            margin ratio related to one logical processor used in
                            CPU cycle regulation
      -t THRESH_FILE, --thresh-file THRESH_FILE
                            threshold model file build from analyze.py tool


### analyze tool

    usage: analyze.py [-h] [-v] [-t THRESH]
                      [-f {quartile,normal,gmm-strict,gmm-normal}]
                      [-m METRIC_FILE]
                      workload_conf_file

    This tool analyzes CPU utilization and platform metrics collected from eris
    agent and build data model for contention detect and resource regulation.

    positional arguments:
      workload_conf_file    workload configuration file describes each task name,
                            type, id, request cpu count

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         increase output verbosity
      -t THRESH, --thresh THRESH
                            threshold used in outlier detection
      -a {gmm-standard, gmm-origin}, --fense-method {gmm-standard, gmm-origin}
                            fense method in outiler detection
      -f {gmm-strict,gmm-normal}, --fense-type {gmm-strict,gmm-normal}
                            fense type used in outlier detection
      -m METRIC_FILE, --metric-file METRIC_FILE
                            metrics file collected from eris agent
      -u UTIL_FILE, --util-file UTIL_FILE
                            Utilization file collected from eris agent
      -o, --offline         do offline analysis based on given metrics file
      -i, --key-cid         use container id in workload configuration file as key
                            id


## Typical usage


1.  Run latency critical tasks and stress workloads on one node. The CPU
    utilization will be recorded in `util.csv` and platform metrics will be recorded in `metrics.csv`.

      ```
      sudo python eris.py --collect-metrics --record workload.json
      ```

2.  Analyze data collected from the eris agent and build the data model for
    resource contention detection and regulation. This step generates a model file `threshold.json`.

      ```
      sudo python analyze.py workload.json
      ```

3.  Add best-efforts task to node, restart monitor, and detect potential
    resource contention.

      ```
      sudo python eris.py --collect-metrics --record --detect workload.json
      ```

Optionally, you can enable resource regulation on best-efforts tasks with the
following command:

    sudo python eris.py --collect-metrics --record --detect --control workload.json

## Contribution

Intel® PRM is an open source project licensed under the [Apache v2 License](http://www.apache.org/licenses/LICENSE-2.0).

**Coding style**

Intel® PRM follows the standard formatting recommendations and language idioms
set out in C, Go, and Python.

**Pull requests**

We accept [github pull requests](https://github.com/intel/platform-resource-manager/pulls).

**Issue tracking**

If you have a problem, please let us know. If you find a bug not already
documented, please [file a new issue in github](https://github.com/intel/platform-resource-manager/issues) so we can work toward resolution.
