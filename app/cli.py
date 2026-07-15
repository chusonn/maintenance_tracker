"""Maintenance CLI: flask backup / restore / list-backups.

All paths are derived from app.instance_path so the commands always
operate on the database the app actually uses. Stop the dev server
before backup/restore — Windows locks the open SQLite file.
"""

import shutil
from datetime import datetime
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext


def _db_path() -> Path:
    return Path(current_app.instance_path) / "maintenance_tracker.db"


def _backups_dir() -> Path:
    d = Path(current_app.root_path).parent / "backups"
    d.mkdir(exist_ok=True)
    return d


def _list_backups() -> list[Path]:
    return sorted(_backups_dir().glob("*.db"), reverse=True)


@click.command("backup")
@with_appcontext
def backup_command() -> None:
    """Copy the live database into backups/."""
    src = _db_path()
    if not src.exists():
        raise click.ClickException(f"No database at {src}")
    dest = _backups_dir() / f"maintenance_tracker_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(src, dest)
    click.echo(f"Backed up to {dest}")


@click.command("list-backups")
@with_appcontext
def list_backups_command() -> None:
    """List available backups, newest first."""
    backups = _list_backups()
    if not backups:
        click.echo("No backups found.")
        return
    for i, path in enumerate(backups, 1):
        size_kb = path.stat().st_size // 1024
        click.echo(f"{i}. {path.name} ({size_kb} KB)")


@click.command("restore")
@click.argument("number", type=int)
@with_appcontext
def restore_command(number: int) -> None:
    """Restore backup NUMBER (from list-backups) over the live database."""
    backups = _list_backups()
    if not 1 <= number <= len(backups):
        raise click.ClickException(f"No backup #{number}; run list-backups first.")
    src = backups[number - 1]
    dest = _db_path()
    if dest.exists():
        safety = _backups_dir() / f"pre_restore_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(dest, safety)
        click.echo(f"Current database saved to {safety}")
    shutil.copy2(src, dest)
    click.echo(f"Restored {src.name} to {dest}")


def register(app) -> None:
    app.cli.add_command(backup_command)
    app.cli.add_command(list_backups_command)
    app.cli.add_command(restore_command)
