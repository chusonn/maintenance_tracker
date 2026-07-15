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


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RUN_SCHEMA_SYNC = False
    WTF_CSRF_ENABLED = False
