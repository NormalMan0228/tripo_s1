"""Account-owned village life. All growth, catches and exchanges use server time/state.

Leaf coins are a closed village economy: never converted to API-credit shards.
Walking is cosmetic/local in the village; action ownership, inventory and timing
are authoritative, but these endpoints do not claim to attest client proximity.
"""
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
    'pumpkin': {'name':'호박','seconds':150,'yield':2,'seed_cost':4,'price':6},
}
PRICES = {'turnip':3,'pumpkin':6,'perch':4,'silverfish':8,'apple':2,'herb':1}
NAMES = {'turnip':'순무','pumpkin':'호박','perch':'강농어','silverfish':'은빛 도미',
         'apple':'사과','herb':'향초','bait':'미끼','turnip_seed':'순무 씨앗','pumpkin_seed':'호박 씨앗'}

class Rejected(ValueError): pass

def initial():
    return {'version':0,'coins':12,'bag':{'turnip_seed':3,'pumpkin_seed':1,'bait':5},
            'plots':[{} for _ in range(6)],'fishing':None,'cooldowns':{},
            'harvested':0,'caught':0,'collection':{},'order_day':-1}

def public(state, now):
    result=copy.deepcopy(state)
    result['server_time']=now
    for plot in result['plots']:
        if plot:
            plot['remaining']=max(0,plot['ready_at']-now) if plot.get('watered') else None
            plot['ready']=bool(plot.get('watered') and now>=plot['ready_at'])
    fish=result.get('fishing')
    if fish:
        fish.pop('catch',None)
        fish['phase']='waiting' if now<fish['bite_at'] else ('bite' if now<=fish['ends_at'] else 'escaped')
    result['catalog']={'crops':CROPS,'prices':PRICES,'names':NAMES}
    result['order_available']=state['order_day']!=int(now//86400)
    return result

def spend(state, item, count=1):
    if state['bag'].get(item,0)<count: raise Rejected('life_missing_items')
    state['bag'][item]-=count

def add(state, item, count):
    state['bag'][item]=state['bag'].get(item,0)+count

def act(state, body, now):
    """Caller runs in one DB transaction; failure never persists partial mutations."""
    if body.version!=state['version']: raise Rejected('stale_life_version')
    action=body.action
    result=''
    if action in ('plant','water','harvest'):
        plot=state['plots'][body.plot]
        if action=='plant':
            if body.item not in CROPS: raise Rejected('life_invalid_crop')
            if plot: raise Rejected('life_plot_occupied')
            spend(state,body.item+'_seed')
            state['plots'][body.plot]={'crop':body.item,'planted_at':now,'watered':False,'ready_at':None}
            result=CROPS[body.item]['name']+' 씨앗을 심었어요. 물을 주세요.'
        elif action=='water':
            if not plot: raise Rejected('life_empty_plot')
            if plot['watered']: raise Rejected('life_already_watered')
            plot.update(watered=True,ready_at=now+CROPS[plot['crop']]['seconds'])
            result='물을 주었어요. 마을을 떠나도 계속 자랍니다.'
        else:
            if not plot or not plot['watered'] or now<plot['ready_at']: raise Rejected('life_not_ready')
            crop=plot['crop']; amount=CROPS[crop]['yield']
            add(state,crop,amount); state['harvested']+=amount
            state['plots'][body.plot]={}
            result=f'{CROPS[crop]["name"]} {amount}개를 수확했어요!'
    elif action=='cast':
        if body.spot not in ('pond','sea'): raise Rejected('life_invalid_spot')
        current=state['fishing']
        if current and now<=current['ends_at']: raise Rejected('life_already_fishing')
        spend(state,'bait')
        delay=5+secrets.randbelow(4)
        catch='silverfish' if secrets.randbelow(100)<(55 if body.spot=='sea' else 15) else 'perch'
        state['fishing']={'spot':body.spot,'bite_at':now+delay,'ends_at':now+delay+3.5,'catch':catch}
        result='찌를 던졌어요. 입질이 오면 E 또는 챔질 버튼을 누르세요.'
    elif action=='reel':
        fish=state['fishing']
        if not fish: raise Rejected('life_not_fishing')
        state['fishing']=None
        if now<fish['bite_at']: result='너무 빨리 당겼어요. 다음 입질을 기다려 보세요.'
        elif now>fish['ends_at']: result='물고기가 달아났어요. 다시 도전해 보세요.'
        else:
            item=fish['catch']; add(state,item,1); state['caught']+=1
            state['collection'][item]=state['collection'].get(item,0)+1
            result=NAMES[item]+' 한 마리를 낚았어요!'
    elif action=='cancel_fishing':
        state['fishing']=None
        result='낚싯대를 거두었어요. 사용한 미끼는 돌아오지 않습니다.'
    elif action=='gather':
        if body.item not in ('apple','herb'): raise Rejected('life_invalid_item')
        if now<state['cooldowns'].get(body.item,0): raise Rejected('life_regrowing')
        add(state,body.item,2)
        state['cooldowns'][body.item]=now+(60 if body.item=='apple' else 45)
        result=NAMES[body.item]+' 2개를 모았어요.'
    elif action=='buy':
        costs={'turnip_seed':2,'pumpkin_seed':4,'bait':1}
        if body.item not in costs: raise Rejected('life_invalid_item')
        cost=costs[body.item]*body.quantity
        if state['coins']<cost: raise Rejected('life_not_enough_coins')
        state['coins']-=cost; add(state,body.item,body.quantity)
        result=f'{NAMES[body.item]} {body.quantity}개를 샀어요.'
    elif action=='sell':
        if body.item not in PRICES: raise Rejected('life_invalid_item')
        spend(state,body.item,body.quantity)
        income=PRICES[body.item]*body.quantity; state['coins']+=income
        result=f'{NAMES[body.item]}을 팔고 잎전 {income}개를 받았어요.'
    elif action=='order':
        day=int(now//86400)
        if state['order_day']==day: raise Rejected('life_order_completed')
        spend(state,'turnip',2); spend(state,'perch')
        state['coins']+=20; state['order_day']=day
        result='마을 식탁 배달 완료! 잎전 20개를 받았어요.'
    else: raise Rejected('life_unknown_action')
    state['version']+=1
    response=public(state,now); response['message']=result
    return response
