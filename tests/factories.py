"""Tiny factory helpers. Each returns a committed instance."""

from datetime import date

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Contractor, Flat, MaintenanceJob, MessageTemplate, User

_counter = {"n": 0}


def _next() -> int:
    _counter["n"] += 1
    return _counter["n"]


def make_flat(**overrides) -> Flat:
    n = _next()
    defaults = {
        "flat_number": f"F{n}",
        "payment_reference": f"PAY-{n:04d}",
        "address": f"{n} Test Street, London",
        "postcode": "SW1A 1AA",
        "tenant_name": f"Tenant {n}",
        "rent_amount": 1200.0,
    }
    flat = Flat(**{**defaults, **overrides})
    db.session.add(flat)
    db.session.commit()
    return flat


def make_contractor(**overrides) -> Contractor:
    n = _next()
    defaults = {
        "name": f"Contractor {n}",
        "company": f"Company {n} Ltd",
        "email": f"contractor{n}@example.com",
        "phone": "07700900000",
        "specialty": "Plumbing",
    }
    contractor = Contractor(**{**defaults, **overrides})
    db.session.add(contractor)
    db.session.commit()
    return contractor


def make_template(**overrides) -> MessageTemplate:
    n = _next()
    defaults = {
        "name": f"Template {n}",
        "subject": "Follow-up: {job_title} ({payment_reference})",
        "body": "Hi {contractor_name},\n\nAny update on {job_title}?\n\nThanks",
    }
    template = MessageTemplate(**{**defaults, **overrides})
    db.session.add(template)
    db.session.commit()
    return template


def make_job(flat: Flat | None = None, **overrides) -> MaintenanceJob:
    n = _next()
    if flat is None:
        flat = make_flat()
    defaults = {
        "flat_id": flat.id,
        "title": f"Job {n}",
        "description": "Something needs fixing",
        "priority": "Medium",
        "status": "Pending",
        "reported_date": date.today(),
    }
    job = MaintenanceJob(**{**defaults, **overrides})
    db.session.add(job)
    db.session.commit()
    return job


TEST_PASSWORD = "correct horse battery"


def make_user(password: str = TEST_PASSWORD, **overrides) -> User:
    n = _next()
    defaults = {"email": f"user{n}@example.com", "name": f"User {n}"}
    user = User(**{**defaults, **overrides})
    # Cheap hash keeps the suite fast; check_password_hash reads any method.
    user.password_hash = generate_password_hash(password, method="pbkdf2:sha256:1000")
    db.session.add(user)
    db.session.commit()
    return user
