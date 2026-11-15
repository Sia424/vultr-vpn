#!/usr/bin/env python3
"""Scan public worktree, index and reachable Git history without echoing secrets."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOTS = {'AGENTS.md', 'README.md', 'ROADMAP.md', 'DESIGN.md', 'DEPLOYMENT.md',
                'MAINTENANCE.md', 'LICENSE', '.gitignore'}
PUBLIC_DIRS = {'scripts', 'templates', 'config', 'docs', 'tests'}
PATTERNS = [
    re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    re.compile(rb'vless://[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}'),
    re.compile(rb'(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}'),
    re.compile(rb'/' + rb'Users' + rb'/[^/\s<>]+/'),
    re.compile(rb'/' + rb'home' + rb'/[^/\s<>]+/'),
]


def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True)
    if result.returncode:
        raise SystemExit('Git scan failed; resolve repository access before publishing.')
    return result.stdout


def allowed_path(name):
    path = Path(name)
    return name in PUBLIC_ROOTS or (
        path.parts[0] in PUBLIC_DIRS
        and all(part not in {'__pycache__', '.env', '.DS_Store'} for part in path.parts)
        and path.suffix not in {'.pem', '.key', '.pyc', '.log'}
        and not path.name.startswith('.env'))


def known_private_values():
    values = []
    example = json.loads((ROOT / 'config/environment.example.json').read_text())
    generic_values = {example['server']['host'], example['server']['expected_hostname'],
                      example['client']['node_name']}
    env_path = ROOT / 'private/environment.json'
    if env_path.exists():
        env = json.loads(env_path.read_text())
        values.extend(env['server'].get(k, '') for k in ('host', 'expected_hostname'))
        values.append(env['client'].get('node_name', ''))
        artifact_path = Path(env['paths']['artifacts_dir']).expanduser()
        if not artifact_path.is_absolute():
            artifact_path = ROOT / artifact_path
        credentials = artifact_path / 'node-credentials.json'
        if credentials.exists():
            data = json.loads(credentials.read_text())
            values.extend(data.get(k, '') for k in ('uuid', 'private_key', 'public_key', 'short_id'))
    # Legacy imports remain private, too; never require these for a fresh clone.
    for file in (ROOT / 'private').rglob('*') if (ROOT / 'private').exists() else []:
        if file.is_file() and file.name in {'vultr-api-key', 'instance.json'}:
            if file.name == 'instance.json':
                data = json.loads(file.read_text())
                values.extend(data.get(k, '') for k in ('id', 'main_ip', 'default_password'))
            else:
                values.append(file.read_text().strip())
    return [v.encode() for v in values if isinstance(v, str) and len(v) >= 8
            and v not in generic_values and not v.startswith('REPLACE_')]


def content_safe(content, private_values):
    return not any(p.search(content) for p in PATTERNS) and not any(v in content for v in private_values)


def main():
    private_values = known_private_values()
    problems = []
    files = git('ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')
    count = 0
    for name in filter(None, files):
        path = ROOT / name
        if not allowed_path(name) or path.is_symlink():
            problems.append('Disallowed public path: ' + name)
        elif path.exists():
            count += 1
            if not content_safe(path.read_bytes(), private_values):
                problems.append('Private value or sensitive pattern in worktree: ' + name)
    staged = git('ls-files', '--stage', '-z').decode().split('\0')
    for entry in filter(None, staged):
        meta, name = entry.split('\t', 1)
        mode, oid, stage = meta.split()
        if mode == '120000' or stage != '0' or not allowed_path(name):
            problems.append('Disallowed staged entry: ' + name)
        elif not content_safe(git('cat-file', 'blob', oid), private_values):
            problems.append('Sensitive staged content: ' + name)
    history_blobs = 0
    for line in git('rev-list', '--objects', '--all').decode().splitlines():
        parts = line.split(' ', 1)
        oid = parts[0]
        kind = git('cat-file', '-t', oid).strip()
        if kind == b'blob':
            history_blobs += 1
            name = parts[1] if len(parts) == 2 else '<unnamed>'
            if not allowed_path(name) or not content_safe(git('cat-file', 'blob', oid), private_values):
                problems.append('Sensitive or disallowed reachable history blob: ' + name)
    if problems:
        print('\n'.join(problems))
        raise SystemExit(1)
    print(f'PASS: {count} public files, index and {history_blobs} reachable history blobs scanned; values hidden.')
    print('Pattern scanning is limited; review the publish list and commit identity separately.')


if __name__ == '__main__':
    main()
