import pytest

from prm.resource import Resource, RDTResource
from prm.cpucycle import CpuCycle
from wca.allocators import AllocationType


@pytest.fixture(scope="module")
def cpu_cycle():
    res = CpuCycle(1600, 0.5, False)
    return res

def test_cpucycle_budgeting(cpu_cycle):
    allocs = dict()
    ncpu = 20
    cpu_cycle.update_allocs(dict(), allocs, ncpu)
    cpu_cycle.budgeting({'1'}, {})
    cpu_cycle.increase_level()
    cpu_cycle.budgeting({'2'}, {})
    cpu_cycle.set_level(Resource.BUGET_LEV_FULL)
    bes = {'3', '4'}
    cpu_cycle.budgeting(bes, {})

    assert '1' in allocs
    assert AllocationType.QUOTA in allocs['1']
    assert allocs['1'][AllocationType.QUOTA] == CpuCycle.CPU_QUOTA_MIN
    assert '2' in allocs
    assert AllocationType.QUOTA in allocs['2']
    assert allocs['2'][AllocationType.QUOTA] == 1600 / 100 / ncpu / Resource.BUGET_LEV_MAX
    assert '3' in allocs
    assert AllocationType.QUOTA in allocs['3']
    assert allocs['3'][AllocationType.QUOTA] == CpuCycle.CPU_QUOTA_DEFAULT / len(bes)

def test_cpucycle_set_share(cpu_cycle):
    allocs = dict()
    ncpu = 20
    cpu_cycle.update_allocs(dict(), allocs, ncpu)
    cpu_cycle.set_share('1', 1.0)
    assert '1' in allocs
    assert AllocationType.SHARES in allocs['1']
    assert allocs['1'][AllocationType.SHARES] == 1.0


@pytest.mark.parametrize(
    'lcu, beu, exceed, hold', [
        (1256, 188, False, False),
        (1135, 411, False, True),
        (1324, 229, True, True)
    ]
)
def test_detect_margin_exceed(cpu_cycle, lcu, beu, exceed, hold):
    exc, hld = cpu_cycle.detect_margin_exceed(lcu, beu)
    assert exc == exceed
    assert hld == hold
