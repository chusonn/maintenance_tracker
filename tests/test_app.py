import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db

from .factories import make_flat


def test_root_redirects_to_dashboard(client):
    response = client.get("/")
    assert response.status_code == 200  # / serves the dashboard directly


def test_404_page(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404


def test_gbp_and_ukdate_filters(app):
    gbp = app.jinja_env.filters["gbp"]
    ukdate = app.jinja_env.filters["ukdate"]
    from datetime import date

    assert gbp(1250) == "£1,250.00"
    assert gbp(None) == "—"
    assert ukdate(date(2026, 7, 15)) == "15/07/2026"
    assert ukdate(None) == "—"


class CsrfConfig(TestConfig):
    WTF_CSRF_ENABLED = True


@pytest.fixture
def csrf_client():
    app = create_app(CsrfConfig)
    with app.app_context():
        _db.create_all()
        yield app.test_client()
        _db.session.remove()
        _db.drop_all()


def test_post_without_csrf_token_rejected(csrf_client):
    flat = make_flat()
    response = csrf_client.post(f"/flats/{flat.id}/delete")
    assert response.status_code == 400
