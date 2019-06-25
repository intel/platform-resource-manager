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

package main

// #include <stdint.h>
// #include <sys/types.h>
// #include <stdlib.h>
// #include <linux/perf_event.h>
// #cgo CFLAGS: -fstack-protector-strong
// #cgo CFLAGS: -fPIE -fPIC
// #cgo CFLAGS: -O2 -D_FORTIFY_SOURCE=2
// #cgo CFLAGS: -Wformat -Wformat-security
// #cgo LDFLAGS: -lpqos -lm ./perf.o ./pgos.o ./helper.o
// #cgo LDFLAGS: -Wl,-z,noexecstack
// #cgo LDFLAGS: -Wl,-z,relro
// #cgo LDFLAGS: -Wl,-z,now
// #include <pqos.h>
// #include "perf.h"
// #include "pgos.h"
// #include "helper.h"
import "C"
import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"reflect"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	ErrorPqosInitFailure     C.int = 1 << iota
	ErrorCannotOpenCgroup    C.int = 1 << iota
	ErrorCannotOpenTasks     C.int = 1 << iota
	ErrorCannotPerfomSyscall C.int = 1 << iota
	ErrorPerfInitFailure     C.int = 1 << iota
)

const (
	UNKNOWN C.int = iota
	BROADWELL
	SKYLAKE
	CASCADELAKE
)

var coreCount int
var peCounters = []PerfEventCounter{}

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

//export pgos_init
func pgos_init(ctx C.struct_init_context) C.int {

	var confPath string
	if ctx.path != nil {
		confPath = C.GoString(ctx.path)
	} else {
		family := C.get_cpu_family()
		switch family {
		case BROADWELL:
			confPath = "./broadwell.json"
		case SKYLAKE:
			confPath = "./skylake.json"
		case CASCADELAKE:
			confPath = "./cascadelake.json"
		default:
			return ErrorPerfInitFailure
		}
	}
	ret := handlePerfEventConfig(confPath)
	if ret != 0 {
		return ret
	}
	*ctx.perf_counter_count = C.int(len(peCounters))
	for i := 0; i < len(peCounters); i++ {
		name := C.CString(peCounters[i].EventName)
		C.set_perf_counter_name(&ctx, C.int(i), name)
		C.free(unsafe.Pointer(name))
	}

	pqosLog, err := os.OpenFile("/tmp/pqos.log", os.O_CREATE|os.O_WRONLY|os.O_TRUNC, os.ModePerm)
	if err != nil {
		return ErrorPqosInitFailure
	}

	config := C.struct_pqos_config{
		fd_log:     C.int(pqosLog.Fd()),
		verbose:    2,
		_interface: C.PQOS_INTER_OS,
	}
	if C.pqos_init(&config) != C.PQOS_RETVAL_OK {
		return ErrorPqosInitFailure
	}
	return 0
}

//export pgos_finalize
func pgos_finalize() {
	pqosLog.Close()
	C.pqos_fini()
}

//export collect
func collect(ctx C.struct_context) C.struct_context {
	ctx.ret = 0
	coreCount = int(ctx.core)

	cgroups := make([]*Cgroup, 0, int(ctx.cgroup_count))

	for i := 0; i < int(ctx.cgroup_count); i++ {
		cg := C.get_cgroup(ctx.cgroups, C.int(i))
		cg.ret = 0
		path, cid := C.GoString(cg.path), C.GoString(cg.cid)
		c, code := NewCgroup(path, cid, i)
		cg.ret |= code
		if c != nil {
			cg.ret |= c.GetPgosHandler()
		}
		if cg.ret == 0 {
			cgroups = append(cgroups, c)
		}
	}
	now := time.Now().Unix()
	ctx.timestamp = C.uint64_t(now)
	for j := 0; j < len(cgroups); j++ {
		for k := 0; k < len(cgroups[j].Leaders); k++ {
			cg := C.get_cgroup(ctx.cgroups, C.int(cgroups[j].Index))
			code := StartLeader(cgroups[j].Leaders[k])
			cg.ret |= code
		}
	}
	time.Sleep(time.Duration(ctx.period) * time.Millisecond)
	for j := 0; j < len(cgroups); j++ {
		cg := C.get_cgroup(ctx.cgroups, C.int(cgroups[j].Index))
		res := make([]uint64, len(peCounters))
		for k := 0; k < coreCount; k++ {
			code := StopLeader(cgroups[j].Leaders[k])
			cg.ret |= code
			result, code := ReadLeader(cgroups[j].Leaders[k])
			cg.ret |= code
			for l := 0; l < len(peCounters); l++ {
				res[l] += result.Data[l].Value
			}
		}
		if cg.ret != 0 {
			continue
		}
		pgosValue := C.pgos_mon_poll(cgroups[j].PgosHandler)

		for i := 0; i < len(peCounters); i++ {
			C.set_perf_result(cg, C.int(i), C.uint64_t(res[i]))
		}

		cg.llc_occupancy = pgosValue.llc / 1024
		cg.mbm_local = C.double(float64(pgosValue.mbm_local_delta) / 1024.0 / 1024.0 / (float64(ctx.period) / 1000.0))
		cg.mbm_remote = C.double(float64(pgosValue.mbm_remote_delta) / 1024.0 / 1024.0 / (float64(ctx.period) / 1000.0))
		cgroups[j].Close()
	}
	C.pgos_mon_stop()
	return ctx
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

func main() {

}
