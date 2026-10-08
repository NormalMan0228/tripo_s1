"""Consistent private snapshots. Assets are immutable after DB publication."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile


class BackupError(Exception):
    pass


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def asset_path(root, name):
    # The server only publishes a single filename, never arbitrary relative paths.
    if not isinstance(name, str) or not name.endswith('.glb') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.' for c in name):
        raise BackupError('invalid_asset_path')
    path = root / 'assets' / name
    if path.is_symlink() or path.resolve().parent != (root / 'assets').resolve():
        raise BackupError('invalid_asset_path')
    return path


def paint_path(root, name):
    # Painted textures live in assets/paint as '<object_id>.<sha256>.png' (server/object_paint.py).
    stem, _, rest = name.partition('.') if isinstance(name, str) else ('', '', '')
    checksum = rest[:-4] if rest.endswith('.png') else ''
    if (not stem or len(stem) > 64 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in stem)
            or len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum)):
        raise BackupError('invalid_paint_path')
    path = root / 'assets' / 'paint' / name
    if path.is_symlink() or path.resolve().parent != (root / 'assets' / 'paint').resolve():
        raise BackupError('invalid_paint_path')
    return path


def paint_files(db):
    """[(file name, sha256)] of every current painted texture; older databases have none."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='object_paint'").fetchone():
        return []
    return [(f'{object_id}.{checksum}.png', checksum) for object_id, checksum in
            db.execute('SELECT object_id,sha256 FROM object_paint WHERE sha256 IS NOT NULL ORDER BY object_id')]


