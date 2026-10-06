"""Tilling, foraging spots and the fishing fight added to the village life loop."""
import pathlib, re
from server import homestead
from server.tests.test_api import world, account, mutation
from server.tests.test_homestead import get, do

def test_till_stays_in_farm_meadow_on_grid_apart_and_under_cap(world):
    app,c,t=world; a=account(c,'tiller')
    state=get(c,a)
    assert len(state['plots'])==6 and all('x' in plot and 'crop' not in plot for plot in state['plots'])
    for x,z,code in [(0,0,'life_not_farmland'),(-22.0,-29.4+30,'life_not_farmland'),(-22.3,-31.2,'life_not_farmland'),
                     (-22.0,-33.0,'life_not_farmland'),(-20.2,-33.0,'life_plot_overlap')]:
        r=do(c,a,'till',x=x,z=z)
        assert r.status_code==409 and r.json()['detail']==code,(x,z,r.text)
    tilled=do(c,a,'till',x=-22.0,z=-31.2).json()
    assert len(tilled['plots'])==7 and tilled['reward']=={'kind':'till','plot':6}
    assert do(c,a,'till',x=-22.0,z=-31.2).json()['detail']=='life_plot_overlap'
    # Plant, water and harvest work on the new bed like on starter beds.
    assert do(c,a,'plant',plot=6,item='carrot').status_code==200
    assert do(c,a,'water',plot=6).status_code==200
    t[0]+=120
    harvest=do(c,a,'harvest',plot=6).json()
    assert harvest['bag']['carrot']==2 and harvest['reward']['items']=={'carrot':2}
    assert harvest['plots'][6]=={'x':-22.0,'z':-31.2}
    # Starter beds stay; tilled empty beds can be grassed over again.
    assert do(c,a,'untill',plot=0).json()['detail']=='life_starter_plot'
    assert len(do(c,a,'untill',plot=6).json()['plots'])==6
    cells=[(x,z) for x in (-23.8,-22.0,-20.2,-18.4,-16.6) for z in (-29.4,-31.2,-36.6,-38.4,-40.2)]
    made=0
    for x,z in cells:
        if do(c,a,'till',x=x,z=z).status_code==200: made+=1
    assert made==homestead.MAX_PLOTS-6
    assert do(c,a,'till',x=-23.8,z=-34.8).json()['detail']=='life_plot_limit'
    assert do(c,a,'plant',plot=18,item='turnip').status_code==422

def test_old_saves_get_starter_positions_without_losing_crops(world):
    old={'version':3,'coins':5,'bag':{},'plots':[{'crop':'turnip','planted_at':1,'watered':True,'ready_at':5}]+[{} for _ in range(5)],
         'fishing':None,'cooldowns':{},'harvested':0,'caught':0,'collection':{},'order_day':-1}
    view=homestead.public(old,10)
    assert view['plots'][0]['crop']=='turnip' and view['plots'][0]['ready']
    assert [(p['x'],p['z']) for p in view['plots']]==homestead.STARTER_PLOTS
    assert view['records']=={} and view['nodes']=={}

def test_forage_spots_respawn_per_node_and_rate_limit(world,monkeypatch):
    app,c,t=world; a=account(c,'forager')
    first=do(c,a,'gather',node='rock_01').json()
    assert first['reward']['node']=='rock_01' and first['bag']['stone']>=1
    assert first['nodes']['rock_01']==t[0]+homestead.FORAGE['rock']['respawn']
    assert do(c,a,'gather',node='rock_02').json()['detail']=='life_too_fast'
    t[0]+=1
    assert do(c,a,'gather',node='rock_02').status_code==200
    t[0]+=1
    assert do(c,a,'gather',node='rock_01').json()['detail']=='life_regrowing'
    for bad in ['rock_99','../x']:
        assert do(c,a,'gather',node=bad).status_code in (409,422)
    t[0]+=homestead.FORAGE['rock']['respawn']
    again=do(c,a,'gather',node='rock_01').json()
    assert again['reward']['kind']=='gather' and 'rock_02' not in again['nodes']
    # Pinned rolls: shells give exactly one find, the rare pearl only on its own roll.
    monkeypatch.setattr('server.homestead.secrets.randbelow',lambda upper: 0)
    t[0]+=1
    assert do(c,a,'gather',node='shell_01').json()['reward']['items']=={'shell':1}
    # Legacy apple/herb gathering still works alongside spots.
    assert do(c,a,'gather',item='herb').json()['bag']['herb']==2

