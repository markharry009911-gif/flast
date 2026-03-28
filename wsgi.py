"""
WSGI entry point – used by PythonAnywhere.
Point your WSGI config at this file.
"""
import sys
import os
from pathlib import Path

# ── Set project root on sys.path ─────────────────────────────────────────────
# Change this to your actual PythonAnywhere path, e.g.:
#   /home/yourusername/fbflask
PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Optional: load a .env file ───────────────────────────────────────────────
_env = Path(PROJECT_ROOT) / '.env'
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

# ── Init DB and import app ────────────────────────────────────────────────────
from app import app, init_db
init_db()

application = app
