"""Operator-only recovery of a KNOWN provider task; never guesses or resubmits.
Stop the server using this data directory before running this maintenance tool.
"""
import argparse,asyncio,json,sys,time,uuid
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.config import Settings,read_tripo_key
from server.app import create_app
from server.backups import create_backup,readonly
from server.operations import refund_studio_not_submitted,evidence
from server.database import Database

async def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['list-held','resume-known','refund-not-submitted'])
    p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--key-file',type=Path)
    p.add_argument('--job-id',type=uuid.UUID);p.add_argument('--backup-root',type=Path)
    p.add_argument('--evidence-reference');p.add_argument('--verified-not-submitted',action='store_true');args=p.parse_args()
    with closing(readonly(args.data_dir/'world.sqlite3')) as conn:
        mode=conn.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()[0]
        if args.action=='list-held':
            rows=conn.execute("SELECT id,state,cost,error,updated FROM studio_jobs WHERE state='unknown' ORDER BY created").fetchall()
            print(json.dumps({'jobs':[dict(zip(('id','state','cost','error','updated'),r)) for r in rows]}));return
    if not args.job_id or not args.backup_root:raise RuntimeError('job_and_private_backup_required')
    evidence(args.evidence_reference);args.job_id=str(args.job_id)
    if args.action=='refund-not-submitted' and not args.verified_not_submitted:raise RuntimeError('confirm_provider_non_submission_required')
    if args.action=='resume-known' and not args.key_file:raise RuntimeError('private_key_file_required')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    create_backup(args.data_dir,args.backup_root/('studio-reconcile-'+stamp))
    if args.action=='refund-not-submitted':
        db=Database(args.data_dir/'world.sqlite3',mode)
        print(json.dumps(refund_studio_not_submitted(db,args.job_id,args.evidence_reference,verified=True)));return
    settings=Settings(data_dir=args.data_dir,mode=mode,studio_llm='fixture',paid_enabled=args.action=='resume-known',tripo_key=read_tripo_key(args.key_file) if args.key_file else '',daily_generation_limit=100)
    app=create_app(settings,worker_enabled=False)
    with app.state.db.transaction() as conn:
        row=conn.execute('SELECT * FROM studio_jobs WHERE id=?',(args.job_id,)).fetchone()
        if not row:raise RuntimeError('job_not_found')
        if row['state']=='ready':print('already_ready');return
        if row['state'] not in ('unknown','failed'):raise RuntimeError('job_not_held_or_failed')
        if conn.execute("SELECT 1 FROM ledger WHERE reason='studio_resume_refund' AND reference=?",(args.job_id,)).fetchone():raise RuntimeError('resume_already_failed_manual_audit_required')
        parts=json.loads(row['parts'])
        if not parts or any(p['state'] not in ('ready','generating') or (p['state']=='generating' and not p.get('task')) for p in parts.values()):raise RuntimeError('missing_confirmed_task_cannot_resume')
        if conn.execute('SELECT 1 FROM studio_leases WHERE job_id=? AND expires>?',(args.job_id,time.time())).fetchone():raise RuntimeError('worker_still_holds_lease')
        refunded=conn.execute("SELECT 1 FROM ledger WHERE user_id=? AND reason='studio_refund' AND reference=?",(row['owner_id'],args.job_id)).fetchone()
        if refunded and not conn.execute("SELECT 1 FROM ledger WHERE reason='studio_resume_charge' AND reference=?",(args.job_id,)).fetchone():
            if not conn.execute('UPDATE users SET shards=shards-? WHERE id=? AND shards>=?',(row['cost'],row['owner_id'],row['cost'])).rowcount:raise RuntimeError('insufficient_shards_to_resume')
            conn.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),row['owner_id'],-row['cost'],'studio_resume_charge',args.job_id,time.time()))
        conn.execute("UPDATE studio_jobs SET state='building',error=NULL WHERE id=?",(args.job_id,))
        conn.execute('INSERT INTO audit(user_id,action,target,outcome,created) VALUES (?,?,?,?,?)',(row['owner_id'],'studio_operator_resume',args.job_id,json.dumps({'action':'known_task_only','evidence':args.evidence_reference}),time.time()))
    for _ in range(180):
        await app.state.studio.process(args.job_id)
        with app.state.db.transaction() as conn:row=dict(conn.execute('SELECT state,object_id,error,provenance FROM studio_jobs WHERE id=?',(args.job_id,)).fetchone())
        if row['state'] in ('ready','failed','unknown'):
            row['provenance']=json.loads(row['provenance'] or '{}');print(json.dumps(row));return
        await asyncio.sleep(5)
    raise RuntimeError('existing_task_still_pending_no_new_submission')
if __name__=='__main__':asyncio.run(main())
