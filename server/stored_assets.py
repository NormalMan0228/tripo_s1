"""Bounded, hash-verified reads of immutable server-private model files."""
import hashlib
from .backups import asset_path,BackupError
from .provider import ProviderError

def read_glb(assets,filename,expected_hash):
    try:
        path=asset_path(assets.parent,filename)
        with path.open('rb') as source:blob=source.read(20*1024*1024+1)
        if len(blob)>20*1024*1024 or hashlib.sha256(blob).hexdigest()!=expected_hash:
            raise ProviderError('asset_integrity_failed')
        return blob
    except (OSError,BackupError):raise ProviderError('asset_integrity_failed') from None
