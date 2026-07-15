from sqlalchemy import func, select

from app.extensions import db
from app.models import Contractor, Flat, MaintenanceJob
from app.seed import seed_data


def test_seed_is_deterministic_and_consistent(app):
    counts = seed_data()
    assert counts == {"flats": 15, "contractors": 6, "jobs": 60}

    def count(model):
        return db.session.scalar(select(func.count()).select_from(model))

    assert count(Flat) == 15
    assert count(Contractor) == 6
    assert count(MaintenanceJob) == 60

    # completed jobs must be coherent: contractor, dates, actual cost
    completed = db.session.scalars(
        select(MaintenanceJob).where(MaintenanceJob.status == "Completed")
    ).all()
    assert completed
    for job in completed:
        assert job.contractor_id is not None
        assert job.completed_date >= job.scheduled_date >= job.reported_date
        assert job.actual_cost > 0

    # payment references unique
    refs = db.session.scalars(select(Flat.payment_reference)).all()
    assert len(refs) == len(set(refs))
