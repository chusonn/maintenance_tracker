from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Contractor

bp = Blueprint("contractors", __name__, url_prefix="/contractors")


@bp.route("")
def index():
    contractors = db.session.scalars(
        Contractor.active_select().order_by(Contractor.name)
    ).all()
    return render_template("contractors.html", contractors=contractors)


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        contractor = Contractor(
            name=request.form["name"],
            company=request.form["company"],
            email=request.form["email"],
            phone=request.form["phone"],
            specialty=request.form["specialty"],
        )
        db.session.add(contractor)
        db.session.commit()
        flash("Contractor added successfully!", "success")
        return redirect(url_for("contractors.index"))
    return render_template("add_contractor.html")


@bp.route("/<int:contractor_id>/edit", methods=["GET", "POST"])
def edit(contractor_id: int):
    contractor = db.get_or_404(Contractor, contractor_id)
    if request.method == "POST":
        contractor.name = request.form["name"]
        contractor.company = request.form["company"]
        contractor.email = request.form["email"]
        contractor.phone = request.form["phone"]
        contractor.specialty = request.form["specialty"]
        db.session.commit()
        flash("Contractor updated successfully!", "success")
        return redirect(url_for("contractors.index"))
    return render_template("edit_contractor.html", contractor=contractor)


@bp.route("/<int:contractor_id>/delete", methods=["POST"])
def delete(contractor_id: int):
    contractor = db.get_or_404(Contractor, contractor_id)
    contractor.soft_delete()
    db.session.commit()
    flash(
        f"Contractor {contractor.name} moved to the recycle bin. "
        "Their history on past jobs is preserved.",
        "success",
    )
    return redirect(url_for("contractors.index"))
