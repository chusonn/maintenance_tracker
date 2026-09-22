import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

DEV_SECRET_KEY = "dev-only-secret-key"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", DEV_SECRET_KEY)
    # Relative sqlite paths resolve against the Flask instance/ folder,
    # so this is instance/maintenance_tracker.db. In production it must be
    # an absolute path on the persistent volume (enforced in create_app).
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///maintenance_tracker.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Idempotent startup schema sync (PRAGMA column adds + create_all).
    RUN_SCHEMA_SYNC = True

    # APP_ENV=production (set on the server) turns on HTTPS-only cookies and
    # proxy-header trust, and refuses to start with an unsafe configuration.
    PRODUCTION = os.getenv("APP_ENV") == "production"
    SESSION_COOKIE_SECURE = PRODUCTION
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = PRODUCTION
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # Wrong passwords before an account is locked, and for how long.
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
    MIN_PASSWORD_LENGTH = 10

    # First account, created at startup only while no accounts exist yet.
    INITIAL_USER_EMAIL = os.getenv("INITIAL_USER_EMAIL")
    INITIAL_USER_NAME = os.getenv("INITIAL_USER_NAME")
    INITIAL_USER_PASSWORD = os.getenv("INITIAL_USER_PASSWORD")

    # Daily automatic backup (first request of each day). Default location is
    # <project>/backups locally, or a backups/ folder beside the database file
    # in production (i.e. on the persistent volume).
    AUTO_BACKUP = True
    BACKUP_DIR = os.getenv("BACKUP_DIR")
    BACKUP_KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "30"))

    # Follow-up emails (optional): leave username/password unset to disable
    # sending — the composer then degrades to "record without emailing".
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    # Set to 0 only for a local test sink (e.g. aiosmtpd) with no TLS/auth.
    SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "1") != "0"
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Maintenance Tracker")
    # Days before an active job is due another follow-up.
    FOLLOW_UP_DAYS = int(os.getenv("FOLLOW_UP_DAYS", "7"))


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RUN_SCHEMA_SYNC = False
    WTF_CSRF_ENABLED = False
    PRODUCTION = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    AUTO_BACKUP = False
    INITIAL_USER_EMAIL = None
    INITIAL_USER_NAME = None
    INITIAL_USER_PASSWORD = None
