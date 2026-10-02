import copy
import pytest
from server.asset_assembly import demo_design
from server.asset_vm import AssetVM,ProgramError,exercise,exercise_extended


def program(body,state=None):
    return {'version':1,'state':state or {},'functions':{},'events':{'tick':body}}


@pytest.mark.parametrize('kind',['flower','clock','chest'])
def test_published_examples_survive_longer_interactions(kind):
    plan,p=demo_design(kind);before=copy.deepcopy(p)
    report=exercise_extended(p,{part['id'] for part in plan['parts']})
    assert report['events_evaluated']==754 and report['accumulated_seconds']==60
    assert p==before


def test_accumulating_rotation_passes_old_gate_but_fails_publication():
    p=program([['store','angle',['add',['state','angle'],['mul',['input','dt'],30]]],
               ['emit','rotate_y','rotor',['state','angle']]],{'angle':0})
    assert exercise(p,{'rotor'})['finite']
    with pytest.raises(ProgramError,match=r'publication_check:tick:\d+:command_range_rotate_y'):
        exercise_extended(p,{'rotor'})


def test_clock_boundary_is_checked_without_claiming_day_long_simulation():
    p=program([['emit','rotate_y','rotor',['input','time']]])
    assert exercise(p,{'rotor'})['finite']
    with pytest.raises(ProgramError,match='command_range_rotate_y'):exercise_extended(p,{'rotor'})


def test_command_count_and_range_have_distinct_private_repair_reasons():
    p=program([['repeat','i',64,[['emit','rotate_z','hand',0],['emit','rotate_z','hand',0],['emit','rotate_z','hand',0]]]])
    with pytest.raises(ProgramError) as error:AssetVM(p,{'hand'}).run('tick')
    assert str(error.value)=='execution_rejected' and error.value.reason=='command_limit'
    p=program([['emit','rotate_z','hand',181]])
    with pytest.raises(ProgramError) as error:AssetVM(p,{'hand'}).run('tick')
    assert str(error.value)=='execution_rejected' and error.value.reason=='command_range_rotate_z'


def test_runtime_error_keeps_public_code_and_rolls_back_without_exception_content():
    p=program([['store','x',2],['do',['div',1,0]]],{'x':0})
    vm=AssetVM(p,[])
    with pytest.raises(ProgramError) as result:vm.run('tick')
    assert str(result.value)=='execution_rejected' and result.value.reason=='division_by_zero'
    assert vm.state=={'x':0} and vm.commands==[]
    p=program([['do',['var','private_name']]])
    with pytest.raises(ProgramError) as result:exercise_extended(p,[])
    assert 'undefined_local' in str(result.value) and 'private_name' not in str(result.value)
