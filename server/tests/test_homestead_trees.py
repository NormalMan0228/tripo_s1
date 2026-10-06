"""Field trees: each tree is shaken on its own, fruit falls to the ground server-side and
is picked up one item at a time; the tree regrows on its own timer."""
import json, pathlib
from collections import Counter
from server import homestead
from server.tests.test_api import world, account
from server.tests.test_homestead import get, do

def test_shake_drops_fixed_fruit_without_filling_the_bag(world,monkeypatch):
    monkeypatch.setattr('server.homestead.secrets.randbelow',lambda upper: upper-1)  # bonus rolls miss
    app,c,t=world; a=account(c,'shaker')
    before=get(c,a)['bag']
    shaken=do(c,a,'shake',node='apple_tree_01').json()
    kind,fruit,count=homestead.tree_fruit('apple_tree_01')
    assert (kind,fruit)==('apple','apple') and count in (2,3)
    assert shaken['reward']=={'kind':'shake','node':'apple_tree_01','drops':['apple']*count}
    assert shaken['bag']==before and shaken['drops']['apple_tree_01']['items']==['apple']*count
    assert shaken['nodes']['apple_tree_01']==t[0]+homestead.TREES['apple']['respawn']
    assert shaken['catalog']['trees']['apple']['hang']==[2,3]
    # The same tree is bare now; a second shake gives nothing until it regrows.
    t[0]+=1
    assert do(c,a,'shake',node='apple_tree_01').json()['detail']=='life_regrowing'
    # Other trees are independent, but shakes keep the gather pace.
    assert do(c,a,'shake',node='apple_tree_02').status_code==200
    assert do(c,a,'shake',node='pine_tree_01').json()['detail']=='life_too_fast'
    t[0]+=1
    pine=do(c,a,'shake',node='pine_tree_01').json()
    assert set(pine['reward']['drops'])=={'pinecone'}
    t[0]+=1
    palm=do(c,a,'shake',node='palm_tree_04').json()
    assert palm['reward']['drops']==['coconut']*homestead.tree_fruit('palm_tree_04')[2]
    # Regrowth: after the tree's own timer it can be shaken again.
    t[0]+=homestead.TREES['apple']['respawn']
    assert do(c,a,'shake',node='apple_tree_01').status_code==200

def test_pickup_moves_one_fallen_item_at_a_time(world,monkeypatch):
    monkeypatch.setattr('server.homestead.secrets.randbelow',lambda upper: 0)  # bonus branch falls too
    app,c,t=world; a=account(c,'picker')
    drops=do(c,a,'shake',node='pine_tree_02').json()['reward']['drops']
    assert drops.count('pinecone')==homestead.tree_fruit('pine_tree_02')[2] and drops[-1]=='branch'
    # Only what lies under this tree, only items that fell.
    assert do(c,a,'pickup',node='pine_tree_03').json()['detail']=='life_nothing_here'
    assert do(c,a,'pickup',node='pine_tree_02',item='coconut').json()['detail']=='life_nothing_here'
    got=do(c,a,'pickup',node='pine_tree_02',item='branch').json()
    assert got['reward']=={'kind':'pickup','node':'pine_tree_02','items':{'branch':1},'left':len(drops)-1}
    assert got['bag']['branch']==1
    for left in range(len(drops)-2,-1,-1):
        got=do(c,a,'pickup',node='pine_tree_02',item='pinecone').json()
        assert got['reward']['left']==left
    assert got['bag']['pinecone']==drops.count('pinecone') and 'pine_tree_02' not in got['drops']
    assert do(c,a,'pickup',node='pine_tree_02').json()['detail']=='life_nothing_here'

def test_fallen_fruit_spoils_and_ids_are_validated(world):
    app,c,t=world; a=account(c,'spoiler')
    assert do(c,a,'shake',node='apple_tree_05').status_code==200
    t[0]+=homestead.DROP_TTL+1
    assert 'apple_tree_05' not in get(c,a)['drops']
    assert do(c,a,'pickup',node='apple_tree_05').json()['detail']=='life_nothing_here'
    for bad in ['apple_tree_39','apple_tree_00','pine_tree_14','rock_01','apple_tree_1']:
        assert do(c,a,'shake',node=bad).status_code==409, bad
    for bad in ['../x','Apple_tree_01','a'*25]:
        assert do(c,a,'shake',node=bad).status_code==422, bad
    assert do(c,a,'pickup',node='rock_01').json()['detail']=='life_nothing_here'

def test_fruit_left_under_a_regrown_tree_stays():
    state=homestead.initial()
    class Body: node='apple_tree_03'; item=''
    homestead.shake(state,Body,100)
    first=list(state['drops']['apple_tree_03']['items'])
    homestead.pickup(state,Body,101)
    homestead.shake(state,Body,100+homestead.TREES['apple']['respawn'])
    lying=state['drops']['apple_tree_03']['items']
    assert lying[:len(first)-1]==first[1:] and len(lying)>len(first)-1

def test_tree_table_matches_the_map_layout():
    layout=json.loads((pathlib.Path(__file__).resolve().parents[2]/'game'/'maps'/'archipelago'/'environment_layout.json').read_text(encoding='utf-8'))
    placed=Counter(instance['id'] for instance in layout['instances'])
    for kind,rule in homestead.TREES.items():
        assert placed[rule['prop']]==rule['count'], kind
        assert rule['fruit'] in homestead.PRICES and rule['fruit'] in homestead.NAMES
    assert len(homestead.TREE_NODES)==sum(rule['count'] for rule in homestead.TREES.values())
    assert not set(homestead.TREE_NODES)&set(homestead.NODES)
    assert all(len(node)<=24 for node in homestead.TREE_NODES)
    client=(pathlib.Path(__file__).resolve().parents[2]/'game'/'scripts'/'tree_fruit.gd').read_text(encoding='utf-8')
    for kind,rule in homestead.TREES.items():
        assert f'"{rule["prop"]}":"{kind}"' in client
