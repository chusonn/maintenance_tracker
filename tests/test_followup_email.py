"""Follow-up email feature: SMTP transport, placeholder rendering, the
composer flow, the due-followups queue, and bulk sending."""

import smtplib
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import MessageTemplate
from app.services import emailer
from app.services.followup import (
    due_followups_stmt,
    ensure_default_templates,
    render_placeholders,
    render_template_for_job,
)

from .factories import make_contractor, make_flat, make_job, make_template

# ---------- emailer ----------


def test_email_not_configured_without_credentials(app):
    assert not emailer.is_configured(app.config)
    with pytest.raises(emailer.EmailNotConfiguredError):
        emailer.send_email(app.config, to="a@b.com", subject="Hi", body="Hello")


def test_send_email_happy_path(mail_configured, smtp_spy):
    emailer.send_email(
        mail_configured.config, to="dave@plumbing.co.uk", subject="Follow-up", body="Any news? £80"
    )
    assert smtp_spy.init_args == ("smtp.gmail.com", 587, 20)
    assert smtp_spy.starttls_called
    # App-password spaces are stripped; the password never lands in the message.
    assert smtp_spy.login_args == ("tracker@example.com", "abcdefghijklmnop")
    (message,) = smtp_spy.sent_messages
    assert message["To"] == "dave@plumbing.co.uk"
    assert message["Subject"] == "Follow-up"
    assert message["From"] == "Maintenance Tracker <tracker@example.com>"
    assert "Any news?" in message.get_content()
    assert "abcdefghijklmnop" not in str(message)


def test_send_email_plain_mode_for_local_sink(mail_configured, smtp_spy):
    mail_configured.config.update(SMTP_STARTTLS=False, SMTP_HOST="localhost", SMTP_PORT=1025)
    emailer.send_email(mail_configured.config, to="a@b.com", subject="Hi", body="Hello")
    assert smtp_spy.init_args == ("localhost", 1025, 20)
    assert not smtp_spy.starttls_called
    assert smtp_spy.login_args is None
    assert len(smtp_spy.sent_messages) == 1


def test_send_email_rejects_header_injection_and_blanks(mail_configured, smtp_spy):
    with pytest.raises(emailer.EmailSendError):
        emailer.send_email(
            mail_configured.config, to="a@b.com\nBcc: x@y.com", subject="Hi", body="Hello"
        )
    with pytest.raises(emailer.EmailSendError):
        emailer.send_email(mail_configured.config, to="a@b.com", subject="", body="Hello")
    assert smtp_spy.sent_messages == []


def test_send_email_wraps_smtp_errors(mail_configured, smtp_spy):
    smtp_spy.raise_on_send = smtplib.SMTPException("boom")
    with pytest.raises(emailer.EmailSendError) as excinfo:
        emailer.send_email(mail_configured.config, to="a@b.com", subject="Hi", body="Hello")
    assert "abcdefghijklmnop" not in str(excinfo.value)


# ---------- placeholder rendering ----------


def test_render_placeholders_substitutes_job_details(db):
    flat = make_flat(address="Flat 2, 9 High St, Leeds", tenant_name="Amelia Clarke")
    contractor = make_contractor(name="Dave Thompson")
    job = make_job(
        flat=flat,
        contractor_id=contractor.id,
        title="Boiler repair",
        scheduled_date=date(2026, 7, 20),
        estimated_cost=1234.0,
    )
    text = (
        "{contractor_name}: {job_title} at {flat_address} on {scheduled_date}"
        " for {estimated_cost}"
    )
    assert render_placeholders(text, job) == (
        "Dave Thompson: Boiler repair at Flat 2, 9 High St, Leeds on 20/07/2026 for £1,234.00"
    )


def test_render_placeholders_is_safe_on_bad_input(db):
    job = make_job()  # no contractor
    assert render_placeholders("{typo_token} stays", job) == "{typo_token} stays"
    assert render_placeholders("stray { brace } ok", job) == "stray { brace } ok"
    assert render_placeholders("to {contractor_name}.", job) == "to ."


def test_render_template_for_job(db):
    job = make_job(title="Fix tap")
    template = make_template(subject="Re: {job_title}", body="About {job_title}...")
    rendered = render_template_for_job(template, job)
    assert rendered == {"subject": "Re: Fix tap", "body": "About Fix tap..."}


# ---------- default templates ----------


def test_ensure_default_templates_is_idempotent(db):
    assert ensure_default_templates() == 3
    assert ensure_default_templates() == 0
    template = db.session.scalars(select(MessageTemplate)).first()
    template.subject = "My edited subject"
    db.session.commit()
    ensure_default_templates()
    assert db.session.get(MessageTemplate, template.id).subject == "My edited subject"
    assert db.session.scalar(select(func.count()).select_from(MessageTemplate)) == 3


# ---------- composer ----------


def test_composer_page_renders_with_prefill(client, db):
    contractor = make_contractor(email="dave@example.com")
    job = make_job(contractor_id=contractor.id, status="In Progress")
    make_template(name="Chase")
    response = client.get(f"/jobs/{job.id}/followup")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="followup-prefill"' in html
    assert "Chase" in html
    assert "dave@example.com" in html
    assert "Email sending is not set up" in html  # unconfigured hint


def test_composer_warns_when_contractor_has_no_email(client, db, mail_configured):
    contractor = make_contractor(email=None)
    job = make_job(contractor_id=contractor.id)
    html = client.get(f"/jobs/{job.id}/followup").get_data(as_text=True)
    assert "has no email address on file" in html


