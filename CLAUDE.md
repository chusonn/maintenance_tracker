# Maintenance Tracker

Flask web app for UK property-maintenance management: flats (properties + tenancies), contractors, and maintenance jobs with scheduling, follow-ups, cost tracking, Excel import/export, and a soft-delete recycle bin. SQLite storage, sign-in required. Since Sept 2026 it is a **real daily work tool for a 2-person team**, deployed on Railway. The repo is PUBLIC: company details (shared-inbox address, keys, passwords) live only in env vars, never in code.

## Commands (Windows, PowerShell)

```powershell
venv\Scripts\python.exe run.py      # run dev server → http://127.0.0.1:5000
venv\Scripts\pip.exe install -r requirements.txt
$env:FLASK_APP = "run.py"; venv\Scripts\flask.exe backup|list-backups|restore N|seed
$env:FLASK_APP = "run.py"; venv\Scripts\flask.exe create-user EMAIL | set-password EMAIL   # prompts
venv\Scripts\python.exe -m pytest     # test suite (in-memory SQLite, fast)
venv\Scripts\python.exe -m ruff check .
```

Always use the project venv — the system Python does not have the dependencies. `flask seed` fills the DB with deterministic UK demo data (add `--wipe` to replace everything — prompts first).

## Architecture

App-factory + blueprints (Flask 3.1, SQLAlchemy 2.0 style — `Mapped` models, `db.session.scalars(select(...))`, `db.get_or_404`):

