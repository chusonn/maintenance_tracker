import io
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user
from sqlalchemy import select

from ..extensions import db
from ..models import User
from ..services import accounts, backup

bp = Blueprint("settings", __name__, url_prefix="/settings")


def _last_daily_backup():
    try:
        dailies = sorted(backup.backups_dir().glob(f"{backup.DAILY_PREFIX}*.db"), reverse=True)
    except RuntimeError:  # not a file database (tests / in-memory)
        return None
    if not dailies:
        return None
    return datetime.fromtimestamp(dailies[0].stat().st_mtime)


@bp.route("")
def index():
    users = db.session.scalars(select(User).order_by(User.name)).all()
    return render_template(
        "settings.html",
        users=users,
        min_password_length=current_app.config["MIN_PASSWORD_LENGTH"],
        auto_backup=current_app.config["AUTO_BACKUP"],
        keep_days=current_app.config["BACKUP_KEEP_DAYS"],
        last_backup=_last_daily_backup() if current_app.config["AUTO_BACKUP"] else None,
        new_user=request.args,  # never holds a password
    )


@bp.route("/password", methods=["POST"])
def change_password():
    current = request.form.get("current_password") or ""
    new = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    if not current_user.check_password(current):
        flash("Your current password is not correct.", "danger")
    elif new != confirm:
        flash("The new passwords don't match.", "danger")
    else:
        try:
            accounts.validate_password(new, current_app.config["MIN_PASSWORD_LENGTH"])
        except accounts.AccountError as exc:
            flash(str(exc), "danger")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Your password has been changed.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/users", methods=["POST"])
def add_user():
    email = request.form.get("email") or ""
    name = request.form.get("name") or ""
    try:
        user = accounts.create_user(
            email,
            name,
            request.form.get("password") or "",
            min_length=current_app.config["MIN_PASSWORD_LENGTH"],
        )
    except accounts.AccountError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("settings.index", name=name, email=email))
    db.session.commit()
    flash(
        f"{user.name} can now sign in as {user.email}. Share the password with them "
        "privately and ask them to change it under Settings.",
        "success",
    )
    return redirect(url_for("settings.index"))


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
def toggle_user(user_id: int):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You can't disable your own account.", "warning")
        return redirect(url_for("settings.index"))
    user.is_enabled = not user.is_enabled
    if user.is_enabled:
        accounts.reset_lockout(user)
    db.session.commit()
    state = "can sign in again" if user.is_enabled else "can no longer sign in"
    flash(f"{user.name} {state}.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/users/<int:user_id>/password", methods=["POST"])
def reset_user_password(user_id: int):
    """Set a temporary password for someone who forgot theirs."""
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Use 'Change your password' for your own account.", "warning")
        return redirect(url_for("settings.index"))
    password = request.form.get("password") or ""
    try:
        accounts.validate_password(password, current_app.config["MIN_PASSWORD_LENGTH"])
    except accounts.AccountError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("settings.index"))
    user.set_password(password)
    accounts.reset_lockout(user)
    db.session.commit()
    flash(
        f"New password set for {user.name}. Share it with them privately and ask them "
        "to change it under Settings.",
        "success",
    )
    return redirect(url_for("settings.index"))


@bp.route("/backup/download")
def download_backup():
    try:
        data = backup.snapshot_bytes()
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("settings.index"))
    return send_file(
        io.BytesIO(data),
        as_attachment=True,
        download_name=f"maintenance_tracker_backup_{datetime.now():%Y%m%d_%H%M}.db",
        mimetype="application/vnd.sqlite3",
    )
