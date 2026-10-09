"""Account-owned village life. All growth, catches and exchanges use server time/state.

Leaf coins are a closed village economy: never converted to API-credit shards.
Walking is cosmetic/local in the village; action ownership, inventory and timing
are authoritative, but these endpoints do not claim to attest client proximity.
The client checks roads, water and slopes before tilling; the server keeps tilled
plots inside the farm meadow, on its grid, apart from each other and under a cap.
"""
import contextvars
import copy
import secrets


# Village furniture coordinates are metres from the town green; this box covers all
# five islands (the client also refuses water, buildings and props).
VILLAGE_X = (-60.0, 130.0)
VILLAGE_Z = (-115.0, 60.0)


def village_inside(x, z):
    return VILLAGE_X[0] <= x <= VILLAGE_X[1] and VILLAGE_Z[0] <= z <= VILLAGE_Z[1]


def village_reserved(x, z):
    """Outdoor furniture coordinates are relative to the island town green.

    The arrival spot and the walk up to the workshop (town hall) door stay clear.
    Returns an error code, or None when the parcel may be used.
    """
    if abs(x) < 2 and abs(z) < 2:
        return 'spawn_area_reserved'
    if -3.5 < x < 3.5 and -12 < z < -6:
        return 'workshop_area_reserved'
    return None

CROPS = {
    'turnip': {'name':'순무','seconds':90,'yield':2,'seed_cost':2,'price':3},
    'carrot': {'name':'당근','seconds':120,'yield':2,'seed_cost':3,'price':4},
    'pumpkin': {'name':'호박','seconds':150,'yield':2,'seed_cost':4,'price':6},
    'strawberry': {'name':'딸기','seconds':200,'yield':3,'seed_cost':5,'price':4},
    'sunflower': {'name':'해바라기','seconds':260,'yield':1,'seed_cost':6,'price':15},
}
# Fish by water and time of day (KST). weight is the relative chance, size in cm.
# Order matters only for tests that pin the random roll; perch stays the last pond fish.
FISH = {
    'crucian': {'name':'붕어','spots':['pond','river'],'time':'any','rarity':1,'weight':30,'size':[12,26],'price':3,'difficulty':1},
    'carp': {'name':'잉어','spots':['pond'],'time':'any','rarity':2,'weight':14,'size':[35,72],'price':9,'difficulty':3},
    'catfish': {'name':'메기','spots':['pond','river'],'time':'night','rarity':2,'weight':16,'size':[40,95],'price':12,'difficulty':3},
    'koi': {'name':'황금 비단잉어','spots':['pond'],'time':'day','rarity':3,'weight':3,'size':[40,70],'price':40,'difficulty':4},
    'mackerel': {'name':'고등어','spots':['sea'],'time':'any','rarity':1,'weight':34,'size':[22,40],'price':5,'difficulty':2},
    'puffer': {'name':'복어','spots':['sea'],'time':'any','rarity':2,'weight':12,'size':[15,32],'price':12,'difficulty':2},
    'squid': {'name':'달빛 오징어','spots':['sea'],'time':'night','rarity':2,'weight':16,'size':[20,45],'price':11,'difficulty':3},
    'tuna': {'name':'참다랑어','spots':['sea'],'time':'any','rarity':3,'weight':3,'size':[90,190],'price':45,'difficulty':5},
    'silverfish': {'name':'은빛 도미','spots':['sea'],'time':'any','rarity':1,'weight':30,'size':[25,52],'price':8,'difficulty':2},
    'sweetfish': {'name':'은어','spots':['river'],'time':'day','rarity':1,'weight':26,'size':[15,26],'price':7,'difficulty':1},
    'rainbow': {'name':'무지개송어','spots':['river'],'time':'any','rarity':2,'weight':12,'size':[35,62],'price':14,'difficulty':3},
    'eel': {'name':'뱀장어','spots':['river','pond'],'time':'night','rarity':3,'weight':5,'size':[50,110],'price':24,'difficulty':4},
    'trout': {'name':'산천어','spots':['river'],'time':'any','rarity':1,'weight':36,'size':[20,40],'price':6,'difficulty':2},
    'perch': {'name':'강농어','spots':['pond'],'time':'any','rarity':1,'weight':36,'size':[18,36],'price':4,'difficulty':1},
}
SPOTS = ('pond','sea','river')
# Seconds the reel fight must last at least, by difficulty (the client bar cannot fill faster).
FIGHT_MIN = {1:2.0,2:2.2,3:2.6,4:3.0,5:3.4}
FIGHT_MAX = 45
BITE_WINDOW = 2.0
KST = 9
# The player's time zone in minutes from UTC (their PC's), set per request by app.py from the
# X-Villagen-UTC-Offset header; released clients that do not send it keep Korea's +9 h.
UTC_OFFSET = contextvars.ContextVar('utc_offset', default=KST * 60)


