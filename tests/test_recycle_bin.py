from app.extensions import db
from app.models import MaintenanceJob

from .factories import make_job


def test_job_delete_restore_purge_lifecycle(client):
    job = make_job(title="Lifecycle job")
    job_id = job.id

    client.post(f"/jobs/{job_id}/delete")
    assert job.is_deleted is True

    page = client.get("/recycle-bin").get_data(as_text=True)
    assert "Lifecycle job" in page

    client.post(f"/recycle-bin/job/{job_id}/restore")
    assert job.is_deleted is False
    assert job.deleted_at is None

    client.post(f"/jobs/{job_id}/delete")
    client.post(f"/recycle-bin/job/{job_id}/purge")
    assert db.session.get(MaintenanceJob, job_id) is None


def test_recycle_bin_rejects_unknown_kind(client):
    response = client.post("/recycle-bin/widget/1/restore")
    assert response.status_code == 404
