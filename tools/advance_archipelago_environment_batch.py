"""Record the explicit human checkpoint approval and authorize the next fifteen."""
from datetime import datetime, timezone
from archipelago_queue import locked_queue

NEXT=['20_pier','21_boat','25_picnic_table','28_beach_umbrella','29_beach_lounger',
      '30_cafe_umbrella','31_cafe_table','32_cafe_chair','33_signboard',
      '34_timber_fence','35_picket_fence','36_speaker','41_planter','44_pink_flowers','45_reeds']
EVIDENCE='User checkpoint reply: 이대로 확정하고 다음 15종 진행'
with locked_queue() as queue:
    current=queue['active_batch']
    assert current['id']=='batch_02_links_nature_camp'
    assert current['status']=='awaiting_user' and current['placement_verified']
    for item in queue['items']:
        if item['id'] in current['assets']:
            item['review_status']='approved'
            item['placement_status']='placed'
            item['approval_evidence']=EVIDENCE
    current['status']='approved_and_placed'
    current['approval_evidence']=EVIDENCE
    current['approved_at']=datetime.now(timezone.utc).isoformat()
    queue['batch_history'].append(dict(current))
    assert all(next(i for i in queue['items'] if i['id']==ident)['review_status']=='planned' for ident in NEXT)
    queue['active_batch']={'id':'batch_03_coast_cafe_garden','assets':NEXT,'max_concurrent':3,
        'max_observed_concurrent':0,'status':'authorized','approval_evidence':EVIDENCE,
        'checkpoint_policy':'User confirmation after each 15 generated models.',
        'review_package':'art/maps/archipelago_environment_v2','remaining_after_batch':2}
print('NEXT_ENVIRONMENT_BATCH_AUTHORIZED models=15 max_concurrent=3')
