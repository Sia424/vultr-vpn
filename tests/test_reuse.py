"""Offline safety and reuse tests; no real hosts or credentials required."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import project_config as config


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


export = load_script('export_node', 'export-node.py')
public = load_script('check_public', 'check-public.py')


class ReuseTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / '.tmp/public-refactor-tests'
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'private').mkdir()
        self.env = json.loads((ROOT / 'config/environment.example.json').read_text())
        self.env['server'].update(host='8.8.8.8', expected_hostname='example-vpn')
        self.env['client'].update(mihomo_binary='tools/mihomo', geodata_dir='tools/geodata')

    def save_env(self):
        (self.root / 'private/environment.json').write_text(json.dumps(self.env))

    def test_missing_and_placeholder_environment_rejected_without_values(self):
        with self.assertRaises(SystemExit) as caught:
            config.load_environment(self.root)
        self.assertNotIn(str(self.root), str(caught.exception))
        self.env['server']['host'] = 'REPLACE_WITH_PUBLIC_IPV4'
        self.save_env()
        with self.assertRaises(SystemExit):
            config.load_environment(self.root)

    def test_invalid_ports_and_artifact_escape_rejected(self):
        for bad in (0, 65536, True, '443', self.env['server']['ssh_port']):
            self.env['reality']['port'] = bad
            self.save_env()
            with self.assertRaises(SystemExit):
                config.load_environment(self.root)
        self.env['reality']['port'] = 443
        self.env['paths']['artifacts_dir'] = 'docs/generated'
        self.save_env()
        with self.assertRaises(SystemExit):
            config.load_environment(self.root)

    def test_relative_paths_and_strict_ssh_target(self):
        self.save_env()
        env = config.load_environment(self.root)
        self.assertEqual(config.artifacts_dir(env, self.root), self.root / 'private/generated')
        command = config.ssh_command(env, 'hostname', self.root)
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertEqual(command[-2:], ['root@8.8.8.8', 'hostname'])
        self.assertIn(str(self.root / 'private/credentials/ssh-ed25519'), command)

    def test_invalid_host_type_and_reserved_node_names_rejected(self):
        self.env['server']['host'] = 134744072
        self.save_env()
        with self.assertRaises(SystemExit):
            config.load_environment(self.root)
        self.env['server']['host'] = '8.8.8.8'
        for name in ('DIRECT', 'PROXY', 'name\nline'):
            self.env['client']['node_name'] = name
            self.save_env()
            with self.assertRaises(SystemExit):
                config.load_environment(self.root)

    def credentials_and_config(self):
        credentials = {'uuid': str(uuid.uuid4()), 'private_key': 'synthetic-private',
                       'public_key': 'synthetic-public', 'short_id': 'synthetic-id',
                       'port': 443, 'server_name': 'www.cloudflare.com'}
        server = json.loads((ROOT / 'templates/xray-config.json').read_text())
        inbound = server['inbounds'][0]
        inbound['settings']['clients'][0]['id'] = credentials['uuid']
        reality = inbound['streamSettings']['realitySettings']
        reality['privateKey'] = credentials['private_key']
        reality['shortIds'] = [credentials['short_id']]
        return credentials, server

    def test_generated_profiles_use_new_user_and_canonical_rules(self):
        credentials, server = self.credentials_and_config()
        self.env['client']['node_name'] = 'Independent-Node'
        files = export.build_artifacts(self.env, credentials, server)
        profile = json.loads(files['clash-profile.yaml'])
        self.assertEqual(profile['proxies'][0]['server'], self.env['server']['host'])
        self.assertEqual(profile['proxy-groups'][0]['proxies'], ['Independent-Node'])
        self.assertTrue(profile['proxies'][0]['reality-opts']['support-x25519mlkem768'])
        self.assertEqual(profile['rules'], json.loads((ROOT / 'templates/clash-profile.yaml').read_text())['rules'])
        self.assertNotIn('rules', json.loads(files['clash-node.yaml']))
        self.assertTrue(files['node-url.txt'].splitlines()[1].startswith('vless://'))
        self.assertIn('clash-profile.yaml', files['node-url.txt'].splitlines()[0])

    def test_stale_credentials_rejected(self):
        credentials, server = self.credentials_and_config()
        server['inbounds'][0]['settings']['clients'][0]['id'] = str(uuid.uuid4())
        with self.assertRaises(SystemExit):
            export.build_artifacts(self.env, credentials, server)

    def test_export_conflict_writes_nothing_and_preserves_original(self):
        destination = self.root / 'private/generated'
        destination.mkdir()
        (destination / 'existing.json').write_text('original')
        with self.assertRaises(SystemExit):
            export.save_artifacts(destination, {'new.json': 'new', 'existing.json': 'replacement'})
        self.assertFalse((destination / 'new.json').exists())
        self.assertEqual((destination / 'existing.json').read_text(), 'original')

    def test_generated_files_are_private(self):
        destination = self.root / 'private/generated'
        export.save_artifacts(destination, {'test.json': '{}'})
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        self.assertEqual((destination / 'test.json').stat().st_mode & 0o777, 0o600)

    def test_public_scanner_detects_secret_and_forbidden_path(self):
        self.assertFalse(public.allowed_path('private/environment.json'))
        self.assertFalse(public.allowed_path('docs/debug.log'))
        self.assertTrue(public.allowed_path('config/environment.example.json'))
        self.assertFalse(public.content_safe(b'value=' + b'synthetic-secret', [b'synthetic-secret']))
        key = b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----'
        self.assertFalse(public.content_safe(key, []))
        uri = ('vless://' + str(uuid.uuid4()) + '@example.invalid').encode()
        self.assertFalse(public.content_safe(uri, []))

    def test_fresh_copy_initializes_without_authors_private_files(self):
        for directory in ('scripts', 'config'):
            (self.root / directory).mkdir()
        for filename in ('scripts/project_config.py', 'config/environment.example.json'):
            (self.root / filename).write_bytes((ROOT / filename).read_bytes())
        command = [sys.executable, str(self.root / 'scripts/project_config.py'), 'init']
        result = subprocess.run(command, cwd=self.root, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual((self.root / 'private/environment.json').stat().st_mode & 0o777, 0o600)
        before = (self.root / 'private/environment.json').read_bytes()
        result = subprocess.run(command, cwd=self.root, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'private/environment.json').read_bytes(), before)
        with patch.object(public, 'ROOT', self.root):
            self.assertEqual(public.known_private_values(), [])

    def test_prepare_bundle_uses_environment_and_wrong_host_is_rejected(self):
        self.save_env()
        for directory in ('scripts', 'config'):
            (self.root / directory).mkdir()
        for filename in ('scripts/project_config.py', 'scripts/prepare-deployment.py',
                         'scripts/deploy-server.sh', 'config/release.json'):
            (self.root / filename).write_bytes((ROOT / filename).read_bytes())
        self.env['reality'].update(port=8443, server_name='www.example.com')
        self.env['server']['expected_hostname'] = 'intentional-hostname-mismatch'
        self.save_env()
        result = subprocess.run([sys.executable, str(self.root / 'scripts/prepare-deployment.py')],
                                cwd=self.root, capture_output=True)
        self.assertEqual(result.returncode, 0)
        bundle = self.root / 'private/deployment-bundle.sh'
        self.assertIn('export VPN_PORT=8443', bundle.read_text())
        self.assertIn('export VPN_SERVER_NAME=www.example.com', bundle.read_text())
        result = subprocess.run(['bash', str(bundle)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_installer_without_prepared_parameters_fails_before_changes(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('VPN_')}
        result = subprocess.run(['bash', str(ROOT / 'scripts/deploy-server.sh')],
                                env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Use prepare-deployment.py', result.stderr)


if __name__ == '__main__':
    unittest.main()
