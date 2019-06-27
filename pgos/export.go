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

// #include <stdlib.h>
// #include <pqos.h>
// #include "platform.h"
// #include "pgos.h"
// #include "helper.h"
import "C"
import (
	"os"
	"time"
	"unsafe"
)

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
