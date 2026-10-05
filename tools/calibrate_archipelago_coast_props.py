"""Set adult-scale dimensions and unambiguous axes before local mesh preparation."""
from archipelago_queue import locked_queue

DIMENSIONS={
 '20_pier':[3,6,1.65], '21_boat':[1.3,3.4,.75], '25_picnic_table':[2.1,1.65,.82],
 '28_beach_umbrella':[2.6,2.6,2.35], '29_beach_lounger':[.72,1.9,.85],
 '30_cafe_umbrella':[2.5,2.5,2.45], '31_cafe_table':[.9,.9,.78],
 '32_cafe_chair':[.52,.56,.93], '33_signboard':[.62,.60,1.08],
 '34_timber_fence':[2.2,.20,1.02], '35_picket_fence':[2,.16,.9],
 '36_speaker':[.52,.45,1.25], '41_planter':[.58,.58,.72],
 '44_pink_flowers':[.55,.50,.48], '45_reeds':[.62,.60,1.25]}
with locked_queue() as queue:
    assert queue['active_batch']['id']=='batch_03_coast_cafe_garden'
    for item in queue['items']:
        if item['id'] in DIMENSIONS:
            item['target_dimensions_m']=DIMENSIONS[item['id']]
            if item['id'] in ['20_pier','21_boat','29_beach_lounger']:
                item['long_axis_godot']='+Z'
            if item['id'] in ['25_picnic_table','34_timber_fence','35_picket_fence']:
                item['long_axis_godot']='+X'
print('COAST_PROP_SCALE_CONFIGURED models=15')
