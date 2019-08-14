import pytest

from prm.resource import Resource, RDTResource
from prm.membw import MemoryBw
from wca.allocators import AllocationType

@pytest.fixture(scope="module")
def membw():
    res = MemoryBw()
    return res

def test_membw_budgeting(membw):
    allocs = dict()
    membw.update_allocs(dict(), allocs, 10, 10, 2)
    membw.budgeting('1', {})
    membw.set_level(Resource.BUGET_LEV_FULL)
    membw.budgeting('2', {})
    assert '1' in allocs
    assert AllocationType.RDT in allocs['1']
    assert getattr(allocs['1'][AllocationType.RDT], RDTResource.MB) == 'MB:0=10;1=10'
    assert '2' in allocs
    assert AllocationType.RDT in allocs['2']
    assert getattr(allocs['2'][AllocationType.RDT], RDTResource.MB) == 'MB:0=100;1=100' 