def test_send_action_emails_and_records(client, db, mail_configured, smtp_spy):
    job = make_job(contractor_id=make_contractor().id, status="In Progress")
    response = client.post(
        f"/jobs/{job.id}/followup",
        data={
            "action": "send",
            "recipient": "dave@example.com",
            "subject": "Any update?",
            "body": "Please advise.",
            "follow_up_notes": "chased by email",
        },
    )
    assert response.status_code == 302
    assert len(smtp_spy.sent_messages) == 1
    assert job.follow_up_count == 1
    assert "chased by email" in job.follow_up_notes
    assert 'Emailed dave@example.com - "Any update?"' in job.follow_up_notes


def test_send_action_failure_preserves_form_and_records_nothing(
    client, db, mail_configured, smtp_spy
):
    smtp_spy.raise_on_send = smtplib.SMTPException("boom")
    job = make_job(contractor_id=make_contractor().id)
    response = client.post(
        f"/jobs/{job.id}/followup",
        data={
            "action": "send",
            "recipient": "dave@example.com",
            "subject": "My hand-written subject",
            "body": "My hand-written body",
            "follow_up_notes": "",
        },
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200  # re-render, not redirect
    assert "My hand-written subject" in html
    assert "My hand-written body" in html
    assert job.follow_up_count == 0
    assert job.follow_up_date is None


def test_send_action_blocked_when_unconfigured(client, db):
    job = make_job(contractor_id=make_contractor().id)
    response = client.post(
        f"/jobs/{job.id}/followup",
        data={"action": "send", "recipient": "a@b.com", "subject": "s", "body": "b",
              "follow_up_notes": ""},
    )
    assert response.status_code == 200
    assert job.follow_up_count == 0


def test_send_action_requires_recipient(client, db, mail_configured, smtp_spy):
    job = make_job(contractor_id=make_contractor(email=None).id)
    response = client.post(
        f"/jobs/{job.id}/followup",
        data={"action": "send", "recipient": "", "subject": "s", "body": "b",
              "follow_up_notes": ""},
    )
    assert response.status_code == 200
    assert job.follow_up_count == 0
    assert smtp_spy.sent_messages == []


def test_record_action_never_touches_smtp(client, db, mail_configured, smtp_spy):
    job = make_job()
    response = client.post(
        f"/jobs/{job.id}/followup",
        data={"action": "record", "follow_up_notes": "phoned instead"},
    )
    assert response.status_code == 302
    assert job.follow_up_count == 1
    assert job.follow_up_notes == "phoned instead"
    assert smtp_spy.sent_messages == []


# ---------- due queue ----------


def _aged_job(db, *, status="In Progress", reported_days=10, followups=0, last_followup_days=None):
    job = make_job(status=status, reported_date=date.today() - timedelta(days=reported_days))
    job.follow_up_count = followups
    if last_followup_days is not None:
        job.follow_up_date = datetime.now() - timedelta(days=last_followup_days)
    db.session.commit()
    return job


def test_due_followups_query_boundaries(db):
    due_never = _aged_job(db, reported_days=8)
    fresh = _aged_job(db, reported_days=3)
    due_stale = _aged_job(db, followups=1, last_followup_days=8)
    recently_chased = _aged_job(db, followups=1, last_followup_days=1)
    completed = _aged_job(db, status="Completed", reported_days=30)
    pending = _aged_job(db, status="Pending", reported_days=30)
    binned = _aged_job(db, reported_days=30)
    binned.soft_delete()
    db.session.commit()

    due = db.session.scalars(due_followups_stmt(7)).all()
    due_ids = {job.id for job in due}
    assert due_never.id in due_ids
    assert due_stale.id in due_ids
    for job in (fresh, recently_chased, completed, pending, binned):
        assert job.id not in due_ids


def test_due_followups_respects_days_setting(db):
    job = _aged_job(db, reported_days=5)
    assert job.id in {j.id for j in db.session.scalars(due_followups_stmt(3)).all()}
    assert job.id not in {j.id for j in db.session.scalars(due_followups_stmt(7)).all()}


def test_due_followups_page_renders(client, db):
    _aged_job(db, reported_days=10)
    response = client.get("/jobs/due-followups")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Due Follow-ups" in html


# ---------- bulk send ----------


def test_bulk_send_mixed_outcomes(client, db, mail_configured, smtp_spy):
    template = make_template(name="Bulk chase")
    with_email = make_contractor(email="dave@example.com")
    without_email = make_contractor(email=None)
    sendable_one = _aged_job(db, reported_days=10)
    sendable_one.contractor_id = with_email.id
    sendable_two = _aged_job(db, reported_days=12)
    sendable_two.contractor_id = with_email.id
    skipped = _aged_job(db, reported_days=15)
    skipped.contractor_id = without_email.id
    db.session.commit()

    response = client.post(
        "/jobs/due-followups/send-all",
        data={"template_id": template.id},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert len(smtp_spy.sent_messages) == 2
    assert sendable_one.follow_up_count == 1
    assert sendable_two.follow_up_count == 1
    assert skipped.follow_up_count == 0
    assert "Sent 2 follow-up emails" in html
    assert "Skipped 1" in html


def test_bulk_send_requires_configuration_and_template(client, db, mail_configured):
    response = client.post("/jobs/due-followups/send-all", data={}, follow_redirects=True)
    assert "Choose a template" in response.get_data(as_text=True)
