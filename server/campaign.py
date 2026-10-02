"""A small authored story path alongside unrestricted repeatable expeditions.
Only authoritative survival state satisfies objectives. No LLM controls rewards.
"""
CHAPTERS=[
    {'id':'first_fire','title':'1장 · 첫 번째 불씨','map_id':'forest','bonus':20,
     'speaker':'나루','intro':'이 섬의 밤은 길어요. 숲에서 도끼를 만들고, 작은 불을 지켜 주세요. 일곱 번의 아침을 맞으면 오래된 채석장의 길을 알려 드릴게요.',
     'ending':'밤을 버틴 불씨가 공방의 등을 밝혔습니다. 나루가 노을 채석장의 지도를 건넵니다.',
     'requirements':[('harvested','자원 채집',20),('axe','도끼 제작',1),('fires','모닥불 피우기',3)]},
    {'id':'quiet_quarry','title':'2장 · 멈춘 돌바퀴','map_id':'quarry','bonus':30,
     'speaker':'테오','intro':'채석장의 돌바퀴가 멈춘 뒤로 섬의 종이 울리지 않아요. 위험한 틈을 돌아 재료를 모으고 창을 준비해 주세요. 일곱 밤의 기록이 있으면 북쪽 길을 찾을 수 있어요.',
     'ending':'모아 온 기록으로 테오가 종탑의 돌바퀴를 고쳤습니다. 서리빛 분지로 향하는 길이 드러났습니다.',
     'requirements':[('harvested','자원 채집',35),('spear','창 제작',1),('fires','모닥불 피우기',5)]},
    {'id':'returning_light','title':'3장 · 돌아오는 빛','map_id':'frost','bonus':45,
     'speaker':'모루','intro':'북쪽에서는 추위가 가장 큰 적이에요. 수프와 모닥불을 준비하고 일곱 밤을 건너세요. 돌아오면 그동안 모은 별씨로 집에 놓을 첫 작품을 만들어 봅시다.',
     'ending':'일곱 번째 아침, 서리 너머에서 마을의 종소리가 들립니다. 이제 당신의 이야기를 담을 물건을 만들 차례입니다.',
     'requirements':[('harvested','자원 채집',40),('soup','수프 제작',2),('fires','모닥불 피우기',7)]},
]
BY_ID={c['id']:c for c in CHAPTERS}

def progress(state):
    chapter=BY_ID.get(state.get('chapter_id',''))
    if not chapter:return None
    goals=[{'label':'일곱 밤 생존','current':min(7,int(state['elapsed']/state['day_seconds'])),'target':7}]
    for key,label,target in chapter['requirements']:
        value=state.get('crafted',{}).get(key,0) if key in ('axe','spear','soup') else state.get(key,0)
        goals.append({'label':label,'current':min(target,value),'target':target})
    return {'id':chapter['id'],'title':chapter['title'],'goals':goals,
            'objectives_met':state['status']=='won' and all(g['current']>=g['target'] for g in goals),
            'ending':chapter['ending'],'bonus':chapter['bonus']}

def completed(conn,user_id):
    return {r[0] for r in conn.execute('SELECT chapter_id FROM campaign_progress WHERE user_id=?',(user_id,))}

def public(conn,user_id):
    done=completed(conn,user_id)
    return [{k:v for k,v in c.items() if k!='requirements'}|{'completed':c['id'] in done,
        'unlocked':i==0 or CHAPTERS[i-1]['id'] in done,
        'objectives':['일곱 밤 생존']+[f'{label} {target}' for _,label,target in c['requirements']]}
        for i,c in enumerate(CHAPTERS)]

def pending_bonus(conn,user_id,state):
    info=progress(state)
    if not info or not info['objectives_met'] or info['id'] in completed(conn,user_id):return 0
    index=next(i for i,c in enumerate(CHAPTERS) if c['id']==info['id'])
    if index and CHAPTERS[index-1]['id'] not in completed(conn,user_id):return 0
    return info['bonus']