- `run.py` — entry point (also gunicorn's `run:app` in production); debug/host/port from `FLASK_DEBUG`/`HOST`/`PORT`; sets INFO logging so migration/backup logs show.
- `app/__init__.py` — `create_app()`, blueprint registration, `gbp`/`ukdate` template filters, 404/500 handlers, `/healthz`.
  - **Login guard:** one `before_request` redirects anonymous users to `auth.login` for every endpoint not in `PUBLIC_ENDPOINTS` (`auth.login`, `health`, `static`). `test_auth.py` walks the whole URL map to prove it.
  - `APP_ENV=production` → `ProxyFix` + `_check_production_config()`, which refuses a weak `SECRET_KEY` or a relative SQLite path.
- `app/models.py` — `User` (table `app_user`; `is_enabled` backs Flask-Login's `is_active`; lockout fields), `Flat`, `Contractor`, `MaintenanceJob` (`created_by` = user name) + `SoftDeleteMixin` (`active_select()` / `deleted_select()` / `soft_delete()` / `restore()`). Status/priority constants live here.
- `app/blueprints/` — `auth` (login/logout, safe `next`), `settings` (people with access, password change/reset, backup download), `dashboard`, `analytics`, `jobs`, `flats`, `contractors`, `message_templates`, `recycle` (endpoints are `blueprint.name`, e.g. `jobs.index`; recycle uses `kind` + `item_id` params for all three models).
- `app/services/accounts.py` — `create_user`, `sign_in`, `ensure_initial_user`.
  - `sign_in`: 5 wrong passwords → 15-minute lock. An unknown email and a disabled account fail exactly like a wrong password.
  - `ensure_initial_user`: creates the first account from `INITIAL_USER_*`, only while no accounts exist.
- `app/services/backup.py` — everything goes through SQLite's **online-backup API**, which is consistent while the app runs and includes WAL content.
  - Functions: `create_backup`, `snapshot_bytes` (download), `restore_backup`, `ensure_daily_backup`.
  - `ensure_daily_backup`: the first request of each day writes `daily_YYYYMMDD.db` and keeps `BACKUP_KEEP_DAYS` of them. Failures are logged, never raised.
  - The DB path comes from `db.engine.url`, so it's right both locally and on the volume.
- `app/extensions.py` — `db`, `csrf`, `login_manager`, and a global engine `connect` listener that sets SQLite `journal_mode=WAL`.
- `app/services/excel_io.py` — Excel import/export. Parsing helpers (`clean_rent_value`, `parse_uk_date`, `clean_due_date`) are dependency-free; pandas is lazy-imported only inside `import_flats_from_file` / `build_jobs_export`.
- `app/services/analytics.py` — pure aggregation functions for the analytics page (monthly volume, cost trend, status/priority breakdowns, top contractors); month keys are `"YYYY-MM"` strings via `func.strftime`. Charts: Chart.js 4 (CDN) in `app/static/js/analytics.js` — colors read the `--mt-*` CSS tokens at runtime (never hard-coded), and charts are built only after `document.fonts.ready` (Chart.js caches label measurements per font string; building before the Inter webfont loads clips the widest axis tick).
- `app/db_migrate.py` — `ensure_schema()`: idempotent PRAGMA-based column adds + `create_all()`; runs in `create_app()` when `RUN_SCHEMA_SYNC` is true (off in `TestConfig`). Migrations only ever ADD columns and backfill.
- `app/cli.py` — `flask backup` / `list-backups` / `restore N` (via services/backup.py) + `create-user` / `set-password`.
- `app/templates/` — Jinja2. Design system lives in `app/static/css/app.css` (tokens) + `_components.html`/`_icons.html` (macros); see the `design-system` skill before touching any UI. Bootstrap 5.3 CDN is used for grid + JS behaviors only.
- **Dark mode**: `data-theme`/`data-bs-theme` on `<html>`, set before paint by `static/js/theme.js` (`?theme=` param > localStorage > OS preference). All dark values live in one `[data-theme="dark"]` block in app.css; the topbar toggle dispatches `mt:themechange` and analytics.js rebuilds its charts to re-read tokens. **New colors must be defined in both `:root` and the dark block** — details in the `design-system` skill.
- **Live database: `instance/maintenance_tracker.db`** — NOT the root path that `DATABASE_URL=sqlite:///maintenance_tracker.db` appears to point at. Flask-SQLAlchemy 3.x resolves relative SQLite paths against `app.instance_path`. This looks wrong but is correct; don't "fix" it.

### Current plan (approved 22 Sept 2026): shared online work tool + AI intake

The full plan and its decisions are kept in Claude's private project memory, not in this public repo. Check in with Ralph after each phase.
1. **Online + login.** Flask-Login accounts, lockout, who-did-what names, Railway (`railway.json`, volume at `/data`), WAL, daily backups + download. **Code done; deploy pending.**
2. **AI "New request" box.** Paste text or a screenshot → pre-filled job form + duplicate check. Uses `claude-sonnet-5` (Ralph's cost choice) via the `anthropic` SDK, and a new `IntakeItem` table.
3. **Shared company Outlook inbox via Microsoft Graph.** Delegated `Mail.Read.Shared` / `Mail.Send.Shared`; IT does the Entra registration and mailbox permissions. Auto-check every 15 minutes; follow-ups send from the shared address.
4. **One-time old-email + WhatsApp-export scan, done by Claude Code in chat (NOT the API).** The app exports threads to a file, Claude sorts them, and the app imports the results for review.

WhatsApp is the Business *phone app* (no API), so it stays paste/screenshot/chat-export. Nothing becomes a job without human review.

### Portfolio roadmap (July 2026, complete)

Portfolio upgrade in phases — **all complete (July 2026)**: ~~(1) modernize deps to Flask 3.1~~ ✔ ~~(2) app-factory + blueprints refactor~~ ✔ ~~(3) pytest + CSRF + bug fixes + `flask seed` + GitHub Actions CI~~ ✔ ~~(4) full UI redesign — clean SaaS design system~~ ✔ ~~(5) analytics page with Chart.js~~ ✔ ~~(6) README + screenshots (`docs/screenshots/`, taken on seeded scratch DB)~~ ✔ ~~(stretch) dark mode — token swap via `data-theme`, chart palette CVD-validated per mode~~ ✔. Public on GitHub since July 2026: `github.com/chusonn/maintenance_tracker` (remote `origin`), CI green.

## Domain conventions

- **Currency is GBP (£)** everywhere. **Dates display as UK `dd/mm/yyyy`**; HTML date inputs use ISO as required by the spec.
- `Flat.payment_reference` is the unique business identifier (not `flat_number` — several flats share numbers across buildings). Excel import upserts by payment reference.
- Job lifecycle: `Pending → Scheduled → In Progress → Completed` (or `Cancelled`). Priorities: `Low / Medium / High / Urgent`.
- **Soft delete**: all three models carry `is_deleted / deleted_at / deleted_by` via `SoftDeleteMixin`. Deleting moves rows to the recycle bin; "permanent delete" from the bin is the only hard delete. Always query through `Model.active_select()` — raw `select(Model)` without the filter has been a recurring bug class here.
- **Flat delete cascade**: soft-deleting a flat cascades to its live jobs (tagged `deleted_by='cascade:flat'`); restoring the flat restores exactly those jobs and not independently-binned ones. Purging a flat hard-deletes its jobs first (`flat_id` is NOT NULL). Deleting is blocked while the flat has active jobs.
- Contractor `is_active` is retired: the column still exists in old SQLite files but is unmapped; `is_deleted` is the single hidden-flag. A startup migration folds `is_active=0` rows into the recycle bin.
- Follow-ups: `follow_up_count` increments per follow-up sent; dashboards flag active jobs with zero follow-ups.
- **Follow-up emails**: `jobs.followup` is a composer (template picker → editable To/Subject/Body → "Send email & record" or "Record without emailing"). Transport is `app/services/emailer.py` (stdlib smtplib, STARTTLS, `SMTP_*` env vars; unset creds = sending disabled, composer degrades gracefully). Domain logic in `app/services/followup.py`: `{placeholder}` rendering is regex-based (never `str.format` — user templates may contain stray braces), unknown tokens stay literal; `due_followups_stmt(days)` powers `/jobs/due-followups` + bulk send (`FOLLOW_UP_DAYS`, default 7). `MessageTemplate` is hard-delete (no recycle bin); 3 defaults auto-seed when the table is empty (startup + `flask seed`). On send, an `[Emailed …]` audit line is appended to `follow_up_notes` — no new job columns. SMTP failure = flash + re-render with the typed email preserved, count NOT incremented. Tests mock `smtplib.SMTP` via the `smtp_spy` fixture (+ `mail_configured`) in conftest.

## Gotchas

- **Windows + SQLite file locking**: never *restore* (or file-copy) the DB while the dev server is running.
  - `flask backup` and the daily/download backups use the online-backup API, so they're safe while it runs.
  - The DB is in WAL mode, so `-wal`/`-shm` files beside it are normal. Never copy the `.db` file alone.
- **Local dev needs an account.** Every page requires sign-in. Create one with `flask create-user EMAIL`, or set `INITIAL_USER_*` in `.env` (used only while no accounts exist).
- **Tests:**
  - The `client` fixture is **already signed in** as "Test User".
  - Use `anon_client` for signed-out behaviour and `login_as(client, user)` for other users.
  - `make_user()` uses a cheap pbkdf2 hash for speed.
- **Templates and browser automation:**
  - With `FLASK_DEBUG=0`, Jinja templates are cached, so restart the server to see template edits.
  - The topbar sign-out is also a `button[type=submit]`, so target form buttons by their text.
- The debug reloader imports the app twice, so startup migration messages print twice — harmless (migrations are idempotent).
- Console is cp1252: don't `print()` emoji/unicode from Python on startup paths — it raises `UnicodeEncodeError` on some Windows consoles. Keep startup logging ASCII.
- `requirements.txt` must stay UTF-8. (It was once UTF-16 and broke `pip install -r` on Linux.)
- pandas import costs ~1–2 s on Windows — keep it lazily imported inside the Excel routes, never at module top level.
- Backups:
  - `backups/` is git-ignored. In production they go to `/data/backups` beside the DB, unless `BACKUP_DIR` is set.
  - `flask restore N` saves a `pre_restore_*` safety copy first. Stop the server before restoring.
  - Pruning only touches `daily_*` files.

## Project skills

`.claude/skills/`: `run-app` (start the dev server), `verify` (end-to-end smoke test), `db-migrate` (schema-change procedure), `design-system` (UI tokens/conventions — completed during the redesign phase).
