"""Aggregations for the analytics page.

Every query filters is_deleted so binned rows never leak into charts.
Month keys are zero-padded "YYYY-MM" strings, which sort and compare
correctly as text — that is what makes the strftime bucketing work.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from ..extensions import db
from ..models import JOB_PRIORITIES, JOB_STATUSES, Contractor, MaintenanceJob

_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def month_keys(months: int = 12, today: date | None = None) -> list[str]:
    """The last `months` month-keys ("YYYY-MM"), oldest first, ending this month."""
    today = today or date.today()
    year, month = today.year, today.month
    keys = []
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return list(reversed(keys))


def month_display(key: str) -> str:
    """"2026-07" -> "Jul 2026"."""
    year, month = key.split("-")
    return f"{_MONTH_NAMES[int(month) - 1]} {year}"


def monthly_job_volume(months: int = 12) -> list[dict]:
    """Jobs reported per month, zero-filled across the window."""
    keys = month_keys(months)
    month = func.strftime("%Y-%m", MaintenanceJob.reported_date)
    rows = db.session.execute(
        select(month, func.count())
        .where(MaintenanceJob.is_deleted == False, month >= keys[0])  # noqa: E712
        .group_by(month)
    ).all()
    counts = dict(rows)
    return [
        {"month": key, "label": month_display(key), "count": counts.get(key, 0)}
        for key in keys
    ]


def cost_trend(months: int = 12) -> list[dict]:
    """Estimated vs actual spend per month on completed jobs, zero-filled."""
    keys = month_keys(months)
    month = func.strftime("%Y-%m", MaintenanceJob.completed_date)
    rows = db.session.execute(
        select(
            month,
            func.coalesce(func.sum(MaintenanceJob.estimated_cost), 0.0),
            func.coalesce(func.sum(MaintenanceJob.actual_cost), 0.0),
        )
        .where(
            MaintenanceJob.is_deleted == False,  # noqa: E712
            MaintenanceJob.status == "Completed",
            MaintenanceJob.completed_date.is_not(None),
            month >= keys[0],
        )
        .group_by(month)
    ).all()
    sums = {key: (estimated, actual) for key, estimated, actual in rows}
    return [
        {
            "month": key,
            "label": month_display(key),
            "estimated": round(sums.get(key, (0.0, 0.0))[0], 2),
            "actual": round(sums.get(key, (0.0, 0.0))[1], 2),
        }
        for key in keys
    ]


def status_breakdown() -> list[dict]:
    """Job counts in lifecycle order; every status present even at zero."""
    rows = dict(
        db.session.execute(
            select(MaintenanceJob.status, func.count())
            .where(MaintenanceJob.is_deleted == False)  # noqa: E712
            .group_by(MaintenanceJob.status)
        ).all()
    )
    return [{"status": status, "count": rows.get(status, 0)} for status in JOB_STATUSES]


def priority_breakdown() -> list[dict]:
    """Job counts in severity order; every priority present even at zero."""
    rows = dict(
        db.session.execute(
            select(MaintenanceJob.priority, func.count())
            .where(MaintenanceJob.is_deleted == False)  # noqa: E712
            .group_by(MaintenanceJob.priority)
        ).all()
    )
    return [
        {"priority": priority, "count": rows.get(priority, 0)}
        for priority in JOB_PRIORITIES
    ]


def top_contractors(limit: int = 5) -> list[dict]:
    """Contractors by completed-job count, with average actual cost."""
    completed = func.count(MaintenanceJob.id)
    rows = db.session.execute(
        select(Contractor.name, completed, func.avg(MaintenanceJob.actual_cost))
        .join(MaintenanceJob, MaintenanceJob.contractor_id == Contractor.id)
        .where(
            Contractor.is_deleted == False,  # noqa: E712
            MaintenanceJob.is_deleted == False,  # noqa: E712
            MaintenanceJob.status == "Completed",
        )
        .group_by(Contractor.id)
        .order_by(completed.desc(), Contractor.name.asc())
        .limit(limit)
    ).all()
    return [
        {
            "name": name,
            "completed": count,
            "avg_cost": round(avg_cost, 2) if avg_cost is not None else None,
        }
        for name, count, avg_cost in rows
    ]


def summary(months: int = 12) -> dict:
    """Headline figures for the KPI row, scoped to the last `months` months."""
    start = month_keys(months)[0]
    reported_month = func.strftime("%Y-%m", MaintenanceJob.reported_date)
    completed_filters = (
        MaintenanceJob.is_deleted == False,  # noqa: E712
        MaintenanceJob.status == "Completed",
        MaintenanceJob.completed_date.is_not(None),
        func.strftime("%Y-%m", MaintenanceJob.completed_date) >= start,
    )

    def scalar(stmt):
        return db.session.scalar(stmt)

    has_data = bool(
        scalar(select(func.count()).select_from(MaintenanceJob).where(
            MaintenanceJob.is_deleted == False  # noqa: E712
        ))
    )
    reported = scalar(
        select(func.count())
        .select_from(MaintenanceJob)
        .where(MaintenanceJob.is_deleted == False, reported_month >= start)  # noqa: E712
    )
    completed = scalar(
        select(func.count()).select_from(MaintenanceJob).where(*completed_filters)
    )
    total_spend = scalar(
        select(func.coalesce(func.sum(MaintenanceJob.actual_cost), 0.0)).where(
            *completed_filters
        )
    )
    avg_cost = scalar(
        select(func.avg(MaintenanceJob.actual_cost)).where(*completed_filters)
    )
    return {
        "has_data": has_data,
        "reported": reported,
        "completed": completed,
        "total_spend": round(total_spend, 2),
        "avg_cost": round(avg_cost, 2) if avg_cost is not None else None,
    }
