"""Private server backups. Restore always creates a new data directory."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.backups import create_backup, verify_backup, restore_backup, BackupError

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest='action',required=True)
    create=actions.add_parser('create')
    create.add_argument('--data-dir',type=Path,required=True)
    create.add_argument('--destination',type=Path,required=True)
    verify=actions.add_parser('verify')
    verify.add_argument('--snapshot',type=Path,required=True)
    restore=actions.add_parser('restore')
    restore.add_argument('--snapshot',type=Path,required=True)
    restore.add_argument('--destination',type=Path,required=True)
    restore.add_argument('--mode',choices=['demo','live'],required=True)
    args=parser.parse_args()
    try:
        if args.action=='create': result=create_backup(args.data_dir,args.destination)
        elif args.action=='verify': result=verify_backup(args.snapshot)
        else: result=restore_backup(args.snapshot,args.destination,args.mode)
        print(json.dumps({'ok':True,'action':args.action,'mode':result['mode'],'counts':result['counts']}))
        return 0
    except BackupError as error:
        print(json.dumps({'ok':False,'error':str(error)}))
    except Exception:
        print(json.dumps({'ok':False,'error':'backup_io_or_format_error'}))
    return 1

if __name__=='__main__': sys.exit(main())
