from app.extensions import db

from .factories import make_contractor


def test_contractors_list_excludes_soft_deleted(client):
    make_contractor(name="Active Plumber")
    gone = make_contractor(name="Departed Sparky")
    gone.soft_delete()
    db.session.commit()

    page = client.get("/contractors").get_data(as_text=True)
    assert "Active Plumber" in page
    assert "Departed Sparky" not in page


def test_edit_contractor_updates_fields(client):
    contractor = make_contractor()
    client.post(
        f"/contractors/{contractor.id}/edit",
        data={
            "name": "Renamed Trades",
            "company": "Renamed Ltd",
            "email": "new@example.com",
            "phone": "07000111222",
            "specialty": "Electrical",
        },
    )
    assert contractor.name == "Renamed Trades"
    assert contractor.specialty == "Electrical"


def test_delete_contractor_soft_deletes_into_recycle_bin(client):
    contractor = make_contractor(name="Binned Trades")
    client.post(f"/contractors/{contractor.id}/delete")

    assert contractor.is_deleted is True
    page = client.get("/recycle-bin").get_data(as_text=True)
    assert "Binned Trades" in page


def test_deleted_contractor_keeps_history_on_jobs(client):
    """Soft-deleting a contractor must not detach them from past jobs."""
    from .factories import make_job

    contractor = make_contractor(name="History Trades")
    job = make_job(status="Completed", contractor_id=contractor.id)

    client.post(f"/contractors/{contractor.id}/delete")
    assert job.contractor_id == contractor.id
