import base64
import json
from server.tests.test_concept import Provider, world, craft, run
from server.tests.test_studio import account, mutation


def test_feedback_edits_current_picture_and_approved_edit_is_built_once(tmp_path):
    provider=Provider();app,client=world(tmp_path,provider)
    with client as c:
        owner=account(c,'alice')
        job=c.post('/v1/studio/jobs',headers=owner,json=craft()).json()['id'];run(app,job)
        route='/v1/studio/jobs/'+job
        before=c.get(route,headers=owner).json()
        image=c.get(before['concept']['url'],headers=owner).content
        body=mutation(feedback='  지붕은 파랗게, 다리는 짧게  ')
        reply=c.post(route+'/redraw',headers=owner,json=body)
        assert reply.status_code==200 and c.post(route+'/redraw',headers=owner,json=body).json()==reply.json()
        run(app,job)
        result=c.get(route,headers=owner).json()
        assert result['state']=='awaiting_confirmation'
        assert result['concept']['feedback']=='지붕은 파랗게, 다리는 짧게'
        assert result['concept']['draws']==2 and result['concept']['estimate_with_concept']==40
        assert base64.b64decode(provider.uploads[0].split(',')[1])==image
        assert provider.calls[-1][0]=='/generation/image-to-image'
        assert provider.calls[-1][1]['input']=='uploaded-reference-1'
        assert '지붕은 파랗게, 다리는 짧게' in provider.calls[-1][1]['prompt']
        assert 'Preserve its identity' in provider.calls[-1][1]['prompt']
        confirm=mutation(use_concept=True)
        assert c.post(route+'/confirm',headers=owner,json=confirm).status_code==200
        assert c.post(route+'/confirm',headers=owner,json=confirm).status_code==200
        run(app,job,4)
        assert provider.calls[-1][1]['input']=='concept-2'
        assert len(provider.calls)==3
        assert c.get(route,headers=owner).json()['state']=='ready'


def test_failed_edit_keeps_previous_image_task_and_does_not_claim_feedback_applied(tmp_path):
    provider=Provider();app,client=world(tmp_path,provider)
    with client as c:
        owner=account(c,'alice');job=c.post('/v1/studio/jobs',headers=owner,json=craft()).json()['id'];run(app,job)
        route='/v1/studio/jobs/'+job
        before=c.get(route,headers=owner).json();image=c.get(before['concept']['url'],headers=owner).content
        provider.fail_concept=True
        assert c.post(route+'/redraw',headers=owner,json=mutation(feedback='make the roof blue')).status_code==200
        run(app,job)
        result=c.get(route,headers=owner).json()
        assert result['state']=='awaiting_confirmation' and result['concept']['draws']==1
        assert result['concept']['feedback']=='' and result['provenance']['concept_error']=='concept_failed'
        assert c.get(result['concept']['url'],headers=owner).content==image
        assert c.post(route+'/confirm',headers=owner,json=mutation()).status_code==200
        run(app,job,4)
        assert provider.calls[-1][1]['input']=='concept-1'


def test_feedback_is_owned_bounded_moderated_and_blank_keeps_old_redraw(tmp_path):
    provider=Provider();app,client=world(tmp_path,provider)
    with client as c:
        owner=account(c,'alice');other=account(c,'bob')
        job=c.post('/v1/studio/jobs',headers=owner,json=craft()).json()['id'];run(app,job)
        route='/v1/studio/jobs/'+job+'/redraw'
        assert c.post(route,headers=other,json=mutation(feedback='blue')).status_code==404
        assert c.post(route,headers=owner,json=mutation(feedback='x'*501)).status_code==422
        assert c.post(route,headers=owner,json=mutation(feedback='fuck')).status_code==422
        assert len(provider.calls)==1
        assert c.post(route,headers=owner,json=mutation(feedback='   ')).status_code==200
        run(app,job)
        assert provider.calls[-1][0]=='/generation/text-to-image' and not provider.uploads
        with app.state.db.read() as conn:
            quote=json.loads(conn.execute('SELECT provenance FROM studio_jobs WHERE id=?',(job,)).fetchone()[0])
        assert quote['concept_redraw_attempts']==1
