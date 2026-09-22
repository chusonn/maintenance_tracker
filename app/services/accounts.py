"""Login accounts: creation, password rules, and sign-in with lockout.

Pure domain logic (no request/session handling); callers commit where noted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from functools import cache

from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import User, utcnow


class AccountError(ValueError):
    """A user-facing validation problem (bad email, weak password, duplicate)."""


@dataclass
class SignInResult:
    user: User | None = None
    locked_minutes: int = 0  # > 0 when the account is currently locked

    @property
    def ok(self) -> bool:
        return self.user is not None


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_password(password: str, min_length: int) -> None:
    if len(password or "") < min_length:
        raise AccountError(f"Passwords must be at least {min_length} characters.")


def find_user(email: str) -> User | None:
    return db.session.scalar(select(User).where(User.email == normalize_email(email)))


def create_user(email: str, name: str, password: str, *, min_length: int) -> User:
    """Validate and add a new account (caller commits)."""
    email = normalize_email(email)
    name = (name or "").strip()
    if "@" not in email:
        raise AccountError("Enter a valid email address.")
    if not name:
        raise AccountError("Enter a name - it is shown on the jobs this person logs.")
    validate_password(password, min_length)
    if find_user(email):
        raise AccountError(f"An account for {email} already exists.")
    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    return user


def reset_lockout(user: User) -> None:
    user.failed_logins = 0
    user.locked_until = None


@cache
def _dummy_hash() -> str:
    return generate_password_hash("not-a-real-account-password")


def sign_in(email: str, password: str, *, max_attempts: int, lockout_minutes: int) -> SignInResult:
    """Check credentials, counting failures towards a temporary lock. Commits.

    Unknown emails and disabled accounts fail exactly like a wrong password, so
    the login form never reveals which accounts exist.
    """
    user = find_user(email)
    if user is None:
        check_password_hash(_dummy_hash(), password or "")  # similar timing to a real check
        return SignInResult()

    now = utcnow()
    if user.locked_until and user.locked_until > now:
        remaining = (user.locked_until - now).total_seconds() / 60
        return SignInResult(locked_minutes=max(1, math.ceil(remaining)))

    if not user.check_password(password or "") or not user.is_enabled:
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= max_attempts:
            user.failed_logins = 0
            user.locked_until = now + timedelta(minutes=lockout_minutes)
            db.session.commit()
            return SignInResult(locked_minutes=lockout_minutes)
        db.session.commit()
        return SignInResult()

    reset_lockout(user)
    user.last_login_at = now
    db.session.commit()
    return SignInResult(user=user)


def ensure_initial_user(config) -> User | None:
    """Create the first account from INITIAL_USER_* settings, only while the
    app has no accounts at all (so it never resurrects or overwrites one)."""
    email = config.get("INITIAL_USER_EMAIL")
    password = config.get("INITIAL_USER_PASSWORD")
    if not (email and password):
        return None
    if db.session.scalar(select(func.count()).select_from(User)):
        return None
    user = create_user(
        email,
        config.get("INITIAL_USER_NAME") or email.split("@")[0],
        password,
        min_length=config["MIN_PASSWORD_LENGTH"],
    )
    db.session.commit()
    return user