def offset_from(value):
    try:
        minutes = int(str(value).strip())
    except (TypeError, ValueError):
        return KST * 60
    return minutes if -720 <= minutes <= 840 else KST * 60


def local_day(now):
    """The player's calendar day (daily orders reset at their midnight)."""
    return int((now + UTC_OFFSET.get() * 60) // 86400)

# Gather node kinds: [item, chance in %, min, max] rolls, then respawn seconds.
FORAGE = {
    'rock': {'drops':[['stone',100,1,2],['copper_ore',18,1,1]],'respawn':420},
    'shell': {'drops':[['shell',82,1,1],['conch',15,1,1],['pearl',3,1,1]],'respawn':300,'exclusive':True},
    'flower': {'drops':[['flower',100,1,2]],'respawn':300},
    'mushroom': {'drops':[['mushroom',100,1,2],['gold_mushroom',8,1,1]],'respawn':480},
    'herb': {'drops':[['herb',100,2,2]],'respawn':300},
    'branch': {'drops':[['branch',100,1,3]],'respawn':240},
}
# Node id -> kind. Positions live in game/scripts/forage.gd (same ids, checked by tests).
NODES = {
    **{f'rock_{i:02d}':'rock' for i in range(1,13)},
    **{f'shell_{i:02d}':'shell' for i in range(1,13)},
    **{f'flower_{i:02d}':'flower' for i in range(1,13)},
    **{f'mushroom_{i:02d}':'mushroom' for i in range(1,9)},
    **{f'herb_{i:02d}':'herb' for i in range(1,9)},
    **{f'branch_{i:02d}':'branch' for i in range(1,11)},
}
GATHER_GAP = 0.6

# Field trees. Ids are '<kind>_tree_NN', numbered in the order the map lists each kind
# (game/maps/archipelago/environment_layout.json, checked by tests). A shake drops the
# tree's hanging fruit plus a rolled bonus onto the ground; drops wait there (server
# side) until picked up one by one or until they spoil. The tree regrows on its own timer.
# 'hang' is the fruit range; a tree's own count is fixed by its number (tree_fruit()),
# so the client can draw exactly the fruit that will fall.
TREES = {
    'apple': {'prop':'37_round_tree','count':38,'fruit':'apple','hang':(2,3),'bonus':[['branch',25,1,1]],'respawn':600},
    'pine': {'prop':'38_conifer','count':13,'fruit':'pinecone','hang':(2,3),'bonus':[['branch',45,1,1]],'respawn':540},
    'palm': {'prop':'39_palm','count':4,'fruit':'coconut','hang':(1,2),'bonus':[],'respawn':900},
}
TREE_NODES = {f'{kind}_tree_{i:02d}':kind for kind,rule in TREES.items() for i in range(1,rule['count']+1)}
DROP_TTL = 900
MAX_DROPS = 4

PRICES = {'turnip':3,'carrot':4,'pumpkin':6,'strawberry':4,'sunflower':15,'apple':2,'herb':1,
          'stone':1,'copper_ore':6,'shell':2,'conch':7,'pearl':30,'flower':2,'mushroom':3,'gold_mushroom':16,'branch':1,
          'pinecone':2,'coconut':5}
PRICES.update({fish:data['price'] for fish,data in FISH.items()})
SEED_COSTS = {crop+'_seed':data['seed_cost'] for crop,data in CROPS.items()}
SHOP = {**SEED_COSTS,'bait':1}
NAMES = {'apple':'사과','herb':'향초','bait':'미끼','stone':'돌멩이','copper_ore':'구리 원석','shell':'가리비 껍데기',
         'conch':'소라 껍데기','pearl':'진주','flower':'들꽃','mushroom':'숲 버섯','gold_mushroom':'금빛 송이','branch':'나뭇가지',
         'pinecone':'솔방울','coconut':'코코넛'}
NAMES.update({crop:data['name'] for crop,data in CROPS.items()})
NAMES.update({crop+'_seed':data['name']+' 씨앗' for crop,data in CROPS.items()})
NAMES.update({fish:data['name'] for fish,data in FISH.items()})

# Farm meadow below the windmill (map metres), east of the conifer that would hide it. Tilled plots snap to a 1.8 m grid
# centred on the scarecrow, which keeps its own cell.
FARM_ZONES = [(-24.5,-40.5,-15.5,-29.0)]
GRID = 1.8
GRID_ORIGIN = (-22.0,-33.0)
STARTER_PLOTS = [(-20.2,-33.0),(-18.4,-33.0),(-16.6,-33.0),(-20.2,-34.8),(-18.4,-34.8),(-16.6,-34.8)]
MAX_PLOTS = 18

class Rejected(ValueError): pass

def initial():
    return normalise({'version':0,'coins':12,'bag':{'turnip_seed':3,'pumpkin_seed':1,'carrot_seed':2,'bait':5},
            'plots':[{} for _ in range(6)],'fishing':None,'cooldowns':{},
            'harvested':0,'caught':0,'collection':{},'order_day':-1})

def normalise(state):
    """Older saves had six position-less plots; give them the starter beds and new fields."""
    for index,plot in enumerate(state['plots']):
        if 'x' not in plot:
            plot['x'],plot['z']=STARTER_PLOTS[index] if index<len(STARTER_PLOTS) else STARTER_PLOTS[0]
    for key,value in (('records',{}),('nodes',{}),('drops',{}),('gathered',0),('last_gather',0)):
        state.setdefault(key,value)
    return state

def planted(plot): return bool(plot.get('crop'))

def public(state, now):
    result=copy.deepcopy(normalise(state))
    result['server_time']=now
    for plot in result['plots']:
        if planted(plot):
            plot['remaining']=max(0,plot['ready_at']-now) if plot.get('watered') else None
            plot['ready']=bool(plot.get('watered') and now>=plot['ready_at'])
    fish=result.get('fishing')
    if fish:
        for secret in ('catch','size'): fish.pop(secret,None)
        if fish.get('hooked_at') is not None: fish['phase']='hooked'
        else: fish['phase']='waiting' if now<fish['bite_at'] else ('bite' if now<=fish['ends_at'] else 'escaped')
    result['nodes']={node:at for node,at in result['nodes'].items() if at>now}
    result['drops']={node:drop for node,drop in result['drops'].items() if drop['until']>now and drop['items']}
    result['catalog']={'crops':CROPS,'prices':PRICES,'names':NAMES,'fish':FISH,'shop':SHOP,'max_plots':MAX_PLOTS,
                       'starter_plots':len(STARTER_PLOTS),
                       'trees':{kind:{'fruit':rule['fruit'],'hang':list(rule['hang']),'respawn':rule['respawn']} for kind,rule in TREES.items()}}
    result['order_available']=state['order_day']!=local_day(now)
    result['night']=night(now)
    return result

def night(now):
    hour=(now/3600+UTC_OFFSET.get()/60)%24
    return hour<6 or hour>=19

def spend(state, item, count=1):
    if state['bag'].get(item,0)<count: raise Rejected('life_missing_items')
    state['bag'][item]-=count

def add(state, item, count):
    state['bag'][item]=state['bag'].get(item,0)+count

def roll(chance): return secrets.randbelow(100)<chance

def amount(low, high): return low+secrets.randbelow(high-low+1)

def on_grid(value, origin):
    steps=(value-origin)/GRID
    return abs(steps-round(steps))<0.01

def tillable(state, x, z):
    if len(state['plots'])>=MAX_PLOTS: raise Rejected('life_plot_limit')
    if not any(x0<=x<=x1 and z0<=z<=z1 for x0,z0,x1,z1 in FARM_ZONES): raise Rejected('life_not_farmland')
    if not (on_grid(x,GRID_ORIGIN[0]) and on_grid(z,GRID_ORIGIN[1])): raise Rejected('life_not_farmland')
    if abs(x-GRID_ORIGIN[0])<1 and abs(z-GRID_ORIGIN[1])<1: raise Rejected('life_not_farmland')
    for plot in state['plots']:
        if max(abs(plot['x']-x),abs(plot['z']-z))<1.7: raise Rejected('life_plot_overlap')

def pick_fish(spot, now):
    time='night' if night(now) else 'day'
    pool=[(fish,data) for fish,data in FISH.items() if spot in data['spots'] and data['time'] in ('any',time)]
    ticket=secrets.randbelow(sum(data['weight'] for _,data in pool))
    for fish,data in pool:
        ticket-=data['weight']
        if ticket<0: break
    low,high=data['size']
    # Two rolls lean sizes toward the middle; trophies stay rare.
    size=low+(high-low)*(secrets.randbelow(1001)+secrets.randbelow(1001))/2000
    return fish,round(size,1)

def plot_action(state, body, now):
    if body.plot>=len(state['plots']): raise Rejected('life_no_plot')
    plot=state['plots'][body.plot]
    if body.action=='plant':
        if body.item not in CROPS: raise Rejected('life_invalid_crop')
        if planted(plot): raise Rejected('life_plot_occupied')
        spend(state,body.item+'_seed')
        plot.update(crop=body.item,planted_at=now,watered=False,ready_at=None)
        return CROPS[body.item]['name']+' 씨앗을 심었어요. 물을 주세요.',None
    if body.action=='water':
        if not planted(plot): raise Rejected('life_empty_plot')
        if plot['watered']: raise Rejected('life_already_watered')
        plot.update(watered=True,watered_at=now,ready_at=now+CROPS[plot['crop']]['seconds'])
        return '물을 주었어요. 마을을 떠나도 계속 자랍니다.',None
    if body.action=='untill':
        if body.plot<len(STARTER_PLOTS): raise Rejected('life_starter_plot')
        if planted(plot): raise Rejected('life_plot_occupied')
        state['plots'].pop(body.plot)
        return '밭을 다시 풀밭으로 덮었어요.',None
    if not planted(plot) or not plot['watered'] or now<plot['ready_at']: raise Rejected('life_not_ready')
    crop=plot['crop']; count=CROPS[crop]['yield']
    add(state,crop,count); state['harvested']+=count
    state['plots'][body.plot]={'x':plot['x'],'z':plot['z']}
    return f'{CROPS[crop]["name"]} {count}개를 수확했어요!',{'kind':'crop','plot':body.plot,'items':{crop:count}}

def reel(state, body, now):
    fish=state['fishing']
    if not fish: raise Rejected('life_not_fishing')
    if fish.get('hooked_at') is None:
        # First pull sets the hook: too early spooks the fish, too late it is gone.
        if now<fish['bite_at']:
            state['fishing']=None
            return '너무 빨리 당겼어요. 다음 입질을 기다려 보세요.',{'kind':'miss','why':'early'}
        if now>fish['ends_at']:
            state['fishing']=None
            return '물고기가 달아났어요. 다시 도전해 보세요.',{'kind':'miss','why':'late'}
        data=FISH[fish['catch']]; low,high=data['size']
        fish.update(hooked_at=now,difficulty=data['difficulty'],fight_min=FIGHT_MIN[data['difficulty']],
                    shadow='large' if fish['size']>=low+(high-low)*0.6 else 'small')
        return '걸렸다! 줄을 감아 끌어올리세요.',{'kind':'hooked'}
    if body.outcome!='landed' or now>fish['hooked_at']+FIGHT_MAX:
        state['fishing']=None
        return '물고기가 줄을 끊고 달아났어요.',{'kind':'miss','why':'lost'}
    if now<fish['hooked_at']+fish['fight_min']: raise Rejected('life_reel_too_fast')
    item=fish['catch']; size=fish['size']
    state['fishing']=None
    add(state,item,1); state['caught']+=1
    first=state['collection'].get(item,0)==0
    state['collection'][item]=state['collection'].get(item,0)+1
    record=size>state['records'].get(item,0)
    if record: state['records'][item]=size
    return NAMES[item]+' 한 마리를 낚았어요!',{'kind':'fish','item':item,'size':size,'first':first,'record':record,
                                         'spot':fish['spot'],'items':{item:1}}

def gather(state, body, now):
    if body.node:
        kind=NODES.get(body.node)
        if not kind: raise Rejected('life_invalid_item')
        if now<state['nodes'].get(body.node,0): raise Rejected('life_regrowing')
        if now<state['last_gather']+GATHER_GAP: raise Rejected('life_too_fast')
        rules=FORAGE[kind]; items={}
        for item,chance,low,high in rules['drops']:
            if roll(chance):
                items[item]=items.get(item,0)+amount(low,high)
                if rules.get('exclusive'): break
        if not items: items={rules['drops'][0][0]:1}
        for item,count in items.items(): add(state,item,count)
        state['nodes'][body.node]=now+rules['respawn']
        state['nodes']={node:at for node,at in state['nodes'].items() if at>now}
        state['last_gather']=now; state['gathered']+=1
        text=', '.join(f'{NAMES[item]} {count}개' for item,count in items.items())
        return text+'를 얻었어요.',{'kind':'gather','node':body.node,'items':items}
    if body.item not in ('apple','herb'): raise Rejected('life_invalid_item')
    if now<state['cooldowns'].get(body.item,0): raise Rejected('life_regrowing')
    add(state,body.item,2)
    state['cooldowns'][body.item]=now+(60 if body.item=='apple' else 45)
    return NAMES[body.item]+' 2개를 모았어요.',{'kind':'gather','items':{body.item:2}}

def tree_fruit(node):
    """(kind, fruit item, hanging count) of a field tree; the count is fixed per tree."""
    kind=TREE_NODES[node]; rule=TREES[kind]; low,high=rule['hang']
    return kind,rule['fruit'],low+int(node[-2:])%(high-low+1)

def shake(state, body, now):
    """Fruit falls to the ground next to the tree; nothing enters the bag until picked up."""
    if body.node not in TREE_NODES: raise Rejected('life_invalid_item')
    if now<state['nodes'].get(body.node,0): raise Rejected('life_regrowing')
    if now<state['last_gather']+GATHER_GAP: raise Rejected('life_too_fast')
    kind,fruit,count=tree_fruit(body.node)
    items=[fruit]*count
    for item,chance,low,high in TREES[kind]['bonus']:
        if roll(chance): items+=[item]*amount(low,high)
    items=items[:MAX_DROPS]
    state['nodes'][body.node]=now+TREES[kind]['respawn']
    state['nodes']={node:at for node,at in state['nodes'].items() if at>now}
    state['drops']={node:drop for node,drop in state['drops'].items() if drop['until']>now and drop['items']}
    # Fruit still lying under a tree that regrew stays there; the newest drops come last.
    lying=state['drops'].get(body.node,{}).get('items',[])
    state['drops'][body.node]={'items':(lying+items)[-MAX_DROPS*2:],'until':now+DROP_TTL}
    state['last_gather']=now; state['gathered']+=1
    return '나무에서 열매가 떨어졌어요.',{'kind':'shake','node':body.node,'drops':items}

def pickup(state, body, now):
    """One fallen item from a shaken tree into the bag (the drop list bounds the count)."""
    drop=state['drops'].get(body.node)
    if body.node not in TREE_NODES or not drop or drop['until']<=now or not drop['items']: raise Rejected('life_nothing_here')
    item=body.item or drop['items'][0]
    if item not in drop['items']: raise Rejected('life_nothing_here')
    drop['items'].remove(item)
    if not drop['items']: del state['drops'][body.node]
    add(state,item,1)
    return NAMES[item]+' 1개를 주웠어요.',{'kind':'pickup','node':body.node,'items':{item:1},'left':len(drop['items'])}

def act(state, body, now):
    """Caller runs in one DB transaction; failure never persists partial mutations."""
    normalise(state)
    if body.version!=state['version']: raise Rejected('stale_life_version')
    action=body.action
    reward=None
    if action in ('plant','water','harvest','untill'):
        result,reward=plot_action(state,body,now)
    elif action=='till':
        tillable(state,body.x,body.z)
        state['plots'].append({'x':round(body.x,2),'z':round(body.z,2)})
        result='괭이로 땅을 일궜어요. 씨앗을 심을 수 있어요.'
        reward={'kind':'till','plot':len(state['plots'])-1}
    elif action=='cast':
        if body.spot not in SPOTS: raise Rejected('life_invalid_spot')
        current=state['fishing']
        hooked=current and current.get('hooked_at') is not None
        if current and (now<=current['hooked_at']+FIGHT_MAX if hooked else now<=current['ends_at']): raise Rejected('life_already_fishing')
        spend(state,'bait')
        delay=4+secrets.randbelow(60)/10
        catch,size=pick_fish(body.spot,now)
        # Nibbles are cosmetic bobs before the real bite; reeling on one is too early.
        nibbles=sorted(now+1.2+secrets.randbelow(int((delay-1.8)*10))/10 for _ in range(secrets.randbelow(3)))
        state['fishing']={'spot':body.spot,'cast_at':now,'bite_at':now+delay,'ends_at':now+delay+BITE_WINDOW,
                          'catch':catch,'size':size,'nibbles':nibbles,'hooked_at':None}
        result='찌를 던졌어요. 찌가 쑥 잠기면 E로 챔질하세요.'
    elif action=='reel':
        result,reward=reel(state,body,now)
    elif action=='cancel_fishing':
        state['fishing']=None
        result='낚싯대를 거두었어요. 사용한 미끼는 돌아오지 않습니다.'
    elif action=='gather':
        result,reward=gather(state,body,now)
    elif action=='shake':
        result,reward=shake(state,body,now)
    elif action=='pickup':
        result,reward=pickup(state,body,now)
    elif action=='buy':
        if body.item not in SHOP: raise Rejected('life_invalid_item')
        cost=SHOP[body.item]*body.quantity
        if state['coins']<cost: raise Rejected('life_not_enough_coins')
        state['coins']-=cost; add(state,body.item,body.quantity)
        result=f'{NAMES[body.item]} {body.quantity}개를 샀어요.'
    elif action=='sell':
        if body.item not in PRICES: raise Rejected('life_invalid_item')
        spend(state,body.item,body.quantity)
        income=PRICES[body.item]*body.quantity; state['coins']+=income
        result=f'{NAMES[body.item]}을 팔고 잎전 {income}개를 받았어요.'
    elif action=='order':
        day=local_day(now)
        if state['order_day']==day: raise Rejected('life_order_completed')
        spend(state,'turnip',2); spend(state,'perch')
        state['coins']+=20; state['order_day']=day
        result='마을 식탁 배달 완료! 잎전 20개를 받았어요.'
    else: raise Rejected('life_unknown_action')
    state['version']+=1
    response=public(state,now); response['message']=result
    if reward: response['reward']=reward
    return response
