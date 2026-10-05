"""One-process authoritative prototype. Run behind HTTPS for remote use."""
import asyncio
import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from .config import Settings, ROOT
from .database import Database
from .models import Credentials, Mutation, ObjectEdit, Input, Generate, Listing, RunStart, Avatar, AvatarEdit, LifeAction
from .provider import TripoProvider, ProviderError, validate_glb
from . import simulation, catalog, homestead, campaign
from .security import BodyLimitMiddleware
from .stored_assets import read_glb

def uid(): return str(uuid.uuid4())
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def fail(code, status=409): raise HTTPException(status, code)
def obj_public(row):
    return {k: row[k] for k in ('id','name','color','version','state','x','z','rotation')}

def create_app(settings=None, clock=time.time, provider=None, worker_enabled=True, designer=None):
    settings = settings or Settings()
    settings.validate()
    db = Database(settings.data_dir/'world.sqlite3',settings.mode)
    provider = provider or TripoProvider(settings)
    hasher = PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1)
    dummy = hasher.hash(secrets.token_urlsafe(32))
    assets = settings.data_dir/'assets'
    assets.mkdir(exist_ok=True)
    sample = (ROOT/'game/assets/sample_stool.glb').read_bytes()
    validate_glb(sample)
    sample_path = assets/'starter.glb'
    if not sample_path.exists():
        sample_path.write_bytes(sample)
    with db.transaction() as conn:
        conn.execute('INSERT OR IGNORE INTO assets VALUES (?,?,?,?)',
                     ('starter','starter.glb',hashlib.sha256(sample).hexdigest(),'authored_sample'))
        expected = conn.execute("SELECT digest FROM assets WHERE id='starter'").fetchone()[0]
        if hashlib.sha256(sample_path.read_bytes()).hexdigest() != expected:
            raise ValueError('Stored starter asset integrity check failed')
        # A crash between submit and saving its task id must never cause a second paid call.
        conn.execute("UPDATE jobs SET state='unknown',error_code='submission_interrupted' WHERE state='submitting'")

    def auth(conn, request):
        value = request.headers.get('authorization','')
        if not value.startswith('Bearer ') or len(value)>256: fail('login_required',401)
        row = conn.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id '
                           'WHERE token_hash=? AND expires>?',(digest(value[7:]),clock())).fetchone()
        if not row: fail('session_expired',401)
        return row

    def session(conn,user_id):
        token = secrets.token_urlsafe(32)
        conn.execute('DELETE FROM sessions WHERE expires<?',(clock(),))
        conn.execute('INSERT INTO sessions VALUES (?,?,?)',(digest(token),user_id,clock()+settings.session_seconds))
        return {'token':token,'mode':settings.mode}

    def money(conn,user_id,amount,reason,reference):
        conn.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)',(uid(),user_id,amount,reason,reference,clock()))
        if conn.execute('UPDATE users SET shards=shards+? WHERE id=? AND shards+?>=0',
                        (amount,user_id,amount)).rowcount != 1: fail('insufficient_shards')

    def own(conn,user_id,object_id,version=None):
        row = conn.execute('SELECT * FROM objects WHERE id=? AND owner_id=?',(object_id,user_id)).fetchone()
        if not row: fail('object_not_found',404)
        if version is not None and row['version'] != version: fail('stale_object_version')
        return row

    def new_object(conn,user_id,asset_id,name):
        object_id = uid()
        conn.execute('INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) VALUES (?,?,?,?,?,?)',
                     (object_id,user_id,user_id,asset_id,name,clock()))
        return object_id

    def mutate(request, body, operation, callback):
        with db.transaction() as conn:
            user = auth(conn,request)
            fingerprint = digest(body.model_dump_json())
            previous = conn.execute('SELECT * FROM requests WHERE user_id=? AND request_id=?',
                                   (user['id'],str(body.request_id))).fetchone()
            if previous:
                if previous['operation'] != operation or previous['fingerprint'] != fingerprint:
                    fail('request_id_reused')
                return json.loads(previous['response'])
            result = callback(conn,user)
            conn.execute('INSERT INTO requests VALUES (?,?,?,?,?,?)',
                         (user['id'],str(body.request_id),operation,fingerprint,json.dumps(result),clock()))
            conn.execute('INSERT INTO audit(user_id,action,target,outcome,created) VALUES (?,?,?,?,?)',
                         (user['id'],operation,None,'accepted',clock()))
            return result

    def job_error(job_id,error):
        with db.transaction() as conn:
            job = conn.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if job['state'] in ('ready','failed','unknown'): return
            state = 'unknown' if error.uncertain else 'failed'
            conn.execute('UPDATE jobs SET state=?,error_code=?,updated=? WHERE id=?',
                         (state,error.code,clock(),job_id))
            if state=='failed': money(conn,job['owner_id'],job['cost'],'generation_refund',job_id)

    async def process_job(job_id):
        with db.transaction() as conn:
            job = dict(conn.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())
            if job['state'] not in ('queued','generating'):
                return
            if job['state']=='queued':
                conn.execute("UPDATE jobs SET state='submitting',updated=? WHERE id=?",(clock(),job_id))
        try:
            if settings.mode=='demo':
                blob = sample
            else:
                if job['state']=='queued':
                    # The global worker serializes balance checks and provider submissions.
                    available = await provider.balance()
                    if available < settings.credit_reserve: raise ProviderError('insufficient_provider_credit')
                    task = await provider.submit(job['prompt'])
                    with db.transaction() as conn:
                        conn.execute("UPDATE jobs SET state='generating',provider_task=?,updated=? WHERE id=?",(task,clock(),job_id))
                    job['provider_task'] = task
                result = await provider.task(job['provider_task'])
                if result.get('status') in ('queued','running'): return
                if result.get('status') in ('failed','cancelled'): raise ProviderError('generation_failed')
                if result.get('status') != 'success': raise ProviderError('upstream_schema',uncertain=True)
                url = result.get('output',{}).get('model_url')
                if not isinstance(url,str): raise ProviderError('model_url_missing')
                blob = await provider.download(url)
            validate_glb(blob)
            asset_id = uid()
            (assets/(asset_id+'.glb')).write_bytes(blob)
            with db.transaction() as conn:
                conn.execute('INSERT INTO assets VALUES (?,?,?,?)',
                             (asset_id,asset_id+'.glb',hashlib.sha256(blob).hexdigest(),settings.mode))
                object_id = new_object(conn,job['owner_id'],asset_id,('샘플 · ' if settings.mode=='demo' else '')+job['prompt'][:32])
                conn.execute("UPDATE jobs SET state='ready',asset_id=?,object_id=?,updated=? WHERE id=?",
                             (asset_id,object_id,clock(),job_id))
        except ProviderError as error:
            # Safe failures only; raw requests/responses (and keys) never escape this boundary.
            if settings.mode=='live' and job.get('provider_task') and error.code in (
                'upstream_unreachable','upstream_unavailable','upstream_rate_limit','asset_download_failed',
                'upstream_authentication','upstream_non_json','upstream_invalid_json','upstream_rejected'):
                # Keep the paid task ID and retry polling/downloading; never generate again.
                with db.transaction() as conn:
                    conn.execute('UPDATE jobs SET error_code=?,updated=? WHERE id=?',(error.code,clock(),job_id))
                return
            job_error(job_id,error)

    async def worker():
        while True:
            with db.transaction() as conn:
                jobs = [r['id'] for r in conn.execute("SELECT id FROM jobs WHERE state IN ('queued','generating') AND (error_code IS NULL OR updated<?) ORDER BY created LIMIT 10",(clock()-30,))]
            for job_id in jobs:
                try: await process_job(job_id)
                except asyncio.CancelledError: raise
                except Exception:
                    job_error(job_id,ProviderError('worker_internal',uncertain=True))
            await studio.tick()
            await asyncio.sleep(2)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(worker()) if worker_enabled else None
        yield
        if task:
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass

    app = FastAPI(title='Tripothon authoritative server',version='0.6.0',lifespan=lifespan,
                  docs_url=None,redoc_url=None,openapi_url=None)
    app.state.db,app.state.settings,app.state.process_job = db,settings,process_job
    rates = defaultdict(deque)
    last_rate_cleanup = 0

    @app.middleware('http')
    async def boundary(request,call_next):
        nonlocal last_rate_cleanup
        # No cookie authentication and no CORS. Remote login requires a trusted HTTPS proxy.
        if settings.mode=='demo' and request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
            return JSONResponse({'detail':'demo_is_local_only'},403)
        if settings.mode=='live' and request.url.scheme!='https':
            return JSONResponse({'detail':'https_required'},400)
        now = clock()
        identity = request.client.host if request.client else 'unknown'
        is_auth = request.url.path.startswith('/v1/auth/')
        if not is_auth and request.headers.get('authorization', '').startswith('Bearer '):
            try:
                with db.read() as conn:
                    identity = 'user:' + auth(conn, request)['id']
            except HTTPException:
                pass
        key = (identity,'auth' if is_auth else 'general')
        if now-last_rate_cleanup >= 60:
            for old_key, old_queue in list(rates.items()):
                if not old_queue or old_queue[-1] <= now-60:
                    del rates[old_key]
            last_rate_cleanup = now
        if key not in rates and len(rates) >= 4096:
            return JSONResponse({'detail':'rate_limited'},429)
        queue = rates[key]
        while queue and queue[0] <= now-60: queue.popleft()
        if len(queue) >= (20 if is_auth else 1200): return JSONResponse({'detail':'rate_limited'},429)
        queue.append(now)
        response = await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return JSONResponse({'detail':'invalid_request'},422)

    @app.exception_handler(ProviderError)
    async def protected_asset_error(request,exc):
        return JSONResponse({'detail':'asset_integrity_failed' if exc.code=='asset_integrity_failed' else 'service_unavailable'},503,
                            headers={'Cache-Control':'no-store'})

    @app.get('/health')
    def health(): return {'ok':True,'service':'tripothon','mode':settings.mode,'version':'0.8.1','protocol':6,
                          'studio_tripo_enabled':bool(settings.tripo_key and settings.paid_enabled),
                          'studio_llm':settings.studio_llm, 'multiplayer_protocol':1, 'max_party_members':3}

    def life_state(conn,user_id):
        row=conn.execute('SELECT state FROM homesteads WHERE user_id=?',(user_id,)).fetchone()
        return json.loads(row['state']) if row else homestead.initial()

    @app.get('/v1/homestead')
    def get_life(request:Request):
        with db.read() as conn:
            user=auth(conn,request)
            return homestead.public(life_state(conn,user['id']),clock())

    @app.post('/v1/homestead')
    def edit_life(body:LifeAction,request:Request):
        def edit(conn,user):
            state=life_state(conn,user['id'])
            try: result=homestead.act(state,body,clock())
            except homestead.Rejected as error: fail(str(error))
            conn.execute('INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state',
                         (user['id'],json.dumps(state)))
            return result
        return mutate(request,body,'homestead',edit)

    def profile(conn,user_id):
        row=conn.execute('SELECT avatar,version FROM profiles WHERE user_id=?',(user_id,)).fetchone()
        return {'avatar':json.loads(row['avatar']),'version':row['version']} if row else {'avatar':Avatar().model_dump(),'version':0}

    @app.post('/v1/profile')
    def edit_profile(body:AvatarEdit,request:Request):
        def save(conn,user):
            previous=profile(conn,user['id'])
            if body.version!=previous['version']: fail('stale_profile_version')
            value=body.avatar.model_dump()
            version=previous['version']+1
            conn.execute('INSERT INTO profiles VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET avatar=excluded.avatar,version=excluded.version',
                         (user['id'],json.dumps(value),version))
            return {'avatar':value,'version':version}
        return mutate(request,body,'profile_edit',save)

    @app.post('/v1/auth/register')
    def register(body:Credentials):
        if settings.mode=='live' and not secrets.compare_digest(body.invitation.encode(),settings.registration_code.encode()):
            fail('invalid_invitation',403)
        password_hash = hasher.hash(body.password)
        with db.transaction() as conn:
            user_id = uid()
            try:
                conn.execute('INSERT INTO users VALUES (?,?,?,?,?)',(user_id,body.username.lower(),password_hash,0,clock()))
            except sqlite3.IntegrityError: fail('username_unavailable')
            new_object(conn,user_id,'starter','환영의 나무 의자')
            if settings.mode=='demo': money(conn,user_id,80,'demo_welcome',user_id)
            return session(conn,user_id)

    @app.post('/v1/auth/login')
    def login(body:Credentials):
        with db.read() as conn:
            user = conn.execute('SELECT * FROM users WHERE username=?',(body.username.lower(),)).fetchone()
        try: hasher.verify(user['password_hash'] if user else dummy,body.password)
        except VerificationError: fail('invalid_credentials',401)
        if not user: fail('invalid_credentials',401)
        with db.transaction() as conn:
            return session(conn,user['id'])

    @app.post('/v1/auth/logout')
    def logout(request:Request):
        with db.transaction() as conn:
            user=auth(conn,request)
            conn.execute('DELETE FROM mp_presence WHERE user_id=?',(user['id'],))
            conn.execute('DELETE FROM sessions WHERE token_hash=?',(digest(request.headers['authorization'][7:]),))
        return {'ok':True}

    @app.get('/v1/me')
    def me(request:Request):
        with db.read() as conn:
            user = auth(conn,request)
            active = conn.execute("SELECT id,state FROM runs WHERE owner_id=? AND status='active'",(user['id'],)).fetchone()
            active_summary = None
            if active:
                snapshot=simulation.public_state(json.loads(active['state']))
                active_summary={k:snapshot[k] for k in ('day','elapsed','hp','hunger','map_id','difficulty')}
            pending_reward = conn.execute("SELECT id,reward,state FROM runs WHERE owner_id=? AND status='won' AND claimed=0 ORDER BY created LIMIT 1",(user['id'],)).fetchone()
            pending_job = conn.execute("SELECT id FROM jobs WHERE owner_id=? AND state IN ('queued','submitting','generating','unknown') ORDER BY created LIMIT 1",(user['id'],)).fetchone()
            return {'username':user['username'],'shards':user['shards'],'mode':settings.mode,
                'generation_enabled': settings.mode=='demo' or bool(settings.legacy_generation_enabled and settings.tripo_key and settings.paid_enabled),
                'studio_tripo_enabled': bool(settings.tripo_key and settings.paid_enabled),
                'generation_cost':25,'profile':profile(conn,user['id']),'catalog':catalog.public_catalog(),'campaign':campaign.public(conn,user['id']),
                'active_run':active['id'] if active else None,
                'active_run_summary':active_summary,
                'pending_reward':{'id':pending_reward['id'],'reward':pending_reward['reward']+campaign.pending_bonus(conn,user['id'],json.loads(pending_reward['state']))} if pending_reward else None,
                'pending_job':pending_job['id'] if pending_job else None,
                'objects':[{**obj_public(r),'room':r['room'],'studio':bool(r['studio']),'runtime_version':r['runtime_version']} for r in conn.execute("SELECT objects.*,COALESCE(furniture_locations.room,'village') AS room,CASE WHEN studio_assets.asset_id IS NULL THEN 0 ELSE 1 END AS studio,(SELECT version FROM studio_runtime WHERE object_id=objects.id) AS runtime_version FROM objects LEFT JOIN furniture_locations ON furniture_locations.object_id=objects.id LEFT JOIN studio_assets ON studio_assets.asset_id=objects.asset_id WHERE owner_id=? ORDER BY created",(user['id'],))]}

    @app.post('/v1/objects/{object_id}')
    def edit_object(object_id:str,body:ObjectEdit,request:Request):
        def edit(conn,user):
            row = own(conn,user['id'],object_id,body.version)
            if row['state']=='listed': fail('object_is_listed')
            if body.action=='paint':
                conn.execute('UPDATE objects SET color=?,version=version+1 WHERE id=?',(body.color.lower(),object_id))
            elif body.action=='retrieve':
                conn.execute("UPDATE objects SET state='inventory',x=NULL,z=NULL,version=version+1 WHERE id=?",(object_id,))
            else:
                # Uniform 2x2 parcel; matches normalized 1.6m props on the client.
                if row['state']!='inventory': fail('retrieve_before_moving')
                if not homestead.village_inside(body.x, body.z): fail('outside_room')
                reserved = homestead.village_reserved(body.x, body.z)
                if reserved: fail(reserved)
                other = conn.execute("SELECT x,z FROM objects LEFT JOIN furniture_locations ON object_id=objects.id WHERE owner_id=? AND state='placed' AND COALESCE(room,'village')='village'",(user['id'],)).fetchall()
                if len(other)>=30: fail('village_full')
                if any(abs(r['x']-body.x)<2 and abs(r['z']-body.z)<2 for r in other): fail('placement_overlap')
                from . import room_budget
                try:room_budget.check(conn,assets,user['id'],'village',object_id,row['asset_id'])
                except ProviderError as error:fail(error.code,409 if error.code=='room_render_budget_exceeded' else 503)
                conn.execute("UPDATE objects SET state='placed',x=?,z=?,rotation=?,version=version+1 WHERE id=?",
                             (body.x,body.z,body.rotation,object_id))
                conn.execute("INSERT INTO furniture_locations VALUES (?,'village') ON CONFLICT(object_id) DO UPDATE SET room='village'",(object_id,))
            return obj_public(own(conn,user['id'],object_id))
        return mutate(request,body,'object:'+object_id,edit)

    @app.get('/v1/objects/{object_id}/model')
    def model(object_id:str,request:Request):
        with db.transaction() as conn:
            user = auth(conn,request)
            row = own(conn,user['id'],object_id)
            asset = conn.execute('SELECT * FROM assets WHERE id=?',(row['asset_id'],)).fetchone()
            # Read while holding ownership transaction. No signed/public download links.
            blob = read_glb(assets,asset['relative_path'],asset['digest'])
            return Response(blob,media_type='model/gltf-binary',headers={'Cache-Control':'no-store'})

    @app.post('/v1/runs')
    def start(body:RunStart,request:Request):
        def create(conn,user):
            if multiplayer.active_coop(conn,user['id']): fail('party_expedition_active')
            existing = conn.execute("SELECT id FROM runs WHERE owner_id=? AND status='active'",(user['id'],)).fetchone()
            if existing: return {'id':existing['id']}
            region=body.map_id
            if body.chapter_id:
                chapter=next(c for c in campaign.public(conn,user['id']) if c['id']==body.chapter_id)
                if not chapter['unlocked']:fail('chapter_locked')
                region=chapter['map_id']
            run_id=uid(); state=simulation.new_run(secrets.randbits(32),clock(),settings.day_seconds,region,body.difficulty)
            state['chapter_id']=body.chapter_id
            conn.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?)',(run_id,user['id'],json.dumps(state),'active',0,0,clock()))
            return {'id':run_id}
        return mutate(request,body,'run_start',create)

    def own_run(conn,user_id,run_id):
        row=conn.execute('SELECT * FROM runs WHERE id=? AND owner_id=?',(run_id,user_id)).fetchone()
        if not row: fail('run_not_found',404)
        return row

    def run_reply(conn,user_id,row,state):
        if row['claimed']:
            recorded=conn.execute("SELECT amount FROM ledger WHERE user_id=? AND reason='story_reward' AND reference=(SELECT chapter_id FROM campaign_progress WHERE user_id=? AND completed_run=?)",(user_id,user_id,row['id'])).fetchone()
            bonus=recorded[0] if recorded else 0
        else:bonus=campaign.pending_bonus(conn,user_id,state)
        return dict(id=row['id'],reward=row['reward']+bonus,story_bonus=bonus,claimed=bool(row['claimed']),**simulation.public_state(state))

    @app.get('/v1/runs/{run_id}')
    def get_run(run_id:str,request:Request):
        with db.read() as conn:
            user=auth(conn,request); row=own_run(conn,user['id'],run_id)
            return run_reply(conn,user['id'],row,json.loads(row['state']))

    @app.post('/v1/runs/{run_id}/input')
    def run_input(run_id:str,body:Input,request:Request):
        with db.transaction() as conn:
            user=auth(conn,request); row=own_run(conn,user['id'],run_id); state=json.loads(row['state'])
            if body.sequence <= state['sequence']: fail('stale_input')
            state['sequence']=body.sequence
            simulation.advance(state,clock(),body.dx,body.dz,body.sprint)
            if body.action: state['message']=simulation.action(state,body.action,body.target)
            award=simulation.reward(state)
            conn.execute('UPDATE runs SET state=?,status=?,reward=? WHERE id=?',(json.dumps(state),state['status'],award,run_id))
            return run_reply(conn,user['id'],{**dict(row),'reward':award},state)

    @app.post('/v1/runs/{run_id}/claim')
    def claim(run_id:str,body:Mutation,request:Request):
        def finish(conn,user):
            row=own_run(conn,user['id'],run_id)
            if row['status']!='won': fail('run_not_won')
            if row['claimed']: fail('reward_already_claimed')
            state=json.loads(row['state']);bonus=campaign.pending_bonus(conn,user['id'],state)
            if bonus:
                conn.execute('INSERT INTO campaign_progress VALUES (?,?,?,?)',(user['id'],state['chapter_id'],run_id,clock()))
                money(conn,user['id'],bonus,'story_reward',state['chapter_id'])
            money(conn,user['id'],row['reward'],'survival_reward',run_id)
            conn.execute('UPDATE runs SET claimed=1 WHERE id=?',(run_id,))
            return {'reward':row['reward']+bonus,'story_bonus':bonus,'chapter_completed':state.get('chapter_id') if bonus else None}
        return mutate(request,body,'claim:'+run_id,finish)

    @app.post('/v1/runs/{run_id}/abandon')
    def abandon(run_id:str,body:Mutation,request:Request):
        def stop(conn,user):
            row=own_run(conn,user['id'],run_id)
            if row['status']=='active':
                state=json.loads(row['state']); state['status']='abandoned'
                conn.execute("UPDATE runs SET status='abandoned',state=? WHERE id=?",(json.dumps(state),run_id))
            return {'ok':True}
        return mutate(request,body,'abandon:'+run_id,stop)

    @app.post('/v1/generations')
    def generate(body:Generate,request:Request):
        if settings.mode=='live' and not settings.legacy_generation_enabled:
            fail('legacy_generation_disabled',403)
        def queue(conn,user):
            if settings.mode=='live' and conn.execute("SELECT 1 FROM studio_jobs WHERE state NOT IN ('ready','failed','cancelled')").fetchone():fail('provider_busy')
            if settings.mode=='live' and not (settings.tripo_key and settings.paid_enabled): fail('live_generation_disabled',503)
            if conn.execute("SELECT 1 FROM jobs WHERE owner_id=? AND state IN ('queued','submitting','generating','downloading','unknown')",(user['id'],)).fetchone(): fail('generation_pending')
            count=conn.execute('SELECT count(*) FROM jobs WHERE created>=?',(int(clock()//86400)*86400,)).fetchone()[0]
            if count >= settings.daily_generation_limit: fail('daily_generation_limit',429)
            # One live job globally avoids overlapping credit reservations. Unknown holds the lock.
            if settings.mode=='live' and conn.execute("SELECT 1 FROM jobs WHERE state IN ('queued','submitting','generating','unknown')").fetchone(): fail('provider_busy')
            job_id=uid(); money(conn,user['id'],-25,'generation_charge',job_id)
            conn.execute('INSERT INTO jobs(id,owner_id,prompt,state,cost,provider_reserve,created,updated) VALUES (?,?,?,?,?,?,?,?)',
                         (job_id,user['id'],body.prompt.strip(),'queued',25,settings.credit_reserve,clock(),clock()))
            return {'id':job_id,'state':'queued','mode':settings.mode}
        return mutate(request,body,'generate',queue)

    @app.get('/v1/generations/{job_id}')
    def job(job_id:str,request:Request):
        with db.transaction() as conn:
            user=auth(conn,request)
            row=conn.execute('SELECT id,state,object_id,error_code FROM jobs WHERE id=? AND owner_id=?',(job_id,user['id'])).fetchone()
            if not row: fail('job_not_found',404)
            return dict(row)

    @app.get('/v1/market')
    def market(request:Request):
        with db.transaction() as conn:
            user=auth(conn,request)
            return {'listings':[dict(r) for r in conn.execute("SELECT listings.id,objects.name,objects.color,listings.price,users.username AS seller,"
                "CASE WHEN seller_id=? THEN 1 ELSE 0 END AS mine FROM listings JOIN objects ON objects.id=listings.object_id "
                "JOIN users ON users.id=listings.seller_id WHERE listings.state='open' LIMIT 100",(user['id'],))]}

    @app.post('/v1/market')
    def list_object(body:Listing,request:Request):
        # Kept as a separate transaction callback so ownership and listing commit together.
        def create(conn,user):
            row=own(conn,user['id'],str(body.object_id),body.version)
            if row['state']!='inventory': fail('object_not_in_inventory')
            listing_id=uid()
            conn.execute('INSERT INTO listings VALUES (?,?,?,?,?,?,?)',(listing_id,row['id'],user['id'],body.price,'open',None,clock()))
            conn.execute("UPDATE objects SET state='listed',version=version+1 WHERE id=?",(row['id'],))
            return {'id':listing_id}
        return mutate(request,body,'list',create)

    @app.post('/v1/market/{listing_id}/{action}')
    def trade(listing_id:str,action:str,body:Mutation,request:Request):
        if action not in ('buy','cancel'): fail('unknown_action',404)
        def transfer(conn,user):
            row=conn.execute('SELECT * FROM listings WHERE id=? AND state=\'open\'',(listing_id,)).fetchone()
            if not row: fail('listing_unavailable')
            item=own(conn,row['seller_id'],row['object_id'])
            if item['state']!='listed': fail('listing_unavailable')
            if action=='cancel':
                if row['seller_id']!=user['id']: fail('listing_not_found',404)
                conn.execute("UPDATE listings SET state='cancelled' WHERE id=?",(listing_id,))
                conn.execute("UPDATE objects SET state='inventory',version=version+1 WHERE id=?",(row['object_id'],))
            else:
                if row['seller_id']==user['id']: fail('cannot_buy_own')
                money(conn,user['id'],-row['price'],'purchase',listing_id)
                money(conn,row['seller_id'],row['price'],'sale',listing_id)
                conn.execute("UPDATE listings SET state='sold',buyer_id=? WHERE id=?",(user['id'],listing_id))
                conn.execute("UPDATE objects SET owner_id=?,state='inventory',version=version+1,x=NULL,z=NULL WHERE id=?",(user['id'],row['object_id']))
            return {'ok':True}
        return mutate(request,body,'market:'+listing_id+':'+action,transfer)

    from .asset_studio import Studio
    studio=Studio(app,db,settings,clock,provider,auth,mutate,money,own,new_object,assets,designer,profile)
    app.state.studio=studio
    from .multiplayer import Multiplayer
    multiplayer=Multiplayer(app,db,settings,clock,auth,mutate,money,profile,assets)
    app.state.multiplayer=multiplayer
    app.add_middleware(BodyLimitMiddleware,limit=8192,path_limits={'/v1/studio/jobs':1500000})
    return app
