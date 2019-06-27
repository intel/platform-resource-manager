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

import requests
import logging
from enum import Enum
from prm.model_distribution.metric import GroupInfo, Metric

log = logging.getLogger(__name__)

class PromResponseStatus(str, Enum):
    SUCCESS = 'success'
    ERROR = 'error'

class PromResponseError(Exception):
    pass

def _prom_format_label_dict(label_dict):
    labels = ''
    for key, value in label_dict.items():
        labels += key+'="'+value+'",'
    return '{' + labels + '}'

def _http_format_url(url):
    if 'http' not in url:
        return 'http://' + url
    else:
        return url

class PromHttp(object):
    """ The current stable HTTP API is reachable under /api/v1 on a Prometheus server
    """
    def __init__(self, url, timeout):
        self.url = _http_format_url(url)
        self.timeout = timeout

    def get_prom_value_url(self):
        return self.url + '/api/v1/label/__name__/values'

    def get_prom_query_url(self):
        return self.url + '/api/v1/query_range'

    def get_prom_series_url(self):
        return self.url + '/api/v1/series'

    def get_all_metrics_value_names(self,):

        url = self.get_prom_value_url()

        res = requests.get(url, timeout=self.timeout)
        if res.status_code == requests.codes.ok:
            result = res.json()
            if result['status'] == PromResponseStatus.SUCCESS:
                return result['data']
            elif result['status'] == PromResponseStatus.ERROR:
                raise PromResponseError("prometheus error")
            else:
                raise PromResponseError("unknown")
        else:
            res.raise_for_status()

    def get_data_with_label(self, metric_name,  start, end, label_dict={}, step=15):
        url = self.get_prom_query_url()

        labels = _prom_format_label_dict(label_dict)

        query = metric_name + labels

        params = {'query': query, 'start': start, 'end': end, 'step': step}
        res = requests.get(url, params=params, timeout=self.timeout)

        if res.status_code == requests.codes.ok:
            result = res.json()
            if result['status'] == PromResponseStatus.SUCCESS:
                return result['data']
            elif result['status'] == PromResponseStatus.ERROR:
                log.info(PromResponseError.RESPONSE_ERROR)
            else:
                log.info(PromResponseError.RESPONSE_UNKNOWN)
        else:
            res.raise_for_status()

    def get_series_with_label(self, metric_name, start, end, label_dict={}):

        url = self.get_prom_series_url()

        labels = _prom_format_label_dict(label_dict)

        query = metric_name + labels

        params = {'match[]': query, 'start': start, 'end': end}

        res = requests.get(url, params=params, timeout=self.timeout)

        if res.status_code == requests.codes.ok:
            result = res.json()
            if result['status'] == PromResponseStatus.SUCCESS:
                return result['data']
            elif result['status'] == PromResponseStatus.ERROR:
                log.info(PromResponseError.RESPONSE_ERROR)
            else:
                log.info(PromResponseError.RESPONSE_UNKNOWN)
        else:
            res.raise_for_status()


