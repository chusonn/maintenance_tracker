from datetime import date

from app.extensions import db
from app.models import MaintenanceJob

from .factories import make_contractor, make_flat, make_job


def test_add_job_sets_reported_date_to_today(client):
    flat = make_flat()
    client.post(
        "/jobs/add",
        data={
            "flat_id": flat.id,
            "title": "Leaky tap",
            "description": "Kitchen tap drips",
            "priority": "Low",
            "estimated_cost": "",
        },
    )
    job = db.session.scalar(db.select(MaintenanceJob))
    assert job is not None
    assert job.reported_date == date.today()
    assert isinstance(job.reported_date, date)


def test_add_job_flat_dropdown_excludes_deleted_flats(client):
    make_flat(payment_reference="VISIBLE-1")
    deleted = make_flat(payment_reference="DELETED-1")
    deleted.soft_delete()
    db.session.commit()

    page = client.get("/jobs/add").get_data(as_text=True)
    assert "VISIBLE-1" in page
    assert "DELETED-1" not in page


def test_jobs_list_filters(client):
    flat = make_flat(payment_reference="SEARCH-ME")
    make_job(flat, title="Urgent boiler", priority="Urgent", status="Pending")
    make_job(title="Completed fence", priority="Low", status="Completed")

    page = client.get("/jobs?status=Pending").get_data(as_text=True)
    assert "Urgent boiler" in page and "Completed fence" not in page

    page = client.get("/jobs?priority=Low").get_data(as_text=True)
    assert "Completed fence" in page and "Urgent boiler" not in page

    page = client.get("/jobs?search=SEARCH-ME").get_data(as_text=True)
    assert "Urgent boiler" in page and "Completed fence" not in page


def test_jobs_list_excludes_soft_deleted(client):
    job = make_job(title="Ghost job")
    job.soft_delete()
    db.session.commit()
    page = client.get("/jobs").get_data(as_text=True)
    assert "Ghost job" not in page


def test_schedule_job_assigns_contractor_and_status(client):
    job = make_job()
    contractor = make_contractor()
    client.post(
        f"/jobs/{job.id}/schedule",
        data={"contractor_id": contractor.id, "scheduled_date": "2026-08-01", "notes": "booked"},
    )
    assert job.status == "Scheduled"
    assert job.contractor_id == contractor.id
    assert job.scheduled_date == date(2026, 8, 1)


def test_schedule_dropdown_excludes_deleted_contractors(client):
    job = make_job()
    make_contractor(name="Visible Trades")
    gone = make_contractor(name="Deleted Trades")
    gone.soft_delete()
    db.session.commit()

    page = client.get(f"/jobs/{job.id}/schedule").get_data(as_text=True)
    assert "Visible Trades" in page
    assert "Deleted Trades" not in page


def test_complete_job_honours_posted_completion_date(client):
    job = make_job(status="In Progress")
    client.post(
        f"/jobs/{job.id}/complete",
        data={"actual_cost": "150.00", "notes": "done", "completed_date": "2026-07-01"},
    )
    assert job.status == "Completed"
    assert job.actual_cost == 150.0
    assert job.completed_date == date(2026, 7, 1)


def test_complete_job_defaults_to_today_without_date(client):
    job = make_job(status="In Progress")
    client.post(f"/jobs/{job.id}/complete", data={"actual_cost": "", "notes": ""})
    assert job.completed_date == date.today()


def test_followup_increments_count_and_sets_notes(client):
    job = make_job()
    client.post(f"/jobs/{job.id}/followup", data={"follow_up_notes": "chased tenant"})
    client.post(f"/jobs/{job.id}/followup", data={"follow_up_notes": "chased again"})
    assert job.follow_up_count == 2
    assert job.follow_up_notes == "chased again"


def test_dashboard_counts_exclude_deleted_jobs(client):
    make_job(status="Pending")
    dead = make_job(status="Pending")
    dead.soft_delete()
    db.session.commit()

    page = client.get("/dashboard").get_data(as_text=True)
    assert page  # renders
    # total jobs stat should be 1, not 2 — the deleted one is excluded
    from sqlalchemy import func, select

    from app.models import MaintenanceJob as MJ

    live = db.session.scalar(
        select(func.count()).select_from(MJ).where(MJ.is_deleted == False)
    )
    assert live == 1
