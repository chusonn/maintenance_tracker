from datetime import timedelta

import pytest
from flask import url_for

from app import PUBLIC_ENDPOINTS
from app.extensions import db
from app.models import User, utcnow
from app.services import accounts

from .conftest import login_as
from .factories import TEST_PASSWORD, make_user


def _login(client, email, password, **extra):
    return client.post("/login", data={"email": email, "password": password, **extra})


def _protected_urls(app, method):
    with app.test_request_context():
        for rule in app.url_map.iter_rules():
            if rule.endpoint in PUBLIC_ENDPOINTS or method not in rule.methods:
                continue
            values = {arg: ("job" if arg == "kind" else 1) for arg in rule.arguments}
            yield url_for(rule.endpoint, **values)


# ---------- the guard ----------


def test_every_get_page_requires_login(app, anon_client):
    urls = list(_protected_urls(app, "GET"))
    assert len(urls) > 20  # sanity: the whole app is covered, not a handful of pages
    for url in urls:
        response = anon_client.get(url)
        assert response.status_code == 302, url
        assert "/login" in response.headers["Location"], url


def test_every_post_action_requires_login(app, anon_client):
    urls = list(_protected_urls(app, "POST"))
    assert len(urls) > 15
    for url in urls:
        response = anon_client.post(url)
        assert response.status_code == 302, url
        assert "/login" in response.headers["Location"], url


def test_unknown_url_redirects_anonymous_to_login(anon_client):
    response = anon_client.get("/no-such-page")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_healthcheck_is_public(anon_client):
    response = anon_client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_login_page_renders(anon_client):
    html = anon_client.get("/login").get_data(as_text=True)
    assert "Sign in" in html
    assert 'name="password"' in html


# ---------- signing in ----------


def test_login_success_redirects_and_records_last_login(app, anon_client):
    user = make_user(email="anna@example.com")
    response = _login(anon_client, "anna@example.com", TEST_PASSWORD)
    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"
    assert anon_client.get("/").status_code == 200
    assert db.session.get(User, user.id).last_login_at is not None


def test_login_email_is_case_and_space_insensitive(anon_client):
    make_user(email="anna@example.com")
    response = _login(anon_client, "  Anna@Example.COM ", TEST_PASSWORD)
    assert response.status_code == 302


def test_wrong_password_counts_a_failure(anon_client):
    user = make_user(email="anna@example.com")
    response = _login(anon_client, "anna@example.com", "wrong password!")
    assert response.status_code == 200
    assert "don&#39;t match" in response.get_data(as_text=True)
    assert db.session.get(User, user.id).failed_logins == 1


def test_unknown_email_gets_the_same_message(anon_client):
    response = _login(anon_client, "nobody@example.com", "whatever12345")
    assert "don&#39;t match" in response.get_data(as_text=True)


def test_account_locks_after_max_attempts(app, anon_client):
    user = make_user(email="anna@example.com")
    for _ in range(app.config["LOGIN_MAX_ATTEMPTS"]):
        response = _login(anon_client, "anna@example.com", "wrong password!")
    assert "locked" in response.get_data(as_text=True)

    # Even the right password is refused while locked.
    response = _login(anon_client, "anna@example.com", TEST_PASSWORD)
    assert response.status_code == 200
    assert "locked" in response.get_data(as_text=True)

    # Once the lock expires, the right password works and the counter resets.
    user = db.session.get(User, user.id)
    user.locked_until = utcnow() - timedelta(minutes=1)
    db.session.commit()
    assert _login(anon_client, "anna@example.com", TEST_PASSWORD).status_code == 302
    user = db.session.get(User, user.id)
    assert user.failed_logins == 0 and user.locked_until is None


def test_disabled_account_cannot_sign_in(anon_client):
    make_user(email="anna@example.com", is_enabled=False)
    response = _login(anon_client, "anna@example.com", TEST_PASSWORD)
    assert response.status_code == 200
    assert "don&#39;t match" in response.get_data(as_text=True)


def test_disabling_an_account_ends_its_session(app):
    user = make_user()
    client = login_as(app.test_client(), user)
    assert client.get("/").status_code == 200
    user.is_enabled = False
    db.session.commit()
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_next_is_followed_when_it_is_a_local_path(anon_client):
    make_user(email="anna@example.com")
    response = _login(anon_client, "anna@example.com", TEST_PASSWORD, next="/jobs?status=Pending")
    assert response.headers["Location"] == "/jobs?status=Pending"


@pytest.mark.parametrize("target", ["https://evil.example.com/", "//evil.example.com", "jobs"])
def test_next_is_ignored_when_not_a_local_path(anon_client, target):
    make_user(email="anna@example.com")
    response = _login(anon_client, "anna@example.com", TEST_PASSWORD, next=target)
    assert response.headers["Location"] == "/dashboard"


def test_signed_in_user_visiting_login_is_sent_to_dashboard(client):
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"


def test_logout_is_post_only_and_ends_the_session(client):
    assert client.get("/logout").status_code == 405
    response = client.post("/logout")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert "/login" in client.get("/").headers["Location"]


def test_topbar_shows_who_is_signed_in(client):
    html = client.get("/").get_data(as_text=True)
    assert "Test User" in html
    assert 'action="/logout"' in html


# ---------- accounts service ----------


def test_create_user_validates_input(app):
    with pytest.raises(accounts.AccountError, match="valid email"):
        accounts.create_user("not-an-email", "Anna", "long enough pw", min_length=10)
    with pytest.raises(accounts.AccountError, match="name"):
        accounts.create_user("anna@example.com", "  ", "long enough pw", min_length=10)
    with pytest.raises(accounts.AccountError, match="at least 10"):
        accounts.create_user("anna@example.com", "Anna", "short", min_length=10)
    make_user(email="taken@example.com")
    with pytest.raises(accounts.AccountError, match="already exists"):
        accounts.create_user("TAKEN@example.com", "Anna", "long enough pw", min_length=10)


def test_initial_user_is_created_only_when_there_are_no_accounts(app):
    config = {
        "INITIAL_USER_EMAIL": "Owner@Example.com",
        "INITIAL_USER_NAME": "Owner",
        "INITIAL_USER_PASSWORD": "a long first password",
        "MIN_PASSWORD_LENGTH": 10,
    }
    user = accounts.ensure_initial_user(config)
    assert user.email == "owner@example.com"
    assert user.check_password("a long first password")
    assert accounts.ensure_initial_user(config) is None  # already has an account


def test_initial_user_needs_email_and_password(app):
    assert accounts.ensure_initial_user({"INITIAL_USER_EMAIL": "a@b.com"}) is None


# ---------- CLI ----------


def test_cli_create_user_and_set_password(app):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-user", "Anna@Example.com", "--name", "Anna", "--password", "first password 1"]
    )
    assert result.exit_code == 0, result.output
    user = accounts.find_user("anna@example.com")
    assert user.name == "Anna" and user.check_password("first password 1")

    user.failed_logins, user.locked_until = 3, utcnow() + timedelta(minutes=5)
    db.session.commit()
    result = runner.invoke(
        args=["set-password", "anna@example.com", "--password", "second password 2"]
    )
    assert result.exit_code == 0, result.output
    user = accounts.find_user("anna@example.com")
    assert user.check_password("second password 2")
    assert user.locked_until is None and user.failed_logins == 0


def test_cli_rejects_short_password(app):
    result = app.test_cli_runner().invoke(
        args=["create-user", "anna@example.com", "--name", "Anna", "--password", "short"]
    )
    assert result.exit_code != 0
    assert "at least" in result.output
