# Demo scenarios

This readme describes how to run demo scenarios for the Intel® Platform
Resource Manager (Intel® PRM) on an Apache Mesos/Aurora cluster.

Refer to the [Intel® PRM plugin readme](https://github.com/intel/platform-resource-manager/blob/master/prm/README.md)
for details on how the plugin interfaces with the
[Orchestration-aware Workload Collocation Agent](https://github.com/intel/wca) (WCA).

## Assumptions

Before you run the demo scenarios, you must have completed the following:

*   Set the working directory to the Intel® PRM project top-level directory.
*   Copy the template file from `demo_scenarios/common/common.template.yaml`
    to `demo_scenarios/common/common.yaml` and fill it in.
*   Copy the `wca.pex` file with the Intel® PRM module included to the nodes
    in your cluster.

## Run demo scenarios

1. Export required environment variables. The variable `REMOTE_IP` should be
   set to one entry of the hosts defined in the `demo_scenarios/common/common.yaml` file.

    ```
    export cinventory=demo_scenarios/common/common.template.yaml # inventory with list of hosts
                                                                 #  please copy template file and fill hosts
    export REMOTE_IP=<remote_ip> # one of the hosts defined in common/common.yaml
    export REMOTE_USER=<user>    # the ad-hoc ansible commands on $REMOTE_IP machine will be run
                                 #  by the user $REMOTE_USER
    export playbook=wca/workloads/run_workloads.yaml # path to wca run_workloads playbook
    ```

2. Kill all jobs, stop agent, and remove temporary model data:

    ```
    ansible-playbook -l $REMOTE_IP -i $cinventory $playbook --tags=clean_jobs -v
    ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -msystemd -a'name=wca state=stopped'
    ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -a'rm -f /var/lib/wca/lc-util.csv /var/lib/wca/workload-meta.json /var/lib/wca/workload-data.csv /var/lib/wca/threshold.json'
    ```

3. Start the application with the commands:

    ```
    # simple scenario
    ansible-playbook -l $REMOTE_IP -i demo_scenarios/simple.0/inventory.yaml -i $cinventory $playbook \
      --tags=clean_jobs,twemcache_mutilate,tensorflow_benchmark_prediction,cassandra_stress--cassandra

    # or complex_llc.0
    ansible-playbook -l $REMOTE_IP -i demo_scenarios/complex_llc.0/inventory.yaml -i $cinventory $playbook \
      --tags=twemcache_mutilate,redis_rpc_perf,cassandra_stress--cassandra

    # or complex_mbw.0
    ansible-playbook -l $REMOTE_IP -i demo_scenarios/complex_mbw.0/inventory.yaml -i $cinventory $playbook \
      --tags=specjbb,tensorflow_benchmark_prediction,tensorflow_benchmark_training,cassandra_stress
    ```

4.  Reconfigure WCA by setting `action_delay` to 20 seconds. Then restart it
    to run in `collect` mode with the commands:

    ```
    ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -mreplace -a'path=/etc/wca/wca_config.yml after=detector regexp="detect" replace="collect"'
    ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -mreplace -a'path=/etc/wca/wca_config.yml regexp="action_delay: .*" replace="action_delay: 20."'
    ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -msystemd -a'name=wca state=restarted'
    ```

5. Repeat the steps to create and kill jobs to observe any anomalies.

    ```
    # simple scenario
    ansible-playbook -l $REMOTE_IP -i demo_scenarios/simple.0/inventory.yaml -i $cinventory $playbook --tags=cassandra_stress--stress -v
    ansible-playbook -l $REMOTE_IP -i demo_scenarios/simple.0/inventory.yaml -i $cinventory $playbook --tags=clean_jobs -ekill_job_name=cassandra_stress.default--cassandra_stress--9142.0 -v

    # complex_llc.0
    ansible-playbook -l $REMOTE_IP -i $inventory $playbook --tags=cassandra_stress--stress -v
    ansible-playbook -l $REMOTE_IP -i $inventory $playbook --tags=clean_jobs -ekill_job_name=cassandra_stress.default--cassandra_stress--9142.0 -v

    # complex_mbw.0
    ansible-playbook -l $REMOTE_IP -i $inventory $playbook --tags=tensorflow_benchmark_prediction -v
    ansible-playbook -l $REMOTE_IP -i $inventory $playbook --tags=clean_jobs -ekill_job_name=tensorflow_benchmark_prediction.default--0.0 -v
    ```

## Additional commands

This section includes several one-line commands to check the WCA
configuration file, WCA status, and the size of PRM state files.

```
# to check status
ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -a'cat /etc/wca/wca_config.yml'
ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -a'systemctl status wca'
ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -a'ls -la /var/lib/wca/'
```
