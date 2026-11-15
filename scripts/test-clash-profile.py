#!/usr/bin/env python3
"""Check an importable profile's routing using real requests in an isolated core."""
import copy
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from project_config import ROOT, artifacts_dir, load_environment, resolve_path

ENV = load_environment()
PRIVATE = artifacts_dir(ENV)
WORK = ROOT / '.tmp/client-routing'
CORE = str(resolve_path(ENV['client']['mihomo_binary']))
if not Path(CORE).is_file():
    raise SystemExit('Configured Mihomo binary missing; check private/environment.json')
os.umask(0o077)
args = [arg for arg in sys.argv[1:] if arg != '--live']
source = Path(args[0]) if args else PRIVATE / 'clash-profile.yaml'
config = copy.deepcopy(json.loads(source.read_text()))
split_routing = 'GEOSITE,cn,DIRECT' in config.get('rules', [])
live = '--live' in sys.argv[1:]
controller_socket = None
token = secrets.token_hex(16)
proxy_port = 17891
if live:
    if not ENV['client'].get('runtime_config'):
        raise SystemExit('Live test needs client.runtime_config and Ruby; see docs/MAINTENANCE.md')
    runtime_path = resolve_path(ENV['client']['runtime_config'])
    runtime = json.loads(subprocess.check_output(['ruby','-ryaml','-rjson','-e',
        'puts JSON.generate(YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true))',
        str(runtime_path)],stderr=subprocess.PIPE))
    controller_socket = runtime['external-controller-unix']
    token = runtime.get('secret', '')
    proxy_port = runtime['mixed-port']
# Only listener/test settings change; source proxies, groups and routing stay intact.
config.update({'mixed-port':17891, 'allow-lan':False, 'bind-address':'127.0.0.1',
               'mode':config.get('mode','rule'), 'log-level':'silent',
               'tun':{'enable':False}, 'dns':{'enable':False}})
config.pop('external-controller', None)
config.pop('external-controller-unix', None)
config['external-controller'] = '127.0.0.1:17892'
config['secret'] = token
WORK.mkdir(parents=True, exist_ok=True)
if split_routing:
    data_dir = resolve_path(ENV['client']['geodata_dir'])
    for name in ('Country.mmdb','geosite.dat'):
        shutil.copy2(data_dir / name, WORK / name)
candidate = PRIVATE / 'clash-profile-routing-test.yaml'
candidate.write_text(json.dumps(config, indent=2)+'\n')
candidate.chmod(0o600)
check = subprocess.run([CORE,'-t','-d',str(WORK),'-f',str(candidate)],capture_output=True)
if check.returncode:
    raise SystemExit('Profile syntax check failed; credentials hidden')
process = None
if not live:
    for port in (17891,17892):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            sock.bind(('127.0.0.1',port))
    process = subprocess.Popen([CORE,'-d',str(WORK),'-f',str(candidate)],
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def api(path):
    conn = http.client.HTTPConnection('127.0.0.1',17892,timeout=10)
    if controller_socket:
        conn.sock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        conn.sock.settimeout(10)
        conn.sock.connect(controller_socket)
    try:
        conn.request('GET',path,headers={'Authorization':'Bearer '+token})
        response = conn.getresponse()
        if response.status != 200:
            raise SystemExit(f'Controller GET {path}: HTTP {response.status}')
        return json.loads(response.read())
    finally:
        conn.close()

results = []
def route_check(host, expected, expected_rule=None):
    # Keep the verified TLS tunnel open while checking its actual core route.
    conn = http.client.HTTPSConnection('127.0.0.1',proxy_port,timeout=15)
    conn.set_tunnel(host,443)
    try:
        conn.connect()
        source_port = conn.sock.getsockname()[1]
        match = None
        for _ in range(20):
            match = next((c for c in api('/connections').get('connections',[])
                          if int(c.get('metadata',{}).get('sourcePort',0)) == source_port),None)
            if match:
                break
            time.sleep(0.1)
        if not match:
            raise SystemExit(f'FAIL: route evidence missing for {host}')
        chains = match.get('chains',[])
        if expected == 'DIRECT':
            assert chains == ['DIRECT'], f'{host}: expected DIRECT, got {chains}'
        else:
            assert ENV['client']['node_name'] in chains, f'{host}: configured node missing from route'
        if expected_rule:
            assert match.get('rule','').lower() == expected_rule.lower(), (host,match.get('rule'))
        conn.request('GET','/',headers={'Host':host,'Connection':'close'})
        response = conn.getresponse()
        assert 200 <= response.status < 500, (host,response.status)
        entry = {'host':host,'chains':chains,'rule':match.get('rule'),
                 'rule_payload':match.get('rulePayload'),'http_status':response.status}
        results.append(entry)
        print(json.dumps(entry,ensure_ascii=False),flush=True)
    finally:
        conn.close()

try:
    for _ in range(50) if process else ():
        if process.poll() is not None:
            raise SystemExit('Isolated core exited early')
        try:
            with socket.create_connection(('127.0.0.1',17891),timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        if process:
            raise SystemExit('Isolated listener not ready')
    if live:
        assert api('/configs').get('mode') == 'rule', 'Live client must be in rule mode'
        assert runtime.get('rules') == config.get('rules'), 'Live rules differ from the requested profile'
    def request(url, extra=()):
        return subprocess.run(['curl','--silent','--show-error','--connect-timeout','8',
            '--max-time','12','--noproxy','','--proxy',f'socks5h://127.0.0.1:{proxy_port}',
            *extra,url],capture_output=True,text=True)
    google = request('https://oauthaccountmanager.googleapis.com/',
                     ('--output','/dev/null','--write-out','%{http_code}'))
    if google.returncode:
        raise SystemExit(f'FAIL: Google HTTPS request, curl={google.returncode}, HTTP={google.stdout}')
    if not 200 <= int(google.stdout) < 500:
        raise SystemExit(f'FAIL: unexpected Google HTTP status {google.stdout}')
    print(f'Google HTTPS connected: HTTP {google.stdout}',flush=True)
    trace = request('https://www.cloudflare.com/cdn-cgi/trace')
    if trace.returncode:
        raise SystemExit(f'FAIL: exit check curl={trace.returncode}')
    fields = dict(line.split('=',1) for line in trace.stdout.splitlines() if '=' in line)
    expected = ENV['server']['host']
    if fields.get('ip') != expected:
        raise SystemExit('FAIL: traffic did not exit through the Vultr node')
    print('PASS: profile routes Google and HTTPS through the Vultr exit',flush=True)
    if split_routing:
        route_check('www.baidu.com','DIRECT','GeoSite')
        route_check('www.bilibili.com','DIRECT','GeoSite')
        route_check('223.5.5.5','DIRECT','GeoIP')
        route_check('oauthaccountmanager.googleapis.com','PROXY','DomainSuffix')
        route_check('chatgpt.com','PROXY','DomainSuffix')
        route_check('example.com','PROXY','Match')
        (WORK/'split-routing-results.json').write_text(json.dumps(results,indent=2)+'\n')
        print('PASS: domestic domains/IP direct, Google/AI and fallback through Vultr',flush=True)
finally:
    if process:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
