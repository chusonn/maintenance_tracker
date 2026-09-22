from datetime import date, datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import ACTIVE_JOB_STATUSES, Contractor, Flat, MaintenanceJob, MessageTemplate
from ..services import emailer, excel_io
from ..services.followup import (
    PLACEHOLDERS,
    due_followups_stmt,
    record_followup,
    render_template_for_job,
)

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
            created_by=current_user.name,
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


def _render_composer(job, form=None):
    """Composer page; `form` echoes submitted values back after a failed send."""
    templates = db.session.scalars(
        select(MessageTemplate).order_by(MessageTemplate.name)
    ).all()
    return render_template(
        "followup_job.html",
        job=job,
        template_options=[(str(t.id), t.name) for t in templates],
        prefill={str(t.id): render_template_for_job(t, job) for t in templates},
        placeholders=PLACEHOLDERS,
        email_configured=emailer.is_configured(current_app.config),
        form=form
        or {
            "recipient": (job.contractor.email or "") if job.contractor else "",
            "subject": "",
            "body": "",
            "follow_up_notes": "",
            "template_id": "",
        },
    )


@bp.route("/<int:job_id>/followup", methods=["GET", "POST"])
def followup(job_id: int):
    job = db.get_or_404(MaintenanceJob, job_id)

    if request.method == "POST":
        action = request.form.get("action", "record")
        notes = request.form.get("follow_up_notes", "")

        if action == "send":
            form = {
                "recipient": (request.form.get("recipient") or "").strip(),
                "subject": request.form.get("subject", ""),
                "body": request.form.get("body", ""),
                "follow_up_notes": notes,
                "template_id": request.form.get("template_id", ""),
            }
            if not emailer.is_configured(current_app.config):
                flash(
                    "Email sending is not configured - set SMTP_USERNAME and "
                    "SMTP_PASSWORD in .env, or record the follow-up without emailing.",
                    "warning",
                )
                return _render_composer(job, form)
            if not form["recipient"]:
                flash("Enter a recipient email address.", "warning")
                return _render_composer(job, form)
            try:
                emailer.send_email(
                    current_app.config,
                    to=form["recipient"],
                    subject=form["subject"],
                    body=form["body"],
                )
            except emailer.EmailSendError as exc:
                flash(str(exc), "danger")
                return _render_composer(job, form)
            record_followup(
                job,
                notes,
                emailed_to=form["recipient"],
                subject=form["subject"],
                by=current_user.name,
            )
            db.session.commit()
            flash(
                f"Follow-up #{job.follow_up_count} emailed to {form['recipient']}.",
                "success",
            )
            return redirect(url_for("jobs.index"))

        record_followup(job, notes)
        db.session.commit()
        flash(f"Follow-up #{job.follow_up_count} marked as sent!", "success")
        return redirect(url_for("jobs.index"))

    return _render_composer(job)


@bp.route("/due-followups")
def due_followups():
    days = current_app.config["FOLLOW_UP_DAYS"]
    jobs = db.session.scalars(due_followups_stmt(days)).all()
    templates = db.session.scalars(
        select(MessageTemplate).order_by(MessageTemplate.name)
    ).all()
    sendable = [j for j in jobs if j.contractor and j.contractor.email]
    return render_template(
        "due_followups.html",
        jobs=jobs,
        template_options=[(str(t.id), t.name) for t in templates],
        days=days,
        sendable_count=len(sendable),
        email_configured=emailer.is_configured(current_app.config),
    )


@bp.route("/due-followups/send-all", methods=["POST"])
def bulk_followup():
    if not emailer.is_configured(current_app.config):
        flash(
            "Email sending is not configured - set SMTP_USERNAME and SMTP_PASSWORD in .env.",
            "warning",
        )
        return redirect(url_for("jobs.due_followups"))

    template = db.session.get(MessageTemplate, request.form.get("template_id", type=int) or 0)
    if template is None:
        flash("Choose a template for the bulk send.", "warning")
        return redirect(url_for("jobs.due_followups"))

    days = current_app.config["FOLLOW_UP_DAYS"]
    jobs = db.session.scalars(due_followups_stmt(days)).all()

    sent, skipped, failed = [], [], []
    for job in jobs:
        recipient = job.contractor.email if job.contractor else None
        if not recipient:
            skipped.append(job.title)
            continue
        rendered = render_template_for_job(template, job)
        try:
            emailer.send_email(
                current_app.config,
                to=recipient,
                subject=rendered["subject"],
                body=rendered["body"],
            )
        except emailer.EmailSendError as exc:
            failed.append(f"{job.title} ({exc})")
            continue
        record_followup(
            job,
            f"Bulk follow-up sent using template '{template.name}'.",
            emailed_to=recipient,
            subject=rendered["subject"],
            by=current_user.name,
        )
        sent.append(job.title)
    db.session.commit()

    if not (sent or skipped or failed):
        flash("Nothing is currently due for follow-up.", "info")
        return redirect(url_for("jobs.due_followups"))

    parts = [f"Sent {len(sent)} follow-up email{'s' if len(sent) != 1 else ''}."]
    if skipped:
        parts.append(f"Skipped {len(skipped)} with no contractor email: {', '.join(skipped)}.")
    if failed:
        parts.append(f"Failed: {'; '.join(failed)}.")
    if sent and not (skipped or failed):
        category = "success"
    elif sent:
        category = "warning"
    else:
        category = "danger"
    flash(" ".join(parts), category)
    return redirect(url_for("jobs.due_followups"))


@bp.route("/<int:job_id>/delete", methods=["POST"])
def delete(job_id: int):
    job = db.get_or_404(MaintenanceJob, job_id)
    job.soft_delete(by=current_user.name)
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
