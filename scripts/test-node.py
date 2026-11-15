#!/usr/bin/env python3
"""Run a temporary loopback-only Mihomo process and check real proxy requests."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import uuid
from project_config import ROOT, artifacts_dir, load_environment, resolve_path

ENV = load_environment()
PRIVATE = artifacts_dir(ENV)
WORK = ROOT / '.tmp/deploy-node'
CORE = str(resolve_path(ENV['client']['mihomo_binary']))
if not Path(CORE).is_file():
    raise SystemExit('Configured Mihomo binary missing; check private/environment.json')
os.umask(0o077)
WORK.mkdir(parents=True, exist_ok=True)
profile = json.loads((PRIVATE / 'clash-test-profile.yaml').read_text())
assert profile['proxies'][0]['reality-opts']['support-x25519mlkem768'] is True
port = profile['mixed-port']

def curl(url):
    return subprocess.run(['curl', '--silent', '--show-error', '--fail',
        '--connect-timeout', '10', '--max-time', '25', '--noproxy', '',
        '--proxy', f'socks5h://127.0.0.1:{port}', url], capture_output=True, text=True)

def check_config(path):
    result = subprocess.run([CORE, '-t', '-d', str(WORK), '-f', str(path)], capture_output=True)
    if result.returncode:
        raise SystemExit('Mihomo config validation failed; contents hidden')

def run_profile(path, callback):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', port))
    process = subprocess.Popen([CORE, '-d', str(WORK), '-f', str(path)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise SystemExit('Temporary Mihomo process exited early')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise SystemExit('Temporary test listener not ready')
        callback()
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
        log = output.decode(errors='replace')
        secrets_to_hide = json.loads((PRIVATE / 'node-credentials.json').read_text())
        for key, value in secrets_to_hide.items():
            if isinstance(value, str) and key != 'server_name':
                log = log.replace(value, '<REDACTED>')
        (WORK / 'mihomo-test.log').write_text(log)

results = {}
valid_path = PRIVATE / 'clash-test-profile.yaml'
check_config(valid_path)
print('Mihomo configuration: OK', flush=True)

def positive():
    trace = curl('https://www.cloudflare.com/cdn-cgi/trace')
    if trace.returncode:
        raise SystemExit(f'HTTPS through node failed (curl {trace.returncode}): {trace.stderr.strip()}')
    fields = dict(line.split('=', 1) for line in trace.stdout.splitlines() if '=' in line)
    expected_ip = ENV['server']['host']
    if fields.get('ip') != expected_ip:
        raise SystemExit('Proxy exit does not match instance IPv4')
    results['https'] = True
    results['exit_ip'] = fields['ip']
    results['exit_country'] = fields.get('loc')
    print('HTTPS and exit IPv4: OK', flush=True)
    other = curl('https://www.wikipedia.org/')
    if other.returncode:
        raise SystemExit(f'Second HTTPS site failed (curl {other.returncode})')
    results['second_https_site'] = True
    print('Second HTTPS site: OK', flush=True)
    blocked = curl('http://169.254.169.254/')
    if blocked.returncode == 0:
        raise SystemExit('Metadata address unexpectedly accessible through node')
    results['metadata_blocked'] = True
    print('Metadata address blocked: OK', flush=True)

run_profile(valid_path, positive)
negative = copy.deepcopy(profile)
negative['proxies'][0]['uuid'] = str(uuid.uuid4())
negative_path = PRIVATE / 'clash-negative-test.yaml'
negative_path.write_text(json.dumps(negative, indent=2)+'\n')
negative_path.chmod(0o600)
check_config(negative_path)

def invalid_credentials():
    result = curl('https://www.cloudflare.com/cdn-cgi/trace')
    if result.returncode == 0:
        raise SystemExit('Invalid credentials unexpectedly accepted')
    results['invalid_uuid_rejected'] = True
    print('Invalid UUID rejected: OK', flush=True)

run_profile(negative_path, invalid_credentials)
run_profile(valid_path, positive)
(WORK / 'connection-results.json').write_text(json.dumps(results, indent=2)+'\n')
print('Temporary Mihomo processes stopped; system proxy and TUN untouched.')
