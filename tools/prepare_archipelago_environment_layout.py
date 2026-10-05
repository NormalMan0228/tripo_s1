"""Reference-guided scatter, bridge bank alignment and reusable runtime assets."""
import ast
from collections import Counter
import json
import math
from pathlib import Path
import random
import sys

import numpy as np
from scipy.interpolate import LinearNDInterpolator
from prepare_archipelago_placement import map_copy

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/maps/archipelago_objects_v1'
queue = json.loads((BASE/'queue.json').read_text(encoding='utf-8'))
OUT = ROOT/queue['active_batch'].get('review_package','art/maps/archipelago_environment_v1')
LAB = ROOT/'labs/terrain_lab'
OUT.mkdir(exist_ok=True,parents=True)
(LAB/'assets/environment').mkdir(exist_ok=True)
terrain = json.loads((ROOT/'art/maps/archipelago_terrain_v6/manifest.json').read_text())
buildings = json.loads((LAB/'building_placements.json').read_text(encoding='utf-8'))['buildings']
batch_ids = [i['id'] for i in queue['items'] if i['category']!='building' and i['review_status']=='approved' and i.get('placement_status')=='placed']
batch_ids += [ident for ident in queue['active_batch']['assets'] if ident not in batch_ids]
if '--bridge-only' in sys.argv:
    batch_ids = [ident for ident in batch_ids if ident in ('18_bridge_short','19_bridge_long','48_bridge_rope','49_bridge_boardwalk')]
namespace = {'np':np,'math':math}
source = (ROOT/'tools/prepare_archipelago_v5.py').read_text()
exec('\n\n'.join(ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)),namespace)
samplers = {}
contours = {}
for island in terrain['islands']:
    v = np.load(ROOT/f"art/maps/archipelago_terrain_v5/{island['id']}.npz")['vertices']
    samplers[island['id']] = LinearNDInterpolator(v[:,:2],v[:,2])
    contours[island['id']] = namespace['catmull'](island['outline'])
rng = random.Random(1052026)
instances = []
trees = []
links = [
    {'id':'18_bridge_short','a':[-11,-36],'b':[15,-36],'islands':[1,2],'name':'북서 ↔ 북동 · 삼나무 아치 다리'},
    {'id':'49_bridge_boardwalk','a':[57,-7],'b':[57,14],'islands':[2,4],'name':'북동 ↔ 남동 · 청록 난간 데크 다리'},
    {'id':'48_bridge_rope','a':[-9,27],'b':[16,27],'islands':[3,4],'name':'남서 ↔ 남동 · 밧줄 난간 다리'},
    {'id':'19_bridge_long','a':[-25,58],'b':[2,73],'islands':[3,5],'name':'남서 ↔ 등대 · 긴 참나무 아치 다리'},
]

def ground(island_no,x,z):
    island = terrain['islands'][island_no-1]
    h = float(samplers[island['id']](x,-z))
    for b in buildings:
        if b['island_index'] != island_no:
            continue
        a = math.radians(b['yaw_degrees'])
        dx,dz = x-b['position'][0],z-b['position'][2]
        lx,lz = dx*math.cos(a)-dz*math.sin(a),dx*math.sin(a)+dz*math.cos(a)
        outside = max(abs(lx)-b['pad_half_extents'][0],abs(lz)-b['pad_half_extents'][1])
        weight = 1-float(namespace['ss'](0,b['pad_blend_m'],outside))
        h = h*(1-weight)+b['position'][1]*weight
    return h

def segment_distance(x,z,a,b):
    p = np.array([x,z]);a=np.array(a);b=np.array(b)
    t = np.clip(np.dot(p-a,b-a)/np.dot(b-a,b-a),0,1)
    return float(np.linalg.norm(p-(a+t*(b-a))))

def building_distance(x,z,b):
    a=math.radians(b['yaw_degrees']);dx=x-b['position'][0];dz=z-b['position'][2]
    lx=dx*math.cos(a)-dz*math.sin(a);lz=dx*math.sin(a)+dz*math.cos(a)
    return math.hypot(max(0,abs(lx)-b['dimensions_m'][0]/2),max(0,abs(lz)-b['dimensions_m'][2]/2))

