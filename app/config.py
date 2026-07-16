import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key")
    # Relative sqlite paths resolve against the Flask instance/ folder,
    # so this is instance/maintenance_tracker.db.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///maintenance_tracker.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Idempotent startup schema sync (PRAGMA column adds + create_all).
    RUN_SCHEMA_SYNC = True

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
