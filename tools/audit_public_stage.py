"""Reject private data and oversized files from the staged public Git snapshot."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import PurePosixPath

sys.path.insert(0, '.')
from server.config import read_tripo_key


def git(*args):
    return subprocess.check_output(['git', *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file')
    args = parser.parse_args()
    key = read_tripo_key(args.key_file) if args.key_file else ''
    needles = [key.encode(), key.encode('utf-16-le')] if key else []
    paths = [p.decode('utf-8') for p in git('ls-files', '-z').split(b'\0') if p]
    issues = []
    total = 0
    for name in paths:
        path = PurePosixPath(name)
        parts = {part.casefold() for part in path.parts}
        if parts & {'.tools', 'artifacts', 'builds', 'server-data', '.godot', '__pycache__'}:
            issues.append((name, 'private_or_generated_directory'))
        if path.suffix.casefold() in {'.db', '.sqlite', '.sqlite3', '.key', '.pem'} or path.name in {'.env', 'tripo_key.txt'}:
            issues.append((name, 'private_file_type'))
        blob = git('show', ':' + name)
        total += len(blob)
        if len(blob) > 100_000_000:
            issues.append((name, 'oversized_git_file'))
        if any(needle in blob for needle in needles):
            issues.append((name, 'known_tripo_key_match'))
        if re.search(rb'(?i)(?:gho_|ghp_|github_pat_|sk-proj-)[A-Za-z0-9_-]{16,}', blob):
            issues.append((name, 'credential_pattern'))
    result = {'files': len(paths), 'bytes': total, 'known_key_checked': bool(key), 'issues': issues}
    print(json.dumps(result))
    return bool(issues)


if __name__ == '__main__':
    sys.exit(main())
