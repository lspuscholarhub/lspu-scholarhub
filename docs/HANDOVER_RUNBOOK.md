# Handover runbook — LSPU ScholarHub

Short operational guide for the people taking over the system. Keep it next to
the deployment details (host, database, mail account) rather than in git.

## 1. Environment variables (Railway → service → Variables)

| Variable | Why it matters |
|---|---|
| `SECRET_KEY` | Signs sessions. If missing in production the app generates a new one per boot and every restart logs all users out. |
| `DATABASE_URL` | MySQL connection (`mysql+pymysql://...`). Use a dedicated app user, not `root`. |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USE_TLS` | SMTP host. Gmail: `smtp.gmail.com`, `587`, `True`. |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | Without them every notification is silently skipped. Gmail requires an App Password. |
| `UPLOAD_FOLDER` | Must point at persistent storage (see below). |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | Optional; when set, uploads go to Cloudinary instead of disk. |
| `BASE_URL` | Public URL used in emails. |

`FLASK_ENV=production` in the deployed service.

## 2. Upload persistence (check this first)

Railway containers are **ephemeral**: anything written under the app directory is
lost on redeploy or restart, and uploaded student documents are written there by
default (`app/static/uploads`).

Either:

1. **Volume** — Railway → service → Volumes → mount at `/data`, then set
   `UPLOAD_FOLDER=/data/uploads` and copy the existing files into it once; or
2. **Cloudinary** — set the three `CLOUDINARY_*` variables; new uploads are stored
   remotely.

Verify after a deploy: upload a document as a student, redeploy the service, and
download the same document. If it 404s, uploads are still on ephemeral disk.

Keep a copy of the upload folder in the same backup rotation as the database
(`tar czf uploads-$(date +%F).tgz -C /data uploads`).

## 3. Backups and restore

```bash
# Database backup (cron daily, keep 14 days)
mysqldump -u USER -p --single-transaction --routines lspu_scholarhub \
  | gzip > backup-$(date +%F).sql.gz

# Uploads backup
tar czf uploads-$(date +%F).tgz -C /data uploads

# Restore into a scratch database and verify before trusting a backup
mysql -u root -e "CREATE DATABASE restore_check"
gunzip -c backup-2026-11-23.sql.gz | mysql -u root restore_check
```

Test a restore at least once before handover — a backup that has never been
restored is not a backup.

## 4. Maintenance commands

Run from the project root with the production `DATABASE_URL` in the environment:

The seed/debug scripts in `scripts/dev/` refuse a production-like database
unless `--confirm-production` is passed. That flag is for deliberate recovery
only — never use it as part of a routine deploy.

The SMS test scripts are separate: `test_sms.py` and `check_semaphore.py`
send a real text only when both `--send-sms` and `TEST_SMS_NUMBER` are set,
and they no longer contain a hardcoded recipient.

```bash
# Does the database have every table/column the models expect?
python scripts/check_schema.py --url "$DATABASE_URL"

# Batch totals: report only, then repair (safe to run repeatedly)
python scripts/recalculate_batch_totals.py --dry-run
python scripts/recalculate_batch_totals.py

# Health check of a running deployment
curl -fsS https://<your-host>/health
```

The recount prints only batches whose stored totals disagreed with their approved
applications, and is quiet when everything already matches.

## 5. Routine checks after a deploy

1. `/health` returns 200.
2. Log in as student, staff and admin once.
3. Open Programs, Batches and Reports; confirm the numbers look right.
4. Submit one notification / check one email arrives.
5. Upload and download one document (upload persistence, section 2).
