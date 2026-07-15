# Maintenance Tracker

Flask web app for UK property-maintenance management: flats (properties + tenancies), contractors, and maintenance jobs with scheduling, follow-ups, cost tracking, Excel import/export, and a soft-delete recycle bin. Single-user, runs locally, SQLite storage.

## Commands (Windows, PowerShell)

```powershell
venv\Scripts\python.exe app.py      # run dev server → http://127.0.0.1:5000
venv\Scripts\pip.exe install -r requirements.txt
```

There is no test suite yet (planned; see Roadmap). Always use the project venv — the system Python does not have the dependencies.

## Architecture

- `app.py` — everything: Flask app, 3 SQLAlchemy models (`Flat`, `Contractor`, `MaintenanceJob`), ~25 routes, Excel import/export via pandas (lazy-imported inside routes).
- `migrate.py` — idempotent, PRAGMA-based column-add migrations; runs automatically at startup from `app.py`'s `__main__` block. SQLite can't easily drop/alter columns, so migrations only ever ADD columns and backfill.
- `backup_manager.py` — standalone backup/restore CLI (`python backup_manager.py backup|list|restore N`).
- `templates/` — Jinja2 + Bootstrap 5 (CDN), styling currently inline per template.
- **Live database: `instance/maintenance_tracker.db`** — NOT the root path that `DATABASE_URL=sqlite:///maintenance_tracker.db` appears to point at. Flask-SQLAlchemy 3.x resolves relative SQLite paths against `app.instance_path`. This looks wrong but is correct; don't "fix" it.

### Roadmap (agreed with Ralph, July 2026)

Portfolio upgrade in phases: (1) modernize deps to Flask 3.1, (2) app-factory + blueprints refactor (`run.py` + `app/` package), (3) pytest + CSRF + bug fixes + `flask seed` + GitHub Actions CI, (4) full UI redesign — clean SaaS design system (token-based CSS, sidebar shell), (5) analytics page with Chart.js, (6) README + screenshots. Update this file as phases land.

## Domain conventions

- **Currency is GBP (£)** everywhere. **Dates display as UK `dd/mm/yyyy`**; HTML date inputs use ISO as required by the spec.
- `Flat.payment_reference` is the unique business identifier (not `flat_number` — several flats share numbers across buildings). Excel import upserts by payment reference.
- Job lifecycle: `Pending → Scheduled → In Progress → Completed` (or `Cancelled`). Priorities: `Low / Medium / High / Urgent`.
- **Soft delete**: all three models carry `is_deleted / deleted_at / deleted_by`. Deleting moves rows to the recycle bin; "permanent delete" from the bin is the only hard delete. Every list/count/export query must filter `is_deleted == False` — missing filters have been a recurring bug class here.
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