def land_ok(island_no,x,z,coast=6,building_clearance=1.0,lake=1.30,avoid_bridges=True):
    island=terrain['islands'][island_no-1]
    if float(namespace['distance'](np.array(x),np.array(-z),contours[island['id']]))<coast:
        return False
    if 'pond' in island and float(namespace['pondq'](np.array(x),np.array(-z),island['pond']))<lake:
        return False
    if any(building_distance(x,z,b)<building_clearance for b in buildings if b['island_index']==island_no):
        return False
    if avoid_bridges and any(segment_distance(x,z,l['a'],l['b'])<3.8 for l in links):
        return False
    # Keep the spring pool and waterfall approach free.
    if math.hypot(x+2.6,z+10.3)<9:
        return False
    return ground(island_no,x,z)>.6

def add(ident,island_no,x,z,yaw=None,scale=1,category=None,y=None):
    if ident not in batch_ids:
        return
    spec=next(i for i in queue['items'] if i['id']==ident)
    instances.append({'id':ident,'island_index':island_no,'position':[float(x),ground(island_no,x,z) if y is None else y,float(z)],
        'yaw_degrees':rng.uniform(-180,180) if yaw is None else yaw,'scale':scale,'category':category or spec['category']})

# Irregular canopy clusters, varied orientation/size and broad open sightlines.
anchors={
 1:[(-65,-54),(-52,-57),(-30,-56),(-16,-53),(-65,-25),(-48,-24),(-20,-26),(-53,-31)],
 2:[(24,-54),(41,-57),(63,-55),(76,-48),(75,-23),(58,-13),(33,-16),(19,-42)],
 3:[(-66,12),(-44,10),(-20,15),(-20,42),(-33,54),(-48,60),(-74,39),(-67,24)],
 4:[(28,20),(46,18),(76,23),(79,40),(62,59),(46,59),(26,46),(29,35)],
}
for island_no in range(1,5):
    island=terrain['islands'][island_no-1]
    desired={1:12,2:11,3:15,4:13}[island_no]
    accepted=[]
    candidates=list(anchors[island_no])
    for _ in range(2400):
        if len(candidates)<30:
            cx,cy=island['center']
            candidates.append((rng.uniform(cx-34,cx+34),rng.uniform(-cy-25,-cy+25)))
        x,z=candidates.pop(0)
        if not land_ok(island_no,x,z,coast=7,building_clearance=2.0,lake=1.45):
            continue
        if any(math.hypot(x-tx,z-tz)<7 for tx,tz in accepted):
            continue
        if island_no==3 and math.hypot(x+33,z-37)<9:
            continue
        if island_no==4 and math.hypot(x-50,z-45)<11:
            continue
        ident='38_conifer' if len(accepted)%4==2 else '37_round_tree'
        scale=rng.uniform(.79,1.06)
        add(ident,island_no,x,z,scale=scale)
        accepted.append((x,z));trees.append((island_no,x,z,scale))
        if len(accepted)==desired:
            break
    assert len(accepted)==desired,(island_no,len(accepted))

for x,z in [(64,-23),(58,-26),(67,-16),(34,-15)]:
    if land_ok(2,x,z,building_clearance=1.5):
        add('39_palm',2,x,z,scale=rng.uniform(.83,1.0))
        trees.append((2,x,z,1.0))

# Garden beds flank architecture, leaving stairs and door approaches open.
for b in buildings:
    if b['island_index']==5:
        offsets=[(-3.2,-1.2),(3.4,-.6)]
    else:
        hx,hz=b['dimensions_m'][0]/2,b['dimensions_m'][2]/2
        offsets=[(-hx-1,-hz*.4),(hx+1,-hz*.35),(-hx*.72,hz+1),(hx*.72,hz+1)]
    a=math.radians(b['yaw_degrees'])
    for ox,oz in offsets:
        x=b['position'][0]+ox*math.cos(a)+oz*math.sin(a)
        z=b['position'][2]-ox*math.sin(a)+oz*math.cos(a)
        if land_ok(b['island_index'],x,z,coast=3,building_clearance=.35,lake=1.2):
            add('40_shrub',b['island_index'],x,z,scale=rng.uniform(.6,.95))
            for _ in range(3):
                fx=x+rng.uniform(-.85,.85);fz=z+rng.uniform(-.8,.8)
                if land_ok(b['island_index'],fx,fz,coast=2.6,building_clearance=.18,lake=1.15):
                    add(rng.choice(['42_white_flowers','43_yellow_flowers']),b['island_index'],fx,fz,scale=rng.uniform(.7,1.08))

