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

// #include "pgos.h"
// #include <stdint.h>
import "C"

import (
	"fmt"
	"os"
	"strings"
	"syscall"
	"unsafe"
)

type Cgroup struct {
	Index       int
	Path        string
	Name        string
	Pid         uint32
	File        *os.File `json:"-"`
	Leaders     []uintptr
	Followers   []uintptr
	PgosHandler C.int
}

func NewCgroup(path string, cid string, index int) (*Cgroup, C.int) {
	cgroupFile, err := os.Open(path)
	if err != nil {
		return nil, ErrorCannotOpenCgroup
	}
	cgroupName := cid
	if cid == "" {
		cgroupNames := strings.Split(strings.Trim(path, string(os.PathSeparator)), string(os.PathSeparator))
		cgroupName = cgroupNames[len(cgroupNames)-1]
	} else {
		cgroupName = cid
	}
	leaders := make([]uintptr, 0, coreCount)
	followers := make([]uintptr, 0, coreCount*(len(peCounters)-1))

	for i := 0; i < coreCount; i++ {
		l, code := OpenLeader(cgroupFile.Fd(), uintptr(i), peCounters[0])
		if code != 0 {
			return nil, code
		}
		leaders = append(leaders, l)
		for j := 1; j < len(peCounters); j++ {
			f, code := OpenFollower(l, uintptr(i), peCounters[j])
			if code != 0 {
				return nil, code
			}
			followers = append(followers, f)
		}
	}
	return &Cgroup{
		Index:     index,
		Path:      path,
		Name:      cgroupName,
		File:      cgroupFile,
		Leaders:   leaders,
		Followers: followers,
	}, 0
}

func (this *Cgroup) GetPgosHandler() (code C.int) {
	f, err := os.OpenFile(this.Path+"/tasks", os.O_RDONLY, os.ModePerm)
	if err != nil {
		code = ErrorCannotOpenTasks
		return
	}
	defer f.Close()
	pids := []C.pid_t{}
	for {
		var pid uint32
		n, err := fmt.Fscanf(f, "%d\n", &pid)
		if n == 0 || err != nil {
			break
		}
		pids = append(pids, C.pid_t(pid))
	}
	this.PgosHandler = C.pgos_mon_start_pids(C.unsigned(len(pids)), (*C.pid_t)(unsafe.Pointer(&pids[0])))

	return
}

func (this *Cgroup) Close() {
	for i := 0; i < len(this.Followers); i++ {
		syscall.Close(int(this.Followers[i]))
	}
	for i := 0; i < len(this.Leaders); i++ {
		syscall.Close(int(this.Leaders[i]))
	}
	this.File.Close()
	return
}
