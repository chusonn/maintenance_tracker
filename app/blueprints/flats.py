from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import select

from ..extensions import db
from ..models import ACTIVE_JOB_STATUSES, Flat
from ..services import excel_io

bp = Blueprint("flats", __name__, url_prefix="/flats")


def _apply_form(flat: Flat) -> None:
    flat.flat_number = request.form["flat_number"]
    flat.address = request.form["address"]
    flat.postcode = request.form["postcode"]
    flat.tenant_name = request.form["tenant_name"]
    flat.tenant_contact_details = request.form["tenant_contact_details"]
    flat.rent_amount = float(request.form["rent_amount"]) if request.form["rent_amount"] else None
    flat.rent_due_date = int(request.form["rent_due_date"]) if request.form["rent_due_date"] else None
    flat.tenancy_start_date = _form_date("tenancy_start_date")
    flat.tenancy_end_date = _form_date("tenancy_end_date")
    flat.landlord = request.form["landlord"]
    flat.payment_reference = request.form["payment_reference"]


def _form_date(field: str):
    raw = request.form.get(field)
    return datetime.strptime(raw, "%Y-%m-%d").date() if raw else None


@bp.route("")
def index():
    flats = db.session.scalars(select(Flat).order_by(Flat.flat_number)).all()
    return render_template("flats.html", flats=flats)


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        flat = Flat()
        _apply_form(flat)
        db.session.add(flat)
        db.session.commit()
        flash("Flat added successfully!", "success")
        return redirect(url_for("flats.index"))
    return render_template("add_flat.html")


@bp.route("/<int:flat_id>/edit", methods=["GET", "POST"])
def edit(flat_id: int):
    flat = db.get_or_404(Flat, flat_id)
    if request.method == "POST":
        _apply_form(flat)
        db.session.commit()
        flash("Flat updated successfully!", "success")
        return redirect(url_for("flats.index"))
    return render_template("edit_flat.html", flat=flat)


@bp.route("/<int:flat_id>/delete", methods=["POST"])
def delete(flat_id: int):
    flat = db.get_or_404(Flat, flat_id)

    active_jobs = [job for job in flat.maintenance_jobs if job.status in ACTIVE_JOB_STATUSES]
    if active_jobs:
        flash(
            f"Cannot delete flat {flat.flat_number} - it has {len(active_jobs)} active "
            "maintenance jobs. Complete or cancel the jobs first.",
            "warning",
        )
        return redirect(url_for("flats.index"))

    try:
        db.session.delete(flat)
        db.session.commit()
        flash(f"Flat {flat.flat_number} ({flat.payment_reference}) deleted successfully!", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Error deleting flat: {exc}", "danger")
    return redirect(url_for("flats.index"))


@bp.route("/delete-all", methods=["POST"])
def delete_all():
    if request.form.get("confirm") != "DELETE-ALL-FLATS":
        flash("Deletion cancelled - confirmation phrase was incorrect.", "warning")
        return redirect(url_for("flats.index"))

    flat_count = db.session.scalar(select(db.func.count()).select_from(Flat))
    db.session.execute(db.delete(Flat))
    db.session.commit()
    flash(f"Successfully deleted {flat_count} flats and all related maintenance jobs!", "success")
    return redirect(url_for("flats.index"))


@bp.route("/import", methods=["GET", "POST"])
def import_flats():
    if request.method == "POST":
        file = request.files.get("file")
        if file is None or not file.filename:
            flash("No file selected", "warning")
            return redirect(request.url)

        if not file.filename.endswith((".xlsx", ".xls")):
            flash("Invalid file format. Please upload an Excel file (.xlsx or .xls)", "warning")
            return redirect(url_for("flats.index"))

        try:
            imported, updated, skipped = excel_io.import_flats_from_file(file)
        except Exception as exc:
            db.session.rollback()
            flash(f"Error importing file: {exc}", "danger")
            return redirect(url_for("flats.index"))

        flash(
            f"Successfully imported {imported} new flats, updated {updated} existing flats, "
            f"and skipped {skipped} empty rows!",
            "success",
        )
        return redirect(url_for("flats.index"))

    return render_template("import_flats.html")
