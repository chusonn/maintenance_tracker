import sqlite3
from datetime import date

import pytest
from sqlalchemy import text

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.services import backup

from .conftest import login_as
from .factories import make_flat, make_user


def _count_flats(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM flat").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def file_app(tmp_path):
    """App on a real SQLite file (backups need one), backups in tmp_path."""
    config = type(
        "FileConfig",
        (TestConfig,),
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'live.db').as_posix()}",
            "BACKUP_DIR": str(tmp_path / "backups"),
            "BACKUP_KEEP_DAYS": 3,
        },
    )
    app = create_app(config)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.engine.dispose()  # release the file so Windows can clean tmp_path


def test_file_database_uses_wal_mode(file_app):
    assert _db.session.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_create_backup_includes_committed_rows(file_app):
    make_flat()
    dest = backup.create_backup()
    assert dest.parent == backup.backups_dir()
    assert _count_flats(dest) == 1


def test_snapshot_bytes_is_a_sqlite_file(file_app):
    make_flat()
    assert backup.snapshot_bytes().startswith(b"SQLite format 3\x00")


def test_daily_backup_runs_once_per_day_and_prunes(file_app):
    folder = backup.backups_dir()
    for day in ("20260101", "20260102", "20260103", "20260104"):
        (folder / f"daily_{day}.db").write_bytes(b"old")
    manual = folder / "maintenance_tracker_20260101_120000.db"
    manual.write_bytes(b"manual")

    created = backup.ensure_daily_backup()
    assert created == folder / f"daily_{date.today():%Y%m%d}.db"
    assert backup.ensure_daily_backup() is None  # same day: no second copy

    dailies = sorted(p.name for p in folder.glob("daily_*.db"))
    assert len(dailies) == 3  # BACKUP_KEEP_DAYS
    assert dailies[-1] == created.name
    assert manual.exists()  # manual backups are never pruned
    assert not list(folder.glob("*.partial"))


def test_daily_backup_failure_never_raises(file_app, monkeypatch):
    def boom(*args):
        raise OSError("disk full")

    monkeypatch.setattr(backup, "copy_database", boom)
    assert backup.ensure_daily_backup() is None


def test_first_request_of_the_day_makes_the_backup(tmp_path):
    config = type(
        "AutoConfig",
        (TestConfig,),
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'live.db').as_posix()}",
            "BACKUP_DIR": str(tmp_path / "backups"),
            "AUTO_BACKUP": True,
        },
    )
    app = create_app(config)
    with app.app_context():
        _db.create_all()
        client = login_as(app.test_client(), make_user())
        assert client.get("/").status_code == 200
        assert (tmp_path / "backups" / f"daily_{date.today():%Y%m%d}.db").exists()
        _db.session.remove()
        _db.engine.dispose()


def test_restore_replaces_live_data_and_keeps_a_safety_copy(file_app):
    make_flat()
    saved = backup.create_backup()
    make_flat()
    assert _count_flats(backup.db_path()) == 2

    safety = backup.restore_backup(saved)
    assert _count_flats(backup.db_path()) == 1
    assert _count_flats(safety) == 2


def test_download_backup_button(file_app):
    make_flat()
    client = login_as(file_app.test_client(), make_user())
    response = client.get("/settings/backup/download")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert response.data.startswith(b"SQLite format 3\x00")


def test_cli_backup_and_list(file_app):
    runner = file_app.test_cli_runner()
    result = runner.invoke(args=["backup"])
    assert result.exit_code == 0 and "Backed up to" in result.output
    result = runner.invoke(args=["list-backups"])
    assert "1. maintenance_tracker_" in result.output
