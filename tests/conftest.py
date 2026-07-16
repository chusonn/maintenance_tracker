import smtplib

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def mail_configured(app):
    app.config.update(SMTP_USERNAME="tracker@example.com", SMTP_PASSWORD="abcd efgh ijkl mnop")
    return app


class FakeSMTP:
    """Records the SMTP conversation instead of talking to a server."""

    def __init__(self):
        self.init_args = None
        self.starttls_called = False
        self.login_args = None
        self.sent_messages = []
        self.raise_on_send: Exception | None = None

    def __call__(self, host, port, timeout=None):
        self.init_args = (host, port, timeout)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.starttls_called = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        if self.raise_on_send:
            raise self.raise_on_send
        self.sent_messages.append(message)


@pytest.fixture
def smtp_spy(monkeypatch):
    spy = FakeSMTP()
    monkeypatch.setattr(smtplib, "SMTP", spy)
    return spy
