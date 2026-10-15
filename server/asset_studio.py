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
import threading
import uuid
import unicodedata
from typing import Literal
from PIL import Image, ImageOps, ImageCms
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from fastapi import Request, HTTPException
from fastapi.responses import Response
from .models import Mutation
from .asset_assembly import demo_design, fixture_glb, validate_plan, static_plan, simple_plan
from .asset_vm import AssetVM, ProgramError, exercise_extended as exercise
from .design_provider import DesignProvider, DesignFailure, MODELS, EFFORTS, provider_name
from .provider import ProviderError, validate_glb
from .studio_pricing import mesh_credits,estimate
from .account_limits import daily_counts, tester_credits, check_tester_budget, record_tester_bill
from . import tripo_budget, llm_budget
from . import room_budget
from .stored_assets import read_glb
from .object_paint import version_column as paint_version
from . import object_shape
from . import build_rules
from . import craft_styles
from . import craft_moderation
from .craft_moderation import Refused
from . import interactions
from . import archetypes
from . import clock_hands
from . import behaviour_library as library

SCHEMA='''
CREATE TABLE IF NOT EXISTS studio_jobs (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), request TEXT NOT NULL,
 state TEXT NOT NULL, cost INTEGER NOT NULL, plan TEXT, program TEXT, provenance TEXT,
 parts TEXT NOT NULL DEFAULT '{}', object_id TEXT, error TEXT, created REAL NOT NULL, updated REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS studio_pending ON studio_jobs(owner_id)
 WHERE state NOT IN ('ready','failed','cancelled','unknown');
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

# Reference photos: what the craft window may send, and what the server keeps and passes on (Tripo's
# upload and the LLM take 1 MB). The request body is only checked (check_image: format and size from
# the header, cheap, before sign-in is known); queue() then scales it down and re-encodes it once
# (reference_image), after sign-in, in the worker threads, one photo at a time. Re-encoding also drops
# the metadata (camera, GPS) after applying the camera's rotation.
IMAGE_UPLOAD_BYTES=6*1024*1024
IMAGE_FIELD_CHARS=IMAGE_UPLOAD_BYTES*4//3+64
IMAGE_MAX_SIDE=4096
IMAGE_MAX_PIXELS=16_000_000
IMAGE_KEPT_BYTES=1024*1024
IMAGE_KEPT_SIDE=2048
IMAGE_MIN_SIDE=16
IMAGE_GATE=threading.BoundedSemaphore(1)
SRGB=ImageCms.createProfile('sRGB')
# The image codes the craft window words (app.py turns a refused photo into one of these).
IMAGE_CODES=('invalid_image','image_too_large','image_too_small','image_unreadable')

def _photo_blob(value):
    if not value.startswith(('data:image/png;base64,','data:image/jpeg;base64,')):raise ValueError('image_unreadable')
    try:blob=base64.b64decode(value.split(',',1)[1],validate=True)
    except Exception:raise ValueError('image_unreadable') from None
    if len(blob)>IMAGE_UPLOAD_BYTES:raise ValueError('image_too_large')
    return blob

def check_image(value):
    """A reference photo's format and size, read from its header only (no pixel is decoded).
    Raises ValueError with one of IMAGE_CODES."""
    if not value:return value
    blob=_photo_blob(value)
    try:
        with Image.open(io.BytesIO(blob)) as im:kind,size=im.format,im.size
    except Exception:raise ValueError('image_unreadable') from None
    if kind not in ('PNG','JPEG'):raise ValueError('image_unreadable')
    if max(size)>IMAGE_MAX_SIDE or size[0]*size[1]>IMAGE_MAX_PIXELS:raise ValueError('image_too_large')
    if min(size)<IMAGE_MIN_SIDE:raise ValueError('image_too_small')
    return value

def reference_image(value):
    """A checked reference photo as a PNG or JPEG data URL of at most IMAGE_KEPT_SIDE px and
    IMAGE_KEPT_BYTES, upright and without metadata, or '' for none. Raises ValueError (IMAGE_CODES)."""
    if not value:return value
    check_image(value)
    blob=_photo_blob(value)
    try:
        with Image.open(io.BytesIO(blob)) as im:
            # A large JPEG decodes straight at a reduced scale.
            if im.format=='JPEG':im.draft('RGB',(IMAGE_KEPT_SIDE,IMAGE_KEPT_SIDE))
            im.load()
            picture=ImageOps.exif_transpose(im)
            # A wide-gamut photo (Display P3, Adobe RGB) becomes sRGB: the saved file carries no profile.
            icc=im.info.get('icc_profile')
            if icc:
                try:picture=ImageCms.profileToProfile(picture,ImageCms.ImageCmsProfile(io.BytesIO(icc)),SRGB,outputMode='RGBA' if 'A' in picture.mode else 'RGB')
                except Exception:pass
            alpha=picture.mode in ('RGBA','LA') or (picture.mode=='P' and 'transparency' in picture.info)
            mode='RGBA' if alpha else 'RGB'
            if picture.mode!=mode:picture=picture.convert(mode)
    except ValueError as error:
        if str(error) in IMAGE_CODES:raise
        raise ValueError('image_unreadable') from None
    except Exception:raise ValueError('image_unreadable') from None
    if max(picture.size)>IMAGE_KEPT_SIDE:picture.thumbnail((IMAGE_KEPT_SIDE,IMAGE_KEPT_SIDE),Image.LANCZOS)
    if min(picture.size)<IMAGE_MIN_SIDE:raise ValueError('image_too_small')
    copy,quality=picture,90
    while True:
        out=io.BytesIO()
        if alpha:copy.save(out,'PNG');kind='png'
        else:copy.save(out,'JPEG',quality=quality);kind='jpeg'
        if out.tell()<=IMAGE_KEPT_BYTES or max(copy.size)<=512:break
        copy=copy.copy();copy.thumbnail((int(max(copy.size)*.75),)*2,Image.LANCZOS);quality=85
    if out.tell()>IMAGE_KEPT_BYTES:
        # A noisy transparent picture: kept as a JPEG on white.
        flat=Image.new('RGB',copy.size,'white');flat.paste(copy,mask=copy.split()[-1] if alpha else None)
        out=io.BytesIO();flat.save(out,'JPEG',quality=85);kind='jpeg'
    return 'data:image/'+kind+';base64,'+base64.b64encode(out.getvalue()).decode()

class StudioRequest(Mutation):
    # Two letters name plenty of furniture ("의자", "책상").
    prompt: str=Field(min_length=2,max_length=1500)
    material: Literal['mesh','textured']='mesh'
    motion: Literal['static','dynamic']='dynamic'
    designer: Literal['fixture','llm','simple']='fixture'
    geometry: Literal['proxy','tripo']='proxy'
    mesh_model: Literal['configured','v3.1-20260211','P2-20260801']='configured'
    image_mode: Literal['original','refine']='original'
    model: Literal['gpt-6-luna','gpt-5.6-terra','gpt-6-sol','gpt-6-astra']='gpt-6-luna'
    effort: Literal['low','medium','high','xhigh']='high'
    # A reference photo up to IMAGE_UPLOAD_BYTES; stored and sent on as at most 2048 px and 1 MB (see image_data).
    image: str=Field(default='',max_length=IMAGE_FIELD_CHARS)
    # Text-only crafts: draw a concept picture first and let the player approve it (see draw_concept).
    concept: bool=False
    # Named look and size the player picked (server/craft_styles.py).
    style: Literal[craft_styles.STYLE_IDS]=craft_styles.DEFAULT_STYLE
    size: Literal[craft_styles.SIZE_IDS]='auto'
    # Or the box the player dragged: [width x, height y, depth z] in metres (wins over size).
    dims: list[float]|None=Field(default=None,min_length=3,max_length=3)

    @field_validator('dims')
    @classmethod
    def dims_box(cls,v):
        if v is None:return v
        if not all(math.isfinite(x) and craft_styles.DIMS_MIN-1e-9<=x<=craft_styles.DIMS_MAX+1e-9 for x in v):raise ValueError('invalid_dims')
        step=craft_styles.DIMS_STEP
        return [round(min(craft_styles.DIMS_MAX,max(craft_styles.DIMS_MIN,round(x/step)*step)),2) for x in v]

    @field_validator('image')
    @classmethod
    def image_data(cls,v):
        return check_image(v)

class KindQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str=Field(default='',max_length=1500)

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
    # Build mode (server/build_rules.py); released clients send none of these and place on the floor.
    surface: Literal['floor','wall','ceiling','top']='floor'
    # Bottom height (m): on a wall, or the measured top of the support under a 'top' piece.
    y: float=Field(default=0,ge=0,le=8)
    parent: uuid.UUID|None=None
    wall: Literal['back','left','right']|None=None

    @field_validator('parent','wall',mode='before')
    @classmethod
    def blank(cls,v):return None if v=='' else v

    # A 'top' piece names its support and only it does; a wall piece names its wall.
    @model_validator(mode='after')
    def mount(self):
        if self.action=='place' and (self.surface=='top')!=(self.parent is not None):raise ValueError('parent_only_on_top')
        if self.action=='place' and self.surface=='wall' and self.wall is None:raise ValueError('wall_required')
        return self

# Learned designs (behaviour_library) made under older designer rules are not reused: 'safety1' is the
# contract that refuses inappropriate requests instead of softening them (asset_contract.py SAFETY).
DESIGN_RULES='safety1'

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
    return tripo_budget.committed_credits(conn,exclude)

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


# A held (unknown) submission waits for an operator and uses no provider capacity, so it does not
# stop other crafts; its credits still count against the budget (tripo_credits_committed).
def provider_busy(conn,exclude=''):
    return conn.execute("SELECT 1 FROM studio_jobs WHERE state NOT IN ('ready','failed','cancelled','awaiting_confirmation','unknown') AND id!=?",(exclude,)).fetchone() or         conn.execute("SELECT 1 FROM jobs WHERE state IN ('queued','submitting','generating')").fetchone()

def track(entry,result):
    """Keeps the progress (0-100) a Tripo task poll reports, for the craft window's percentage."""
    value=result.get('progress')
    if type(value) in (int,float) and math.isfinite(value):entry['progress']=max(0,min(100,int(value)))

def build_progress(parts):
    """How far the 3D build is (0..1), or None before Tripo reported anything. A refined reference
    picture is the first fifth of its part."""
    total=0.0;reported=False
    for p in parts.values():
        state=p.get('state');share=(p.get('progress') or 0)/100;picture=.2 if p.get('image_task') else 0.0
        reported=reported or state=='ready' or 'progress' in p
        if state=='ready':total+=1
        elif state=='generating':total+=picture+share*(1-picture)
        elif state=='image_generating':total+=share*.2
        elif state=='image_ready':total+=.2
    return round(total/len(parts),3) if parts and reported else None

def stage(state,provenance):
    """The step the craft window shows: design, concept (the picture), confirm, mesh, or the final state."""
    if state in ('queued','planning'):return 'concept' if provenance.get('redraw') or provenance.get('stage')=='concept' else 'design'
    if state=='awaiting_confirmation':return 'confirm'
    if state in ('building','submitting'):return 'mesh'
    return state

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
            conn.executescript(library.SCHEMA)
            conn.executescript(build_rules.SCHEMA)
            if 'bindings' not in [r[1] for r in conn.execute('PRAGMA table_info(studio_runtime)')]:
                conn.execute("ALTER TABLE studio_runtime ADD COLUMN bindings TEXT NOT NULL DEFAULT '{}'")
        # Worlds made before held (unknown) crafts stopped counting as the owner's craft under way.
        with db.transaction() as conn:
            index=conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='studio_pending'").fetchone()
            if index and "'unknown'" not in index[0]:
                conn.execute('DROP INDEX studio_pending')
                conn.execute("CREATE UNIQUE INDEX studio_pending ON studio_jobs(owner_id) WHERE state NOT IN ('ready','failed','cancelled','unknown')")
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
            conn.execute("UPDATE tripo_job_holds SET credits=0 WHERE job_id IN (SELECT id FROM studio_jobs WHERE state='unknown')")

        def manifest(conn,user_id,object_id):
            obj=own(conn,user_id,object_id)
            row=conn.execute('SELECT manifest FROM studio_assets WHERE asset_id=?',(obj['asset_id'],)).fetchone()
            if not row:fail('not_studio_object',404)
            state=conn.execute('SELECT * FROM studio_runtime WHERE object_id=?',(object_id,)).fetchone()
            # The player's interaction (server/interactions.py) replaces the crafted program everywhere.
            return obj,interactions.apply(conn,object_id,json.loads(row[0])),state

        @app.get('/v1/studio')
        def info(request:Request):
            with db.transaction() as conn:
                user=auth(conn,request)
                limits=settings.limits_for(user)
                return {'mode':settings.mode,'llm':settings.studio_llm,
                    'models':('gpt-6-luna',) if settings.mode=='live' else MODELS,
                    'efforts':('high',) if settings.mode=='live' else EFFORTS,
                    'profile':profile(conn,user['id']) if profile else {},
                    'room_usage':{room:room_budget.usage(conn,assets,user['id'],room) for room in ('home','workshop','village')},
                    'geometry_enabled':bool(settings.paid_enabled and settings.tripo_key),
                    'max_tripo_credits':limits.max_credits_per_craft,
                    'max_stars_per_craft':limits.max_stars_per_craft,
                    'tester_budget':limits.tester_credit_budget,
                    'tester_budget_used':tester_credits(conn) if limits.is_tester else 0,
                    'tripo_requests_used':tripo_requests(conn,user['id']),
                    'tripo_requests_limit':limits.user_total_generation_limit,
                    'tripo_budget':limits.tripo_credit_budget,
                    'tripo_budget_used':round(tripo_credits_committed(conn)) if limits.tripo_credit_budget else 0,
                    **craft_styles.public(),
                    'prices':{'static_mesh':20,'static_textured':40,'dynamic_mesh':30,'dynamic_textured':50},
                    'tripo_estimate':{'models':{'v3.1-20260211':{'text_mesh':10,'text_textured':20,'image_mesh':20,'image_textured':30},'P2-20260801':{'text_mesh':100,'text_textured':110,'image_mesh':100,'image_textured':110}},'image_refinement_per_part':5,'source':'official_rates_and_measured_2026_10_02','max_parts':8,'confirmation_required':True},
                    'jobs':[dict(r) for r in conn.execute('SELECT id,state,cost,object_id,error,created FROM studio_jobs WHERE owner_id=? ORDER BY created DESC LIMIT 30',(user['id'],))],
                    'objects':[build_rules.listed(object_shape.listed(dict(r))) for r in conn.execute("SELECT objects.id,name,color,objects.version,objects.state,x,z,rotation,COALESCE(room,'village') AS room,EXISTS(SELECT 1 FROM studio_assets WHERE studio_assets.asset_id=objects.asset_id) AS studio,(SELECT version FROM studio_runtime WHERE object_id=objects.id) AS runtime_version,"+paint_version('objects.id')+" AS paint_version,"+object_shape.column('objects.id')+" AS shape,"+build_rules.column('objects.id')+" AS mount FROM objects LEFT JOIN furniture_locations ON furniture_locations.object_id=objects.id WHERE owner_id=? AND state!='gifted' ORDER BY created DESC",(user['id'],))],
                    'categories':[r[0] for r in conn.execute('SELECT name FROM asset_categories ORDER BY name LIMIT 100')],
                    'shards':user['shards']}

        # The library of object types (server/archetype_library.py), for listings and the QA gallery.
        @app.get('/v1/studio/library')
        def library_listing(request:Request):
            with db.read() as conn:auth(conn,request)
            return archetypes.public()

        # The craft window asks what a request is before it is sent: a library type always built
        # moving (a clock and its free hands) and the Tripo meshes a moving craft of it needs.
        @app.post('/v1/studio/kind')
        def kind(body:KindQuery,request:Request):
            with db.read() as conn:auth(conn,request)
            return archetypes.craft_kind(body.prompt)

        @app.post('/v1/studio/jobs')
        def queue(body:StudioRequest,request:Request):
            # The photo is scaled and re-encoded here, once: after sign-in, in this worker thread (queue is
            # a plain def), one at a time. The stored request keeps the result (the worker reuses it).
            # Cheap refusals first: a refused description is never decoded or charged (server/craft_moderation.py).
            refused=craft_moderation.check_text(body.prompt)
            if refused:fail(craft_moderation.refusal_detail(refused,request.headers.get('x-villagen-version','')[:40]),422)
            if body.image:
                if body.designer!='llm':fail('image_requires_llm')
                with db.read() as conn:auth(conn,request)
                # One photo at a time; a pool thread waits a moment at most, then the window says the workshop is busy.
                if not IMAGE_GATE.acquire(timeout=3):fail('provider_busy')
                try:image=reference_image(body.image)
                except ValueError as error:fail(str(error),422)
                finally:IMAGE_GATE.release()
                body=body.model_copy(update={'image':image})
            # A clock is always built with its hands, even when asked for a still piece: the game makes
            # them (no credits, so it fits wherever the still piece fits). The price stays what was asked.
            asked=body
            kind=archetypes.classify(body.prompt)
            if kind and kind.get('always_moving') and body.motion=='static' and body.designer!='simple':
                body=body.model_copy(update={'motion':'dynamic','concept':False})
            # Moving furniture keeps separate parts: at least two Tripo meshes, or one when the game
            # makes every moving part.
            meshes=archetypes.least_meshes(kind,body.motion)
            # The photo and subtler requests are judged by the designer (asset_contract.py SAFETY).
            def create(conn,user):
                limits=settings.limits_for(user)
                if body.designer=='llm' and settings.studio_llm=='fixture':fail('llm_not_configured',503)
                if body.geometry=='tripo' and not (settings.paid_enabled and settings.tripo_key):fail('live_generation_disabled',503)
                if body.designer=='simple' and (body.motion!='static' or body.image):fail('simple_requires_static_text')
                if settings.mode=='live' and (body.designer not in ('llm','simple') or body.geometry!='tripo'):fail('development_mode_forbidden',403)
                if settings.mode=='live' and body.designer=='llm' and (body.model!='gpt-6-luna' or body.effort!='high'):
                    fail('model_not_available',403)
                if body.image and body.designer!='llm':fail('image_requires_llm')
                if body.image_mode=='refine' and (not body.image or body.geometry!='tripo'):fail('refinement_requires_image_and_tripo')
                # A held (unknown) craft waits for an operator (server/operations.py), which may take days; it
                # keeps its starseeds and still counts toward every limit, but does not stop a new craft.
                if conn.execute("SELECT 1 FROM studio_jobs WHERE owner_id=? AND state NOT IN ('ready','failed','cancelled','unknown')",(user['id'],)).fetchone():fail('generation_pending')
                if body.geometry=='tripo':
                    if provider_busy(conn):fail('provider_busy')
                    cap=limits.max_credits_per_craft
                    if cap:
                        try:
                            least=estimate(settings.tripo_model if body.mesh_model=='configured' else body.mesh_model,body.material=='textured',meshes,bool(body.image),body.image_mode=='refine')
                        except ProviderError:least=cap+1
                        if least>cap:fail('craft_over_trial_limit',403)
                    if limits.tripo_credit_budget or limits.is_tester:
                        try:need=estimate(settings.tripo_model if body.mesh_model=='configured' else body.mesh_model,body.material=='textured',meshes,bool(body.image),body.image_mode=='refine')
                        except ProviderError:need=0
                        if body.concept and not body.image:need+=CONCEPT_CREDITS
                        if limits.tripo_credit_budget and tripo_credits_committed(conn)+need>limits.tripo_credit_budget:fail('tripo_budget_exhausted',429)
                        try:check_tester_budget(conn,limits,need)
                        except ProviderError as error:fail(error.code,429)
                count=daily_counts(conn,int(clock()//86400)*86400)
                if limits.daily_generation_limit and count>=limits.daily_generation_limit:fail('daily_generation_limit',429)
                if settings.mode=='live':
                    user_count=daily_counts(conn,int(clock()//86400)*86400,user['id'])
                    if limits.user_daily_generation_limit and user_count>=limits.user_daily_generation_limit:fail('user_daily_generation_limit',429)
                    limit=limits.user_total_generation_limit
                    # Failed jobs may already have used Tripo: the cap also counts every Tripo request.
                    if limit and (conn.execute("SELECT count(*) FROM studio_jobs WHERE owner_id=? AND state!='failed'",(user['id'],)).fetchone()[0]>=limit
                                  or (body.geometry=='tripo' and tripo_requests(conn,user['id'])>=limit)):
                        # The village craft window (main.gd) words the code itself. The room studio of
                        # released clients (<= 0.10.2) prints the detail after its own prefix, so it gets
                        # the sentence; it is the only caller that sends image_mode.
                        fail(TRIAL_USED_UP % limit if 'image_mode' in body.model_fields_set else 'user_total_generation_limit',429)
                job_id=str(uuid.uuid4());cost=price(asked)
                if cost>limits.max_stars_per_craft:fail('craft_star_limit_exceeded',403)
                money(conn,user['id'],-cost,'studio_charge',job_id)
                conn.execute('INSERT INTO studio_jobs(id,owner_id,request,state,cost,created,updated) VALUES (?,?,?,?,?,?,?)',
                    (job_id,user['id'],body.model_dump_json(),'queued',cost,clock(),clock()))
                tripo_budget.manage_job(conn,job_id,user['id'],limits.is_tester,clock())
                return {'id':job_id,'state':'queued','cost':cost}
            return mutate(request,body,'studio_generate',create)

        @app.get('/v1/studio/jobs/{job_id}')
        def status(job_id:str,request:Request):
            with db.transaction() as conn:
                user=auth(conn,request)
                row=conn.execute("SELECT id,state,cost,object_id,error,provenance,parts,plan,json_extract(request,'$.concept') AS concept_asked,"
                    "COALESCE(json_extract(request,'$.image'),'')!='' AS image_given FROM studio_jobs WHERE id=? AND owner_id=?",(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                value=dict(row);value['provenance']=json.loads(value['provenance'] or '{}')
                asked,photo=value.pop('concept_asked'),value.pop('image_given')
                # What the designer made of the request: the title and the sentence each part sends to Tripo.
                plan=json.loads(value.pop('plan') or '{}')
                if plan.get('parts'):
                    value['design']={'title':str(plan.get('title',''))[:120],
                        'parts':[{'id':str(p.get('id',''))[:40],'prompt':str(p.get('prompt',''))[:600]} for p in plan['parts'][:8]]}
                parts=json.loads(value['parts'])
                if value['provenance'].get('geometry')=='tripo':
                    managed=conn.execute('SELECT 1 FROM tripo_job_holds WHERE job_id=?',(job_id,)).fetchone()
                    value['provenance'].update(tripo_budget.job_billing(conn,job_id) if managed else billing(parts))
                    if value['state'] in ('submitting','unknown'):value['provenance'].update(billing_complete=False,tripo_credits_consumed=None)
                # The window's steps: design -> picture (text-only crafts that drew one) -> 3D parts -> done.
                value['stage']=stage(value['state'],value['provenance'])
                drawn=value['state'] in ('queued','planning') or bool(value['provenance'].get('concept'))
                value['stages']=['design']+(['concept'] if asked and not photo and drawn else [])+['mesh','done']
                value['progress']=build_progress(parts) if value['state'] in ('building','submitting') else None
                value['parts']={k:v['state'] for k,v in parts.items()}
                # Why a craft failed, in the few reasons the window words (craft_moderation.failure_reason).
                value['reason'],value['refusal']=craft_moderation.failure_reason(value['error'] if value['state'] in ('failed','unknown') else '')
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
                row=conn.execute('SELECT plan,program,provenance FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                if not row['plan'] or not row['program']:fail('design_not_ready')
                plan=validate_plan(json.loads(row['plan']))
                program=json.loads(row['program'])
                exercise(program,[p['id'] for p in plan['parts']])
                # What the finished object will do: its library type's behaviour when it starts with one.
                quote=json.loads(row['provenance'] or '{}')
                kind=quote.get('archetype')
                try:assigned=archetypes.assign(kind,plan,program,quote.get('style','')) if kind else None
                except interactions.InteractionError:assigned=None
                if assigned and assigned['compiled']:program=assigned['compiled']['program']
                blobs={p['id']:base64.b64encode(fixture_glb(p['shape'],False)).decode() for p in plan['parts']}
                return interactions.for_client(request,{'schema':1,'preview_only':True,'plan':plan,'program':program,
                    'provenance':{'geometry':'procedural_proxy'},'runtime':{},'blobs':blobs})

        @app.post('/v1/studio/jobs/{job_id}/confirm')
        def confirm(job_id:str,body:StudioConfirm,request:Request):
            def edit(conn,user):
                limits=settings.limits_for(user)
                row=conn.execute('SELECT * FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                if row['state']!='awaiting_confirmation':fail('not_awaiting_confirmation')
                # Proxy builds (development) can wait on a concept picture too; they never reach Tripo.
                tripo_job=json.loads(row['request']).get('geometry')=='tripo'
                if tripo_job and not (settings.paid_enabled and settings.tripo_key):fail('live_generation_disabled',503)
                if tripo_job and provider_busy(conn,job_id):fail('provider_busy')
                if limits.user_total_generation_limit and tripo_requests(conn,user['id'],job_id)>=limits.user_total_generation_limit:
                    fail('user_total_generation_limit',429)
                quote=json.loads(row['provenance']);parts=json.loads(row['parts'] or '{}')
                if quote.get('concept'):
                    for entry in parts.values():entry['use_concept']=body.use_concept
                    quote['concept_used']=body.use_concept
                    if not body.use_concept and quote.get('estimate_text_only') is not None:
                        quote['estimated_tripo_credits']=quote['estimate_text_only']
                        quote['quoted_game_cost']=max(row['cost'],math.ceil(float(quote['estimated_tripo_credits'])*settings.studio_credit_rate))
                if limits.tripo_credit_budget and tripo_credits_committed(conn,job_id)+float(quote.get('estimated_tripo_credits') or 0)>limits.tripo_credit_budget:
                    fail('tripo_budget_exhausted',429)
                total=max(row['cost'],int(quote.get('quoted_game_cost',row['cost'])))
                if total>limits.max_stars_per_craft:fail('craft_star_limit_exceeded',403)
                if tripo_job:
                    try:tripo_budget.hold_build(conn,limits,job_id,user['id'],0 if getattr(self.provider,'_in_process_fake',False) else self.remaining_build(row,parts),clock())
                    except ProviderError as error:fail(error.code,429)
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
                limits=settings.limits_for(user)
                row=conn.execute('SELECT * FROM studio_jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
                if not row:fail('job_not_found',404)
                quote=json.loads(row['provenance'] or '{}')
                if row['state']!='awaiting_confirmation' or not quote.get('concept'):fail('cannot_redraw')
                if int(quote['concept'].get('draws',1))>=MAX_CONCEPT_DRAWS:fail('concept_redraw_limit',429)
                # Failed/uncertain pictures can still cost credits. Count accepted attempts
                # durably under the mutation transaction, not only successful pictures.
                attempts=int(quote.get('concept_redraw_attempts',max(0,int(quote['concept'].get('draws',1))-1)))
                if attempts>=MAX_CONCEPT_DRAWS-1:fail('concept_redraw_limit',429)
                asked=json.loads(row['request'])
                if asked.get('geometry')=='tripo':
                    parts=json.loads(row['parts'] or '{}')
                    spent=tripo_budget.attempt_credits(conn,job_id)
                    model=settings.tripo_model if asked.get('mesh_model','configured')=='configured' else asked['mesh_model']
                    cap=limits.max_credits_per_craft
                    if cap and spent+CONCEPT_CREDITS+mesh_credits(model,asked.get('material')=='textured',True)>cap:fail('craft_over_trial_limit',403)
                    if limits.tripo_credit_budget and tripo_credits_committed(conn,job_id)+spent+CONCEPT_CREDITS>limits.tripo_credit_budget:fail('tripo_budget_exhausted',429)
                    try:check_tester_budget(conn,limits,CONCEPT_CREDITS)
                    except ProviderError as error:fail(error.code,429)
                    if provider_busy(conn,job_id):fail('provider_busy')
                quote['redraw']=True
                quote['concept_redraw_attempts']=attempts+1
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
                return interactions.for_client(request,{**value,'program':interactions.compat(value),'original_plan':original,'runtime':{'state':json.loads(state['state']),'colors':json.loads(state['colors']),'bindings':bindings,'version':state['version']},'object_version':obj['version']})

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
                vm=AssetVM(value['program'],interactions.targets(value),json.loads(state['state']))
                try:commands=vm.run(body.event,{'near':int(body.event=='near')})
                except ProgramError:fail('behavior_rejected')
                conn.execute('UPDATE studio_runtime SET state=?,version=version+1 WHERE object_id=?',(json.dumps(interactions.settle(value,dict(vm.state))),object_id))
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
                vm=AssetVM(value['program'],interactions.targets(value),before)
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
                    # Whatever stood on it goes to the bag too.
                    pose={'retrieved':build_rules.retrieve(conn,object_id)}
                else:
                    # An object standing in the village is retrieved there first (the village placement
                    # already requires that): the village scene is kept while visiting a room, so moving
                    # it straight into a room left it showing in both. Rooms are rebuilt on entry, so
                    # moving between rooms stays a single step.
                    here=conn.execute('SELECT room FROM furniture_locations WHERE object_id=?',(object_id,)).fetchone()
                    if obj['state']=='placed' and (here['room'] if here else 'village')=='village' and body.room!='village':fail(PLACED_ELSEWHERE)
                    # Floor, wall, ceiling or on top of a piece; sized overlap, room limits; carries what stands on it.
                    pose=build_rules.place(conn,assets,user['id'],obj,body)
                return {'version':obj['version']+1,'room':body.room,'state':'inventory' if body.action=='retrieve' else 'placed',**pose}
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

    def limits_for_job(self,job):
        with self.db.read() as conn:
            return self.settings.limits_for(conn.execute('SELECT * FROM users WHERE id=?',(job['owner_id'],)).fetchone())

    def remaining_build(self,job,parts):
        """Estimates for the provider requests that have not yet been submitted."""
        body=StudioRequest.model_validate_json(job['request'])
        model=self.settings.tripo_model if body.mesh_model=='configured' else body.mesh_model
        needed=0
        for part in parts.values():
            if part.get('primitive'):continue
            image=bool(part.get('use_concept') or (body.image and (len(parts)==1 or body.image_mode=='refine')))
            if not part.get('task') and not part.get('mesh_attempt') and part.get('state')!='ready':
                needed+=mesh_credits(model,body.material=='textured',image)
            if body.image_mode=='refine' and not part.get('image_task') and not part.get('refine_attempt'):
                needed+=CONCEPT_CREDITS
        return needed

    def reserve_build(self,job,parts,quote,part_id,kind,predicted,tripo):
        limits=self.limits_for_job(job)
        if max(job['cost'],int(quote.get('quoted_game_cost',job['cost'])))>limits.max_stars_per_craft:
            raise ProviderError('craft_star_limit_exceeded')
        remaining=max(0,self.remaining_build(job,parts)-predicted)
        # Only the built-in in-process transport is provably free. Real providers
        # reporting zero still retain their original reservations.
        if getattr(self.provider,'_in_process_fake',False):predicted=remaining=0
        with self.db.transaction() as conn:
            attempt=tripo_budget.reserve_attempt(conn,limits,job['id'],job['owner_id'],kind,part_id,
                predicted,remaining,self.clock(),provider_key=getattr(tripo,'fingerprint',''))
            # The marker and request reservation are committed before any POST.
            parts[part_id][kind+'_attempt']=attempt
            conn.execute("UPDATE studio_jobs SET state='submitting',parts=?,updated=? WHERE id=?",
                (json.dumps(parts),self.clock(),job['id']))
        return attempt

    def record_build_bill(self,job,parts):
        actual=sum(p.get(key) or 0 for p in parts.values() for key in ('credits_consumed','image_credits_consumed')
                   if type(p.get(key)) in (int,float) and math.isfinite(p[key]) and p[key]>=0)
        with self.db.transaction() as conn:record_tester_bill(conn,job['id']+':build',actual)

    def record_attempt(self,attempt,result):
        if attempt:
            with self.db.transaction() as conn:tripo_budget.record_result(conn,attempt,result,self.clock())

    async def draw_concept(self,job,body,mesh_model,plan,parts,provenance):
        """Text-only crafts: a concept picture of the designed object (Tripo text-to-image, 5 credits) that
        the player approves before the 3D build, which then uses it as its reference image. Skipped (the
        text build stays) when it would pass the per-craft cap or the server budget; a failed picture
        never fails the craft. Proxy (development) crafts get a drawn placeholder, no Tripo."""
        limits=self.limits_for_job(job)
        part=plan['parts'][0];entry=parts[part['id']]
        concept=dict(provenance.get('concept') or {'draws':0})
        textured=body.material=='textured'
        with self.db.read() as conn:spent=tripo_budget.attempt_credits(conn,job['id'])
        if body.geometry=='tripo':
            cap=limits.max_credits_per_craft
            if cap and spent+CONCEPT_CREDITS+mesh_credits(mesh_model,textured,True)>cap:
                provenance['concept_skipped']='over_cap';return
            if limits.tripo_credit_budget:
                with self.db.transaction() as conn:committed=tripo_credits_committed(conn,job['id'])
                if committed+spent+CONCEPT_CREDITS>limits.tripo_credit_budget:
                    provenance['concept_skipped']='budget';return
        # A product-style render: the picture becomes Tripo's image reference, so believable shapes and
        # materials give a better model. Style words in the description (cute, anime...) still win.
        # Tripo rebuilds only what the picture shows: the whole object, small enough to leave wide margins
        # (an object touching the edge came back cut, task 73).
        prompt=('Concept art of ONLY this object. A zoomed-out full shot: the ENTIRE object centred with wide empty margins '
                '(at least 15% of the picture) on every side, nothing touching or cut by the picture edge, no floor. '
                'Three-quarter view, plain light-grey background, soft studio lighting. Style: '+craft_styles.style(body.style)['concept']+
                ', unless the description asks for another style. No text, no people. Object: '+str(part.get('prompt','')))[:1800]
        try:
            if body.geometry!='tripo':blob=fixture_concept(str(part.get('prompt','')))
            else:
                tripo=self.provider_for(entry['key']) if entry.get('key') else await self.pick_provider(CONCEPT_CREDITS)
                with self.db.transaction() as conn:
                    attempt=tripo_budget.reserve_attempt(conn,limits,job['id'],job['owner_id'],'concept',part['id'],
                        0 if getattr(self.provider,'_in_process_fake',False) else CONCEPT_CREDITS,
                        0,self.clock(),provider_key=getattr(tripo,'fingerprint',''),
                        craft_extra=mesh_credits(mesh_model,textured,True))
                data=await tripo.request('POST','/generation/text-to-image',{'model':'seedream_v4','prompt':prompt})
                task=data.get('task_id')
                if not isinstance(task,str) or not task or len(task)>200 or '/' in task:raise ProviderError('upstream_schema',uncertain=True)
                with self.db.transaction() as conn:tripo_budget.record_task(conn,attempt,task,self.clock())
                for _ in range(80):
                    result=await tripo.task(task)
                    self.record_attempt(attempt,result)
                    if result.get('status')=='success':break
                    if result.get('status')=='banned':raise Refused('other')
                    if result.get('status') in ('failed','cancelled','expired'):raise ProviderError('concept_failed')
                    await asyncio.sleep(self.poll_pause)
                else:raise ProviderError('concept_timeout')
                credits=result.get('credits_consumed')
                entry['concept_credits_consumed']=spent+(credits if type(credits) in (int,float) else CONCEPT_CREDITS)
                blob=await tripo.fetch_image(image_url(result.get('output') or {}))
                entry.update(key=getattr(tripo,'fingerprint',''),concept_task=task,concept_attempt=attempt)
        except ProviderError as error:
            if 'attempt' in locals():
                with self.db.transaction() as conn:tripo_budget.mark_unknown(conn,attempt,self.clock())
            if error.code in ('tester_credit_budget_exhausted','tripo_budget_exhausted','craft_over_trial_limit'):raise
            # Tripo refused the picture for its content: the 3D build would be refused too, so the craft ends here.
            if error.code.startswith('refused_'):raise
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

    def part_colour(self,plan,parts,part,entry,body):
        """A game-made part's colour (a clock hand): the craft style's hand colour that stands out on
        the dial, sampled from the finished body's texture (or its plan colour)."""
        dial=next((p for p in plan['parts'] if p['id']==part['parent']),plan['parts'][0])
        shade=clock_hands.rgb(dial['color'])
        built=parts.get(dial['id'],{})
        if body.material=='textured' and body.geometry=='tripo' and built.get('file'):
            try:shade=clock_hands.dial_colour((self.assets/built['file']).read_bytes(),dial['color'])
            except OSError:pass
        return clock_hands.colours(body.style,shade).get(entry.get('make','minute'),part['color'])

    def guard_tripo_cap(self,job,parts):
        """Last check before a new Tripo request: the account's earlier requests plus the ones
        this job already sent must leave room for one more (live trial cap)."""
        limit=self.limits_for_job(job).user_total_generation_limit
        if not limit:return
        with self.db.transaction() as conn:used=tripo_requests(conn,job['owner_id'],job['id'])
        sent=sum(1 for p in parts.values() for k in ('task','image_task') if p.get(k))
        if used+sent>=limit:raise ProviderError('user_total_generation_limit')

    def overdue(self,parts):
        """Raises generation_timeout when a submitted part has waited on Tripo past the deadline
        (settings.studio_part_deadline). Parts submitted before deadlines existed start counting now."""
        for entry in parts.values():
            if entry.get('state') not in ('generating','image_generating'):continue
            started=entry.setdefault('submitted',self.clock())
            if self.clock()-started>self.settings.studio_part_deadline:raise ProviderError('generation_timeout')

    def refund(self,conn,row):
        tripo_budget.clear_hold(conn,row['id'])
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
            tripo_budget.clear_hold(conn,job_id)
            if state=='failed':self.refund(conn,row)

    async def tick(self):
        with self.db.transaction() as conn:
            # Recover abandoned claims without requiring another server restart.
            stale=conn.execute("SELECT studio_jobs.* FROM studio_jobs JOIN studio_leases ON job_id=id WHERE expires<=? AND state IN ('planning','submitting')",(self.clock(),)).fetchall()
            for row in stale:
                state='unknown' if row['state']=='submitting' else 'failed'
                conn.execute('UPDATE studio_jobs SET state=?,error=? WHERE id=?',(state,'worker_lease_expired',row['id']))
                tripo_budget.clear_hold(conn,row['id'])
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
        limits=self.limits_for_job(job)
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
                learned=None
                if body.designer=='fixture':
                    plan,program=demo_design(body.prompt);provenance={'provider':'authored_fixture','validation':exercise(program,[p['id'] for p in plan['parts']])}
                elif body.designer=='simple':
                    plan=simple_plan(body.prompt,look['prop'],body.dims);program={'version':1,'state':{},'functions':{},'events':{}}
                    provenance={'provider':'direct_prompt','validation':exercise(program,['whole'])}
                else:
                    style_text=craft_styles.designer_style(body.style,body.size,body.dims)
                    # A text-only request made before (same words, style, size and motion): the learned design, no LLM call.
                    learned=None if body.image else library.make_key('design',library.normalize(body.prompt),body.style,body.size,body.motion,style_text,archetypes.VERSION,DESIGN_RULES,*([body.dims] if body.dims else []))
                    with self.db.transaction() as conn:cached=library.find(conn,learned) if learned else None
                    if cached:
                        plan,program=cached['value']['plan'],cached['value']['program']
                        provenance={'provider':'library','library':{'key':learned,'made_by':cached['provider'],'origin':cached['origin']},
                            'validation':exercise(program,[p['id'] for p in plan['parts']])}
                        with self.db.transaction() as conn:library.used(conn,learned,self.clock())
                        learned=None
                    else:
                        request_prompt=body.prompt+('\nOutput ONE complete static part and an empty program.' if body.motion=='static' else '')
                        if body.image and body.image_mode=='original':
                            # A one-part craft sends this photo itself to Tripo image-to-model, which rebuilds
                            # everything in front of the background, people included (refine drops them).
                            request_prompt+='\nThis photo may be rebuilt in 3D exactly as it is, so if any real person (or part of one) appears in it, return {"refused":"person"}.'
                        with self.db.transaction() as conn:categories=[r[0] for r in conn.execute('SELECT name FROM asset_categories ORDER BY name LIMIT 100')]
                        request_prompt+='\nExisting category names (reuse a matching kind, otherwise propose a short new kind): '+json.dumps(categories,ensure_ascii=False)
                        request_prompt+=archetypes.designer_hint(body.prompt,body.motion)
                        plan,program,provenance=await llm_budget.generate(self.db,self.settings,self.clock,job['owner_id'],'craft_design',job_id,self.designer,request_prompt,body.model,body.effort,body.image,style_text)
                designed=(plan,program)
                if body.motion=='static':
                    plan=static_plan(plan,body.prompt,look['prop'],body.dims)
                    program={'version':1,'state':{},'functions':{},'events':{}}
                # Normalize generated designs through the exact same gates as local fixtures.
                plan=validate_plan(plan);exercise(program,[p['id'] for p in plan['parts']])
                category=unicodedata.normalize('NFKC',plan['category']).casefold().strip()
                plan['category']='_'.join(''.join(c if c.isalnum() else ' ' for c in category).split())[:40] or 'decoration'
                # The library type (server/archetypes.py): its behaviours start on the finished object.
                kind=archetypes.classify(body.prompt,plan)
                if kind:
                    provenance['archetype']=kind['id']
                    plan=archetypes.seat_parts(kind['id'],plan)
                provenance.update(geometry='procedural_proxy' if body.geometry=='proxy' else 'tripo',material=body.material,motion=body.motion)
                # The game sizes the finished object by size_m (0 = the designer's own size).
                provenance.update(style=body.style,size=body.size,size_m=craft_styles.meters(body.size))
                # The dragged box: its longest side is the game's size_m, its sides were the designer's target.
                if body.dims:provenance.update(dims=body.dims,size_m=max(body.dims))
                parts={p['id']:{'state':'pending'} for p in plan['parts']}
                # Role parts the game makes itself (clock hands, server/clock_hands.py): no Tripo credits.
                for part_id,make in archetypes.primitive_parts(provenance.get('archetype'),plan).items():parts[part_id].update(primitive=True,make=make)
                if body.geometry=='tripo':
                    def quote():
                        meshes=sum(1 for entry in parts.values() if not entry.get('primitive'))
                        return estimate(mesh_model,body.material=='textured',meshes,bool(body.image) and (len(plan['parts'])==1 or body.image_mode=='refine'),body.image_mode=='refine')
                    cap=limits.max_credits_per_craft
                    if cap and quote()>cap and len(plan['parts'])>1:
                        # Over the per-craft cap with its parts: one complete piece instead, with the type's
                        # whole-object behaviours, rather than no craft at all.
                        plan=static_plan(plan,body.prompt,look['prop'],body.dims)
                        program={'version':1,'state':{},'functions':{},'events':{}}
                        parts={p['id']:{'state':'pending'} for p in plan['parts']}
                        provenance['fallback']='single_piece_credit_cap'
                    provenance.update(tripo_model=mesh_model,estimated_tripo_credits=quote(),estimate_source='official_rates_and_measured_2026_10_02')
                    provenance.update(quoted_game_cost=max(job['cost'],math.ceil(provenance['estimated_tripo_credits']*self.settings.studio_credit_rate)),stars_per_credit=self.settings.studio_credit_rate,reserved_game_cost=job['cost'])
                    if cap and provenance['estimated_tripo_credits']>cap:raise ProviderError('craft_over_trial_limit')
                with self.db.transaction() as conn:existed=conn.execute('SELECT 1 FROM asset_categories WHERE name=?',(plan['category'],)).fetchone() is not None
                provenance.update(category=plan['category'],category_existed=existed,generated_api_count=len(program['functions']))
                if learned:
                    # Kept now, served once this craft has become an object.
                    provenance['library_key']=learned
                    with self.db.transaction() as conn:
                        library.remember(conn,learned,'design',library.normalize(body.prompt),library.signature(designed[0]['parts']),
                            {'plan':designed[0],'program':designed[1]},self.clock(),provider=str(provenance.get('provider') or ''),
                            origin=job_id,category=plan['category'],ready=False)
                concept=body.concept and not body.image and len(plan['parts'])==1
                if concept:
                    # The craft window shows the picture step while it is drawn.
                    self.update(job_id,provenance=json.dumps({**provenance,'stage':'concept'}))
                    await self.draw_concept(job,body,mesh_model,plan,parts,provenance)
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
            # The game's own parts come last: their colour follows the finished body.
            for p in sorted(plan['parts'],key=lambda part:bool(parts[part['id']].get('primitive'))):
                entry=parts[p['id']]
                if entry['state']=='ready':continue
                if entry.get('primitive'):
                    entry['color']=self.part_colour(plan,parts,p,entry,body)
                    blob=clock_hands.hand_glb(entry.get('make','minute'),p['size'],p['pivot'],body.geometry=='tripo')
                elif body.geometry=='proxy':blob=fixture_glb(p['shape'],textured)
                else:
                    if entry['state']=='pending' and body.image_mode=='refine':
                        self.guard_tripo_cap(job,parts)
                        tripo=await self.pick_provider(5)
                        entry['key']=getattr(tripo,'fingerprint','')
                        reference=await tripo.upload_image(body.image)
                        attempt=self.reserve_build(job,parts,provenance,p['id'],'refine',CONCEPT_CREDITS,tripo)
                        data=await tripo.request('POST','/generation/image-to-image',{'model':'seedream_v5','input':reference,
                            'prompt':'Create a clean isolated product reference of ONLY this component: '+p['prompt']+'. Preserve the reference design and soft illustrated island style. Neutral background, no text, no other components.',
                            'size':'2K','output_format':'png'})
                        task=data.get('task_id')
                        if not isinstance(task,str) or not task or len(task)>200 or '/' in task:raise ProviderError('upstream_schema',uncertain=True)
                        with self.db.transaction() as conn:tripo_budget.record_task(conn,attempt,task,self.clock())
                        entry.update(state='image_generating',image_task=task,submitted=self.clock())
                        self.update(job_id,state='building',parts=json.dumps(parts));return
                    if entry['state']=='image_generating':
                        result=await self.provider_for(entry.get('key')).task(entry['image_task'])
                        self.record_attempt(entry.get('refine_attempt'),result)
                        if result.get('credits_consumed') is not None:
                            entry['image_credits_consumed']=result['credits_consumed']
                            self.record_build_bill(job,parts)
                        if result.get('status') in ('queued','running'):
                            track(entry,result);self.overdue(parts)
                            self.update(job_id,state='building',parts=json.dumps(parts));return
                        if result.get('status')=='banned':raise Refused('other')
                        if result.get('status') in ('failed','cancelled','expired'):raise ProviderError('image_refinement_failed')
                        if result.get('status')!='success':raise ProviderError('upstream_schema',uncertain=True)
                        entry.update(state='image_ready',image_credits_consumed=result.get('credits_consumed'));entry.pop('progress',None)
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
                        attempt=self.reserve_build(job,parts,provenance,p['id'],'mesh',predicted,tripo)
                        data=await tripo.request('POST',route,payload)
                        task=data.get('task_id')
                        if not isinstance(task,str) or not task or len(task)>200 or '/' in task:raise ProviderError('upstream_schema',uncertain=True)
                        with self.db.transaction() as conn:tripo_budget.record_task(conn,attempt,task,self.clock())
                        entry.update(state='generating',task=task,key=getattr(tripo,'fingerprint',''),submitted=self.clock())
                        self.update(job_id,state='building',parts=json.dumps(parts),provenance=json.dumps(provenance))
                        return
                    tripo=self.provider_for(entry.get('key'))
                    result=await tripo.task(entry['task'])
                    self.record_attempt(entry.get('mesh_attempt'),result)
                    if result.get('credits_consumed') is not None:
                        entry['credits_consumed']=result['credits_consumed']
                        self.record_build_bill(job,parts)
                    if result.get('status') in ('queued','running'):
                        track(entry,result);self.overdue(parts)
                        self.update(job_id,state='building',parts=json.dumps(parts));return
                    # Tripo's content check banned the task: refused, not a held (unknown) submission.
                    if result.get('status')=='banned':raise Refused('other')
                    if result.get('status') in ('failed','cancelled','expired'):raise ProviderError('generation_failed')
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
            for p in plan['parts']:
                p.update(file=parts[p['id']]['file'],sha256=parts[p['id']]['sha256'])
                if parts[p['id']].get('color'):p['color']=parts[p['id']]['color']
            with self.db.read() as conn:
                managed=conn.execute('SELECT 1 FROM tripo_job_holds WHERE job_id=?',(job_id,)).fetchone()
                provenance.update((tripo_budget.job_billing(conn,job_id) if managed else billing(parts)) if body.geometry=='tripo' else {'tripo_credits_consumed':0,'known_tripo_credits':0,'billing_complete':True})
            provenance['image_refinement_credits']=sum(p.get('image_credits_consumed') or 0 for p in parts.values())
            assigned=None
            if provenance.get('archetype'):
                try:assigned=archetypes.assign(provenance['archetype'],plan,program,body.style)
                except interactions.InteractionError as error:provenance['behaviour_error']=error.code
                if assigned:provenance['behaviour']={'archetype':provenance['archetype'],'presets':len(assigned['spec']['presets']),'rest':assigned['spec']['rest']}
            effective=assigned['compiled']['program'] if assigned and assigned['compiled'] else program
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
                initial=AssetVM(effective,interactions.targets_of(plan['parts']));initial.run('spawn')
                conn.execute('INSERT INTO studio_runtime(object_id,state) VALUES (?,?)',(obj,json.dumps(initial.state)))
                if assigned:interactions.attach(conn,obj,assigned,self.clock())
                if provenance.get('library_key'):library.mark_ready(conn,provenance['library_key'])
                conn.execute('INSERT OR IGNORE INTO asset_categories VALUES (?,?)',(plan['category'],self.clock()))
                conn.execute("UPDATE studio_jobs SET state='ready',object_id=?,provenance=?,updated=?,error=NULL WHERE id=?",(obj,json.dumps(provenance),self.clock(),job_id))
                tripo_budget.clear_hold(conn,job_id)
        except asyncio.CancelledError:raise
        except ProviderError as error:
            if isinstance(error,DesignFailure):
                # Rejected output still consumed LLM tokens; never label it free.
                self.update(job_id,provenance=json.dumps({'provider':provider_name(self.settings),
                    'model':body.model,'effort':body.effort,'usage':error.usage,'attempts':error.attempts,
                    'tripo_credits_consumed':0,'known_tripo_credits':0,'billing_complete':True}))
            # Poll/download errors keep the paid task ID. Never submit it again; past the part's deadline
            # the craft fails (and is refunded) instead of waiting on Tripo forever.
            if 'parts' in locals() and any((p.get('task') and p['state']=='generating') or (p.get('image_task') and p['state']=='image_generating') for p in parts.values()) and error.code in ('upstream_unreachable','upstream_unavailable','upstream_rate_limit','asset_download_failed','key_not_configured','upstream_authentication','upstream_non_json','upstream_invalid_json'):
                try:
                    self.overdue(parts)
                    self.update(job_id,state='building',error=error.code,parts=json.dumps(parts));return
                except ProviderError as late:error=late
            self.error(job_id,error)
        except Exception:self.error(job_id,ProviderError('studio_validation_failed'))
