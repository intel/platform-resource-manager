#! /bin/bash

export REMOTE_USER=ssg
export REMOTE_IP=100.64.176.19
export cinventory=demo_scenarios/common/common.yaml
export playbook=wca/workloads/run_workloads.yaml

ansible-playbook -l $REMOTE_IP -i $cinventory -i demo_scenarios/complex_mbw.0/inventory_contend.yaml $playbook --tags=tensorflow_benchmark_prediction -vvvvv
