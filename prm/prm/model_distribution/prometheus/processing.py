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
import numpy as np
import pandas as pd
from enum import Enum
from prm.model_distribution.metric import GroupInfo, Metric, GroupLabel
from prm.model_distribution.prometheus.query import PromHttp

log = logging.getLogger(__name__)

class NotExistInPrometheus(Exception):
    pass

class PromProcessor(object):
    """ Processing data from promentheus, aggregrating metrics by cpu_model, application and cpu_assignment.
    """
    def __init__(self, url, timeout):
        self.prom_http = PromHttp(url, timeout)
        self.metric_names = self.prom_http.get_all_metrics_value_names()

    def non_exsist_hint(self, metric_name):
        raise NotExistInPrometheus("Can not query {} in prometheus,all avaliable metrics in prometheus: {} \n".format(
            metric_name, self.metric_names))

    def _transfer_models_to_nested(self, models):
        """
        build thresholds for each unique combination of cpu_model, application, cpu_assignment ,
        but store each cpu_model as an unique key into database
        """

        nested_models = {}
        for model in models:
            if nested_models.get(model.cpu_model) == None:
                nested_models[model.cpu_model] = {
                    model.application: {
                        model.initial_task_cpu_assignment: True}
                }
            elif nested_models.get(model.cpu_model).get(model.application) == None:
                temp = nested_models[model.cpu_model]
                temp[model.application] = {
                    model.initial_task_cpu_assignment: True}
                nested_models[model.cpu_model] = temp
            elif nested_models.get(model.cpu_model).get(model.application).get(model.initial_task_cpu_assignment) == None:
                temp = nested_models.get(
                    model.cpu_model).get(model.application)
                temp[model.initial_task_cpu_assignment] = True
                nested_models[model.cpu_model][model.application] = temp
        return nested_models

    def generate_existing_models_by_cpu_util(self, starts_ends):
        # query all series in the timerange
        series = []
        for start_end in starts_ends:
            serie = self.prom_http.get_series_with_label(Metric.UTIL, start_end[0], start_end[1], {})
            series = series + serie

        # make unique group labels
        models = {}
        for s in series:
            if GroupInfo.CPU_MODEL not in s or GroupInfo.APPLICATION not in s or GroupInfo.INITIAL_TASK_CPU_ASSIGNMENT not in s:
                continue
            temp_model = GroupLabel(
                s[GroupInfo.CPU_MODEL], s[GroupInfo.APPLICATION], s[GroupInfo.INITIAL_TASK_CPU_ASSIGNMENT])
            if models.get(temp_model) == None:
                models[temp_model] = True

        if len(models) == 0:
            log.warning(
                "no data at this time range, please set a larger timerange")

        # transfer models to nested dict
        return list(models), self._transfer_models_to_nested(list(models))

    def aggregrate_metric_by_application_and_label(self, metric_name, group_label, start, end, step):
        """prometheus db data format
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {
                        "__name__": "memory_bandwidth",
                        "application": "stress_ng",
                        ....
                    },
                    "values": [
                        [
                            1555056098.363,
                            "11707465728"
                        ],
                        ....
                },
                {
                    "metric": {
                        "__name__": "memory_bandwidth",
                        "application": "stress_ng",
                        ....
                    },
                    "values": [
                        [
                            1555056098.363,
                            "11707465728"
                        ],
                        ....
                }
                ...
            ]
        }
        """

        if metric_name not in self.metric_names:
            self.non_exsist_hint(metric_name)

        data = self.prom_http.get_data_with_label(
            metric_name,  start, end, group_label, step)

        if len(data['result']) == 0:
            log.info("{} data is empty from {} to {}.".format(metric_name, start, end))
            return 0, []

        metric_arrary = [[], []]
        for result in data['result']:
            value = np.transpose(result['values']).astype(np.float)
            # group metric by same labels
            metric_arrary = np.concatenate((metric_arrary, value), axis=1)

        # timestamp:axis=0, value:axis=1
        return len(metric_arrary[1]), metric_arrary[1]

    def generate_new_metric_dataframes(self, metric_name_list, group_label, starts_ends, step):
        frames = []
        for start_end in starts_ends:
            frame = self.generate_new_metric_dataframe(metric_name_list, group_label, start_end[0], start_end[1], step)
            frames.append(frame)
        return pd.concat(frames)

    def generate_new_metric_dataframe(self, metric_name_list, group_label, start, end, step):
        metric_lengths = []
        metric_data = {}

        for metric_name in metric_name_list:
            metric_length, metric_data[metric_name] = self.aggregrate_metric_by_application_and_label(
                metric_name, group_label, start, end, step)
            metric_lengths.append(metric_length)

        # align timestamp between differnt metrics
        if len(set(metric_lengths)) > 1:
            log.info('Length of values does not match length of index for {} '.format(group_label))
            final_length = min(metric_lengths)
            for key, value in metric_data.items():
                metric_data[key] = value[:final_length]

        return pd.DataFrame.from_dict(metric_data)


