"""One-shot: patch nginx config on the prod server to proxy /admin to uvicorn.

Local-only, gitignored (lives under scripts/_*.py).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scripts.deploy_ssh as deploy_ssh  # noqa: E402

NGINX_SITE = """server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name 72.56.38.35;

    client_max_body_size 25m;

    root /opt/suupr/frontend/dist;
    index index.html;

    location /media/ {
        alias /opt/suupr/media/;
        access_log off;
        expires 30d;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_set_header Host $host;
    }

    # Серверная Jinja-админка (FastAPI /admin/*)
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }
    location = /admin {
        proxy_pass http://127.0.0.1:8000/admin/;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
"""


def main() -> int:
    client = deploy_ssh.connect()
    try:
        deploy_ssh.upload_text(client, NGINX_SITE, "/etc/nginx/sites-available/suupr")
        deploy_ssh.run(client, "ln -sf /etc/nginx/sites-available/suupr /etc/nginx/sites-enabled/suupr")
        deploy_ssh.run(client, "rm -f /etc/nginx/sites-enabled/default")
        deploy_ssh.run(client, "nginx -t")
        deploy_ssh.run(client, "systemctl reload nginx || systemctl restart nginx")
        deploy_ssh.run(
            client,
            "curl -sS -o /dev/null -w 'admin/login=%{http_code} content_type=%{content_type}\\n' http://127.0.0.1/admin/login",
        )
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
