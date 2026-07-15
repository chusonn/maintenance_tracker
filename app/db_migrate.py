"""Idempotent, additive schema sync for pre-existing SQLite databases.

SQLite can't easily drop or alter columns, so migrations here only ever
ADD columns (existence-checked via PRAGMA) and backfill. Runs on every
startup; every step must stay safe to repeat. New tables need no step —
create_all() at the end creates whatever is missing.
"""

import logging

from sqlalchemy import text

from .extensions import db

log = logging.getLogger(__name__)

_SOFT_DELETE_TABLES = ("flat", "contractor", "maintenance_job")


def _columns(conn, table: str) -> list[str]:
    return [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]


def ensure_schema() -> None:
    with db.engine.connect() as conn:
        for table in _SOFT_DELETE_TABLES:
            cols = _columns(conn, table)
            if not cols:
                continue  # table doesn't exist yet; create_all handles it
            if "is_deleted" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN deleted_at DATETIME"))
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN deleted_by VARCHAR(100)"))
                log.info("Added soft-delete columns to %s", table)

        # Contractor.is_active was superseded by is_deleted; fold the old
        # flag in so hidden contractors land in the recycle bin. The column
        # itself stays in SQLite (dropping is not worth the table rebuild).
        contractor_cols = _columns(conn, "contractor")
        if "is_active" in contractor_cols and "is_deleted" in contractor_cols:
            result = conn.execute(
                text(
                    "UPDATE contractor SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP, "
                    "deleted_by = 'migration:is_active' "
                    "WHERE is_active = 0 AND is_deleted = 0"
                )
            )
            if result.rowcount:
                log.info("Migrated %d inactive contractors to recycle bin", result.rowcount)

        job_cols = _columns(conn, "maintenance_job")
        if job_cols and "follow_up_count" not in job_cols:
            conn.execute(
                text("ALTER TABLE maintenance_job ADD COLUMN follow_up_count INTEGER DEFAULT 0")
            )
            if "follow_up_sent" in job_cols:
                conn.execute(
                    text("UPDATE maintenance_job SET follow_up_count = 1 WHERE follow_up_sent = 1")
                )
            log.info("Added follow_up_count to maintenance_job")

        conn.commit()

    db.create_all()
