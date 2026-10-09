"""Authoritative furniture workshop. No native generated code is executed.

Plan/mesh/code are separate provenance records. Paid submissions are persisted
before HTTP; ambiguous submissions stop for reconciliation instead of resubmitting.
"""
import asyncio
import base64
import hashlib
import io
import json
import math
import uuid
import unicodedata
from typing import Literal
from PIL import Image
from pydantic import Field, field_validator
from fastapi import Request, HTTPException
from fastapi.responses import Response
from .models import Mutation
from .homestead import village_reserved, village_inside
from .asset_assembly import demo_design, fixture_glb, validate_plan, static_plan, simple_plan
from .asset_vm import AssetVM, ProgramError, exercise_extended as exercise
from .design_provider import DesignProvider, DesignFailure, MODELS, EFFORTS, provider_name
from .provider import ProviderError, validate_glb
from .studio_pricing import mesh_credits,estimate
from . import room_budget
from .stored_assets import read_glb
from .object_paint import version_column as paint_version
from . import object_shape
from . import craft_styles

SCHEMA='''
CREATE TABLE IF NOT EXISTS studio_jobs (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), request TEXT NOT NULL,
 state TEXT NOT NULL, cost INTEGER NOT NULL, plan TEXT, program TEXT, provenance TEXT,
 parts TEXT NOT NULL DEFAULT '{}', object_id TEXT, error TEXT, created REAL NOT NULL, updated REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS studio_pending ON studio_jobs(owner_id)
 WHERE state NOT IN ('ready','failed','cancelled');
CREATE TABLE IF NOT EXISTS studio_assets (
 asset_id TEXT PRIMARY KEY REFERENCES assets(id), manifest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS studio_runtime (
 object_id TEXT PRIMARY KEY REFERENCES objects(id), state TEXT NOT NULL,
 colors TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS asset_categories (name TEXT PRIMARY KEY, first_created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS generated_apis (
 asset_id TEXT NOT NULL REFERENCES assets(id), name TEXT NOT NULL, definition TEXT NOT NULL,
 digest TEXT NOT NULL, PRIMARY KEY(asset_id,name));
CREATE TABLE IF NOT EXISTS studio_leases (job_id TEXT PRIMARY KEY, token TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS furniture_locations (
 object_id TEXT PRIMARY KEY REFERENCES objects(id), room TEXT NOT NULL DEFAULT 'village');
'''

class StudioRequest(Mutation):
    prompt: str=Field(min_length=3,max_length=1500)
    material: Literal['mesh','textured']='mesh'
    motion: Literal['static','dynamic']='dynamic'
    designer: Literal['fixture','llm','simple']='fixture'
    geometry: Literal['proxy','tripo']='proxy'
    mesh_model: Literal['configured','v3.1-20260211','P2-20260801']='configured'
    image_mode: Literal['original','refine']='original'
    model: Literal['gpt-6-luna','gpt-5.6-terra','gpt-6-sol','gpt-6-astra']='gpt-6-luna'
    effort: Literal['low','medium','high','xhigh']='high'
    image: str=Field(default='',max_length=1400000)
    # Text-only crafts: draw a concept picture first and let the player approve it (see draw_concept).
    concept: bool=False
    # Named look and size the player picked (server/craft_styles.py).
    style: Literal[craft_styles.STYLE_IDS]=craft_styles.DEFAULT_STYLE
    size: Literal[craft_styles.SIZE_IDS]='auto'

    @field_validator('image')
    @classmethod
    def image_data(cls,v):
        if not v:return v
        if not v.startswith(('data:image/png;base64,','data:image/jpeg;base64,')):raise ValueError('invalid_image')
        try:
            blob=base64.b64decode(v.split(',',1)[1],validate=True)
            if len(blob)>1024*1024:raise ValueError()
            with Image.open(io.BytesIO(blob)) as im:
                if im.format not in ('PNG','JPEG') or max(im.size)>2048 or min(im.size)<16:raise ValueError()
                im.verify()
        except Exception:raise ValueError('invalid_image') from None
        return v

class StudioConfirm(Mutation):
    # With a concept picture: build from it (image-to-3D) or ignore it and build from the text.
    use_concept: bool=True

class StudioEvent(Mutation):
    version: int=Field(ge=1)
    event: Literal['click','near','leave']

class StudioPaint(Mutation):
    version: int=Field(ge=1)
    part: str=Field(default='all',max_length=48)
    color: str=Field(pattern=r'^#[0-9a-fA-F]{6}$')
    reset: bool=False

class InvokeAPI(Mutation):
    version: int=Field(ge=1)
    function: str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_]{0,47}$')
    args: list[float]=Field(default_factory=list,max_length=8)

    @field_validator('args')
    @classmethod
    def numeric_args(cls,value):
        from .asset_vm import number
        return [number(v) for v in value]

class BindingEdit(Mutation):
    version: int=Field(ge=1)
    part: str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_]{0,47}$')
    reset: bool=False
    position: list[float]|None=Field(default=None,min_length=3,max_length=3)
    rotation: list[float]|None=Field(default=None,min_length=3,max_length=3)
    pivot: list[float]|None=Field(default=None,min_length=3,max_length=3)
    size: list[float]|None=Field(default=None,min_length=3,max_length=3)

class Placement(Mutation):
    version: int=Field(ge=1)
    action: Literal['place','retrieve']='place'
    room: Literal['village','home','workshop']='home'
    x: float=Field(default=0,ge=-130,le=130)
    z: float=Field(default=0,ge=-130,le=130)
    # Facing in whole degrees; released clients send quarter turns only.
    rotation: int=Field(default=0,ge=0,le=359)

def price(body):
    # Game economy quote, deliberately NOT advertised as the provider's credit price.
    return (20 if body.material=='mesh' else 40)+(10 if body.motion=='dynamic' else 0)

def fail(code,status=409):raise HTTPException(status,code)

# Concept pictures (text-only crafts): Tripo text-to-image, seedream, 5 credits each; a few redraws.
CONCEPT_CREDITS=5
MAX_CONCEPT_DRAWS=4

def image_url(output):
    """The picture URL in a Tripo image task's output (field names vary by model)."""
    for key in ('generated_image','image','image_url','url'):
        value=output.get(key)
        if isinstance(value,str) and value.startswith('https://'):return value
    for value in output.values():
        if isinstance(value,str) and value.startswith('https://'):return value
        if isinstance(value,list):
            for item in value:
                if isinstance(item,str) and item.startswith('https://'):return item
    raise ProviderError('upstream_schema')

def fixture_concept(prompt):
    """A drawn placeholder concept for proxy (development/test) crafts: no provider call."""
    import hashlib as _hash,io
    from PIL import Image,ImageDraw
    tint=_hash.sha256(prompt.encode()).digest()
    image=Image.new('RGB',(512,512),(244,236,220));draw=ImageDraw.Draw(image)
    draw.ellipse((96,96,416,416),fill=(80+tint[0]%150,80+tint[1]%150,80+tint[2]%150),outline=(90,70,50),width=8)
    out=io.BytesIO();image.save(out,'JPEG',quality=85);return out.getvalue()

