# Copyright (C) 2019 Intel Corporation
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

from wca.detectors import TasksData, TaskMeasurements, TaskAllocations
from wca.nodes import TaskId, TaskResources, TaskLabels

TasksLabels = [TaskId, TaskLabels]
TasksResources = [TaskId, TaskResources]
TasksMeasurements = [TaskId, TaskMeasurements]
TasksAllocations = [TaskId, TaskAllocations]


def extract_tasks_data(tasks_data: TasksData):
    """ Extracts provided tasks data to tuple. """
    tasks_resources: TasksResources = {}
    tasks_labels: TasksLabels = {}
    tasks_measurements: TasksMeasurements = {}
    tasks_allocations: TasksAllocations = {}

    for task_id, task_data in tasks_data.items():
        tasks_resources[task_id] = task_data.resources
        tasks_labels[task_id] = task_data.labels
        tasks_measurements[task_id] = task_data.measurements

        if task_data.allocations:
            tasks_allocations[task_id] = task_data.allocations

    return tasks_resources, tasks_labels, tasks_measurements, tasks_allocations
