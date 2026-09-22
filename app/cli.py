"""Maintenance CLI: flask backup / list-backups / restore N / create-user / set-password.

Backups go through services/backup.py (SQLite online-backup API), so
`flask backup` is safe while the server runs. `restore` overwrites the live
database: stop the web server first.
"""

import click
from flask import current_app
from flask.cli import with_appcontext

from .extensions import db
from .services import accounts, backup


@click.command("backup")
@with_appcontext
def backup_command() -> None:
    """Copy the live database into the backups folder."""
    try:
        dest = backup.create_backup()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Backed up to {dest}")


@click.command("list-backups")
@with_appcontext
def list_backups_command() -> None:
    """List available backups, newest first."""
    backups = backup.list_backups()
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
    backups = backup.list_backups()
    if not 1 <= number <= len(backups):
        raise click.ClickException(f"No backup #{number}; run list-backups first.")
    src = backups[number - 1]
    safety = backup.restore_backup(src)
    click.echo(f"Current database saved to {safety}")
    click.echo(f"Restored {src.name} to {backup.db_path()}")


@click.command("create-user")
@click.argument("email")
@click.option("--name", prompt="Name shown on jobs", help="Display name, e.g. 'Anna'.")
@click.password_option(help="Prompted (hidden) if omitted.")
@with_appcontext
def create_user_command(email: str, name: str, password: str) -> None:
    """Add a login account."""
    try:
        user = accounts.create_user(
            email, name, password, min_length=current_app.config["MIN_PASSWORD_LENGTH"]
        )
    except accounts.AccountError as exc:
        raise click.ClickException(str(exc)) from exc
    db.session.commit()
    click.echo(f"Created account for {user.name} <{user.email}>")


@click.command("set-password")
@click.argument("email")
@click.password_option(help="Prompted (hidden) if omitted.")
@with_appcontext
def set_password_command(email: str, password: str) -> None:
    """Reset an account's password (also clears a lockout)."""
    user = accounts.find_user(email)
    if user is None:
        raise click.ClickException(f"No account for {email}")
    try:
        accounts.validate_password(password, current_app.config["MIN_PASSWORD_LENGTH"])
    except accounts.AccountError as exc:
        raise click.ClickException(str(exc)) from exc
    user.set_password(password)
    accounts.reset_lockout(user)
    db.session.commit()
    click.echo(f"Password updated for {user.email}")


def register(app) -> None:
    app.cli.add_command(backup_command)
    app.cli.add_command(list_backups_command)
    app.cli.add_command(restore_command)
    app.cli.add_command(create_user_command)
    app.cli.add_command(set_password_command)
