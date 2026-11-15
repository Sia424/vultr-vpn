#!/usr/bin/env python3
"""Run read-only server checks with the configured target identity and port."""
import shlex
import subprocess
from project_config import ROOT, load_environment, ssh_command

env = load_environment()
command = ('test "$(hostname)" = ' + shlex.quote(env['server']['expected_hostname'])
           + ' && bash -s -- ' + str(env['reality']['port']))
with (ROOT / 'scripts/check-server.sh').open('rb') as stream:
    raise SystemExit(subprocess.run(ssh_command(env, command), stdin=stream).returncode)
