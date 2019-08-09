# WCA/PRM Agent Installation Guide

## Table of Contents

- [Build](#Build)
- [Configuration](#Configuration)
- [Run](#Run)
- [Metrics data persistence](#Metrics-data-persistence)
- [Cluster job scheduler integration](#Cluster-job-scheduler-integration)

## Build

WCA use PEX distribution for executable binary, before you start to build WCA with PRM plugin
you need to prepare build environment for PEX distribution. Please refer to 
[WCA installation guide](https://github.com/intel/workload-collocation-agent/blob/1.0.x/docs/install.rst) <BR>
  
Note: you don't need to get WCA source code and build WCA executable binary in above step. PRM use WCA as 
sub-module, you will build WCA with PRM plugin in next step.


To build WCA/PRM, please use following commands:

```
// get prm source code
git clone https://github.com/intel/platform-resource-manager
cd platform-resource-manager
// get submodule wca source code
git submodule update --init
cd prm
// build wca with prm plugin
make
```

You can find executable binary under dist/wca-prm.pex

## Configuration

The example WCA/PRM agent configuration file is ```wca_prm_mesos.yaml```, in this configuration,
agent works with Mesos worker node and pull the contention detection model from zookeeper service every 3600 seconds and detects 
workload resource contention without allocation control. 

For more detail about WCA configuration. Please refer to [WCA Configuration](https://github.com/intel/workload-collocation-agent/blob/1.0.x/README.rst#id16) 

```yaml
runner: !AllocationRunner
  node: !MesosNode
    mesos_agent_endpoint: "http://127.0.0.1:5051"
  action_delay: &action_delay 1.
  metrics_storage: !LogStorage
    output_filename: 'metrics.prom'
    overwrite: true
  anomalies_storage: !LogStorage
    output_filename: 'anomalies.prom'
    overwrite: true
  allocations_storage: !LogStorage
    output_filename: 'allocations.prom'
    overwrite: true
  allocator: !ResourceAllocator
    database: !ModelDatabase # model database configuration
      db_type: zookeeper    # 1) local 2)zookeeper 3)etcd
      directory: ~     # required for local
      host: "10.239.157.129:2181"     # required for zookeeper and etcd
      namespace: ~     # for zookeeper, if none, using default model_distribution
      ssl: !SSL        # enable ssl 
        server_verify: false
        client_cert_path: ~
        client_key_path: ~
    action_delay: *action_delay
    agg_period: 20.          # aggregate platform metrics every 20s
    model_pull_cycle: 180.   # pull model from configuration service (zookeeper or etcd) every 180 * 20 = 3600s
    metric_file: "metric.csv" # local file path to save metrics, default save to same directory as agent working directory, if set to other path, make sure the parent directory is accessible  
    enable_control: False    # if False, detects contention only, if True, enable resource allocation on best-efforts workloads
    exclusive_cat: False     # when control is enabled, if True, Last Level cache way will not be shared between latency-critical and best-efforts workloads
  rdt_enabled: True
  extra_labels:
    env_uniq_id: "15"
    own_ip: "100.64.176.15"
```

## Run

If you need to validate your agent in command line, use following commands in worker node:

```
sudo -s

// Syscall 'perf_event_open' consumes lots of file descriptors.
// Set an appropriate value.
ulimit -n 65536

// detect contention in worker node, pull model from central model database
// for security reason, WCA requires absolute file path for agent configuration file
./dist/wca-prm.pex -0 -c $PWD/wca_prm_mesos.yaml -r prm.allocator:ResourceAllocator -r prm.model_distribution.db:ModelDatabase -l info
```

Note:
When you need to deploy your agent in a cluster, it is highly recommended to run agent as systemd service with a non-root user. 
You can refer to [Running WCA as non-root user](https://github.com/intel/workload-collocation-agent/blob/1.0.x/docs/install.rst#running-wca-as-non-root-user) section and [Running as systemd service](https://github.com/intel/workload-collocation-agent/blob/1.0.x/docs/install.rst#running-as-systemd-service) section for detail.

## Metrics data persistence 

WCA/PRM Agent collect platform metrics for each workloads periodically and support to store the metrics in multple
ways which depends on the [agent storage configuration](https://github.com/intel/workload-collocation-agent/blob/1.0.x/README.rst#components) 

User can determine the approach based on their own infrastrucutre condition. For example, you can configure agent 
to send metrics to your existing Kafka service or you can configure agent to store the metrics in log file and 
use Prometheus Node exporter to export metrics to central Prometheus database.

WCA/PRM agent also persists metrics in local file with csv format. By default agent store the file in the same directory 
as agent working directory. User can change the file path in agent configuration file. Since agent itself does not rotate 
the csv file, it is highly recommanded that user rotates it manually or periodically with logrotate utility (use copytruncate).

In most of cases, it is recommanded that central model builder train models from metrics data stored in a Prometheus
database. But if user does not have Prometheus database services available, user can let model builder train models from
a single csv file, which requires user to combine all the csv files collected from those nodes into a single csv file with automation.
  
## Cluster job scheduler integration

Agent supports to integrate with different type of job schedulers in cluster, including Mesos and Kubernetes. 
It has some version requirements and configuration restrictions to these job schedulers. Also Agent itself support 
different configuration options for different job scheduler. For detail, please refer to following links:<BR>
[Mesos Integration](https://github.com/intel/workload-collocation-agent/blob/1.0.x/docs/mesos.rst)   
[Kubernetes Integration](https://github.com/intel/workload-collocation-agent/blob/1.0.x/docs/kubernetes.rst)


Also there are some required task labels passed by WCA agent to PRM plugin:

* `application`
* `application_version_name`

Please read WCA guide on [Generating additional labels for tasks](https://github.com/intel/workload-collocation-agent/blob/1.0.x/docs/detection.rst#generating-additional-labels-for-tasks) 
to understand how configure WCA to set those labels to indented values.

The label `applicaiton_version_name` is required because multiple instances of the same application may exist and 
they may have different initial resource assignment, which requires separate statistical models.

For example, two instances of `twemcache` with different allocated vCPU count
needs separate models. Therefore, the label `application_version_name` must be
different for each of the `twemcache` instances.

Also if you need to support dynamic resource allocation, following label is required
to label the task as best-efforts workload by setting label value to 'best_efforts'

 * `type`
