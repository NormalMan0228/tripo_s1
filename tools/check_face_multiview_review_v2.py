import httpx,re,json
u='http://127.0.0.1:8842/character-face-multiview-meshhair-v2/'
with httpx.Client(timeout=25) as c:
 r=c.get(u);r.raise_for_status();paths=set(re.findall(r'(?:src|href)="([^"]+)"',r.text));checks=[(p,c.head(u+p).status_code) for p in paths if not p.startswith(('http','#'))]
 assert all(s==200 for p,s in checks),checks
 s=c.get(u+'workflow-status.json').json();assert s['hair_cards']==False and s['new_total_credits']==125 and s['remaining_credits']==750 and s['face_views']==['front','left','right']
 print(json.dumps({'page_status':r.status_code,'linked_assets':len(checks),'all_assets_200':True,'new_credits':125,'remaining':750}))
