import json
import pytest
from server.tests.test_studio import world,account,build,mutation
from server import room_budget

def test_room_limit_measures_all_parts_and_rolls_back_placement(world,monkeypatch):
    app,c=world;owner=account(c,'owner');stranger=account(c,'stranger')
    oid=build(app,c,owner,'flower');route='/v1/objects/'+oid
    assembly=c.get(route+'/assembly',headers=owner).json()
    total=sum(len(c.get(route+'/parts/'+part['id'],headers=owner).content) for part in assembly['plan']['parts'])
    original=room_budget.LIMITS.copy()
    monkeypatch.setitem(room_budget.LIMITS,'bytes',total-1)
    request=mutation(version=1,room='home',x=2,z=0)
    denied=c.post(route+'/placement',headers=owner,json=request)
    assert denied.status_code==409 and denied.json()['detail']=='room_render_budget_exceeded'
    current=next(o for o in c.get('/v1/me',headers=owner).json()['objects'] if o['id']==oid)
    assert current['state']=='inventory' and current['version']==1
    monkeypatch.setitem(room_budget.LIMITS,'bytes',total)
    assert c.post(route+'/placement',headers=owner,json=request).status_code==200
    usage=c.get('/v1/studio',headers=owner).json()['room_usage']
    assert usage['home']['used']['bytes']==total and usage['home']['percent']==100
    assert usage['home']['count']==1 and usage['workshop']['count']==0
    assert c.get('/v1/studio',headers=stranger).json()['room_usage']['home']['count']==0
    assert c.post(route+'/placement',headers=owner,json=mutation(version=2,room='home',x=-2,z=0)).status_code==200
    assert c.post(route+'/placement',headers=owner,json=mutation(version=3,room='home',action='retrieve')).status_code==200
    assert c.get('/v1/studio',headers=owner).json()['room_usage']['home']['used']['bytes']==0

def test_legacy_route_cannot_bypass_room_budget(world,monkeypatch):
    app,c=world;owner=account(c,'owner')
    starter=c.get('/v1/me',headers=owner).json()['objects'][0]
    monkeypatch.setitem(room_budget.LIMITS,'bytes',1)
    response=c.post('/v1/objects/'+starter['id'],headers=owner,json=mutation(version=1,action='place',x=4,z=4))
    assert response.status_code==409 and response.json()['detail']=='room_render_budget_exceeded'
    assert c.get('/v1/me',headers=owner).json()['objects'][0]['version']==1

def test_same_room_aggregates_existing_furniture(world,monkeypatch):
    app,c=world;owner=account(c,'owner')
    first=build(app,c,owner,'chest');second=build(app,c,owner,'clock')
    assert c.post('/v1/objects/'+first+'/placement',headers=owner,json=mutation(version=1,room='home',x=2,z=0)).status_code==200
    usage=c.get('/v1/studio',headers=owner).json()['room_usage']['home']['used']
    monkeypatch.setitem(room_budget.LIMITS,'draw_calls',usage['draw_calls'])
    response=c.post('/v1/objects/'+second+'/placement',headers=owner,json=mutation(version=1,room='home',x=-2,z=0))
    assert response.status_code==409 and response.json()['detail']=='room_render_budget_exceeded'
    # Independent room has its own capacity; changing client geometry/count is forbidden.
    assert c.post('/v1/objects/'+second+'/placement',headers=owner,json=mutation(version=1,room='home',x=-2,z=0,bytes=0)).status_code==422
    monkeypatch.setitem(room_budget.LIMITS,'draw_calls',3)
    assert c.post('/v1/objects/'+second+'/placement',headers=owner,json=mutation(version=1,room='workshop',x=2,z=0)).status_code==200
