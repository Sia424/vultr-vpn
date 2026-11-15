#!/usr/bin/env bash
set -euo pipefail
node_port="${1:-443}"
[[ "$node_port" =~ ^[0-9]+$ && "$node_port" -ge 1 && "$node_port" -le 65535 ]]
hostname
/usr/local/bin/xray version | sed -n '1p'
runuser -u xray -- /usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json
systemctl is-active xray
systemctl is-enabled xray
systemctl show xray -p User -p NRestarts -p ExecMainStatus
ss -lntH "sport = :$node_port"
ufw status
stat -c '%a %U:%G %n' /usr/local/etc/xray /usr/local/etc/xray/config.json
cat /proc/sys/kernel/random/boot_id
