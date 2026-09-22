from app.extensions import db
from app.models import Contractor, Flat, MaintenanceJob, User, utcnow

from .factories import TEST_PASSWORD, make_contractor, make_flat, make_job, make_user

# ---------- settings page ----------


def test_settings_page_lists_people(client, user):
    other = make_user(name="Anna")
    html = client.get("/settings").get_data(as_text=True)
    assert "People with access" in html
    assert "Test User" in html and "(you)" in html
    assert other.email in html
    assert f"/settings/users/{user.id}/toggle" not in html  # can't disable yourself
    assert f"/settings/users/{other.id}/toggle" in html


def test_change_password_success(client, user):
    response = client.post(
        "/settings/password",
        data={
            "current_password": TEST_PASSWORD,
            "new_password": "a brand new password",
            "confirm_password": "a brand new password",
        },
        follow_redirects=True,
    )
    assert "password has been changed" in response.get_data(as_text=True)
    assert db.session.get(User, user.id).check_password("a brand new password")


def test_change_password_rejects_bad_input(client, user):
    cases = [
        (("wrong", "x" * 12, "x" * 12), "current password is not correct"),
        ((TEST_PASSWORD, "x" * 12, "y" * 12), "don&#39;t match"),
        ((TEST_PASSWORD, "short", "short"), "at least"),
    ]
    for (current, new, confirm), message in cases:
        data = {"current_password": current, "new_password": new, "confirm_password": confirm}
        response = client.post("/settings/password", data=data, follow_redirects=True)
        assert message in response.get_data(as_text=True)
    assert db.session.get(User, user.id).check_password(TEST_PASSWORD)


def test_add_user(client):
    response = client.post(
        "/settings/users",
        data={"name": "Anna", "email": "Anna@Example.com", "password": "temporary pass 1"},
        follow_redirects=True,
    )
    assert "Anna can now sign in" in response.get_data(as_text=True)
    anna = db.session.scalar(db.select(User).where(User.email == "anna@example.com"))
    assert anna.check_password("temporary pass 1")


def test_add_user_error_keeps_typed_name_and_email(client):
    response = client.post(
        "/settings/users", data={"name": "Anna", "email": "anna@example.com", "password": "short"}
    )
    assert response.status_code == 302
    assert "name=Anna" in response.headers["Location"]
    assert "short" not in response.headers["Location"]  # the password is never echoed
    html = client.get(response.headers["Location"]).get_data(as_text=True)
    assert 'value="anna@example.com"' in html


def test_disable_and_enable_another_user(client):
    other = make_user(name="Anna")
    client.post(f"/settings/users/{other.id}/toggle")
    assert db.session.get(User, other.id).is_enabled is False
    other = db.session.get(User, other.id)
    other.failed_logins, other.locked_until = 4, utcnow()
    db.session.commit()
    client.post(f"/settings/users/{other.id}/toggle")
    other = db.session.get(User, other.id)
    assert other.is_enabled is True
    assert other.failed_logins == 0 and other.locked_until is None


def test_cannot_disable_yourself(client, user):
    response = client.post(f"/settings/users/{user.id}/toggle", follow_redirects=True)
    assert "can&#39;t disable your own account" in response.get_data(as_text=True)
    assert db.session.get(User, user.id).is_enabled is True


def test_reset_another_users_password(client):
    other = make_user(name="Anna", failed_logins=3, locked_until=utcnow())
    response = client.post(
        f"/settings/users/{other.id}/password",
        data={"password": "temporary pass 2"},
        follow_redirects=True,
    )
    assert "New password set for Anna" in response.get_data(as_text=True)
    other = db.session.get(User, other.id)
    assert other.check_password("temporary pass 2")
    assert other.locked_until is None and other.failed_logins == 0


def test_reset_password_rules(client, user):
    other = make_user(name="Anna")
    html = client.post(
        f"/settings/users/{other.id}/password", data={"password": "short"}, follow_redirects=True
    ).get_data(as_text=True)
    assert "at least" in html
    html = client.post(
        f"/settings/users/{user.id}/password",
        data={"password": "a long password"},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert "Change your password" in html
    assert db.session.get(User, user.id).check_password(TEST_PASSWORD)


def test_download_backup_needs_a_file_database(client):
    response = client.get("/settings/backup/download", follow_redirects=True)
    assert "not using a file-based SQLite database" in response.get_data(as_text=True)


# ---------- who did what ----------


def test_new_job_records_who_logged_it(client):
    flat = make_flat()
    client.post(
        "/jobs/add",
        data={"flat_id": flat.id, "title": "Leak", "description": "", "priority": "High"},
    )
    job = db.session.scalar(db.select(MaintenanceJob))
    assert job.created_by == "Test User"
    assert "Logged by" in client.get(f"/jobs/{job.id}/edit").get_data(as_text=True)


def test_deletes_record_who_deleted(client):
    job = make_job()
    contractor = make_contractor()
    idle_flat = make_flat()
    client.post(f"/jobs/{job.id}/delete")
    client.post(f"/contractors/{contractor.id}/delete")
    client.post(f"/flats/{idle_flat.id}/delete")
    assert db.session.get(MaintenanceJob, job.id).deleted_by == "Test User"
    assert db.session.get(Contractor, contractor.id).deleted_by == "Test User"
    assert db.session.get(Flat, idle_flat.id).deleted_by == "Test User"
    assert "by Test User" in client.get("/recycle-bin").get_data(as_text=True)


def test_flat_cascade_tag_is_kept_for_its_jobs(client):
    flat = make_flat()
    job = make_job(flat=flat, status="Completed")
    client.post(f"/flats/{flat.id}/delete")
    assert db.session.get(Flat, flat.id).deleted_by == "Test User"
    assert db.session.get(MaintenanceJob, job.id).deleted_by == "cascade:flat"


def test_emailed_followup_audit_line_names_the_sender(client, mail_configured, smtp_spy):
    job = make_job(contractor_id=make_contractor().id, status="Scheduled")
    client.post(
        f"/jobs/{job.id}/followup",
        data={
            "action": "send",
            "recipient": "contractor@example.com",
            "subject": "Any update?",
            "body": "Hello",
            "follow_up_notes": "",
        },
    )
    assert "by Test User]" in db.session.get(MaintenanceJob, job.id).follow_up_notes
