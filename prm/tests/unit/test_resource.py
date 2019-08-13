import pytest

from prm.resource import Resource, RDTResource
from wca.allocators import AllocationType

@pytest.fixture(scope="module")
def resource():
    res = Resource()
    return res

@pytest.mark.parametrize(
    'tid, atype, alloc, rdt_res, name', [
        (1, AllocationType.SHARES, 0.0, None, None),
        (2, AllocationType.QUOTA, 0.0, None, None),
        (3, AllocationType.RDT, 'L3:0=0x1', RDTResource.L3, 'BE_Group'),
        (4, AllocationType.RDT, 'MB:0=10', RDTResource.L3, 'BE_Group'),
    ]
)
def test_set_alloc_empty(resource, tid, atype, alloc, rdt_res, name):
    resource.set_alloc(tid, atype, alloc, rdt_res, name)
    assert tid in resource.new_allocs
    assert atype in resource.new_allocs[tid]
    if atype == AllocationType.RDT:
        val = getattr(resource.new_allocs[tid][atype], rdt_res)
    else:
        val = resource.new_allocs[tid][atype]
    assert val == alloc

@pytest.mark.parametrize(
    'tid, atype, alloc, rdt_res, name', [
        (1, AllocationType.SHARES, 0.5, None, None),
        (2, AllocationType.QUOTA, 1.0, None, None),
        (3, AllocationType.RDT, 'L3:0=0x3', RDTResource.L3, 'BE_Group'),
        (4, AllocationType.RDT, 'MB:0=50', RDTResource.MB, 'BE_Group'),
    ]
)
def test_set_alloc_update(resource, tid, atype, alloc, rdt_res, name):
    assert tid in resource.new_allocs
    assert atype in resource.new_allocs[tid]
    resource.set_alloc(tid, atype, alloc, rdt_res, name)
    if atype == AllocationType.RDT:
        val = getattr(resource.new_allocs[tid][atype], rdt_res)
    else:
        val = resource.new_allocs[tid][atype]
    assert val == alloc

@pytest.mark.parametrize(
    'tid, atype, alloc, rdt_res, name', [
        (1, AllocationType.RDT, 'MB:0=50', RDTResource.MB, 'BE_Group'),
        (2, AllocationType.SHARES, 0.5, None, None),
        (3, AllocationType.QUOTA, 0.8, None, None),
        (4, AllocationType.RDT, 'L3:0=0xf', RDTResource.L3, 'BE_Group'),
    ]
)
def test_set_alloc_different(resource, tid, atype, alloc, rdt_res, name):
    assert tid in resource.new_allocs
    resource.set_alloc(tid, atype, alloc, rdt_res, name)
    assert atype in resource.new_allocs[tid]
    if atype == AllocationType.RDT:
        val = getattr(resource.new_allocs[tid][atype], rdt_res)
    else:
        val = resource.new_allocs[tid][atype]
    assert val == alloc

def test_set_alloc_check_final(resource):
    assert 1 in resource.new_allocs
    assert AllocationType.SHARES in resource.new_allocs[1]
    assert resource.new_allocs[1][AllocationType.SHARES] == 0.5
    assert 2 in resource.new_allocs
    assert AllocationType.QUOTA in resource.new_allocs[2]
    assert resource.new_allocs[2][AllocationType.QUOTA] == 1.0
    assert 3 in resource.new_allocs
    assert AllocationType.RDT in resource.new_allocs[3]
    assert getattr(resource.new_allocs[3][AllocationType.RDT], RDTResource.L3) == 'L3:0=0x3'
    assert 4 in resource.new_allocs
    assert AllocationType.RDT in resource.new_allocs[4]
    assert getattr(resource.new_allocs[4][AllocationType.RDT], RDTResource.MB) == 'MB:0=50'
