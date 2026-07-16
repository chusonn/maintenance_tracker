from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import MessageTemplate
from ..services.followup import PLACEHOLDERS

bp = Blueprint("message_templates", __name__, url_prefix="/message-templates")


@bp.route("")
def index():
    templates = db.session.scalars(
        select(MessageTemplate).order_by(MessageTemplate.name)
    ).all()
    return render_template("message_templates.html", templates=templates)


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        template = MessageTemplate(
            name=request.form["name"].strip(),
            subject=request.form["subject"],
            body=request.form["body"],
        )
        db.session.add(template)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A template with that name already exists.", "warning")
            return render_template("add_message_template.html", placeholders=PLACEHOLDERS)
        flash("Template added successfully!", "success")
        return redirect(url_for("message_templates.index"))
    return render_template("add_message_template.html", placeholders=PLACEHOLDERS)


@bp.route("/<int:template_id>/edit", methods=["GET", "POST"])
def edit(template_id: int):
    template = db.get_or_404(MessageTemplate, template_id)
    if request.method == "POST":
        template.name = request.form["name"].strip()
        template.subject = request.form["subject"]
        template.body = request.form["body"]
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A template with that name already exists.", "warning")
        else:
            flash("Template updated successfully!", "success")
            return redirect(url_for("message_templates.index"))
    return render_template(
        "edit_message_template.html", template=template, placeholders=PLACEHOLDERS
    )


@bp.route("/<int:template_id>/delete", methods=["POST"])
def delete(template_id: int):
    template = db.get_or_404(MessageTemplate, template_id)
    db.session.delete(template)
    db.session.commit()
    flash(f"Template '{template.name}' deleted.", "success")
    return redirect(url_for("message_templates.index"))
