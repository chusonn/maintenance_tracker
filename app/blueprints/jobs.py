from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import ACTIVE_JOB_STATUSES, Contractor, Flat, MaintenanceJob, utcnow
from ..services import excel_io

bp = Blueprint("jobs", __name__, url_prefix="/jobs")

PER_PAGE = 25


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_cost(field: str) -> tuple[float | None, bool]:
    """Returns (value, was_invalid) for an optional currency form field."""
    raw = (request.form.get(field) or "").strip()
    if not raw:
        return None, False
    try:
        return float(raw), False
    except ValueError:
        return None, True


def _filtered_jobs_stmt(args):
    stmt = MaintenanceJob.active_select().join(Flat)

    if args.get("status"):
        stmt = stmt.where(MaintenanceJob.status == args["status"])
    if args.get("priority"):
        stmt = stmt.where(MaintenanceJob.priority == args["priority"])

    search = (args.get("search") or "").strip()
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                MaintenanceJob.title.ilike(pattern),
                MaintenanceJob.description.ilike(pattern),
                MaintenanceJob.notes.ilike(pattern),
                Flat.payment_reference.ilike(pattern),
                Flat.flat_number.ilike(pattern),
                Flat.address.ilike(pattern),
            )
        )

    if date_from := _parse_date(args.get("date_from")):
        stmt = stmt.where(MaintenanceJob.reported_date >= date_from)
    if date_to := _parse_date(args.get("date_to")):
        stmt = stmt.where(MaintenanceJob.reported_date <= date_to)

    return stmt


def _count(stmt) -> int:
    return db.session.scalar(select(func.count()).select_from(stmt.subquery()))


@bp.route("")
def index():
    filtered = _filtered_jobs_stmt(request.args)

    jobs = db.paginate(
        filtered.order_by(MaintenanceJob.created_at.desc()),
        page=request.args.get("page", 1, type=int),
        per_page=PER_PAGE,
        error_out=False,
    )

    status_counts = {
        "pending": _count(filtered.where(MaintenanceJob.status == "Pending")),
        "in_progress": _count(filtered.where(MaintenanceJob.status == "In Progress")),
        "completed": _count(filtered.where(MaintenanceJob.status == "Completed")),
        "need_followup": _count(
            filtered.where(
                MaintenanceJob.follow_up_count == 0,
                MaintenanceJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        ),
    }

    return render_template(
        "jobs.html",
        jobs=jobs,
        status_filter=request.args.get("status"),
        priority_filter=request.args.get("priority"),
        search_query=(request.args.get("search") or "").strip(),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        status_counts=status_counts,
    )


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        estimated_cost, invalid = _parse_cost("estimated_cost")
        if invalid:
            flash("Estimated cost must be a valid number. It has been left empty.", "warning")

        job = MaintenanceJob(
            flat_id=request.form["flat_id"],
            title=request.form["title"],
            description=request.form["description"],
            priority=request.form["priority"],
            estimated_cost=estimated_cost,
            reported_date=date.today(),
        )
        db.session.add(job)
        db.session.commit()
        flash("Job added successfully!", "success")
        return redirect(url_for("jobs.index"))

    flats = db.session.scalars(Flat.active_select().order_by(Flat.payment_reference)).all()
    return render_template("add_job.html", flats=flats)


@bp.route("/<int:job_id>/edit", methods=["GET", "POST"])
def edit(job_id: int):
    job = db.get_or_404(MaintenanceJob, job_id)

    if request.method == "POST":
        estimated_cost, invalid = _parse_cost("estimated_cost")
        if invalid:
            flash("Estimated cost must be a valid number. It has been left empty.", "warning")

        job.title = request.form["title"]
        job.description = request.form["description"]
        job.priority = request.form["priority"]
        job.status = request.form["status"]
        job.estimated_cost = estimated_cost
        job.notes = request.form["notes"]
        db.session.commit()
        flash("Job updated successfully!", "success")
        return redirect(url_for("jobs.index"))

    flats = db.session.scalars(Flat.active_select().order_by(Flat.payment_reference)).all()
    return render_template("edit_job.html", job=job, flats=flats)


@bp.route("/<int:job_id>/schedule", methods=["GET", "POST"])
def schedule(job_id: int):
    job = db.get_or_404(MaintenanceJob, job_id)

    if request.method == "POST":
        job.contractor_id = request.form["contractor_id"]
        job.scheduled_date = _parse_date(request.form["scheduled_date"])
        job.status = "Scheduled"
        job.notes = request.form["notes"]
        db.session.commit()
        flash("Job scheduled successfully!", "success")
        return redirect(url_for("jobs.index"))

    contractors = db.session.scalars(
        Contractor.active_select().order_by(Contractor.name)
    ).all()
    return render_template("schedule_job.html", job=job, contractors=contractors)


@bp.route("/<int:job_id>/complete", methods=["GET", "POST"])
def complete(job_id: int):
    job = db.get_or_404(MaintenanceJob, job_id)

    if request.method == "POST":
        actual_cost, invalid = _parse_cost("actual_cost")
        if invalid:
            flash("Actual cost must be a valid number. It has been left empty.", "warning")

        job.status = "Completed"
        job.completed_date = _parse_date(request.form.get("completed_date")) or date.today()
        job.actual_cost = actual_cost
        job.notes = request.form["notes"]
        db.session.commit()
        flash("Job marked as completed!", "success")
        return redirect(url_for("jobs.index"))

    return render_template(
        "complete_job.html", job=job, today_date=date.today().strftime("%Y-%m-%d")
    )


@bp.route("/<int:job_id>/followup", methods=["GET", "POST"])
def followup(job_id: int):
    job = db.get_or_404(MaintenanceJob, job_id)

    if request.method == "POST":
        job.follow_up_count = (job.follow_up_count or 0) + 1
        job.follow_up_date = utcnow()
        job.follow_up_notes = request.form["follow_up_notes"]
        db.session.commit()
        flash(f"Follow-up #{job.follow_up_count} marked as sent!", "success")
        return redirect(url_for("jobs.index"))

    return render_template("followup_job.html", job=job, today_date=date.today())


@bp.route("/<int:job_id>/delete", methods=["POST"])
def delete(job_id: int):
    job = db.get_or_404(MaintenanceJob, job_id)
    job.soft_delete()
    db.session.commit()
    flash("Job moved to recycle bin. You can restore it from the Recycle Bin page.", "success")
    return redirect(url_for("jobs.index"))


@bp.route("/export")
def export():
    jobs = db.session.scalars(
        MaintenanceJob.active_select().order_by(
            MaintenanceJob.status, MaintenanceJob.reported_date.desc()
        )
    ).all()

    output = excel_io.build_jobs_export(jobs)
    filename = f"maintenance_jobs_export_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