# Player-facing wording of user_total_generation_limit for the room studio (see queue()).
TRIAL_USED_UP='체험판 제작 %d회를 모두 썼어요. 만든 물건으로 마을을 꾸며 보세요!'
# Room placement refusal; released room clients print the detail after their own prefix.
PLACED_ELSEWHERE='다른 곳에 놓여 있는 가구예요. 그곳에서 먼저 회수한 뒤 놓아 주세요.'

def billing(parts):
    reported=[];missing=False
    for part in parts.values():
        for task,key in (('task','credits_consumed'),('image_task','image_credits_consumed'),('concept_task','concept_credits_consumed')):
            if not part.get(task):continue
            value=part.get(key)
            if type(value) in (int,float) and math.isfinite(value) and 0<=value<=1000000:reported.append(value)
            else:missing=True
    return {'known_tripo_credits':sum(reported),'tripo_credits_consumed':None if missing else sum(reported),'billing_complete':not missing}

# A quote awaiting the owner's confirmation has not reached Tripo, so it must
# not block other players. The single-provider limit is enforced again at confirm.
def tripo_credits_committed(conn,exclude=''):
    """Tripo credits this server has spent or committed: the reported bill of finished jobs, and for
    builds still running (or with an incomplete bill) at least their confirmed quote.
    The server-wide budget (TRIPOTHON_TRIPO_CREDIT_BUDGET) is checked against this."""
    total=0.0
    for row in conn.execute("SELECT state,parts,provenance FROM studio_jobs WHERE id!=? AND state IN ('queued','planning','awaiting_confirmation','building','submitting','unknown','ready','failed','cancelled')",(exclude,)):
        try:parts,quote=json.loads(row['parts'] or '{}'),float(json.loads(row['provenance'] or '{}').get('estimated_tripo_credits') or 0)
        except (TypeError,ValueError):parts,quote={},0.0
        bill=billing(parts)
        if row['state'] in ('queued','planning','awaiting_confirmation'):total+=bill['known_tripo_credits']
        elif row['state'] in ('building','submitting','unknown') or not bill['billing_complete']:total+=max(bill['known_tripo_credits'],quote)
        else:total+=bill['known_tripo_credits']
    return total

def tripo_requests(conn,user_id,exclude=''):
    """Tripo submissions an account has made: every part sent to Tripo (mesh or image task),
    failed and cancelled jobs included, and at least one for a job confirmed into the build.
    The per-account trial cap (TRIPO_USER_TOTAL_REQUEST_LIMIT) is checked against this."""
    total=0
    for row in conn.execute('SELECT state,request,parts FROM studio_jobs WHERE owner_id=? AND id!=?',(user_id,exclude)):
        try:
            if json.loads(row['request']).get('geometry')!='tripo':continue
            parts=json.loads(row['parts'] or '{}')
        except (TypeError,ValueError):parts={}
        sent=sum(1 for p in parts.values() if isinstance(p,dict) for k in ('task','image_task') if p.get(k))
        if row['state'] in ('building','submitting','unknown','ready'):sent=max(sent,1)
        total+=sent
    return total


def provider_busy(conn,exclude=''):
    return conn.execute("SELECT 1 FROM studio_jobs WHERE state NOT IN ('ready','failed','cancelled','awaiting_confirmation') AND id!=?",(exclude,)).fetchone() or         conn.execute("SELECT 1 FROM jobs WHERE state IN ('queued','submitting','generating','unknown')").fetchone()

