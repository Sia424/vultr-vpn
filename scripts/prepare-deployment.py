#!/usr/bin/env python3
"""Build a private remote installer; does not connect or deploy."""
import json
import os
import re
import shlex
from project_config import ROOT, load_environment

env = load_environment()
if env['server']['ssh_user'] != 'root':
    raise SystemExit('Fresh installer requires root SSH; adapt explicitly before deployment.')
release = json.loads((ROOT / 'config/release.json').read_text())
for field, pattern in [('xray_version', r'\d+\.\d+\.\d+'),
                       ('installer_commit', r'[0-9a-f]{40}'),
                       ('installer_sha256', r'[0-9a-f]{64}'),
                       ('xray_sha256', r'[0-9a-f]{64}')]:
    if not re.fullmatch(pattern, release[field]):
        raise SystemExit('Invalid pinned release metadata')
settings = {
    'VPN_EXPECTED_HOSTNAME': env['server']['expected_hostname'],
    'VPN_SSH_PORT': env['server']['ssh_port'],
    'VPN_PORT': env['reality']['port'],
    'VPN_SERVER_NAME': env['reality']['server_name'],
    'VPN_XRAY_VERSION': release['xray_version'],
    'VPN_XRAY_SHA256': release['xray_sha256'],
    'VPN_INSTALLER_COMMIT': release['installer_commit'],
    'VPN_INSTALLER_SHA256': release['installer_sha256'],
}
content = '#!/usr/bin/env bash\nset -euo pipefail\n'
content += ''.join('export ' + key + '=' + shlex.quote(str(value)) + '\n' for key, value in settings.items())
content += (ROOT / 'scripts/deploy-server.sh').read_text()
os.umask(0o077)
path = ROOT / 'private/deployment-bundle.sh'
if path.exists() and path.read_text() != content:
    raise SystemExit('Deployment bundle differs; back up and review before replacing.')
if not path.exists():
    with path.open('x') as stream:
        stream.write(content)
path.chmod(0o600)
print('Prepared private/deployment-bundle.sh; no server changes made.')
