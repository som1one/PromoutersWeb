"""Diagnostic SSH probe for /opt/suupr after CI deploy.

Reads SSH credentials from env (SUUPR_SSH_HOST/USER/PASSWORD) and runs a
sequence of read-only commands on the server. Local-only, never committed.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.deploy_ssh as deploy_ssh  # noqa: E402

CHECKS = [
    "echo '=== app dir ===' && ls -la /opt/suupr | head -25",
    "echo '=== git HEAD on server ===' && cd /opt/suupr && git log --oneline -3 2>&1 || echo 'no git'",
    "echo '=== git remote ===' && cd /opt/suupr && git remote -v 2>&1 || true",
    "echo '=== frontend dist mtime ===' && ls -la /opt/suupr/frontend/dist/index.html /opt/suupr/frontend/dist/assets/ 2>&1 | head -10",
    "echo '=== systemctl suupr-backend ===' && systemctl status suupr-backend --no-pager -l | head -25",
    "echo '=== uvicorn process ===' && ps -ef | grep -E 'uvicorn|promouters' | grep -v grep || true",
    "echo '=== nginx site ===' && cat /etc/nginx/sites-enabled/suupr 2>&1 | head -40 || ls /etc/nginx/sites-enabled/",
    "echo '=== /api/v1/health ===' && curl -sS -o - -w '\\nHEALTH=%{http_code}\\n' http://127.0.0.1/api/v1/health || true",
    "echo '=== / (first 200 chars) ===' && curl -sS http://127.0.0.1/ | head -c 400 && echo && curl -sS -o /dev/null -w 'INDEX=%{http_code}\\n' http://127.0.0.1/",
]


def main() -> int:
    client = deploy_ssh.connect()
    try:
        for cmd in CHECKS:
            deploy_ssh.run(client, cmd)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
