# Maintenance Tracker

Flask web app for UK property-maintenance management: flats (properties + tenancies), contractors, and maintenance jobs with scheduling, follow-ups, cost tracking, Excel import/export, and a soft-delete recycle bin. Single-user, runs locally, SQLite storage.

## Commands (Windows, PowerShell)

```powershell
venv\Scripts\python.exe run.py      # run dev server → http://127.0.0.1:5000
venv\Scripts\pip.exe install -r requirements.txt
$env:FLASK_APP = "run.py"; venv\Scripts\flask.exe backup|list-backups|restore N|seed
venv\Scripts\python.exe -m pytest     # test suite (in-memory SQLite, fast)
venv\Scripts\python.exe -m ruff check .
```

Always use the project venv — the system Python does not have the dependencies. `flask seed` fills the DB with deterministic UK demo data (add `--wipe` to replace everything — prompts first).

## Architecture

App-factory + blueprints (Flask 3.1, SQLAlchemy 2.0 style — `Mapped` models, `db.session.scalars(select(...))`, `db.get_or_404`):

- `run.py` — entry point; debug/host/port from `FLASK_DEBUG`/`HOST`/`PORT` env vars.
- `app/__init__.py` — `create_app()`, blueprint registration, `gbp`/`ukdate` template filters, 404/500 handlers.
- `app/models.py` — `Flat`, `Contractor`, `MaintenanceJob` + `SoftDeleteMixin` (`active_select()` / `deleted_select()` / `soft_delete()` / `restore()`). Status/priority constants live here.
- `app/blueprints/` — `dashboard`, `analytics`, `jobs`, `flats`, `contractors`, `recycle` (endpoints are `blueprint.name`, e.g. `jobs.index`; recycle uses `kind` + `item_id` params for all three models).
- `app/services/excel_io.py` — Excel import/export. Parsing helpers (`clean_rent_value`, `parse_uk_date`, `clean_due_date`) are dependency-free; pandas is lazy-imported only inside `import_flats_from_file` / `build_jobs_export`.
- `app/services/analytics.py` — pure aggregation functions for the analytics page (monthly volume, cost trend, status/priority breakdowns, top contractors); month keys are `"YYYY-MM"` strings via `func.strftime`. Charts: Chart.js 4 (CDN) in `app/static/js/analytics.js` — colors read the `--mt-*` CSS tokens at runtime (never hard-coded), and charts are built only after `document.fonts.ready` (Chart.js caches label measurements per font string; building before the Inter webfont loads clips the widest axis tick).
- `app/db_migrate.py` — `ensure_schema()`: idempotent PRAGMA-based column adds + `create_all()`; runs in `create_app()` when `RUN_SCHEMA_SYNC` is true (off in `TestConfig`). Migrations only ever ADD columns and backfill.
- `app/cli.py` — `flask backup` / `list-backups` / `restore N`; paths derive from `app.instance_path` so they always hit the live DB.
- `app/templates/` — Jinja2. Design system lives in `app/static/css/app.css` (tokens) + `_components.html`/`_icons.html` (macros); see the `design-system` skill before touching any UI. Bootstrap 5.3 CDN is used for grid + JS behaviors only.
- **Live database: `instance/maintenance_tracker.db`** — NOT the root path that `DATABASE_URL=sqlite:///maintenance_tracker.db` appears to point at. Flask-SQLAlchemy 3.x resolves relative SQLite paths against `app.instance_path`. This looks wrong but is correct; don't "fix" it.

### Roadmap (agreed with Ralph, July 2026)

Portfolio upgrade in phases — **all complete (July 2026)**: ~~(1) modernize deps to Flask 3.1~~ ✔ ~~(2) app-factory + blueprints refactor~~ ✔ ~~(3) pytest + CSRF + bug fixes + `flask seed` + GitHub Actions CI~~ ✔ ~~(4) full UI redesign — clean SaaS design system~~ ✔ ~~(5) analytics page with Chart.js~~ ✔ ~~(6) README + screenshots (`docs/screenshots/`, taken on seeded scratch DB)~~ ✔. Not yet pushed to GitHub — the README's CI badge assumes `chusonn/maintenance_tracker`; fix the URL if the repo name differs.

## Domain conventions

- **Currency is GBP (£)** everywhere. **Dates display as UK `dd/mm/yyyy`**; HTML date inputs use ISO as required by the spec.
- `Flat.payment_reference` is the unique business identifier (not `flat_number` — several flats share numbers across buildings). Excel import upserts by payment reference.
- Job lifecycle: `Pending → Scheduled → In Progress → Completed` (or `Cancelled`). Priorities: `Low / Medium / High / Urgent`.
- **Soft delete**: all three models carry `is_deleted / deleted_at / deleted_by` via `SoftDeleteMixin`. Deleting moves rows to the recycle bin; "permanent delete" from the bin is the only hard delete. Always query through `Model.active_select()` — raw `select(Model)` without the filter has been a recurring bug class here.
- **Flat delete cascade**: soft-deleting a flat cascades to its live jobs (tagged `deleted_by='cascade:flat'`); restoring the flat restores exactly those jobs and not independently-binned ones. Purging a flat hard-deletes its jobs first (`flat_id` is NOT NULL). Deleting is blocked while the flat has active jobs.
- Contractor `is_active` is retired: the column still exists in old SQLite files but is unmapped; `is_deleted` is the single hidden-flag. A startup migration folds `is_active=0` rows into the recycle bin.
- Follow-ups: `follow_up_count` increments per follow-up sent; dashboards flag active jobs with zero follow-ups.

## Gotchas

- **Windows + SQLite file locking**: never copy/backup/restore the DB while the dev server is running.
- The debug reloader imports the app twice, so startup migration messages print twice — harmless (migrations are idempotent).
- Console is cp1252: don't `print()` emoji/unicode from Python on startup paths — it raises `UnicodeEncodeError` on some Windows consoles. Keep startup logging ASCII.
- `requirements.txt` must stay UTF-8. (It was once UTF-16 and broke `pip install -r` on Linux.)
- pandas import costs ~1–2 s on Windows — keep it lazily imported inside the Excel routes, never at module top level.
- Backups: `backups/` is git-ignored. `backup_manager.py restore` currently restores to the repo root, which the app never reads — restore manually into `instance/` until this is fixed in the refactor.

## Project skills

`.claude/skills/`: `run-app` (start the dev server), `verify` (end-to-end smoke test), `db-migrate` (schema-change procedure), `design-system` (UI tokens/conventions — completed during the redesign phase).
