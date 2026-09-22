"""Follow-up email domain logic: placeholder rendering, the due-for-follow-up
query, follow-up bookkeeping, and the default message templates.

Placeholders use {name} tokens substituted per job. Rendering is regex-based
(NOT str.format) so a stray brace in user-typed template text can never raise,
and unknown tokens are left literal for the user to spot in the preview.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import MaintenanceJob, MessageTemplate, utcnow

# name -> description; drives the "Placeholders" help card in the UI.
PLACEHOLDERS = {
    "contractor_name": "Contractor's name",
    "contractor_company": "Contractor's company",
    "job_title": "Job title",
    "job_description": "Job description",
    "priority": "Job priority (Low/Medium/High/Urgent)",
    "status": "Job status",
    "flat_address": "Property address",
    "flat_number": "Flat number",
    "payment_reference": "Unique property reference",
    "tenant_name": "Tenant's name",
    "scheduled_date": "Scheduled visit date (dd/mm/yyyy)",
    "reported_date": "Date the issue was reported (dd/mm/yyyy)",
    "estimated_cost": "Estimated cost (£)",
}

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _ukdate(value) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def job_placeholder_context(job: MaintenanceJob) -> dict[str, str]:
    contractor = job.contractor
    flat = job.flat
    return {
        "contractor_name": contractor.name if contractor else "",
        "contractor_company": (contractor.company or "") if contractor else "",
        "job_title": job.title or "",
        "job_description": job.description or "",
        "priority": job.priority or "",
        "status": job.status or "",
        "flat_address": flat.address or "",
        "flat_number": flat.flat_number or "",
        "payment_reference": flat.payment_reference or "",
        "tenant_name": flat.tenant_name or "",
        "scheduled_date": _ukdate(job.scheduled_date),
        "reported_date": _ukdate(job.reported_date),
        "estimated_cost": f"£{job.estimated_cost:,.2f}" if job.estimated_cost is not None else "",
    }


def render_placeholders(text: str, job: MaintenanceJob) -> str:
    context = job_placeholder_context(job)

    def replace(match: re.Match) -> str:
        name = match.group(1)
        # Unknown tokens stay literal so typos are visible in the preview.
        return context[name] if name in context else match.group(0)

    return _PLACEHOLDER_RE.sub(replace, text)


def render_template_for_job(template: MessageTemplate, job: MaintenanceJob) -> dict[str, str]:
    return {
        "subject": render_placeholders(template.subject, job),
        "body": render_placeholders(template.body, job),
    }


def due_followups_stmt(days: int):
    """Active Scheduled/In Progress jobs whose last touch is over `days` old:
    never followed up and reported that long ago, or last follow-up that old."""
    cutoff_date = date.today() - timedelta(days=days)
    cutoff_dt = utcnow() - timedelta(days=days)
    return (
        MaintenanceJob.active_select()
        .where(
            MaintenanceJob.status.in_(["Scheduled", "In Progress"]),
            or_(
                (MaintenanceJob.follow_up_count == 0)
                & (MaintenanceJob.reported_date <= cutoff_date),
                MaintenanceJob.follow_up_date.is_not(None)
                & (MaintenanceJob.follow_up_date <= cutoff_dt),
            ),
        )
        .order_by(MaintenanceJob.reported_date.asc())
    )


def record_followup(
    job: MaintenanceJob,
    notes: str,
    emailed_to: str | None = None,
    subject: str | None = None,
    by: str | None = None,
) -> None:
    """Increment the follow-up bookkeeping; caller commits. When an email was
    sent, an audit line is appended to the notes so History shows what went
    out (and, with `by`, who sent it)."""
    job.follow_up_count = (job.follow_up_count or 0) + 1
    job.follow_up_date = utcnow()
    if emailed_to:
        stamp = job.follow_up_date.strftime("%d/%m/%Y %H:%M")
        sender = f" - by {by}" if by else ""
        audit = f'[Emailed {emailed_to} - "{subject}" - {stamp}{sender}]'
        notes = f"{notes}\n\n{audit}" if notes.strip() else audit
    job.follow_up_notes = notes


DEFAULT_TEMPLATES = [
    {
        "name": "Chase - awaiting update",
        "subject": "Follow-up: {job_title} at {flat_address} (ref {payment_reference})",
        "body": (
            "Hi {contractor_name},\n\n"
            "I'm following up on the job below, reported on {reported_date}:\n\n"
            "  {job_title} - {flat_address} (flat {flat_number})\n"
            "  Reference: {payment_reference}\n\n"
            "Could you let me know where things stand and when you expect to "
            "attend? If you've already been, a quick summary of what was done "
            "would be great.\n\n"
            "Many thanks"
        ),
    },
    {
        "name": "Confirm scheduled visit",
        "subject": "Confirming your visit on {scheduled_date} - {job_title} ({payment_reference})",
        "body": (
            "Hi {contractor_name},\n\n"
            "Just confirming you're still on for {scheduled_date} at "
            "{flat_address} (flat {flat_number}) for:\n\n"
            "  {job_title}\n\n"
            "The tenant is {tenant_name} - please give them reasonable notice "
            "before arriving. Let me know if the date no longer works and "
            "we'll rearrange.\n\n"
            "Many thanks"
        ),
    },
    {
        "name": "Urgent chase",
        "subject": "URGENT: {job_title} at {flat_address} - response needed ({payment_reference})",
        "body": (
            "Hi {contractor_name},\n\n"
            "This job is marked {priority} priority and was reported on "
            "{reported_date}, but I still don't have a confirmed date:\n\n"
            "  {job_title} - {flat_address} (flat {flat_number})\n\n"
            "I need a firm date this week, otherwise I'll have to reassign "
            "the work. Please reply today with your availability.\n\n"
            "Regards"
        ),
    },
]


def ensure_default_templates() -> int:
    """Insert the default templates when the table is empty. Idempotent (safe
    under the debug reloader's double startup); never overwrites user edits.
    Returns the number of templates inserted."""
    count = db.session.scalar(select(func.count()).select_from(MessageTemplate))
    if count:
        return 0
    for preset in DEFAULT_TEMPLATES:
        db.session.add(MessageTemplate(**preset))
    db.session.commit()
    return len(DEFAULT_TEMPLATES)