def test_fish_depends_on_water_and_time_and_records_sizes(world):
    for spot in homestead.SPOTS:
        for clock in (3*3600,15*3600):  # 12:00 KST (day) and 00:00 KST (night)
            for _ in range(40):
                fish,size=homestead.pick_fish(spot,clock)
                data=homestead.FISH[fish]
                assert spot in data['spots'] and data['size'][0]<=size<=data['size'][1]
                assert data['time']=='any' or data['time']==('night' if homestead.night(clock) else 'day')
    assert homestead.night(15*3600) and not homestead.night(3*3600)  # 00:00 KST night, 12:00 KST day
    app,c,t=world; a=account(c,'trophy')
    cast=do(c,a,'cast',spot='river').json()
    assert cast['fishing']['spot']=='river' and all(cast['fishing']['cast_at']<n<cast['fishing']['bite_at'] for n in cast['fishing']['nibbles'])
    assert do(c,a,'cast',spot='lava').status_code==422
    t[0]=cast['fishing']['bite_at']+.2
    hooked=do(c,a,'reel').json()
    assert hooked['fishing']['phase']=='hooked' and hooked['fishing']['difficulty']>=1
    assert do(c,a,'cast').json()['detail']=='life_already_fishing'
    t[0]+=hooked['fishing']['fight_min']
    caught=do(c,a,'reel',outcome='landed').json()
    fish=caught['reward']['item']
    assert caught['records'][fish]==caught['reward']['size'] and caught['collection'][fish]==1
    assert caught['bag'][fish]==1 and caught['catalog']['prices'][fish]==homestead.FISH[fish]['price']
    # A lost fight frees the line and gives nothing.
    cast=do(c,a,'cast').json(); t[0]=cast['fishing']['bite_at']+.1
    do(c,a,'reel'); lost=do(c,a,'reel',outcome='lost').json()
    assert lost['fishing'] is None and lost['caught']==1 and lost['reward']['why']=='lost'
    # A fight left hanging expires so the next cast is not blocked forever.
    cast=do(c,a,'cast').json(); t[0]=cast['fishing']['bite_at']+.1
    do(c,a,'reel'); t[0]+=homestead.FIGHT_MAX+1
    assert do(c,a,'cast').status_code==200

def test_client_forage_table_matches_server_nodes():
    source=(pathlib.Path(__file__).resolve().parents[2]/'game'/'scripts'/'forage.gd').read_text(encoding='utf-8')
    rows=re.findall(r'\["(\w+)","(\w+)",(-?[\d.]+),(-?[\d.]+)\]',source)
    assert {node:kind for node,kind,_,_ in rows}==homestead.NODES
    assert set(homestead.NODES.values())==set(homestead.FORAGE)

def test_shop_sells_every_seed_and_buys_every_find(world):
    app,c,t=world; a=account(c,'shopper')
    catalog=get(c,a)['catalog']
    assert set(catalog['shop'])=={crop+'_seed' for crop in homestead.CROPS}|{'bait'}
    every_drop={drop[0] for rule in homestead.FORAGE.values() for drop in rule['drops']}
    assert every_drop|set(homestead.CROPS)|set(homestead.FISH)<=set(catalog['prices'])
    assert all(item in catalog['names'] for item in catalog['prices'])
    assert do(c,a,'buy',item='sunflower_seed',quantity=2).json()['bag']['sunflower_seed']==2
