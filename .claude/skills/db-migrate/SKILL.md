---
name: db-migrate
description: Add or change database schema (new column, new table, backfill) in the Maintenance Tracker. Use for any model/schema change, migration, or "add a field" request.
---

# Schema changes

This project uses **idempotent, additive, PRAGMA-based migrations** (see `migrate.py`), not Alembic. SQLite here never drops or alters columns — it only ADDs them and backfills.

Procedure for any schema change:

1. **Back up first**: with the server STOPPED, copy `instance/maintenance_tracker.db` to `backups/<name>_<timestamp>.db`.
2. **Update the model** in the models file (add the column with a sensible default/nullable).
3. **Add a migration step**: check column existence via `PRAGMA table_info(<table>)`; if missing, `ALTER TABLE <table> ADD COLUMN ...` and backfill with an `UPDATE`. Every step must be safe to run repeatedly (existence-checked) — migrations run on every startup.
4. **Retired columns stay in SQLite** — remove them from the model only, and document the orphaned column in CLAUDE.md.
5. **Test on a copy**: run the app against a copy of the real DB (`DATABASE_URL=sqlite:///<scratch>.db` — note relative paths resolve to `instance/`) and confirm the migration output and app behavior before trusting it on the live file.
6. New tables need no migration step — startup `db.create_all()` creates missing tables.

Never run a migration or copy the DB while the dev server is running (Windows file locking).
