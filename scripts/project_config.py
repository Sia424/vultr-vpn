#!/usr/bin/env python3
"""Load one private environment; never print it as part of an error."""
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def resolve_path(value, root=ROOT):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_environment(root=ROOT):
    try:
        env = json.loads((root / 'private/environment.json').read_text())
        server, reality, client = env['server'], env['reality'], env['client']
        if not isinstance(server['host'], str):
            raise ValueError()
        address = ipaddress.IPv4Address(server['host'])
        if not address.is_global:
            raise ValueError()
        for field in ('expected_hostname', 'ssh_user'):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,252}', server[field]):
                raise ValueError()
            if server[field].startswith('REPLACE_'):
                raise ValueError()
        for port in (server['ssh_port'], reality['port']):
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError()
        if server['ssh_port'] == reality['port']:
            raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', reality['server_name']):
            raise ValueError()
        if not isinstance(client['node_name'], str) or not client['node_name'].strip():
            raise ValueError()
        if client['node_name'] in ('DIRECT', 'PROXY') or any(ord(c) < 32 for c in client['node_name']):
            raise ValueError()
        for section, key in [('server', 'ssh_key'), ('server', 'known_hosts'),
                             ('client', 'mihomo_binary'), ('client', 'geodata_dir')]:
            value = env[section][key]
            if not isinstance(value, str) or not value or value.startswith('REPLACE_'):
                raise ValueError()
        if client.get('runtime_config') is not None:
            if not isinstance(client['runtime_config'], str) or not client['runtime_config']:
                raise ValueError()
        artifacts = resolve_path(env['paths']['artifacts_dir'], root)
        artifacts.relative_to((root / 'private').resolve())
        return env
    except (OSError, ValueError, TypeError, KeyError):
        raise SystemExit('Invalid or missing private/environment.json; follow docs/DEPLOY.md. Values hidden.') from None


def artifacts_dir(env, root=ROOT):
    return resolve_path(env['paths']['artifacts_dir'], root)


def ssh_command(env, command, root=ROOT):
    server = env['server']
    return ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'ConnectTimeout=15', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=' + str(resolve_path(server['known_hosts'], root)),
            '-i', str(resolve_path(server['ssh_key'], root)), '-p', str(server['ssh_port']),
            server['ssh_user'] + '@' + server['host'], command]


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if action == 'init':
        os.umask(0o077)
        (ROOT / 'private/credentials').mkdir(parents=True, exist_ok=True)
        (ROOT / 'private/generated').mkdir(exist_ok=True)
        (ROOT / 'private/records').mkdir(exist_ok=True)
        (ROOT / 'private/backups').mkdir(exist_ok=True)
        (ROOT / 'private').chmod(0o700)
        try:
            with (ROOT / 'private/environment.json').open('x') as stream:
                stream.write((ROOT / 'config/environment.example.json').read_text())
        except FileExistsError:
            raise SystemExit('Environment already exists; nothing overwritten.') from None
        print('Created private/environment.json; fill placeholders before deployment.')
    elif action == 'check':
        load_environment()
        print('Environment schema valid; no network or credentials displayed.')
    elif action == 'ssh':
        args = sys.argv[2:]
        command = args[0] if len(args) == 1 else shlex.join(args)
        result = subprocess.run(ssh_command(load_environment(), command))
        raise SystemExit(result.returncode)
    else:
        raise SystemExit('Usage: project_config.py [init|check|ssh <remote command>]')


if __name__ == '__main__':
    main()
