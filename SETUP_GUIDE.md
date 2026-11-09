# LSPU ScholarHub — Setup Guide

**System:** AI-Enabled Web-Based Scholarship Management and Monitoring System  
**University:** Laguna State Polytechnic University (LSPU)  
**Tech Stack:** Python / Flask / MySQL / Bootstrap 5 / Google Gemini AI

---

## Requirements

### Software to Install

| Software | Version | Download |
|---|---|---|
| **Python** | 3.10 or higher | https://www.python.org/downloads/ |
| **MySQL** | 8.0 or higher | https://dev.mysql.com/downloads/mysql/ |
| **Git** | Any | https://git-scm.com/downloads |
| **phpMyAdmin** *(optional)* | Any | Comes with XAMPP |
| **XAMPP** *(optional, easiest)* | Any | https://www.apachefriends.org/ |

> **Tip:** If you use XAMPP, it includes MySQL and phpMyAdmin — you only need to install Python separately.

---

## Step-by-Step Setup

### Step 1 — Copy the project folder

Copy the entire `capstone` folder to your device. You can put it anywhere, for example:
```
C:\Users\YourName\Desktop\capstone
```

---

### Step 2 — Start MySQL

**If using XAMPP:**
1. Open XAMPP Control Panel
2. Click **Start** next to **MySQL**
3. MySQL is now running on `localhost:3306`

**If using standalone MySQL:**
- Make sure the MySQL service is running

---

### Step 3 — Create the database

**Option A — Using phpMyAdmin (easiest):**
1. Open your browser and go to `http://localhost/phpmyadmin`
2. Click **Import** in the top menu
3. Click **Choose File** and select:
   ```
   capstone/database/lspu_scholarhub.sql
   ```
4. Click **Go** — the database and tables will be created

**Option B — Using MySQL command line:**
```bash
mysql -u root -p < database/lspu_scholarhub.sql
```
Press Enter, then type your MySQL password (leave blank if none).

**Option C — Manual creation:**
```sql
CREATE DATABASE lspu_scholarhub;
```
Then run `python seed_database.py` in Step 6 — it will create all tables automatically.

---

### Step 4 — Configure the environment file

Open the file `capstone/.env` in any text editor (Notepad, VS Code, etc.)

Check and update these settings:

```env
# Database — update if your MySQL has a password
DATABASE_URL=mysql+pymysql://root:@localhost/lspu_scholarhub
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=          ← put your MySQL password here if you have one
MYSQL_DATABASE=lspu_scholarhub

# Email — optional, for sending email notifications
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password

# AI Chatbot — get free key at https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your-gemini-api-key-here
```

> **Note:** If your MySQL has no password (default XAMPP), leave `MYSQL_PASSWORD=` blank.

---

### Step 5 — Install Python packages

Open a terminal (Command Prompt or PowerShell) inside the `capstone` folder:

```bash
cd C:\Users\YourName\Desktop\capstone
```

Install all required packages:

```bash
pip install -r requirements.txt
```

This installs everything — Flask, SQLAlchemy, PyMySQL, Gemini AI, export libraries, etc.

> **If `pip` is not found**, try `python -m pip install -r requirements.txt`

---

### Step 6 — Seed the database with sample data

```bash
python seed_database.py
```

This creates all tables and inserts sample accounts:

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Staff | `staff1` | `staff123` |
| Staff | `staff2` | `staff123` |
| Student | `johndoe` | `student123` |
| Student | `janesmith` | `student123` |

---

### Step 7 — Run the application

```bash
python run.py
```

You should see:
```
✓ Database tables ready
 * Running on http://0.0.0.0:5000
```

Open your browser and go to:
```
http://localhost:5000
```

---

## Getting the Free Gemini AI API Key

The chatbot uses Google Gemini AI for free (no credit card needed).

1. Go to **https://aistudio.google.com/app/apikey**
2. Sign in with any Google account
3. Click **"Create API Key"**
4. Copy the key (starts with `AIzaSy...`)
5. Open `.env` and paste it:
   ```
   GEMINI_API_KEY=AIzaSy...your_key_here
   ```
6. Restart the server

**Free tier limits:** 1,500 requests/day — more than enough for a thesis demo.

---

## Setting Up Gmail for Email Notifications

1. Go to your Google Account → Security → **2-Step Verification** (enable it)
2. Go to **App Passwords** → Select app: Mail → Select device: Windows Computer
3. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)
4. Open `.env` and update:
   ```
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-gmail-app-password
   ```

---

## Common Errors and Fixes

### `ModuleNotFoundError: No module named 'flask'`
```bash
pip install -r requirements.txt
```

### `Access denied for user 'root'@'localhost'`
Your MySQL password is wrong. Update `MYSQL_PASSWORD=` in `.env`.

### `Can't connect to MySQL server`
MySQL is not running. Start it in XAMPP or as a Windows service.

### `Table 'lspu_scholarhub.users' doesn't exist`
Run the seed script:
```bash
python seed_database.py
```

### `pip is not recognized`
Python is not in your PATH. Either:
- Reinstall Python and check "Add Python to PATH"
- Or use: `python -m pip install -r requirements.txt`

### Port 5000 already in use
Change the port in `run.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```
Then access at `http://localhost:5001`

---

## Project Folder Structure

```
capstone/
├── app/
│   ├── models/          ← Database models (User, Scholarship, etc.)
│   ├── views/           ← Route handlers (admin, staff, student, etc.)
│   ├── services/        ← Business logic (notifications, exports, AI chatbot)
│   ├── templates/       ← HTML templates
│   ├── static/          ← CSS, JS, uploaded files
│   └── __init__.py      ← App factory
├── config/
│   └── config.py        ← Configuration classes
├── database/
│   └── lspu_scholarhub.sql  ← Database schema (import this first)
├── logs/                ← Application logs
├── migrations/          ← Flask-Migrate migration files
├── .env                 ← Environment variables (edit this)
├── .env.example         ← Example environment file
├── requirements.txt     ← Python package list
├── run.py               ← Start the application
├── seed_database.py     ← Create sample data
└── SETUP_GUIDE.md       ← This file
```

---

## Quick Reference — Terminal Commands

```bash
# Install packages
pip install -r requirements.txt

# Seed sample data
python seed_database.py

# Run the app
python run.py

# Database migrations (if you change models)
flask db migrate -m "description"
flask db upgrade
```

---

## Default Login Credentials

| Role | Username | Password | Access |
|---|---|---|---|
| Admin | `admin` | `admin123` | Full system access |
| Staff | `staff1` | `staff123` | Review applications, reports |
| Staff | `staff2` | `staff123` | Review applications, reports |
| Student | `johndoe` | `student123` | Apply for scholarships |
| Student | `janesmith` | `student123` | Apply for scholarships |

> **Security Note:** Change all passwords before presenting or deploying.

---

*LSPU ScholarHub — Thesis Project, Laguna State Polytechnic University*
