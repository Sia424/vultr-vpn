#!/usr/bin/env bash
# Render with prepare-deployment.py; run only on an authorized fresh host.
set -euo pipefail
umask 077
: "${VPN_EXPECTED_HOSTNAME:?Use prepare-deployment.py first}"
: "${VPN_PORT:?}" "${VPN_SSH_PORT:?}" "${VPN_SERVER_NAME:?}"
: "${VPN_XRAY_VERSION:?}" "${VPN_XRAY_SHA256:?}"
: "${VPN_INSTALLER_COMMIT:?}" "${VPN_INSTALLER_SHA256:?}"
[[ "$(id -u)" == 0 && "$(hostname)" == "$VPN_EXPECTED_HOSTNAME" ]]
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && "$(uname -m)" == x86_64 ]]
[[ ! -e /usr/local/bin/xray && ! -e /root/vultr-vpn-deployment ]]
for command in python3 curl ufw ss runuser sha256sum; do command -v "$command" >/dev/null; done
LC_ALL=C ufw status | grep -q '^Status: active$'
if ss -lntH "sport = :$VPN_PORT" | grep -q .; then
  echo 'Configured TCP port already in use; stopping.' >&2
  exit 1
fi

python3 - <<'PY'
import os, socket, ssl
target = os.environ['VPN_SERVER_NAME']
context = ssl.create_default_context()
context.minimum_version = ssl.TLSVersion.TLSv1_3
context.set_alpn_protocols(['h2'])
with socket.create_connection((target, 443), timeout=15) as raw:
    with context.wrap_socket(raw, server_hostname=target) as conn:
        assert conn.version() == 'TLSv1.3'
        assert conn.selected_alpn_protocol() == 'h2'
        print('REALITY target: TLS 1.3, h2, certificate verified')
PY
curl --fail --silent --show-error --max-time 20 --output /dev/null \
  --write-out 'REALITY target HTTP status: %{http_code}\n' "https://$VPN_SERVER_NAME/"

install -d -m 700 /root/vultr-vpn-deployment
cp -a /etc/ufw /root/vultr-vpn-deployment/ufw-before
ufw status numbered > /root/vultr-vpn-deployment/ufw-before.txt
cat /proc/sys/kernel/random/boot_id > /root/vultr-vpn-deployment/initial-boot-id
cd /root/vultr-vpn-deployment
curl --fail --silent --show-error --location --max-time 45 \
  "https://raw.githubusercontent.com/XTLS/Xray-install/$VPN_INSTALLER_COMMIT/install-release.sh" \
  -o install-release.sh
printf '%s  %s\n' "$VPN_INSTALLER_SHA256" install-release.sh | sha256sum --check --status
curl --fail --silent --show-error --location --max-time 120 \
  "https://github.com/XTLS/Xray-core/releases/download/v$VPN_XRAY_VERSION/Xray-linux-64.zip" \
  -o Xray-linux-64.zip
printf '%s  %s\n' "$VPN_XRAY_SHA256" Xray-linux-64.zip | sha256sum --check --status
bash install-release.sh install --local ./Xray-linux-64.zip --without-geodata --without-logfiles > installer.log 2>&1
systemctl stop xray
cp -a /usr/local/etc/xray/config.json config-before.json

python3 - <<'PY'
import json, os, re, secrets, subprocess, uuid
from pathlib import Path
os.umask(0o077)
output = subprocess.check_output(['/usr/local/bin/xray', 'x25519'], text=True)
fields = dict(re.findall(r'^([^:\n]+):\s*(\S+)', output, re.M))
private = fields.get('PrivateKey')
public = fields.get('Password (PublicKey)')
if not private or not public:
    raise SystemExit('Unexpected X25519 output format; no key contents displayed')
credentials = {'uuid':str(uuid.uuid4()), 'private_key':private,
               'public_key':public, 'short_id':secrets.token_hex(8),
               'server_name':os.environ['VPN_SERVER_NAME'], 'port':int(os.environ['VPN_PORT'])}
with Path('credentials.json').open('x') as f:
    json.dump(credentials, f, indent=2)
config = {
    'log': {'loglevel':'warning'},
    'inbounds': [{
        'tag':'vless-reality', 'listen':'0.0.0.0', 'port':credentials['port'], 'protocol':'vless',
        'settings':{'clients':[{'id':credentials['uuid'], 'flow':'xtls-rprx-vision'}], 'decryption':'none'},
        'streamSettings':{'network':'raw', 'security':'reality',
            'realitySettings':{'show':False, 'target':credentials['server_name']+':443',
                'xver':0, 'serverNames':[credentials['server_name']],
                'privateKey':private, 'shortIds':[credentials['short_id']]}}
    }],
    'outbounds':[{'tag':'direct','protocol':'freedom'}, {'tag':'block','protocol':'blackhole'}],
    'routing':{'domainStrategy':'IPIfNonMatch', 'rules':[{
        'type':'field', 'ip':['0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8',
            '169.254.0.0/16','172.16.0.0/12','192.168.0.0/16','224.0.0.0/4','240.0.0.0/4',
            '::/128','::1/128','fc00::/7','fe80::/10','ff00::/8'], 'outboundTag':'block'}]}
}
candidate = Path('config.json')
candidate.write_text(json.dumps(config, indent=2)+'\n')
result = subprocess.run(['/usr/local/bin/xray','run','-test','-config',str(candidate)], capture_output=True)
if result.returncode:
    raise SystemExit('Xray config validation failed; credentials not displayed')
print('Generated credentials and validated server configuration')
PY
install -m 640 -o root -g xray config.json /usr/local/etc/xray/config.json
chmod 750 /usr/local/etc/xray
chown root:xray /usr/local/etc/xray
runuser -u xray -- /usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json
systemctl enable --now xray
ufw allow "$VPN_PORT/tcp" comment 'vultr-vpn-reality'
systemctl is-active xray
systemctl is-enabled xray
ss -lntH "sport = :$VPN_PORT"
ufw status
/usr/local/bin/xray version | sed -n '1p'