# Small understory clusters naturally follow trees, rather than a coast ring.
for island_no,x,z,scale in trees:
    angle=rng.uniform(0,math.tau);radius=rng.uniform(1.5,2.8)
    sx=x+math.cos(angle)*radius;sz=z+math.sin(angle)*radius
    if land_ok(island_no,sx,sz,coast=4,building_clearance=.45):
        add('40_shrub',island_no,sx,sz,scale=rng.uniform(.65,.95))
        for _ in range(rng.randint(1,3)):
            fx=sx+rng.uniform(-.7,.7);fz=sz+rng.uniform(-.7,.7)
            if land_ok(island_no,fx,fz,coast=3.5,building_clearance=.3):
                add(rng.choice(['42_white_flowers','43_yellow_flowers']),island_no,fx,fz,scale=rng.uniform(.65,.95))

for island_no,x,z,yaw in [(1,-47,-34,5),(1,-20,-30,0),(2,34,-24,-20),(2,68,-27,-35),
                            (3,-54,33,20),(3,-27,40,-30),(3,-40,58,160),(4,36,40,10),(4,62,40,-15)]:
    if land_ok(island_no,x,z,coast=5,building_clearance=.6):
        add('26_bench',island_no,x,z,yaw=yaw)

lamp_sites=[(1,-61,-29),(1,-35,-40),(1,-20,-37),(2,31,-39),(2,44,-28),(2,69,-30),
    (3,-42,29),(3,-24,29),(3,-57,28),(3,-60,42),(4,33,29),(4,41,30),(4,65,35),(4,68,46),(5,3,82)]
for link in links:
    a=np.array(link['a']);b=np.array(link['b']);direction=(b-a)/np.linalg.norm(b-a);side=np.array([-direction[1],direction[0]])
    for end,island_no in [(a,link['islands'][0]),(b,link['islands'][1])]:
        for sign in [-1,1]:
            p=end+side*3.15*sign
            lamp_sites.append((island_no,float(p[0]),float(p[1])))
for island_no,x,z in lamp_sites:
    if land_ok(island_no,x,z,coast=1.5,building_clearance=.65,lake=1.15,avoid_bridges=False):
        add('27_lamp',island_no,x,z,yaw=rng.choice([0,90,180,270]))

add('22_tent_orange',4,47,42,yaw=-15)
add('23_tent_green',4,61,44,yaw=20)
add('24_firepit',4,54,46,yaw=0)

# Patio furniture, beach leisure and stage equipment follow the reference.
for x,z in [(-68,-24.5),(-63,-26)]:
    add('31_cafe_table',1,x,z,yaw=0)
    add('30_cafe_umbrella',1,x,z,yaw=0)
    for dx,dz in [(-.95,0),(.95,0),(0,.95)]:
        add('32_cafe_chair',1,x+dx,z+dz,yaw=math.degrees(math.atan2(-dx,-dz)))
for island_no,x,z,yaw in [(1,-56,-30,12),(3,-12,32,-15),(3,-36,30,-20)]:
    add('33_signboard',island_no,x,z,yaw=yaw)
for x,z,yaw in [(65,29,90),(43,49,10),(62,48,-15)]:
    add('25_picnic_table',4,x,z,yaw=yaw)
    if (x,z)==(65,29) and '25_picnic_table' in batch_ids:
        instances[-1]['support_surface']='building_floor'
for island_no,x,z,yaw in [(2,83,-22,0),(4,74,59,25)]:
    add('28_beach_umbrella',island_no,x,z,yaw=yaw)
    add('29_beach_lounger',island_no,x-1.1,z-.4,yaw=yaw+10)
    add('29_beach_lounger',island_no,x+1.1,z-.4,yaw=yaw-10)
for x in [34.0,40.0]:
    add('36_speaker',4,x,28.5,yaw=0)
    if '36_speaker' in batch_ids:
        instances[-1]['support_surface']='building_floor'

# Garden boundaries are short, open sections rather than rings around islands.
for island_no,x,z,yaw in [(2,22,-14,0),(2,24.2,-14,0),(2,26.4,-14,0),
        (4,61.5,34.8,0),(4,63.7,34.8,0),(4,68.1,34.8,0),
        (3,-4.8,-1.5,70),(3,-4.05,.56,70)]:
    add('34_timber_fence',island_no,x,z,yaw=yaw)
