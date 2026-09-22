from urllib.parse import urlsplit

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from ..services import accounts

bp = Blueprint("auth", __name__)


def _safe_next(target: str | None) -> str | None:
    """Only follow same-site relative paths after login (no open redirects)."""
    if not target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


@bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = _safe_next(request.values.get("next"))
    if current_user.is_authenticated:
        return redirect(next_url or url_for("dashboard.index"))

    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        result = accounts.sign_in(
            email,
            request.form.get("password") or "",
            max_attempts=current_app.config["LOGIN_MAX_ATTEMPTS"],
            lockout_minutes=current_app.config["LOGIN_LOCKOUT_MINUTES"],
        )
        if result.ok:
            login_user(result.user, remember=bool(request.form.get("remember")))
            return redirect(next_url or url_for("dashboard.index"))
        if result.locked_minutes:
            flash(
                "Too many wrong passwords - this account is locked for "
                f"{result.locked_minutes} minute{'s' if result.locked_minutes != 1 else ''}.",
                "danger",
            )
        else:
            flash("That email and password don't match an account.", "danger")

    return render_template("login.html", email=email, next_url=next_url)


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
