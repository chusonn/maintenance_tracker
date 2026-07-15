from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Contractor

bp = Blueprint("contractors", __name__, url_prefix="/contractors")


@bp.route("")
def index():
    contractors = db.session.scalars(
        Contractor.active_select()
        .where(Contractor.is_active == True)  # noqa: E712
        .order_by(Contractor.name)
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
