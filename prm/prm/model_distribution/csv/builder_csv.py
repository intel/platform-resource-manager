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
import time

from os.path import splitext
from collections import defaultdict
from typing import List, Union, Optional
from datetime import datetime, timedelta
from wca.runners import Runner
from prm.model_distribution.metric import Metric
from prm.model_distribution.model import DistriModel
from prm.model_distribution.db import ModelDatabase, DatabaseError
from prm.analyze.analyzer import ThreshType
from wca.config import Path
import pandas as pd

log = logging.getLogger(__name__)

class ImproperCSVFilePath(Exception):
    """
    Improper CSV file path
    """
    pass
class ImproperCSVFileColumns(Exception):
    """
    Improper CSV file columns
    """
    pass
class BuildRunnerCSV(Runner):
    """
    Using CSV data to build model thresholds and store them in zookeeper.
    Arguments:
        file_path: the file_path of the csv file
        database: model storage database, get/set api is provided
        model: threshold analyzer
    """
    def __init__(
        self,
        file_path: Path,
        database: ModelDatabase,
        model: DistriModel,
    ):
        self._file_path = file_path
        self._model = model
        self._database = database
        self._finish = False

        self.default_columns = {Metric.NAME, Metric.CPU_MODEL, Metric.VCPU_COUNT, Metric.MB, Metric.CPI, Metric.L3MPKI, Metric.NF, Metric.UTIL, Metric.MSPKI}

    def _initialize(self):
        """Three-level nested dict example:
        {
            cpu_model1:{
                application1:{
                    cpu_assignment1:{
                        threshold}
                    }
                }
        }
        """
        if splitext(self._file_path)[1] !='.csv':
            raise ImproperCSVFilePath("Please provide a csv file path.")
        
        # initialize a three-level nested dict
        self.target = defaultdict(lambda: defaultdict(dict))

    def run(self) -> int:
        log.info('model-distribution runner is started!')

        self._initialize()
        
        while True:
            self._iterate()

            if self._finish:
                break
        return 0

    def _iterate(self):

        df = pd.read_csv(self._file_path)
        if not self.default_columns.issubset(set(df.columns)):
            raise ImproperCSVFileColumns("The csv's columns {} and default columns {} do not match".format(set(df.columns), self.default_columns))

        model_keys = df.groupby([Metric.CPU_MODEL, Metric.NAME, Metric.VCPU_COUNT]).groups.keys()
        
        for model_key in model_keys:
            # filter dataframe by cpu_model, application, cpu_assignment
            if any(str(v) == 'nan' for v in model_key):
                continue
            dataframe = df[(df[Metric.CPU_MODEL] == model_key[0]) & (df[Metric.NAME] == model_key[1]) & (df[Metric.VCPU_COUNT] == model_key[2])]
            
            cpu_number = model_key[2]
            tdp_thresh, thresholds = self._model.build_model(dataframe, cpu_number)

            value = {ThreshType.TDP.value: tdp_thresh, ThreshType.METRICS.value: thresholds}
            self.target[model_key[0]][model_key[1]][model_key[2]] = value

        self._store_database(self.target)
        self._finish = True

    def _store_database(self, target):
        for key, value in target.items():
            try:
                self._database.set(key, dict(value))
            except DatabaseError as e:
                log.error("failed to set key-value to the database: {}".format(e))