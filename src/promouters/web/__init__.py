"""Server-rendered admin (Jinja2) — the active UI for the merged СУУПР system.

All routers live under ``/admin``. Cookie-based JWT auth (httpOnly + Lax) lives
in ``web/deps.py`` and ``web/auth.py``. The React SPA in ``frontend/`` is kept
on disk but not served by this layer.
"""
