"""Database backups through SQLite's online-backup API.

Unlike a file copy, the backup API gives a consistent snapshot even while the
app is running and includes changes still sitting in the WAL file. Used by the
CLI (backup / list-backups / restore), the automatic daily backup, and the
Settings "Download backup" button.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path

from flask import current_app

from ..extensions import db

log = logging.getLogger(__name__)

DAILY_PREFIX = "daily_"
_daily_lock = threading.Lock()


def db_path() -> Path:
    """The live SQLite file, exactly as the engine resolved it (Flask-SQLAlchemy
    maps relative paths into instance/)."""
    database = db.engine.url.database
    if not database or database == ":memory:":
        raise RuntimeError("The app is not using a file-based SQLite database.")
    return Path(database)


def backups_dir() -> Path:
    configured = current_app.config.get("BACKUP_DIR")
    if configured:
        directory = Path(configured)
    elif current_app.config.get("PRODUCTION"):
        directory = db_path().parent / "backups"  # same persistent volume as the DB
    else:
        directory = Path(current_app.root_path).parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def list_backups() -> list[Path]:
    """All backups, newest first."""
    return sorted(backups_dir().glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)


def copy_database(src: Path | str, dest: Path | str) -> None:
    source = sqlite3.connect(src)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def create_backup(prefix: str = "maintenance_tracker") -> Path:
    dest = backups_dir() / f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.db"
    copy_database(db_path(), dest)
    return dest


def snapshot_bytes() -> bytes:
    """The whole database as bytes (for the download button) - no temp files."""
    source = sqlite3.connect(db_path())
    memory = sqlite3.connect(":memory:")
    try:
        source.backup(memory)
        return memory.serialize()
    finally:
        memory.close()
        source.close()


def restore_backup(src: Path) -> Path:
    """Replace the live database with `src`; the current one is saved first.
    Only run with the web server stopped. Returns the safety-copy path."""
    safety = create_backup(prefix="pre_restore")
    db.engine.dispose()  # drop pooled connections before overwriting the file
    copy_database(src, db_path())
    return safety


def prune_daily(keep: int) -> list[Path]:
    dailies = sorted(backups_dir().glob(f"{DAILY_PREFIX}*.db"), reverse=True)
    removed = dailies[keep:]
    for path in removed:
        path.unlink(missing_ok=True)
    return removed


def ensure_daily_backup() -> Path | None:
    """Make today's backup unless it already exists, then prune old dailies.

    Called on every request, so after the first check of the day it is a
    cheap in-memory comparison. A failure is logged and never breaks the
    request; it's retried the next day.
    """
    state = current_app.extensions.setdefault("mt_daily_backup", {"checked": None})
    today = date.today()
    if state["checked"] == today:
        return None
    with _daily_lock:
        if state["checked"] == today:
            return None
        state["checked"] = today
        try:
            dest = backups_dir() / f"{DAILY_PREFIX}{today:%Y%m%d}.db"
            if dest.exists():
                return None
            partial = dest.with_suffix(".db.partial")
            copy_database(db_path(), partial)
            os.replace(partial, dest)  # never leave a half-written .db behind
            prune_daily(current_app.config["BACKUP_KEEP_DAYS"])
            log.info("Daily backup written to %s", dest)
            return dest
        except Exception:
            log.exception("Daily backup failed")
            return None
