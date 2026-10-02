"""Reconcile a held job from a trusted server terminal after provider-record review.

No HTTP administrator endpoint exists. Every mutation first creates a private backup.
Never paste an API key into command arguments or the evidence reference.
"""
import argparse
import asyncio
from contextlib import closing
from datetime import datetime,timezone
import json
import re
from pathlib import Path
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.backups import readonly,create_backup,BackupError
from server.config import Settings,read_tripo_key
from server.database import Database
from server.operations import OperationError,attach_task,refund_not_submitted
from server.provider import TripoProvider,ProviderError


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--backup-root',type=Path)
    parser.add_argument('--job-id',type=uuid.UUID)
    parser.add_argument('--evidence-reference')
    parser.add_argument('--key-file',type=Path)
    commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('list-held')
    attach=commands.add_parser('attach-task')
    attach.add_argument('--task-id',required=True)
    refund=commands.add_parser('refund-not-submitted')
    refund.add_argument('--verified-not-submitted',action='store_true')
    args=parser.parse_args()
    try:
        path=args.data_dir.resolve()/'world.sqlite3'
        with closing(readonly(path)) as conn:
            mode=conn.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()[0]
            if args.action=='list-held':
                rows=conn.execute("SELECT id,state,provider_task,error_code,cost,updated FROM jobs WHERE state='unknown' ORDER BY created").fetchall()
                print(json.dumps({'ok':True,'jobs':[dict(zip(('id','state','provider_task','error_code','cost','updated'),r)) for r in rows]}))
                return 0
        if mode!='live': raise OperationError('reconciliation_requires_live_database')
        if not args.job_id or not args.backup_root or not args.evidence_reference:
            raise OperationError('job_backup_and_evidence_required')
        status=None
        if args.action=='attach-task':
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',args.task_id):
                raise OperationError('invalid_provider_task')
            settings=Settings(tripo_key=read_tripo_key(args.key_file)) if args.key_file else Settings()
            result=await TripoProvider(settings).task(args.task_id)
            status=result.get('status')
        elif not args.verified_not_submitted:
            raise OperationError('confirm_provider_non_submission_required')
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        create_backup(args.data_dir,args.backup_root/('reconcile-'+stamp))
        db=Database(path,mode)
        if args.action=='attach-task':
            result=attach_task(db,str(args.job_id),args.task_id,status,args.evidence_reference)
        else:
            result=refund_not_submitted(db,str(args.job_id),args.evidence_reference,verified=True)
        print(json.dumps({'ok':True,**result}))
        return 0
    except (OperationError,ProviderError,BackupError) as error:
        print(json.dumps({'ok':False,'error':str(error)}))
    except Exception:
        print(json.dumps({'ok':False,'error':'operator_configuration_or_storage_error'}))
    return 1

if __name__=='__main__': sys.exit(asyncio.run(main()))
