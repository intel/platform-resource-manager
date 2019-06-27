// Copyright (C) 2018 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.
//
//
// SPDX-License-Identifier: Apache-2.0
//

package main

import "C"
import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"reflect"
	"strings"
)

var coreCount int

var pqosLog *os.File

func conf2PerfEventCounter(c map[string]string) PerfEventCounter {
	ret := PerfEventCounter{}

	retAddr := reflect.ValueOf(&ret)
	retElem := retAddr.Elem()
	retType := reflect.TypeOf(ret)
	for i := 0; i < retType.NumField(); i++ {
		strValue := c[retType.Field(i).Name]
		field := retElem.Field(i)
		fieldType := retType.Field(i).Type
		switch fieldType.String() {
		case "string":
			field.SetString(strValue)
		case "uint":
			var v uint64
			if strings.HasPrefix(strValue, "0x") {
				fmt.Sscanf(strValue, "0x%X", &v)
			} else {
				fmt.Sscanf(strValue, "%d", &v)
			}
			field.SetUint(v)
		}
	}
	return ret
}

func handlePerfEventConfig(confPath string) C.int {
	events := []map[string]string{}
	conf, err := os.Open(confPath)
	if err != nil {
		return ErrorPerfInitFailure
	}
	defer conf.Close()
	b, err := ioutil.ReadAll(conf)
	if err != nil {
		return ErrorPerfInitFailure
	}
	err = json.Unmarshal(b, &events)
	if err != nil {
		return ErrorPerfInitFailure
	}
	for i := 0; i < len(events); i++ {
		peCounters = append(peCounters, conf2PerfEventCounter(events[i]))
	}
	return 0
}
