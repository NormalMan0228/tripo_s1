import httpx,re,json
from pathlib import Path
u='http://127.0.0.1:8842/character-integrated-face-haircards/'
with httpx.Client(timeout=20) as c:
 r=c.get(u);r.raise_for_status();paths=set(re.findall(r'(?:src|href)="([^"]+)"',r.text))
 checks=[(p,c.head(u+p).status_code) for p in paths if not p.startswith(('http','#'))]
 assert all(s==200 for p,s in checks),checks
 state=c.get(u+'workflow-status.json').json();assert state['remaining_credits']==875 and state['new_api_credits']==165
 print(json.dumps({'page_status':r.status_code,'linked_assets_checked':len(checks),'all_assets_200':True,'remaining_credits':state['remaining_credits']}))