class Studio:
    def __init__(self,app,db,settings,clock,provider,auth,mutate,money,own,new_object,assets,designer=None,profile=None):
        self.db,self.settings,self.clock,self.provider=db,settings,clock,provider
        self.money,self.new_object,self.assets=money,new_object,assets
        self.designer=designer or DesignProvider(settings)
        self.lock=asyncio.Lock()
        # Seconds between polls of a Tripo task the worker waits on inline (concept pictures).
        self.poll_pause=3.0
        self.claims={}
        with db.transaction() as conn:
            conn.executescript(SCHEMA)
            if 'bindings' not in [r[1] for r in conn.execute('PRAGMA table_info(studio_runtime)')]:
                conn.execute("ALTER TABLE studio_runtime ADD COLUMN bindings TEXT NOT NULL DEFAULT '{}'")
        # executescript commits implicitly; recovery must start a fresh transaction.
        with db.transaction() as conn:
            for row in conn.execute("SELECT id,cost,provenance FROM studio_jobs WHERE state='awaiting_confirmation'").fetchall():
                quote=json.loads(row['provenance'] or '{}')
                if 'quoted_game_cost' not in quote and 'estimated_tripo_credits' in quote:
                    quote.update(quoted_game_cost=max(row['cost'],math.ceil(quote['estimated_tripo_credits']*settings.studio_credit_rate)),stars_per_credit=settings.studio_credit_rate,reserved_game_cost=row['cost'])
                    conn.execute('UPDATE studio_jobs SET provenance=? WHERE id=?',(json.dumps(quote),row['id']))
            for r in conn.execute("SELECT * FROM studio_jobs WHERE state='planning' AND id NOT IN (SELECT job_id FROM studio_leases WHERE expires>?)",(clock(),)).fetchall():
                conn.execute("UPDATE studio_jobs SET state='failed',error='planning_interrupted' WHERE id=?",(r['id'],))
                self.refund(conn,r)
            conn.execute("UPDATE studio_jobs SET state='unknown',error='submission_interrupted' WHERE state='submitting' AND id NOT IN (SELECT job_id FROM studio_leases WHERE expires>?)",(clock(),))

        def manifest(conn,user_id,object_id):
            obj=own(conn,user_id,object_id)
            row=conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?',(obj['asset_id'],)).fetchone()
            if not row:fail('not_studio_object',404)
            state=conn.execute('SELECT * FROM studio_runtime WHERE object_id=?',(object_id,)).fetchone()
            return obj,json.loads(row[0]),state

        @app.get('/v1/studio')
        def info(request:Request):
            with db.transaction() as conn:
                user=auth(conn,request)
                return {'mode':settings.mode,'llm':settings.studio_llm,
                    'models':('gpt-6-luna',) if settings.mode=='live' else MODELS,
                    'efforts':('high',) if settings.mode=='live' else EFFORTS,
                    'profile':profile(conn,user['id']) if profile else {},
                    'room_usage':{room:room_budget.usage(conn,assets,user['id'],room) for room in ('home','workshop','village')},
                    'geometry_enabled':bool(settings.paid_enabled and settings.tripo_key),
                    'max_tripo_credits':settings.max_credits_per_craft if settings.mode=='live' else 0,
                    'tripo_requests_used':tripo_requests(conn,user['id']),
                    'tripo_requests_limit':settings.user_total_generation_limit if settings.mode=='live' else 0,
                    'tripo_budget':settings.tripo_credit_budget,
                    'tripo_budget_used':round(tripo_credits_committed(conn)) if settings.tripo_credit_budget else 0,
                    **craft_styles.public(),
                    'prices':{'static_mesh':20,'static_textured':40,'dynamic_mesh':30,'dynamic_textured':50},
                    'tripo_estimate':{'models':{'v3.1-20260211':{'text_mesh':10,'text_textured':20,'image_mesh':20,'image_textured':30},'P2-20260801':{'text_mesh':100,'text_textured':110,'image_mesh':100,'image_textured':110}},'image_refinement_per_part':5,'source':'official_rates_and_measured_2026_10_02','max_parts':8,'confirmation_required':True},
                    'jobs':[dict(r) for r in conn.execute('SELECT id,state,cost,object_id,error,created FROM studio_jobs WHERE owner_id=? ORDER BY created DESC LIMIT 30',(user['id'],))],
                    'objects':[object_shape.listed(dict(r)) for r in conn.execute("SELECT objects.id,name,color,objects.version,objects.state,x,z,rotation,COALESCE(room,'village') AS room,EXISTS(SELECT 1 FROM studio_assets WHERE studio_assets.asset_id=objects.asset_id) AS studio,(SELECT version FROM studio_runtime WHERE object_id=objects.id) AS runtime_version,"+paint_version('objects.id')+" AS paint_version,"+object_shape.column('objects.id')+" AS shape FROM objects LEFT JOIN furniture_locations ON furniture_locations.object_id=objects.id WHERE owner_id=? ORDER BY created DESC",(user['id'],))],
                    'categories':[r[0] for r in conn.execute('SELECT name FROM asset_categories ORDER BY name LIMIT 100')],
                    'shards':user['shards']}

        @app.post('/v1/studio/jobs')
        def queue(body:StudioRequest,request:Request):
            def create(conn,user):
                if body.designer=='llm' and settings.studio_llm=='fixture':fail('llm_not_configured',503)
                if body.geometry=='tripo' and not (settings.paid_enabled and settings.tripo_key):fail('live_generation_disabled',503)
                if body.designer=='simple' and (body.motion!='static' or body.image):fail('simple_requires_static_text')
                if settings.mode=='live' and (body.designer not in ('llm','simple') or body.geometry!='tripo'):fail('development_mode_forbidden',403)
                if settings.mode=='live' and body.designer=='llm' and (body.model!='gpt-6-luna' or body.effort!='high'):
                    fail('model_not_available',403)
                if body.image and body.designer!='llm':fail('image_requires_llm')
                if body.image_mode=='refine' and (not body.image or body.geometry!='tripo'):fail('refinement_requires_image_and_tripo')
                if conn.execute("SELECT 1 FROM studio_jobs WHERE owner_id=? AND state NOT IN ('ready','failed','cancelled')",(user['id'],)).fetchone():fail('generation_pending')
                if body.geometry=='tripo':
                    if provider_busy(conn):fail('provider_busy')
                    cap=settings.max_credits_per_craft if settings.mode=='live' else 0
                    if cap:
                        try:
                            # Moving furniture keeps separate parts: count at least two.
                            least=estimate(settings.tripo_model if body.mesh_model=='configured' else body.mesh_model,body.material=='textured',2 if body.motion=='dynamic' else 1,bool(body.image),body.image_mode=='refine')
                        except ProviderError:least=cap+1
                        if least>cap:fail('craft_over_trial_limit',403)
                    if settings.tripo_credit_budget:
                        try:need=estimate(settings.tripo_model if body.mesh_model=='configured' else body.mesh_model,body.material=='textured',2 if body.motion=='dynamic' else 1,bool(body.image),body.image_mode=='refine')
                        except ProviderError:need=0
                        if body.concept and not body.image:need+=CONCEPT_CREDITS
                        if tripo_credits_committed(conn)+need>settings.tripo_credit_budget:fail('tripo_budget_exhausted',429)
                count=conn.execute('SELECT count(*) FROM studio_jobs WHERE created>=?',(int(clock()//86400)*86400,)).fetchone()[0]
                if count>=settings.daily_generation_limit:fail('daily_generation_limit',429)
                if settings.mode=='live':
                    user_count=conn.execute('SELECT count(*) FROM studio_jobs WHERE owner_id=? AND created>=?',
                                            (user['id'],int(clock()//86400)*86400)).fetchone()[0]
                    if user_count>=settings.user_daily_generation_limit:fail('user_daily_generation_limit',429)
                    limit=settings.user_total_generation_limit
                    # Failed jobs may already have used Tripo: the cap also counts every Tripo request.
                    if limit and (conn.execute("SELECT count(*) FROM studio_jobs WHERE owner_id=? AND state!='failed'",(user['id'],)).fetchone()[0]>=limit
                                  or (body.geometry=='tripo' and tripo_requests(conn,user['id'])>=limit)):
                        # The village craft window (main.gd) words the code itself. The room studio of
                        # released clients (<= 0.10.2) prints the detail after its own prefix, so it gets
                        # the sentence; it is the only caller that sends image_mode.
                        fail(TRIAL_USED_UP % limit if 'image_mode' in body.model_fields_set else 'user_total_generation_limit',429)
                job_id=str(uuid.uuid4());cost=price(body)
                money(conn,user['id'],-cost,'studio_charge',job_id)
                conn.execute('INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated) VALUES (?,?,?,?,?,?,?)',
                    (job_id,user['id'],body.model_dump_json(),'queued',cost,clock(),clock()))
                return {'id':job_id,'state':'queued','cost':cost}
            return mutate(request,body,'studio_generate',create)

        @app.get('/v1/studio/jobs/{job_id}')
        def status(job_id:str,request:Request):
            with db.transaction() as conn:
                user=auth(conn,request)
                row=conn.execute('SELECT id,state,cost,object_id,error,provenance,parts,plan FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                value=dict(row);value['provenance']=json.loads(value['provenance'] or '{}')
                # What the designer made of the request: the title and the sentence each part sends to Tripo.
                plan=json.loads(value.pop('plan') or '{}')
                if plan.get('parts'):
                    value['design']={'title':str(plan.get('title',''))[:120],
                        'parts':[{'id':str(p.get('id',''))[:40],'prompt':str(p.get('prompt',''))[:600]} for p in plan['parts'][:8]]}
                parts=json.loads(value['parts'])
                if value['provenance'].get('geometry')=='tripo':
                    value['provenance'].update(billing(parts))
                    if value['state'] in ('submitting','unknown'):value['provenance'].update(billing_complete=False,tripo_credits_consumed=None)
                value['parts']={k:v['state'] for k,v in parts.items()}
                concept=value['provenance'].get('concept')
                if concept:
                    value['concept']={'url':'/v1/studio/jobs/'+job_id+'/concept?v='+str(concept.get('draws',1)),'draws':concept.get('draws',1),
                        'max_draws':MAX_CONCEPT_DRAWS,'redraw_credits':CONCEPT_CREDITS,'used':value['provenance'].get('concept_used'),
                        'estimate_with_concept':value['provenance'].get('estimated_tripo_credits'),'estimate_text_only':value['provenance'].get('estimate_text_only')}
                return value

        @app.post('/v1/studio/jobs/{job_id}/cancel')
        def cancel(job_id:str,body:Mutation,request:Request):
            def edit(conn,user):
                row=conn.execute('SELECT * FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                if row['state'] not in ('queued','awaiting_confirmation'):fail('cannot_cancel_inflight_job')
                conn.execute("UPDATE studio_jobs SET state='cancelled' WHERE id=?",(job_id,))
                self.refund(conn,row)
                return {'state':'cancelled'}
            return mutate(request,body,'studio_cancel:'+job_id,edit)

        @app.get('/v1/studio/jobs/{job_id}/preview')
        def preview(job_id:str,request:Request):
            # A private, read-only rehearsal of the validated plan. No provider call,
            # asset publication, currency change, or persisted runtime mutation.
            with db.transaction() as conn:
                user=auth(conn,request)
                row=conn.execute('SELECT plan,program FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                if not row['plan'] or not row['program']:fail('design_not_ready')
                plan=validate_plan(json.loads(row['plan']))
                program=json.loads(row['program'])
                exercise(program,[p['id'] for p in plan['parts']])
                blobs={p['id']:base64.b64encode(fixture_glb(p['shape'],False)).decode() for p in plan['parts']}
                return {'schema':1,'preview_only':True,'plan':plan,'program':program,
                    'provenance':{'geometry':'procedural_proxy'},'runtime':{},'blobs':blobs}

        @app.post('/v1/studio/jobs/{job_id}/confirm')
        def confirm(job_id:str,body:StudioConfirm,request:Request):
            def edit(conn,user):
                row=conn.execute('SELECT * FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                if row['state']!='awaiting_confirmation':fail('not_awaiting_confirmation')
                # Proxy builds (development) can wait on a concept picture too; they never reach Tripo.
                tripo_job=json.loads(row['request']).get('geometry')=='tripo'
                if tripo_job and not (settings.paid_enabled and settings.tripo_key):fail('live_generation_disabled',503)
                if tripo_job and provider_busy(conn,job_id):fail('provider_busy')
                if settings.mode=='live' and settings.user_total_generation_limit and tripo_requests(conn,user['id'],job_id)>=settings.user_total_generation_limit:
                    fail('user_total_generation_limit',429)
                quote=json.loads(row['provenance']);parts=json.loads(row['parts'] or '{}')
                if quote.get('concept'):
                    for entry in parts.values():entry['use_concept']=body.use_concept
                    quote['concept_used']=body.use_concept
                    if not body.use_concept and quote.get('estimate_text_only') is not None:
                        quote['estimated_tripo_credits']=quote['estimate_text_only']
                        quote['quoted_game_cost']=max(row['cost'],math.ceil(float(quote['estimated_tripo_credits'])*settings.studio_credit_rate))
                if settings.tripo_credit_budget and tripo_credits_committed(conn,job_id)+float(quote.get('estimated_tripo_credits') or 0)>settings.tripo_credit_budget:
                    fail('tripo_budget_exhausted',429)
                total=max(row['cost'],int(quote.get('quoted_game_cost',row['cost'])))
                if total>row['cost']:money(conn,user['id'],row['cost']-total,'studio_quote_charge',job_id)
                conn.execute("UPDATE studio_jobs SET state='building',cost=?,provenance=?,parts=?,updated=? WHERE id=?",(total,json.dumps(quote),json.dumps(parts),clock(),job_id))
                return {'id':job_id,'state':'building','estimate':quote.get('estimated_tripo_credits'),'cost':total}
            return mutate(request,body,'studio_confirm:'+job_id,edit)

        @app.get('/v1/studio/jobs/{job_id}/concept')
        def concept_image(job_id:str,request:Request):
            with db.transaction() as conn:
                user=auth(conn,request)
                row=conn.execute('SELECT provenance FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                concept=json.loads(row['provenance'] or '{}').get('concept') or {}
                path=self.assets/str(concept.get('file',''))
                if not concept.get('file') or not path.is_file():fail('concept_not_found',404)
                return Response(path.read_bytes(),media_type='image/jpeg',headers={'Cache-Control':'no-store'})

        @app.post('/v1/studio/jobs/{job_id}/redraw')
        def redraw(job_id:str,body:Mutation,request:Request):
            def edit(conn,user):
                row=conn.execute('SELECT * FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                quote=json.loads(row['provenance'] or '{}')
                if row['state']!='awaiting_confirmation' or not quote.get('concept'):fail('cannot_redraw')
                if int(quote['concept'].get('draws',1))>=MAX_CONCEPT_DRAWS:fail('concept_redraw_limit',429)
                asked=json.loads(row['request'])
                if asked.get('geometry')=='tripo':
                    parts=json.loads(row['parts'] or '{}')
                    spent=sum(float(p.get('concept_credits_consumed') or 0) for p in parts.values())
                    model=settings.tripo_model if asked.get('mesh_model','configured')=='configured' else asked['mesh_model']
                    cap=settings.max_credits_per_craft if settings.mode=='live' else 0
                    if cap and spent+CONCEPT_CREDITS+mesh_credits(model,asked.get('material')=='textured',True)>cap:fail('craft_over_trial_limit',403)
                    if settings.tripo_credit_budget and tripo_credits_committed(conn,job_id)+spent+CONCEPT_CREDITS>settings.tripo_credit_budget:fail('tripo_budget_exhausted',429)
                    if provider_busy(conn,job_id):fail('provider_busy')
                quote['redraw']=True
                conn.execute("UPDATE studio_jobs SET state='queued',provenance=?,updated=? WHERE id=?",(json.dumps(quote),clock(),job_id))
                return {'id':job_id,'state':'queued'}
            return mutate(request,body,'studio_redraw:'+job_id,edit)

        @app.get('/v1/objects/{object_id}/assembly')
        def assembly(object_id:str,request:Request):
            with db.transaction() as conn:
                user=auth(conn,request);obj,value,state=manifest(conn,user['id'],object_id)
                bindings=json.loads(state['bindings'])
                original=json.loads(json.dumps(value['plan']))
                for p in value['plan']['parts']:p.update(bindings.get(p['id'],{}))
                return {**value,'original_plan':original,'runtime':{'state':json.loads(state['state']),'colors':json.loads(state['colors']),'bindings':bindings,'version':state['version']},'object_version':obj['version']}

        @app.post('/v1/objects/{object_id}/bindings')
        def bindings(object_id:str,body:BindingEdit,request:Request):
            def edit(conn,user):
                obj,value,state=manifest(conn,user['id'],object_id)
                if obj['state']=='listed':fail('object_is_listed')
                if body.version!=state['version']:fail('stale_runtime_version')
                if body.part not in [p['id'] for p in value['plan']['parts']]:fail('part_not_found',404)
                edits=json.loads(state['bindings'])
                if body.reset:edits.pop(body.part,None)
                else:
                    patch={k:v for k,v in body.model_dump().items() if k in ('position','rotation','pivot','size') and v is not None}
                    if not patch:fail('empty_binding_edit')
                    edits.setdefault(body.part,{}).update(patch)
                for part in value['plan']['parts']:part.update(edits.get(part['id'],{}))
                # Strip immutable storage metadata before the strict shape validator.
                clean={**value['plan'],'parts':[{k:v for k,v in p.items() if k not in ('file','sha256')} for p in value['plan']['parts']]}
                try:validate_plan(clean)
                except Exception:fail('binding_out_of_bounds',422)
                conn.execute('UPDATE studio_runtime SET bindings=?,version=version+1 WHERE object_id=?',(json.dumps(edits),object_id))
                return {'bindings':edits,'version':state['version']+1}
            return mutate(request,body,'studio_binding:'+object_id,edit)

        @app.get('/v1/objects/{object_id}/parts/{part_id}')
        def part(object_id:str,part_id:str,request:Request):
            with db.transaction() as conn:
                user=auth(conn,request);_,value,_=manifest(conn,user['id'],object_id)
                p=next((p for p in value['plan']['parts'] if p['id']==part_id),None)
                if not p:fail('part_not_found',404)
                blob=read_glb(assets,p['file'],p['sha256'])
                return Response(blob,media_type='model/gltf-binary',headers={'Cache-Control':'no-store'})

        @app.post('/v1/objects/{object_id}/event')
        def event(object_id:str,body:StudioEvent,request:Request):
            def edit(conn,user):
                obj,value,state=manifest(conn,user['id'],object_id)
                if obj['state']=='listed':fail('object_is_listed')
                if body.version!=state['version']:fail('stale_runtime_version')
                vm=AssetVM(value['program'],[p['id'] for p in value['plan']['parts']],json.loads(state['state']))
                try:commands=vm.run(body.event,{'near':int(body.event=='near')})
                except ProgramError:fail('behavior_rejected')
                conn.execute('UPDATE studio_runtime SET state=?,version=version+1 WHERE object_id=?',(json.dumps(vm.state),object_id))
                before=json.loads(state['state'])
                return {'state':vm.state,'patch':{k:v for k,v in vm.state.items() if before[k]!=v},'commands':commands,'version':state['version']+1}
            return mutate(request,body,'studio_event:'+object_id,edit)

        @app.post('/v1/objects/{object_id}/colors')
        def paint(object_id:str,body:StudioPaint,request:Request):
            def edit(conn,user):
                obj,value,state=manifest(conn,user['id'],object_id)
                if obj['state']=='listed':fail('object_is_listed')
                if body.version!=state['version']:fail('stale_runtime_version')
                ids=[p['id'] for p in value['plan']['parts']]
                if body.part!='all' and body.part not in ids:fail('part_not_found',404)
                colors=json.loads(state['colors'])
                for key in ids if body.part=='all' else [body.part]:
                    if body.reset:colors.pop(key,None)
                    else:colors[key]=body.color.lower()
                conn.execute('UPDATE studio_runtime SET colors=?,version=version+1 WHERE object_id=?',(json.dumps(colors),object_id))
                return {'colors':colors,'version':state['version']+1}
            return mutate(request,body,'studio_paint:'+object_id,edit)

        @app.post('/v1/objects/{object_id}/invoke')
        def invoke(object_id:str,body:InvokeAPI,request:Request):
            def edit(conn,user):
                obj,value,state=manifest(conn,user['id'],object_id)
                if obj['state']=='listed':fail('object_is_listed')
                if body.version!=state['version']:fail('stale_runtime_version')
                before=json.loads(state['state'])
                vm=AssetVM(value['program'],[p['id'] for p in value['plan']['parts']],before)
                try:result=vm.invoke(body.function,body.args)
                except ProgramError:fail('api_call_rejected')
                conn.execute('UPDATE studio_runtime SET state=?,version=version+1 WHERE object_id=?',(json.dumps(vm.state),object_id))
                return {'result':result,'state':vm.state,'patch':{k:v for k,v in vm.state.items() if before[k]!=v},'commands':vm.commands,'version':state['version']+1}
            return mutate(request,body,'studio_invoke:'+object_id,edit)

        @app.post('/v1/objects/{object_id}/placement')
        def placement(object_id:str,body:Placement,request:Request):
            def edit(conn,user):
                obj=own(conn,user['id'],object_id,body.version)
                if obj['state']=='listed':fail('object_is_listed')
                if body.action=='retrieve':
                    conn.execute("UPDATE objects SET state='inventory',x=NULL,z=NULL,version=version+1 WHERE id=?",(object_id,))
                else:
                    # An object standing in the village is retrieved there first (the village placement
                    # already requires that): the village scene is kept while visiting a room, so moving
                    # it straight into a room left it showing in both. Rooms are rebuilt on entry, so
                    # moving between rooms stays a single step.
                    here=conn.execute('SELECT room FROM furniture_locations WHERE object_id=?',(object_id,)).fetchone()
                    if obj['state']=='placed' and (here['room'] if here else 'village')=='village' and body.room!='village':fail(PLACED_ELSEWHERE)
                    if body.room=='village':
                        if not village_inside(body.x,body.z):fail('outside_room')
                    elif abs(body.x)>4 or abs(body.z)>4:fail('outside_room')
                    if body.room!='village' and abs(body.x)<1.5 and body.z>2.5:fail('door_area_reserved')
                    if body.room=='workshop' and body.x < -1.8 and body.z < -1.5:fail('workbench_area_reserved')
                    if body.room=='village' and village_reserved(body.x,body.z):fail('reserved_area')
                    others=conn.execute("SELECT x,z FROM objects LEFT JOIN furniture_locations ON object_id=objects.id WHERE owner_id=? AND objects.id!=? AND state='placed' AND COALESCE(room,'village')=?",(user['id'],object_id,body.room)).fetchall()
                    if len(others)>=30:fail('room_full')
                    if any(abs(o['x']-body.x)<2 and abs(o['z']-body.z)<2 for o in others):fail('placement_overlap')
                    try:room_budget.check(conn,assets,user['id'],body.room,object_id,obj['asset_id'])
                    except ProviderError as error:fail(error.code,409 if error.code=='room_render_budget_exceeded' else 503)
                    conn.execute("UPDATE objects SET state='placed',x=?,z=?,rotation=?,version=version+1 WHERE id=?",(body.x,body.z,body.rotation,object_id))
                    conn.execute('INSERT INTO furniture_locations VALUES (?,?) ON CONFLICT(object_id) DO UPDATE SET room=excluded.room',(object_id,body.room))
                return {'version':obj['version']+1,'room':body.room,'state':'inventory' if body.action=='retrieve' else 'placed'}
            return mutate(request,body,'placement:'+object_id,edit)

    def provider_for(self,fingerprint):
        """The provider bound to the key a task was created with."""
        return self.provider.for_key(fingerprint) if fingerprint and hasattr(self.provider,'for_key') else self.provider

    async def pick_provider(self,predicted):
        """The first configured Tripo key whose balance covers this submission plus the reserve."""
        candidates=self.provider.pool() if hasattr(self.provider,'pool') else [self.provider]
        for candidate in candidates:
            try:
                if await candidate.balance()-predicted>=self.settings.credit_reserve:return candidate
            except ProviderError as error:
                if error.code not in ('upstream_authentication','upstream_rejected'):raise
        raise ProviderError('insufficient_provider_credit')

    def update(self,job_id,**fields):
        with self.db.transaction() as conn:
            fields['updated']=self.clock()
            conn.execute('UPDATE studio_jobs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),job_id))
            conn.execute('UPDATE studio_leases SET expires=? WHERE job_id=? AND token=?',(self.clock()+600,job_id,self.claims.get(job_id,'')))

    async def draw_concept(self,job,body,mesh_model,plan,parts,provenance):
        """Text-only crafts: a concept picture of the designed object (Tripo text-to-image, 5 credits) that
        the player approves before the 3D build, which then uses it as its reference image. Skipped (the
        text build stays) when it would pass the per-craft cap or the server budget; a failed picture
        never fails the craft. Proxy (development) crafts get a drawn placeholder, no Tripo."""
        part=plan['parts'][0];entry=parts[part['id']]
        concept=dict(provenance.get('concept') or {'draws':0})
        textured=body.material=='textured'
        spent=float(entry.get('concept_credits_consumed') or 0)
        if body.geometry=='tripo':
            cap=self.settings.max_credits_per_craft if self.settings.mode=='live' else 0
            if cap and spent+CONCEPT_CREDITS+mesh_credits(mesh_model,textured,True)>cap:
                provenance['concept_skipped']='over_cap';return
            if self.settings.tripo_credit_budget:
                with self.db.transaction() as conn:committed=tripo_credits_committed(conn,job['id'])
                if committed+spent+CONCEPT_CREDITS>self.settings.tripo_credit_budget:
                    provenance['concept_skipped']='budget';return
        # A product-style render: the picture becomes Tripo's image reference, so believable shapes and
        # materials give a better model. Style words in the description (cute, anime...) still win.
        prompt=('Concept art of ONLY this object, the whole object centred and fully visible, three-quarter view, plain '
                'light-grey background, soft studio lighting. Style: '+craft_styles.style(body.style)['concept']+
                ', unless the description asks for another style. No text, no people. Object: '+str(part.get('prompt','')))[:1800]
        try:
            if body.geometry!='tripo':blob=fixture_concept(str(part.get('prompt','')))
            else:
                tripo=self.provider_for(entry['key']) if entry.get('key') else await self.pick_provider(CONCEPT_CREDITS)
                data=await tripo.request('POST','/generation/text-to-image',{'model':'seedream_v4','prompt':prompt})
                task=data.get('task_id')
                if not isinstance(task,str) or not task or len(task)>200 or '/' in task:raise ProviderError('upstream_schema')
                entry.update(key=getattr(tripo,'fingerprint',''),concept_task=task)
                for _ in range(80):
                    result=await tripo.task(task)
                    if result.get('status')=='success':break
                    if result.get('status') in ('failed','cancelled','banned','expired'):raise ProviderError('concept_failed')
                    await asyncio.sleep(self.poll_pause)
                else:raise ProviderError('concept_timeout')
                credits=result.get('credits_consumed')
                entry['concept_credits_consumed']=spent+(credits if type(credits) in (int,float) else CONCEPT_CREDITS)
                blob=await tripo.fetch_image(image_url(result.get('output') or {}))
        except ProviderError as error:
            provenance['concept_error']=error.code
            return
        name=job['id']+'-concept.jpg'
        target=self.assets/name;temporary=target.with_suffix('.tmp');temporary.write_bytes(blob);temporary.replace(target)
        concept.update(file=name,draws=int(concept.get('draws',0))+1)
        provenance['concept']=concept
        provenance.pop('concept_error',None);provenance.pop('concept_skipped',None)
        if body.geometry=='tripo':
            images=float(entry.get('concept_credits_consumed') or 0)
            provenance.update(estimated_tripo_credits=images+mesh_credits(mesh_model,textured,True),
                              estimate_text_only=images+mesh_credits(mesh_model,textured,False))
            provenance['quoted_game_cost']=max(job['cost'],math.ceil(provenance['estimated_tripo_credits']*self.settings.studio_credit_rate))

    def guard_tripo_cap(self,job,parts):
        """Last check before a new Tripo request: the account's earlier requests plus the ones
        this job already sent must leave room for one more (live trial cap)."""
        limit=self.settings.user_total_generation_limit if self.settings.mode=='live' else 0
        if not limit:return
        with self.db.transaction() as conn:used=tripo_requests(conn,job['owner_id'],job['id'])
        sent=sum(1 for p in parts.values() for k in ('task','image_task') if p.get(k))
        if used+sent>=limit:raise ProviderError('user_total_generation_limit')

    def refund(self,conn,row):
        entries=conn.execute("SELECT reason,amount FROM ledger WHERE user_id=? AND reference=? AND reason IN ('studio_charge','studio_quote_charge','studio_refund','studio_resume_charge','studio_resume_refund')",(row['owner_id'],row['id'])).fetchall()
        outstanding=-sum(r['amount'] for r in entries)
        if outstanding<=0:return
        reason='studio_resume_refund' if any(r['reason']=='studio_resume_charge' for r in entries) else 'studio_refund'
        self.money(conn,row['owner_id'],outstanding,reason,row['id'])

    def error(self,job_id,error):
        with self.db.transaction() as conn:
            row=conn.execute('SELECT * FROM studio_jobs WHERE id=?',(job_id,)).fetchone()
            if not row or row['state'] in ('ready','failed','cancelled','unknown'):return
            state='unknown' if error.uncertain else 'failed'
            conn.execute('UPDATE studio_jobs SET state=?,error=?,updated=? WHERE id=?',(state,error.code,self.clock(),job_id))
            if state=='failed':self.refund(conn,row)

    async def tick(self):
        with self.db.transaction() as conn:
            # Recover abandoned claims without requiring another server restart.
            stale=conn.execute("SELECT studio_jobs.* FROM studio_jobs JOIN studio_leases ON job_id=id WHERE expires<=? AND state IN ('planning','submitting')",(self.clock(),)).fetchall()
            for row in stale:
                state='unknown' if row['state']=='submitting' else 'failed'
                conn.execute('UPDATE studio_jobs SET state=?,error=? WHERE id=?',(state,'worker_lease_expired',row['id']))
                if state=='failed':self.refund(conn,row)
            conn.execute('DELETE FROM studio_leases WHERE expires<=?',(self.clock(),))
            jobs=[r[0] for r in conn.execute("SELECT id FROM studio_jobs WHERE state IN ('queued','building') AND updated<? ORDER BY created LIMIT 3",(self.clock()-2,))]
        for job in jobs:await self.process(job)

    async def process(self,job_id):
        async with self.lock:
            token=str(uuid.uuid4())
            with self.db.transaction() as conn:
                lease=conn.execute('SELECT expires FROM studio_leases WHERE job_id=?',(job_id,)).fetchone()
                if lease and lease[0]>self.clock():return
                conn.execute('INSERT INTO studio_leases VALUES (?,?,?) ON CONFLICT(job_id) DO UPDATE SET token=excluded.token,expires=excluded.expires',(job_id,token,self.clock()+600))
            self.claims[job_id]=token
            async def heartbeat():
                while True:
                    await asyncio.sleep(30)
                    with self.db.transaction() as conn:
                        conn.execute('UPDATE studio_leases SET expires=? WHERE job_id=? AND token=?',(self.clock()+600,job_id,token))
            renew=asyncio.create_task(heartbeat())
            try:await self._process(job_id)
            finally:
                renew.cancel()
                try:await renew
                except asyncio.CancelledError:pass
                with self.db.transaction() as conn:conn.execute('DELETE FROM studio_leases WHERE job_id=? AND token=?',(job_id,token))
                self.claims.pop(job_id,None)

    async def _process(self,job_id):
        with self.db.transaction() as conn:
            row=conn.execute('SELECT * FROM studio_jobs WHERE id=?',(job_id,)).fetchone()
            if not row or row['state'] not in ('queued','building'):return
            job=dict(row)
            if job['state']=='queued':conn.execute("UPDATE studio_jobs SET state='planning' WHERE id=?",(job_id,))
        try:
            body=StudioRequest.model_validate_json(job['request'])
            mesh_model=self.settings.tripo_model if body.mesh_model=='configured' else body.mesh_model
            if body.geometry=='tripo' and not self.settings.tripo_key:
                self.update(job_id,state=job['state'],error='provider_configuration_required')
                return
            if job['state']=='queued' and job.get('plan') and json.loads(job['provenance'] or '{}').get('redraw'):
                plan,program,provenance,parts=[json.loads(job[k]) for k in ('plan','program','provenance','parts')]
                provenance.pop('redraw',None)
                await self.draw_concept(job,body,mesh_model,plan,parts,provenance)
                self.update(job_id,state='awaiting_confirmation',provenance=json.dumps(provenance),parts=json.dumps(parts))
                return
            look=craft_styles.style(body.style)
            if job['state']=='queued':
                if body.designer=='fixture':
                    plan,program=demo_design(body.prompt);provenance={'provider':'authored_fixture','validation':exercise(program,[p['id'] for p in plan['parts']])}
                elif body.designer=='simple':
                    plan=simple_plan(body.prompt,look['prop']);program={'version':1,'state':{},'functions':{},'events':{}}
                    provenance={'provider':'direct_prompt','validation':exercise(program,['whole'])}
                else:
                    request_prompt=body.prompt+('\nOutput ONE complete static part and an empty program.' if body.motion=='static' else '')
                    with self.db.transaction() as conn:categories=[r[0] for r in conn.execute('SELECT name FROM asset_categories ORDER BY name LIMIT 100')]
                    request_prompt+='\nExisting category names (reuse a matching kind, otherwise propose a short new kind): '+json.dumps(categories,ensure_ascii=False)
                    plan,program,provenance=await self.designer.generate(request_prompt,body.model,body.effort,body.image,craft_styles.designer_style(body.style,body.size))
                if body.motion=='static':
                    plan=static_plan(plan,body.prompt,look['prop'])
                    program={'version':1,'state':{},'functions':{},'events':{}}
                # Normalize generated designs through the exact same gates as local fixtures.
                plan=validate_plan(plan);exercise(program,[p['id'] for p in plan['parts']])
                category=unicodedata.normalize('NFKC',plan['category']).casefold().strip()
                plan['category']='_'.join(''.join(c if c.isalnum() else ' ' for c in category).split())[:40] or 'decoration'
                with self.db.transaction() as conn:existed=conn.execute('SELECT 1 FROM asset_categories WHERE name=?',(plan['category'],)).fetchone() is not None
                provenance.update(category=plan['category'],category_existed=existed,generated_api_count=len(program['functions']))
                provenance.update(geometry='procedural_proxy' if body.geometry=='proxy' else 'tripo',material=body.material,motion=body.motion)
                # The game sizes the finished object by size_m (0 = the designer's own size).
                provenance.update(style=body.style,size=body.size,size_m=craft_styles.meters(body.size))
                parts={p['id']:{'state':'pending'} for p in plan['parts']}
                if body.geometry=='tripo':
                    provenance.update(tripo_model=mesh_model,estimated_tripo_credits=estimate(mesh_model,body.material=='textured',len(parts),bool(body.image),body.image_mode=='refine'),estimate_source='official_rates_and_measured_2026_10_02')
                    provenance.update(quoted_game_cost=max(job['cost'],math.ceil(provenance['estimated_tripo_credits']*self.settings.studio_credit_rate)),stars_per_credit=self.settings.studio_credit_rate,reserved_game_cost=job['cost'])
                    cap=self.settings.max_credits_per_craft if self.settings.mode=='live' else 0
                    if cap and provenance['estimated_tripo_credits']>cap:raise ProviderError('craft_over_trial_limit')
                concept=body.concept and not body.image and len(plan['parts'])==1
                if concept:await self.draw_concept(job,body,mesh_model,plan,parts,provenance)
                waits=body.geometry=='tripo' or concept
                self.update(job_id,state='awaiting_confirmation' if waits else 'building',plan=json.dumps(plan),program=json.dumps(program),provenance=json.dumps(provenance),parts=json.dumps(parts))
                if waits:return
            else:
                plan,program,provenance,parts=[json.loads(job[k]) for k in ('plan','program','provenance','parts')]
            textured=body.material=='textured'
            # Older interrupted jobs may predate aggregate render accounting.
            for entry in parts.values():
                if entry['state']=='ready' and not entry.get('render_budget'):
                    blob=(self.assets/entry['file']).read_bytes();stats={}
                    validate_glb(blob,allow_textures=textured,stats=stats)
                    if hashlib.sha256(blob).hexdigest()!=entry['sha256']:raise ProviderError('stored_part_changed')
                    entry.update(bytes=len(blob),render_budget=stats)
            for key,limit in (('texture_pixels',32000000),('vertices',300000),('draw_calls',128)):
                if sum(part.get('render_budget',{}).get(key,0) for part in parts.values())>limit:raise ProviderError('assembly_render_budget_exceeded')
            if sum(part.get('bytes',0) for part in parts.values())>48*1024*1024:raise ProviderError('assembly_too_large')
            for p in plan['parts']:
                entry=parts[p['id']]
                if entry['state']=='ready':continue
                if body.geometry=='proxy':blob=fixture_glb(p['shape'],textured)
                else:
                    if entry['state']=='pending' and body.image_mode=='refine':
                        self.guard_tripo_cap(job,parts)
                        tripo=await self.pick_provider(5)
                        entry['key']=getattr(tripo,'fingerprint','')
                        reference=await tripo.upload_image(body.image)
                        self.update(job_id,state='submitting')
                        data=await tripo.request('POST','/generation/image-to-image',{'model':'seedream_v5','input':reference,
                            'prompt':'Create a clean isolated product reference of ONLY this component: '+p['prompt']+'. Preserve the reference design and soft illustrated island style. Neutral background, no text, no other components.',
                            'size':'2K','output_format':'png'})
                        task=data.get('task_id')
                        if not isinstance(task,str) or not task or len(task)>200 or '/' in task:raise ProviderError('upstream_schema',uncertain=True)
                        entry.update(state='image_generating',image_task=task)
                        self.update(job_id,state='building',parts=json.dumps(parts));return
                    if entry['state']=='image_generating':
                        result=await self.provider_for(entry.get('key')).task(entry['image_task'])
                        if result.get('status') in ('queued','running'):self.update(job_id,state='building');return
                        if result.get('status') in ('failed','cancelled'):raise ProviderError('image_refinement_failed')
                        if result.get('status')!='success':raise ProviderError('upstream_schema',uncertain=True)
                        entry.update(state='image_ready',image_credits_consumed=result.get('credits_consumed'))
                        self.update(job_id,state='building',parts=json.dumps(parts))
                    if entry['state'] in ('pending','image_ready'):
                        if entry['state']=='pending':self.guard_tripo_cap(job,parts)
                        concept=entry.get('concept_task') if entry.get('use_concept') else None
                        predicted=mesh_credits(mesh_model,textured,bool(concept or (body.image and (len(parts)==1 or body.image_mode=='refine'))))
                        # A refined image belongs to the key that made it; otherwise any key with credit.
                        if entry.get('key'):
                            tripo=self.provider_for(entry['key'])
                            if await tripo.balance()-predicted<self.settings.credit_reserve:raise ProviderError('insufficient_provider_credit')
                        else:tripo=await self.pick_provider(predicted)
                        payload={'model':mesh_model,
                            'prompt':p['prompt']+' Standalone isolated component. Cozy rounded matte game furniture. No other parts, no ground.',
                            # UVs are always requested (no surcharge): uncoloured crafts are painted
                            # in the game's painter, which maps its texture through them.
                            'face_limit':3000,'texture':textured,'pbr':textured,'quad':False,'export_uv':True}
                        route='/generation/text-to-model'
                        if concept:
                            payload.pop('prompt');payload['input']=concept;route='/generation/image-to-model'
                            provenance['image_path']='approved_concept_image_to_tripo'
                        elif entry.get('image_task'):
                            payload.pop('prompt');payload['input']=entry['image_task'];route='/generation/image-to-model'
                            provenance['image_path']='llm_part_prompt_to_refined_image_to_tripo'
                        elif body.image and len(plan['parts'])==1:
                            token=await tripo.upload_image(body.image)
                            payload.pop('prompt');payload['input']=token;route='/generation/image-to-model'
                            provenance['image_path']='original_reference_to_tripo'
                        elif body.image:provenance['image_path']='llm_interpreted_part_prompts'
                        self.update(job_id,state='submitting')
                        data=await tripo.request('POST',route,payload)
                        task=data.get('task_id')
                        if not isinstance(task,str) or not task or len(task)>200 or '/' in task:raise ProviderError('upstream_schema',uncertain=True)
                        entry.update(state='generating',task=task,key=getattr(tripo,'fingerprint',''))
                        self.update(job_id,state='building',parts=json.dumps(parts),provenance=json.dumps(provenance))
                        return
                    tripo=self.provider_for(entry.get('key'))
                    result=await tripo.task(entry['task'])
                    if result.get('status') in ('queued','running'):self.update(job_id,state='building');return
                    if result.get('status') in ('failed','cancelled'):raise ProviderError('generation_failed')
                    if result.get('status')!='success':raise ProviderError('upstream_schema',uncertain=True)
                    entry['credits_consumed']=result.get('credits_consumed')
                    # Keep actual provider billing even if download/validation subsequently fails.
                    self.update(job_id,parts=json.dumps(parts))
                    blob=await tripo.download(result.get('output',{}).get('model_url',''),allow_textures=textured)
                stats={}
                validate_glb(blob,allow_textures=textured,stats=stats)
                if len(blob)+sum(part.get('bytes',0) for part in parts.values())>48*1024*1024:raise ProviderError('assembly_too_large')
                for key,limit in (('texture_pixels',32000000),('vertices',300000),('draw_calls',128)):
                    if stats[key]+sum(part.get('render_budget',{}).get(key,0) for part in parts.values())>limit:raise ProviderError('assembly_render_budget_exceeded')
                filename=job_id+'-'+p['id']+'.glb'
                target=self.assets/filename;temporary=target.with_suffix('.tmp');temporary.write_bytes(blob);temporary.replace(target)
                entry.update(state='ready',file=filename,sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob),render_budget=stats)
                self.update(job_id,state='building',parts=json.dumps(parts))
            for p in plan['parts']:p.update(file=parts[p['id']]['file'],sha256=parts[p['id']]['sha256'])
            provenance.update(billing(parts) if body.geometry=='tripo' else {'tripo_credits_consumed':0,'known_tripo_credits':0,'billing_complete':True})
            provenance['image_refinement_credits']=sum(p.get('image_credits_consumed') or 0 for p in parts.values())
            manifest={'schema':1,'plan':plan,'program':program,'provenance':provenance}
            with self.db.transaction() as conn:
                current=conn.execute('SELECT state FROM studio_jobs WHERE id=?',(job_id,)).fetchone()[0]
                if current!='building':return
                first=plan['parts'][0]
                conn.execute('INSERT INTO assets VALUES (?,?,?,?)',(job_id,first['file'],first['sha256'],'studio'))
                obj=self.new_object(conn,job['owner_id'],job_id,plan['title'])
                conn.execute('INSERT INTO studio_assets VALUES (?,?)',(job_id,json.dumps(manifest)))
                for name,definition in program['functions'].items():
                    encoded=json.dumps(definition,sort_keys=True,separators=(',',':'))
                    conn.execute('INSERT INTO generated_apis VALUES (?,?,?,?)',(job_id,name,encoded,hashlib.sha256(encoded.encode()).hexdigest()))
                initial=AssetVM(program,[p['id'] for p in plan['parts']]);initial.run('spawn')
                conn.execute('INSERT INTO studio_runtime(object_id,state) VALUES (?,?)',(obj,json.dumps(initial.state)))
                conn.execute('INSERT OR IGNORE INTO asset_categories VALUES (?,?)',(plan['category'],self.clock()))
                conn.execute("UPDATE studio_jobs SET state='ready',object_id=?,provenance=?,updated=?,error=NULL WHERE id=?",(obj,json.dumps(provenance),self.clock(),job_id))
        except asyncio.CancelledError:raise
        except ProviderError as error:
            if isinstance(error,DesignFailure):
                # Rejected output still consumed LLM tokens; never label it free.
                self.update(job_id,provenance=json.dumps({'provider':provider_name(self.settings),
                    'model':body.model,'effort':body.effort,'usage':error.usage,'attempts':error.attempts,
                    'tripo_credits_consumed':0,'known_tripo_credits':0,'billing_complete':True}))
            # Poll/download errors keep the paid task ID. Never submit it again.
            if 'parts' in locals() and any((p.get('task') and p['state']=='generating') or (p.get('image_task') and p['state']=='image_generating') for p in parts.values()) and error.code in ('upstream_unreachable','upstream_unavailable','upstream_rate_limit','asset_download_failed','key_not_configured','upstream_authentication','upstream_non_json','upstream_invalid_json'):
                self.update(job_id,state='building',error=error.code);return
            self.error(job_id,error)
        except Exception:self.error(job_id,ProviderError('studio_validation_failed'))
