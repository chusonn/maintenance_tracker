from flask import Blueprint, render_template
from sqlalchemy import func, select

from ..extensions import db
from ..models import ACTIVE_JOB_STATUSES, MaintenanceJob

bp = Blueprint("dashboard", __name__)


def _job_count(*conditions) -> int:
    return db.session.scalar(
        select(func.count())
        .select_from(MaintenanceJob)
        .where(MaintenanceJob.is_deleted == False, *conditions)  # noqa: E712
    )


@bp.route("/")
@bp.route("/dashboard")
def index():
    needs_followup = (
        MaintenanceJob.status.in_(ACTIVE_JOB_STATUSES),
        MaintenanceJob.follow_up_count == 0,
    )

    recent_jobs = db.session.scalars(
        MaintenanceJob.active_select()
        .order_by(MaintenanceJob.created_at.desc())
        .limit(10)
    ).all()

    urgent_jobs = db.session.scalars(
        MaintenanceJob.active_select().where(
            MaintenanceJob.priority == "Urgent",
            MaintenanceJob.status.in_(["Pending", "In Progress"]),
        )
    ).all()

    jobs_needing_followup = db.session.scalars(
        MaintenanceJob.active_select()
        .where(*needs_followup)
        .order_by(MaintenanceJob.reported_date.asc())
        .limit(5)
    ).all()

    return render_template(
        "dashboard.html",
        total_jobs=_job_count(),
        pending_jobs=_job_count(MaintenanceJob.status == "Pending"),
        in_progress_jobs=_job_count(MaintenanceJob.status == "In Progress"),
        completed_jobs=_job_count(MaintenanceJob.status == "Completed"),
        follow_up_needed=_job_count(*needs_followup),
        recent_jobs=recent_jobs,
        urgent_jobs=urgent_jobs,
        jobs_needing_followup=jobs_needing_followup,
    )
