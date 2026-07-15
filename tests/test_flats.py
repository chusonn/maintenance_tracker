from app.extensions import db
from app.models import Flat, MaintenanceJob

from .factories import make_flat, make_job


def test_flats_list_excludes_soft_deleted(client):
    make_flat(payment_reference="LIVE-FLAT")
    dead = make_flat(payment_reference="DEAD-FLAT")
    dead.soft_delete()
    db.session.commit()

    page = client.get("/flats").get_data(as_text=True)
    assert "LIVE-FLAT" in page
    assert "DEAD-FLAT" not in page


def test_delete_flat_soft_deletes_into_recycle_bin(client):
    flat = make_flat(payment_reference="BINNED-FLAT")
    client.post(f"/flats/{flat.id}/delete")

    assert flat.is_deleted is True
    page = client.get("/recycle-bin").get_data(as_text=True)
    assert "BINNED-FLAT" in page


def test_delete_flat_blocked_when_active_jobs_exist(client):
    flat = make_flat()
    make_job(flat, status="In Progress")
    client.post(f"/flats/{flat.id}/delete")
    assert flat.is_deleted is False


def test_delete_flat_cascades_to_completed_jobs_and_restore_reverses(client):
    flat = make_flat()
    done_job = make_job(flat, status="Completed")
    already_binned = make_job(flat, status="Cancelled")
    already_binned.soft_delete(by="user")
    db.session.commit()

    client.post(f"/flats/{flat.id}/delete")
    assert flat.is_deleted is True
    assert done_job.is_deleted is True
    assert done_job.deleted_by == "cascade:flat"

    client.post(f"/recycle-bin/flat/{flat.id}/restore")
    assert flat.is_deleted is False
    assert done_job.is_deleted is False
    # the independently-deleted job must NOT be resurrected by the cascade restore
    assert already_binned.is_deleted is True


def test_permanent_delete_flat_removes_its_jobs(client):
    flat = make_flat()
    job = make_job(flat, status="Completed")
    job_id, flat_id = job.id, flat.id

    client.post(f"/flats/{flat_id}/delete")
    response = client.post(f"/recycle-bin/flat/{flat_id}/purge")

    assert response.status_code == 302
    assert db.session.get(Flat, flat_id) is None
    assert db.session.get(MaintenanceJob, job_id) is None


def test_delete_all_flats_requires_confirmation_phrase(client):
    flat = make_flat()
    client.post("/flats/delete-all", data={"confirm": "wrong phrase"})
    assert flat.is_deleted is False

    client.post("/flats/delete-all", data={"confirm": "DELETE-ALL-FLATS"})
    assert flat.is_deleted is True  # soft-deleted, recoverable from the bin


def test_edit_flat_updates_fields(client):
    flat = make_flat()
    client.post(
        f"/flats/{flat.id}/edit",
        data={
            "flat_number": "9Z",
            "address": "New Address",
            "postcode": "E1 6AN",
            "tenant_name": "New Tenant",
            "tenant_contact_details": "",
            "rent_amount": "999.50",
            "rent_due_date": "3",
            "tenancy_start_date": "",
            "tenancy_end_date": "",
            "landlord": "New Landlord",
            "payment_reference": flat.payment_reference,
        },
    )
    assert flat.address == "New Address"
    assert flat.rent_amount == 999.5
