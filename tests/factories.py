"""Tiny factory helpers. Each returns a committed instance."""

from datetime import date

from app.extensions import db
from app.models import Contractor, Flat, MaintenanceJob

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
