import pytest

from prm.resource import Resource, RDTResource
from prm.llcoccup import LlcOccup
from wca.allocators import AllocationType

@pytest.fixture(scope="module")
def llc_occup():
    res = LlcOccup(False)
    return res

@pytest.fixture(scope="module")
def llc_occup_excl():
    res = LlcOccup(True)
    return res

def test_llcoccup_budgeting(llc_occup):
    allocs = dict()
    llc_occup.update_allocs(dict(), allocs, 'fffff', 1)
    llc_occup.budgeting({'1'}, {})
    llc_occup.set_level(Resource.BUGET_LEV_FULL)
    llc_occup.budgeting({'2'}, {})
    assert '1' in allocs
    assert AllocationType.RDT in allocs['1']
    assert getattr(allocs['1'][AllocationType.RDT], RDTResource.L3) == 'L3:0=0xc0000'
    assert '2' in allocs
    assert AllocationType.RDT in allocs['2']
    assert getattr(allocs['2'][AllocationType.RDT], RDTResource.L3) == 'L3:0=0xfffff'

def test_llcoccup_excl_budgeting(llc_occup_excl):
    allocs = dict()
    llc_occup_excl.update_allocs(dict(), allocs, 'fff', 2)
    llc_occup_excl.budgeting({'1'}, {'3'})
    llc_occup_excl.set_level(Resource.BUGET_LEV_FULL)
    llc_occup_excl.budgeting({'2'}, {'4'})
    assert '1' in allocs
    assert AllocationType.RDT in allocs['1']
    assert getattr(allocs['1'][AllocationType.RDT], RDTResource.L3) == 'L3:0=0xc00;1=0xc00'
    assert '3' in allocs
    assert AllocationType.RDT in allocs['3']
    assert getattr(allocs['3'][AllocationType.RDT], RDTResource.L3) == 'L3:0=0x3ff;1=0x3ff'
    assert '2' in allocs
    assert AllocationType.RDT in allocs['2']
    assert getattr(allocs['2'][AllocationType.RDT], RDTResource.L3) == 'L3:0=0xfe0;1=0xfe0'
    assert '4' in allocs
    assert AllocationType.RDT in allocs['4']
    assert getattr(allocs['4'][AllocationType.RDT], RDTResource.L3) == 'L3:0=0x1f;1=0x1f'

