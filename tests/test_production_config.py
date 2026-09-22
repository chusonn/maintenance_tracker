import pytest
from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_app
from app.config import DEV_SECRET_KEY, TestConfig

STRONG_KEY = "k" * 64


def _prod_config(tmp_path, **overrides):
    attrs = {
        "PRODUCTION": True,
        "SECRET_KEY": STRONG_KEY,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'live.db').as_posix()}",
        "SESSION_COOKIE_SECURE": True,
        **overrides,
    }
    return type("ProdConfig", (TestConfig,), attrs)


@pytest.mark.parametrize("secret", [DEV_SECRET_KEY, "change-me", "too-short"])
def test_production_refuses_weak_secret_key(tmp_path, secret):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(_prod_config(tmp_path, SECRET_KEY=secret))


def test_production_refuses_relative_sqlite_path(tmp_path):
    with pytest.raises(RuntimeError, match="absolute path"):
        create_app(_prod_config(tmp_path, SQLALCHEMY_DATABASE_URI="sqlite:///maintenance.db"))


def test_production_app_trusts_proxy_and_uses_secure_cookies(tmp_path):
    app = create_app(_prod_config(tmp_path))
    assert isinstance(app.wsgi_app, ProxyFix)
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_development_app_has_no_proxy_fix(app):
    assert not isinstance(app.wsgi_app, ProxyFix)
