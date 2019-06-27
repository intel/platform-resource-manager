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

from wca.databases import LocalDatabase, ZookeeperDatabase, EtcdDatabase
import datetime
from typing import List, Union, Optional
from wca.config import IpPort
from wca.security import SSL
import json
import logging
import string

log = logging.getLogger(__name__)

_VALID_KEY_CHARACTERS = "-_.%s%s" % (string.ascii_letters, string.digits)

def correct_key_characters(key: str):
    for c in key:
        if c not in _VALID_KEY_CHARACTERS:
            key = key.replace(c, '_')
    return key

def _format_host_for_etcd(host: str):
    if 'http' not in host:
        return 'http://'+host
    else:
        return host

class DatabaseError(Exception):
    """Error raised when communcation with the database"""

class ImproperDatabaseTypeError(Exception):
    """Error raised for any of improper dbtype. """
    pass


class ImproperDirectoryError(Exception):
    """Error raised for any of improper directory. """
    pass


class ImproperHostError(Exception):
    """Error raised for any of improper host. """
    pass

class ModelDatabase(object):
    """Model storage database, get/set api is provided
    Arguments:
        db_type: three types of database is supported
            1) local, store model in local folder and files, directory is required
            2) zookeeper, store model in zookeeper, zookeeper host is required
            3) etcd, store model in etcd, host is required
        host: required for zookeeper and etcd, for etcd the host can be a str or an arrary
        namspace: required for zookeeper, if none, using default
            (default to 'model_distribution')
        directory: required for local database
        ssl_verify: for etcd
            (default to true)
        api_path: for etcd, '/v3alpha' for 3.2.x etcd version, '/v3beta' or '/v3' for 3.3.x etcd version
        timeout: for etcd, default 5.0 seconds
        client_cert_path: for ectd
        client_key_path: for etcd
    """
    def __init__(
        self,
        db_type: str,
        host: Union[str, list, None],
        namespace: Optional[str] = 'model_distribution',
        directory: Optional[str] = None,
        api_path: Optional[str] = '/v3alpha',
        timeout: Union[float, int, None] = 5.0,
        ssl: Optional[SSL] = None
        ):

        self.db_type = db_type
        self.directory = directory
        self.host = host
        self.namespace = 'model_distribution' if namespace is None else namespace
        self.api_path = '/v3alpha' if api_path is None else api_path
        self.timeout = 5.0 if timeout is None else timeout
        self.ssl = ssl
        self.instance = self.create()

    def create(self):
        if self.db_type == 'local':

            if self.directory is None or self.directory == '':
                raise ImproperDirectoryError(
                    "Please set a directory for local database")
            elif os.path.isdir(self.directory):
                raise ImproperDirectoryError(
                    "Please specify a non-existing directory for local database")
            return LocalDatabase(self.directory)

        elif self.db_type == 'zookeeper':
            if self.host is None or self.host == '':
                raise ImproperHostError(
                    "Please provide a ip:port for zookeeper database")
            return ZookeeperDatabase(self.host, self.namespace, self.timeout, self.ssl)

        elif self.db_type == 'etcd':

            if isinstance(self.host, str):
                hosts = [_format_host_for_etcd(self.host)]
            elif isinstance(self.host, list):
                hosts = [_format_host_for_etcd(h) for h in self.host]
            return EtcdDatabase(hosts, self.timeout, self.api_path, self.ssl)
        else:
            raise ImproperDatabaseTypeError(
                "The agent only support 1)local 2)zookeeper 3)etcd databases")

    def set(self, key: str, value: dict):
        key = correct_key_characters(key)
        key = bytes(key, 'ascii')
        value = bytes(json.dumps(value), 'ascii')
        self.instance.set(key, value)

    def get(self, key: str):
        key = correct_key_characters(key)
        key = bytes(key, 'ascii')
        value = self.instance.get(key)
        return value.decode('ascii') if value else '{}'


