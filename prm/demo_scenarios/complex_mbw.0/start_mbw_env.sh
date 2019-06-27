#! /bin/bash

export REMOTE_USER=ssg
export REMOTE_IP=100.64.176.19
export cinventory=demo_scenarios/common/common.yaml
export playbook=wca/workloads/run_workloads.yaml

ansible-playbook -l $REMOTE_IP -i $cinventory $playbook --tags=clean_jobs -v
ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -msystemd -a'name=wca state=stopped'
ansible -u $REMOTE_USER -b all -i $REMOTE_IP, -a'rm -f /var/lib/wca/lc-util.csv /var/lib/wca/workload-meta.json /var/lib/wca/workload-data.csv /var/lib/wca/threshold.json'


ansible-playbook -l $REMOTE_IP -i demo_scenarios/complex_mbw.0/inventory.yaml -i $cinventory $playbook --tags=specjbb,tensorflow_benchmark_prediction,tensorflow_benchmark_train,cassandra_stress