def inspect_database(path):
    with closing(readonly(path)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise BackupError('database_integrity_failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise BackupError('database_foreign_key_failed')
        mode = db.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()
        if not mode or mode[0] not in ('demo', 'live'):
            raise BackupError('invalid_database_mode')
        if db.execute('SELECT 1 FROM objects o LEFT JOIN assets a ON o.asset_id=a.id WHERE a.id IS NULL LIMIT 1').fetchone():
            raise BackupError('missing_asset_record')
        files = db.execute('SELECT relative_path,digest FROM assets ORDER BY relative_path').fetchall()
        if len({name for name, _ in files}) != len(files):
            raise BackupError('duplicate_asset_path')
        # The assets row names only the first mesh of an assembly. Include every
        # published part and downloaded work-in-progress part from this snapshot.
        # Older databases do not have the studio tables yet.
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        collected = dict(files)
        def collect(part):
            if not isinstance(part, dict):
                raise BackupError('invalid_studio_part_record')
            name, checksum = part.get('file'), part.get('sha256')
            if not isinstance(name, str) or not isinstance(checksum, str) or len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
                raise BackupError('invalid_studio_part_record')
            if name in collected and collected[name] != checksum:
                raise BackupError('conflicting_asset_digest')
            collected[name] = checksum
        try:
            if 'studio_assets' in tables:
                for (encoded,) in db.execute('SELECT manifest FROM studio_assets'):
                    for part in json.loads(encoded)['plan']['parts']:
                        collect(part)
            if 'studio_jobs' in tables:
                for (encoded,) in db.execute('SELECT parts FROM studio_jobs'):
                    parts = json.loads(encoded)
                    if not isinstance(parts, dict):
                        raise BackupError('invalid_studio_part_record')
                    for part in parts.values():
                        if not isinstance(part, dict):
                            raise BackupError('invalid_studio_part_record')
                        if part.get('state') == 'ready' or 'file' in part or 'sha256' in part:
                            collect(part)
        except (ValueError, KeyError, TypeError) as error:
            raise BackupError('invalid_studio_part_record') from error
        files = sorted(collected.items())
        counts = {table: db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                  for table in ('users', 'objects', 'ledger', 'jobs')}
    return mode[0], files, counts


def create_backup(data_dir, destination):
    data_dir, destination = Path(data_dir).resolve(), Path(destination).resolve()
    if destination.exists() or destination == data_dir or data_dir in destination.parents:
        raise BackupError('destination_must_be_new_and_outside_data')
    if not (data_dir / 'world.sqlite3').is_file():
        raise BackupError('database_not_found')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.tripothon-backup-', dir=destination.parent))
    try:
        with closing(readonly(data_dir / 'world.sqlite3')) as source, closing(sqlite3.connect(stage / 'world.sqlite3')) as target:
            source.backup(target)
        mode, files, counts = inspect_database(stage / 'world.sqlite3')
        (stage / 'assets').mkdir()
        for name, expected in files:
            source, target = asset_path(data_dir, name), asset_path(stage, name)
            shutil.copyfile(source, target)
            if digest(target) != expected:
                raise BackupError('asset_digest_mismatch')
        with closing(readonly(stage / 'world.sqlite3')) as db:
            painted = paint_files(db)
        if painted:
            (stage / 'assets' / 'paint').mkdir()
        for name, expected in painted:
            source, target = paint_path(data_dir, name), paint_path(stage, name)
            shutil.copyfile(source, target)
            if digest(target) != expected:
                raise BackupError('paint_digest_mismatch')
        manifest = {'format':1, 'created_utc':datetime.now(timezone.utc).isoformat(),
                    'mode':mode, 'counts':counts, 'database_sha256':digest(stage / 'world.sqlite3'),
                    'assets':[{'name':name,'sha256':value} for name,value in files]}
        # Only written when there is paint, so earlier snapshots keep their exact manifest.
        if painted:
            manifest['paint'] = [{'name':name,'sha256':value} for name,value in painted]
        (stage / 'manifest.json').write_text(json.dumps(manifest,indent=2), encoding='utf-8')
        stage.rename(destination)
        return manifest
    except Exception:
        # Only this function's freshly created staging directory is removed.
        if stage.exists() and stage.resolve().parent == destination.parent and not stage.is_symlink() and stage.name.startswith('.tripothon-backup-'):
            shutil.rmtree(stage)
        raise


def verify_backup(snapshot):
    snapshot = Path(snapshot).resolve()
    manifest = json.loads((snapshot / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 1 or digest(snapshot / 'world.sqlite3') != manifest.get('database_sha256'):
        raise BackupError('database_digest_mismatch')
    mode, files, counts = inspect_database(snapshot / 'world.sqlite3')
    if manifest.get('mode') != mode or manifest.get('counts') != counts or manifest.get('assets') != [{'name':n,'sha256':h} for n,h in files]:
        raise BackupError('manifest_mismatch')
    for name, expected in files:
        if digest(asset_path(snapshot,name)) != expected:
            raise BackupError('asset_digest_mismatch')
    with closing(readonly(snapshot / 'world.sqlite3')) as db:
        painted = paint_files(db)
    if manifest.get('paint', []) != [{'name':n,'sha256':h} for n,h in painted]:
        raise BackupError('manifest_mismatch')
    for name, expected in painted:
        if digest(paint_path(snapshot,name)) != expected:
            raise BackupError('paint_digest_mismatch')
    return manifest


def restore_backup(snapshot, destination, expected_mode):
    snapshot, destination = Path(snapshot).resolve(), Path(destination).resolve()
    manifest = verify_backup(snapshot)
    if manifest['mode'] != expected_mode:
        raise BackupError('restore_mode_mismatch')
    if destination.exists() or destination == snapshot or snapshot in destination.parents:
        raise BackupError('restore_destination_must_not_exist')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.tripothon-restore-', dir=destination.parent))
    try:
        shutil.copyfile(snapshot / 'world.sqlite3', stage / 'world.sqlite3')
        (stage / 'assets').mkdir()
        for item in manifest['assets']:
            shutil.copyfile(asset_path(snapshot,item['name']),asset_path(stage,item['name']))
            if digest(asset_path(stage,item['name'])) != item['sha256']:
                raise BackupError('asset_digest_mismatch')
        if manifest.get('paint'):
            (stage / 'assets' / 'paint').mkdir()
        for item in manifest.get('paint', []):
            shutil.copyfile(paint_path(snapshot,item['name']),paint_path(stage,item['name']))
            if digest(paint_path(stage,item['name'])) != item['sha256']:
                raise BackupError('paint_digest_mismatch')
        if digest(stage / 'world.sqlite3') != manifest['database_sha256']:
            raise BackupError('database_digest_mismatch')
        with closing(sqlite3.connect(stage / 'world.sqlite3')) as db:
            # Restored sessions must never resurrect an earlier login.
            db.execute('DELETE FROM sessions')
            db.execute("UPDATE jobs SET state='unknown',error_code='restore_requires_reconciliation' WHERE state IN ('queued','submitting','generating','downloading')")
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'studio_jobs' in tables:
                # The provider may have received requests AFTER this snapshot.
                # Even a queued snapshot is not evidence that resubmission is safe.
                db.execute("UPDATE studio_jobs SET state='unknown',error='restore_requires_reconciliation' WHERE state NOT IN ('ready','failed','cancelled')")
            if 'studio_leases' in tables:
                db.execute('DELETE FROM studio_leases')
            db.execute("INSERT INTO audit(user_id,action,target,outcome,created) VALUES (NULL,'operator_restore',NULL,'sessions_revoked_jobs_held',strftime('%s','now'))")
            db.commit()
        stage.rename(destination)
        return manifest
    except Exception:
        if stage.exists() and stage.resolve().parent == destination.parent and not stage.is_symlink() and stage.name.startswith('.tripothon-restore-'):
            shutil.rmtree(stage)
        raise
