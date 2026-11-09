# LSPU ScholarHub — Setup Guide for New Device

## What to copy to the new device

Copy the entire `capstone/` folder. The key files/folders are:

```
capstone/
├── app/                        ← All application code & templates
├── config/                     ← Flask configuration
├── database/
│   └── lspu_scholarhub_dump.sql  ← Full database dump (schema + data)
├── requirements.txt            ← All Python dependencies
├── .env                        ← Environment variables (edit before running)
├── run.py                      ← App entry point
└── SETUP.md                    ← This file
```

> **Note:** The `app/static/uploads/` folder contains uploaded student documents.
> Copy it too if you want to keep existing registration files.

---

## Step 1 — Install Prerequisites

Install these on the new device before anything else:

| Software | Download |
|---|---|
| Python 3.11+ | https://www.python.org/downloads/ |
| XAMPP (includes MySQL + Apache) | https://www.apachefriends.org/ |

After installing XAMPP, start **Apache** and **MySQL** from the XAMPP Control Panel.

---

## Step 2 — Create the Database

Open **phpMyAdmin** (http://localhost/phpmyadmin) or use the MySQL command line:

```sql
CREATE DATABASE lspu_scholarhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Then import the dump file:

**Option A — phpMyAdmin:**
1. Click `lspu_scholarhub` in the left panel
2. Click **Import** tab
3. Choose `database/lspu_scholarhub_dump.sql`
4. Click **Go**

**Option B — Command line (XAMPP):**
```bash
C:\xampp\mysql\bin\mysql.exe -u root lspu_scholarhub < database\lspu_scholarhub_dump.sql
```

---

## Step 3 — Install Python Dependencies

Open a terminal in the `capstone/` folder:

```bash
pip install -r requirements.txt
```

If `pip` is not found, use:
```bash
py -m pip install -r requirements.txt
```

---

## Step 4 — Configure Environment Variables

Edit the `.env` file in the project root. Update these values for the new device:

```env
# Database — update if your MySQL password is different
DATABASE_URL=mysql+pymysql://root:@localhost/lspu_scholarhub
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=          ← leave blank if no password (default XAMPP)
MYSQL_DATABASE=lspu_scholarhub

# Email — keep the same Gmail credentials
MAIL_USERNAME=scholarhubtest@gmail.com
MAIL_PASSWORD=your-gmail-app-password

# Gemini AI — keep the same API key
GEMINI_API_KEY=your-gemini-api-key

# SMS — keep the same Semaphore key
SEMAPHORE_API_KEY=your-semaphore-api-key
```

---

## Step 5 — Run the Application

```bash
py run.py
```

The app will be available at: **http://localhost:5000**

---

## Default Admin Account

After importing the database, the admin account is:

| Field | Value |
|---|---|
| Username | `admin` |
| Email | `admin@lspu-scholarhub.edu` |
| Password | *(same as on the original device — check your email or the seed_database.py file)* |

If you need to reset the admin password, run:
```bash
py -c "
from app import create_app, db
from app.models import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(user_type='admin').first()
    u.set_password('Admin@1234')
    db.session.commit()
    print('Admin password reset to: Admin@1234')
"
```

---

## Troubleshooting

**`ModuleNotFoundError`** — Run `pip install -r requirements.txt` again.

**`Can't connect to MySQL`** — Make sure XAMPP MySQL is running (green in Control Panel).

**`Access denied for user 'root'`** — Your MySQL has a password. Add it to `.env` under `MYSQL_PASSWORD=`.

**`Table doesn't exist`** — The SQL import didn't complete. Re-import `database/lspu_scholarhub_dump.sql`.

**Port 5000 already in use** — Change the port in `run.py`:
```python
app.run(debug=True, port=5001)
```

**Gemini quota exceeded** — The free tier resets daily. Registration still works via native PDF extraction. Chatbot falls back to rule-based responses.

---

## Re-exporting the Database (when you want to move again)

Run this from the `capstone/` folder on the source device:

```bash
C:\xampp\mysql\bin\mysqldump.exe --host=localhost --user=root --single-transaction --add-drop-table lspu_scholarhub > database\lspu_scholarhub_dump.sql
```

If MySQL has a password:
```bash
C:\xampp\mysql\bin\mysqldump.exe --host=localhost --user=root --password=YOUR_PASSWORD --single-transaction --add-drop-table lspu_scholarhub > database\lspu_scholarhub_dump.sql
```