for x,z,yaw in [(-74,35,90),(-74,37,90),(-72,39,0),(-70,39,0),(-66,39,0)]:
    add('35_picket_fence',3,x,z,yaw=yaw)
for b in buildings:
    if b['id'] in ['04_windmill','14_stage','15_picnic_shelter']:
        continue
    hx,hz=b['dimensions_m'][0]/2,b['dimensions_m'][2]/2
    a=math.radians(b['yaw_degrees'])
    for sign in [-1,1]:
        ox=sign*max(1.5,hx*.65);oz=hz+.65
        x=b['position'][0]+ox*math.cos(a)+oz*math.sin(a)
        z=b['position'][2]-ox*math.sin(a)+oz*math.cos(a)
        if land_ok(b['island_index'],x,z,coast=1.8,building_clearance=.1,lake=1.05):
            add('41_planter',b['island_index'],x,z,scale=rng.uniform(.85,1.05))

if '44_pink_flowers' in batch_ids:
    for shrub in [p for p in instances if p['id']=='40_shrub'][::3]:
        x,z=shrub['position'][0]+.8,shrub['position'][2]-.45
        if land_ok(shrub['island_index'],x,z,coast=2.2,building_clearance=.25,lake=1.2):
            add('44_pink_flowers',shrub['island_index'],x,z,scale=rng.uniform(.75,1.0))
for island_no in [2,3]:
    island=terrain['islands'][island_no-1]
    px,py,rx,ry,water=island['pond']
    for angle in [.12,.33,.45,1.7,1.95,2.15,3.4,3.6,4.9,5.08,5.25]:
        angle+=rng.uniform(-.055,.055)
        x=px+math.cos(angle)*rx*1.09
        z=-py+math.sin(angle)*ry*1.09
        add('45_reeds',island_no,x,z,yaw=rng.uniform(-180,180),scale=rng.uniform(.72,1.02),y=max(water-.07,ground(island_no,x,z)-.025))

# Docks meet the actual bank height; the lake dock is shorter and overlooks water.
piers=[]
if '20_pier' in batch_ids:
    support=BASE/'20_pier/support_geometry.json'
    deck=json.loads(support.read_text())['deck_height_m'] if support.exists() else 1.1
    for island_no,landing,tip,water in [(1,[-72,-27],[-75.8,-22.4],0),(3,[-32.5,44],[-38.5,44],1.18),(5,[0,80],[-5,83.3],0)]:
        a=np.array(landing,float);b=np.array(tip,float)
        center=(a+b)/2
        yaw=math.degrees(math.atan2(float((a-b)[0]),float((a-b)[1])))
        bank=ground(island_no,*a)
        assert np.isfinite(bank) and bank>.6,(island_no,bank,landing)
        add('20_pier',island_no,*center,yaw=yaw,y=bank+.025-deck)
        instances[-1].update({'water_height_m':water,'deck_height_m':deck,'support_surface':'pier_piles'})
        piers.append({'landing':landing,'tip':tip,'island':island_no,'bank_height_m':bank})
    add('21_boat',5,-4,87,yaw=115,y=-.06)

# Remove only small plants directly under the new furniture; preserve mature trees.
new_solids=[p for p in instances if p['id'] in ['25_picnic_table','29_beach_lounger','31_cafe_table','32_cafe_chair','33_signboard','41_planter']]
instances=[p for p in instances if p['id'] not in ['40_shrub','42_white_flowers','43_yellow_flowers','44_pink_flowers'] or
    not any(math.hypot(p['position'][0]-s['position'][0],p['position'][2]-s['position'][2])<(.85 if s['id']=='25_picnic_table' else .55) for s in new_solids)]

