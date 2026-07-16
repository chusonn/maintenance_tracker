"""Message-template CRUD pages."""

from sqlalchemy import select

from app.models import MessageTemplate

from .factories import make_contractor, make_job, make_template


def test_index_lists_templates(client, db):
    make_template(name="Chase politely")
    html = client.get("/message-templates").get_data(as_text=True)
    assert "Chase politely" in html


def test_index_empty_state(client, db):
    html = client.get("/message-templates").get_data(as_text=True)
    assert "No templates yet" in html


def test_add_template(client, db):
    response = client.post(
        "/message-templates/add",
        data={"name": "New preset", "subject": "Hello {contractor_name}", "body": "Body text"},
        follow_redirects=True,
    )
    assert "Template added successfully" in response.get_data(as_text=True)
    template = db.session.scalars(
        select(MessageTemplate).where(MessageTemplate.name == "New preset")
    ).one()
    assert template.subject == "Hello {contractor_name}"


def test_add_duplicate_name_warns_not_500(client, db):
    make_template(name="Duplicate me")
    response = client.post(
        "/message-templates/add",
        data={"name": "Duplicate me", "subject": "s", "body": "b"},
    )
    assert response.status_code == 200
    assert "already exists" in response.get_data(as_text=True)


def test_edit_template(client, db):
    template = make_template()
    response = client.post(
        f"/message-templates/{template.id}/edit",
        data={"name": template.name, "subject": "Updated subject", "body": template.body},
        follow_redirects=True,
    )
    assert "Template updated successfully" in response.get_data(as_text=True)
    assert db.session.get(MessageTemplate, template.id).subject == "Updated subject"


def test_delete_template_removes_it_everywhere(client, db):
    template = make_template(name="Doomed template")
    job = make_job(contractor_id=make_contractor().id)

    client.post(f"/message-templates/{template.id}/delete", follow_redirects=True)

    assert db.session.get(MessageTemplate, template.id) is None
    composer_html = client.get(f"/jobs/{job.id}/followup").get_data(as_text=True)
    assert "Doomed template" not in composer_html
