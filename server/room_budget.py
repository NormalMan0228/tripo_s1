"""Room render limits are measured by the server, never supplied by a client."""
import json
from .provider import validate_glb,ProviderError
from .stored_assets import read_glb

LIMITS={'bytes':128*1024*1024,'vertices':1500000,'draw_calls':512,'texture_pixels':64000000}

def measured(conn,assets,asset_id):
    cached=conn.execute('SELECT budget FROM asset_render_budgets WHERE asset_id=?',(asset_id,)).fetchone()
    if cached:return json.loads(cached[0])
    studio=conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?',(asset_id,)).fetchone()
    if studio:parts=json.loads(studio[0])['plan']['parts']
    else:
        row=conn.execute('SELECT relative_path,digest FROM assets WHERE id=?',(asset_id,)).fetchone()
        if not row:raise ProviderError('asset_integrity_failed')
        parts=[{'file':row['relative_path'],'sha256':row['digest']}]
    budget={key:0 for key in LIMITS}
    for part in parts:
        blob=read_glb(assets,part['file'],part['sha256'])
        stats={};validate_glb(blob,allow_textures=True,stats=stats)
        for key in budget:budget[key]+=stats[key]
    conn.execute('INSERT INTO asset_render_budgets VALUES (?,?)',(asset_id,json.dumps(budget)))
    return budget

def usage(conn,assets,owner_id,room,exclude=None,include=None):
    rows=conn.execute("SELECT id,asset_id FROM objects LEFT JOIN furniture_locations ON object_id=objects.id WHERE owner_id=? AND state='placed' AND COALESCE(room,'village')=?",(owner_id,room)).fetchall()
    totals={key:0 for key in LIMITS};count=0
    for row in rows:
        if row['id']==exclude:continue
        count+=1;budget=measured(conn,assets,row['asset_id'])
        for key in totals:totals[key]+=budget[key]
    if include:
        count+=1;budget=measured(conn,assets,include)
        for key in totals:totals[key]+=budget[key]
    return {'count':count,'used':totals,'limits':LIMITS,'percent':round(max((totals[k]/LIMITS[k] for k in LIMITS),default=0)*100,1)}

def check(conn,assets,owner_id,room,object_id,asset_id):
    value=usage(conn,assets,owner_id,room,exclude=object_id,include=asset_id)
    if any(value['used'][key]>limit for key,limit in LIMITS.items()):
        raise ProviderError('room_render_budget_exceeded')
    return value