bridge_records=[]
for link in links:
    folder=BASE/link['id']
    mesh=json.loads((folder/'mesh_verification.json').read_text(encoding='utf-8'))
    item=next(i for i in queue['items'] if i['id']==link['id'])
    assert abs(mesh['height_m']-item['target_height_m'])<.01,link['id']
    # Blender +Y becomes Godot -Z. Swap the longitudinal source profile.
    profile=mesh['deck_centerline']
    usable=[p for p in profile if p['height_m'] is not None]
    assert len(usable)>=35,link['id']
    godot_profile=sorted([{**p,'t':-p['t']} for p in usable],key=lambda p:p['t'])
    # End skids may be hit below the deck. Find the uninterrupted deck from its centre.
    middle=min(range(len(godot_profile)),key=lambda n:abs(godot_profile[n]['t']))
    low=high=middle
    while low>0 and abs(godot_profile[low]['height_m']-godot_profile[low-1]['height_m'])<.30:
        low-=1
    while high+1<len(godot_profile) and abs(godot_profile[high]['height_m']-godot_profile[high+1]['height_m'])<.30:
        high+=1
    # Keep one complete board beyond each bank; mesh tips can end between planks.
    low+=1
    high-=1
    walk_bounds=[godot_profile[low]['t'],godot_profile[high]['t']]
    deck_a=godot_profile[low]['height_m'];deck_b=godot_profile[high]['height_m']
    a=np.array(link['a'],float);b=np.array(link['b'],float);span=float(np.linalg.norm(b-a))
    actual_walk_fraction=walk_bounds[1]-walk_bounds[0]
    ga=ground(link['islands'][0],*a);gb=ground(link['islands'][1],*b)
    assert min(ga,gb)>.8,(link['id'],ga,gb)
    scale_z=span/(mesh['dimensions_m'][1]*actual_walk_fraction)
    center=(a+b)/2-(b-a)/span*(sum(walk_bounds)/2)*mesh['dimensions_m'][1]*scale_z
    record={**link,'position':[float(center[0]),0,float(center[1])],'yaw_degrees':math.degrees(math.atan2(float((b-a)[0]),float((b-a)[1]))),
        'scale_z':scale_z,'width_m':mesh['dimensions_m'][0],
        'source_length_m':mesh['dimensions_m'][1], 'bank_heights_m':[ga,gb],
        'source_deck_ends_m':[deck_a,deck_b], 'profile':godot_profile,
        'vertical_end_offsets_m':[ga+.025-deck_a,gb+.025-deck_b], 'walk_fraction':actual_walk_fraction,'walk_bounds':walk_bounds}
    record['additional_arch_m'] = {'18_bridge_short':.7,'19_bridge_long':.8,'48_bridge_rope':0,'49_bridge_boardwalk':0}[link['id']]
    bridge_records.append(record)

if '--plan-only' in sys.argv:
    design={'instances':instances,'bridges':bridge_records,'piers':piers,'counts':dict(Counter(p['id'] for p in instances))}
    (OUT/'environment_design.json').write_text(json.dumps(design,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ENVIRONMENT_DESIGN_READY',design['counts'],'bridges=4')
    sys.exit(0)
models=[]
previous=json.loads((LAB/'environment_layout.json').read_text(encoding='utf-8')) if (LAB/'environment_layout.json').exists() else {'models':[]}
previous_models={m['id']:m for m in previous['models']}
for ident in batch_ids:
    folder=BASE/ident;stem=ident.split('_',1)[1]
    assert (folder/'review_verification.json').exists(),ident
    target=LAB/'assets/environment'/(stem+'.glb')
    if ident in previous_models and target.exists() and target.stat().st_mtime >= (folder/(stem+'.glb')).stat().st_mtime:
        textures=previous_models[ident]['runtime_textures']
    else:
        textures=map_copy(folder/(stem+'.glb'),LAB/'assets/environment'/(stem+'.glb'))
    item=next(i for i in queue['items'] if i['id']==ident)
    models.append({'id':ident,'name':item['name'],'category':item['category'],'model':'res://assets/environment/'+stem+'.glb','height_m':item['target_height_m'],'runtime_textures':textures})
    print('ENVIRONMENT_MODEL_READY',ident,flush=True)
manifest={'version':1,'review_batch':queue['active_batch']['id'],'review_status':'awaiting_user','models':models,
    'instances':instances,'bridges':bridge_records,'piers':piers,'units':'metres','all_five_islands_connected':True,
    'counts':dict(Counter(p['id'] for p in instances)),
    'reserved_remaining_models':len([i for i in queue['items'] if i['id'] not in batch_ids and i['review_status']!='approved']),
    'output_directory':str(OUT.relative_to(ROOT)).replace('\\','/'),
    'placement_scope':'Approved earlier models plus current fifteen-model preview; user confirmation required before next generation batch.'}
encoded=json.dumps(manifest,ensure_ascii=False,indent=2)
(OUT/'environment_layout.json').write_text(encoded,encoding='utf-8')
(LAB/'environment_layout.json').write_text(encoded,encoding='utf-8')
print('ENVIRONMENT_LAYOUT_READY models=',len(models),'instances=',len(instances),'bridges=4',flush=True)
