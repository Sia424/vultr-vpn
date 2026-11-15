#!/usr/bin/env python3
"""Read one configured node and generate private client artifacts."""
import argparse
import copy
import json
import os
import subprocess
from urllib.parse import quote, urlencode
from project_config import ROOT, artifacts_dir, load_environment, ssh_command


def build_artifacts(env, credentials, server_config):
    """Reject stale deployment credentials before generating any client files."""
    try:
        inbound = next(x for x in server_config['inbounds'] if x['tag'] == 'vless-reality')
        reality = inbound['streamSettings']['realitySettings']
        valid = (
            inbound['protocol'] == 'vless'
            and inbound['port'] == credentials['port'] == env['reality']['port']
            and credentials['server_name'] == env['reality']['server_name']
            and credentials['server_name'] in reality['serverNames']
            and credentials['short_id'] in reality['shortIds']
            and credentials['private_key'] == reality['privateKey']
            and any(c['id'] == credentials['uuid'] and c.get('flow') == 'xtls-rprx-vision'
                    for c in inbound['settings']['clients'])
            and bool(credentials['public_key']))
        if not valid:
            raise ValueError()
    except (KeyError, TypeError, StopIteration, ValueError):
        raise SystemExit('Server config and deployment credentials differ; review privately before export.') from None
    node = {
        'name': env['client']['node_name'], 'type': 'vless',
        'server': env['server']['host'], 'port': credentials['port'],
        'uuid': credentials['uuid'], 'flow': 'xtls-rprx-vision',
        'network': 'tcp', 'udp': True, 'packet-encoding': 'xudp',
        'tls': True, 'servername': credentials['server_name'],
        'client-fingerprint': 'chrome',
        'reality-opts': {'public-key': credentials['public_key'],
                        'short-id': credentials['short_id'], 'support-x25519mlkem768': True},
    }
    profile = {
        'mixed-port': 17890, 'allow-lan': False, 'bind-address': '127.0.0.1',
        'mode': 'rule', 'log-level': 'silent', 'ipv6': False,
        'tun': {'enable': False}, 'dns': {'enable': False},
        'proxies': [node],
        'proxy-groups': [{'name': 'PROXY', 'type': 'select', 'proxies': [node['name']]}],
        'rules': ['MATCH,PROXY'],
    }
    import_profile = copy.deepcopy(json.loads((ROOT / 'templates/clash-profile.yaml').read_text()))
    import_profile['proxies'] = [node]
    import_profile['proxy-groups'][0]['proxies'] = [node['name']]
    objects = {'node-credentials.json': credentials, 'xray-config.json': server_config,
               'clash-node.yaml': {'proxies': [node]}, 'clash-profile.yaml': import_profile,
               'clash-test-profile.yaml': profile}
    files = {name: json.dumps(value, indent=2) + '\n' for name, value in objects.items()}
    query = urlencode({'encryption': 'none', 'security': 'reality', 'type': 'tcp',
                       'flow': 'xtls-rprx-vision', 'sni': credentials['server_name'], 'fp': 'chrome',
                       'pbk': credentials['public_key'], 'sid': credentials['short_id']})
    files['node-url.txt'] = ('Clash: import clash-profile.yaml for standalone use; this URI does not carry routing or the Mihomo MLKEM option.\n'
                             + f'vless://{credentials["uuid"]}@{env["server"]["host"]}:{credentials["port"]}?{query}#{quote(node["name"], safe="")}\n')
    return files


def save_artifacts(destination, files):
    # Preflight all conflicts before creating files; a disk failure is not transactional.
    for name, content in files.items():
        path = destination / name
        if path.exists() and path.read_text() != content:
            raise SystemExit(f'{name} differs; nothing written. Back up and review before replacing.')
    os.umask(0o077)
    destination.mkdir(parents=True, exist_ok=True)
    destination.chmod(0o700)
    for name, content in files.items():
        path = destination / name
        if not path.exists():
            with path.open('x') as stream:
                stream.write(content)
        path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', action='store_true', help='Read existing private copies; no SSH')
    parser.add_argument('--check', action='store_true', help='Validate credentials and generated JSON; write nothing')
    args = parser.parse_args()
    env = load_environment()
    destination = artifacts_dir(env)
    if args.local:
        credentials = json.loads((destination / 'node-credentials.json').read_text())
        server_config = json.loads((destination / 'xray-config.json').read_text())
    else:
        def read_remote(path):
            result = subprocess.run(ssh_command(env, 'cat ' + path), capture_output=True, timeout=30)
            if result.returncode:
                raise SystemExit('Private SSH read failed; inspect access without printing credentials.')
            return json.loads(result.stdout)
        credentials = read_remote('/root/vultr-vpn-deployment/credentials.json')
        server_config = read_remote('/usr/local/etc/xray/config.json')
    files = build_artifacts(env, credentials, server_config)
    if args.check:
        for name, content in files.items():
            if name.endswith(('.json', '.yaml')) and (destination / name).exists():
                if json.loads((destination / name).read_text()) != json.loads(content):
                    raise SystemExit(f'{name}: generated JSON differs; no writes made.')
        print('Credentials and available generated JSON match; URI text not compared; no writes made.')
    else:
        save_artifacts(destination, files)
        print('Saved private node artifacts; contents hidden.')


if __name__ == '__main__':
    main()
