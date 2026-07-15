"""Excel import/export for flats and jobs.

pandas is imported lazily inside the I/O functions (it costs ~1-2 s on
Windows); the parsing helpers above them are dependency-free so unit
tests never pay that cost. Spreadsheet cells arrive messy — multiline
values, currency symbols, NaN/NaT — hence the defensive parsing.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO

from ..extensions import db
from ..models import Flat, MaintenanceJob

IMPORT_SHEET_COLUMNS = {
    "payment_reference": "Payment Reference",
    "flat_number": "Flat No.",
    "address": "Tenancy / Property Address",
    "postcode": "Tenancy / Property Postcode",
    "tenant_name": "Tenants",
    "tenant_contact_details": "Tenant Contact Details",
    "rent_amount": "Rent",
    "rent_due_date": "Due Date",
    "landlord": "Landlord",
    "tenancy_start_date": "Tenancy Start Date",
    "tenancy_end_date": "Tenancy End Date",
}


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip() or value.strip().lower() in ("nan", "nat", "none")
    try:
        return value != value  # NaN and NaT are not equal to themselves
    except Exception:
        return False


def clean_rent_value(value) -> float | None:
    """'£1,250.00' -> 1250.0; multiline cells use the first parseable line."""
    if _is_missing(value):
        return None
    for line in str(value).splitlines():
        cleaned = line.replace(",", "").replace("£", "").replace("$", "").strip()
        if not cleaned:
            continue
        try:
            return float(cleaned)
        except ValueError:
            continue
    return None


def parse_uk_date(value) -> date | None:
    """UK-format ('dd/mm/yyyy') date cells; cells holding several dates
    (newline- or space-separated) yield the first parseable one. Real
    datetime cells (pandas Timestamps) pass through directly."""
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for part in re.split(r"\s+", str(value).strip()):
        if "/" not in part:
            continue
        try:
            return datetime.strptime(part, "%d/%m/%Y").date()
        except ValueError:
            continue
    return None


def clean_due_date(value) -> int | None:
    """Rent due day of month: first number in the cell, if it's 1-31."""
    if _is_missing(value):
        return None
    match = re.search(r"\d+", str(value))
    if match:
        day = int(match.group())
        if 1 <= day <= 31:
            return day
    return None


def _cell(row, column: str) -> str:
    value = row.get(column, "")
    return "" if _is_missing(value) else str(value).strip()


def import_flats_from_file(file) -> tuple[int, int, int]:
    """Upsert flats from an Excel sheet, keyed on Payment Reference.

    Returns (imported, updated, skipped)."""
    import pandas as pd

    df = pd.read_excel(file)
    imported = updated = skipped = 0

    for _, row in df.iterrows():
        payment_ref = _cell(row, IMPORT_SHEET_COLUMNS["payment_reference"])
        address = _cell(row, IMPORT_SHEET_COLUMNS["address"])
        if not payment_ref or not address:
            skipped += 1
            continue

        flat = db.session.scalar(
            db.select(Flat).where(Flat.payment_reference == payment_ref)
        )
        if flat is None:
            flat = Flat(payment_reference=payment_ref)
            db.session.add(flat)
            imported += 1
        else:
            updated += 1

        flat_number = _cell(row, IMPORT_SHEET_COLUMNS["flat_number"])
        flat.flat_number = flat_number or flat.flat_number or payment_ref
        flat.address = address
        flat.postcode = _cell(row, IMPORT_SHEET_COLUMNS["postcode"])
        flat.tenant_name = _cell(row, IMPORT_SHEET_COLUMNS["tenant_name"])
        flat.tenant_contact_details = _cell(row, IMPORT_SHEET_COLUMNS["tenant_contact_details"])
        flat.rent_amount = clean_rent_value(row.get(IMPORT_SHEET_COLUMNS["rent_amount"]))
        flat.rent_due_date = clean_due_date(row.get(IMPORT_SHEET_COLUMNS["rent_due_date"]))
        flat.landlord = _cell(row, IMPORT_SHEET_COLUMNS["landlord"])

        start = parse_uk_date(row.get(IMPORT_SHEET_COLUMNS["tenancy_start_date"]))
        end = parse_uk_date(row.get(IMPORT_SHEET_COLUMNS["tenancy_end_date"]))
        if start:
            flat.tenancy_start_date = start
        if end:
            flat.tenancy_end_date = end

    db.session.commit()
    return imported, updated, skipped


def build_jobs_export(jobs: list[MaintenanceJob]) -> BytesIO:
    """Multi-sheet workbook: all jobs, one sheet per status, and a summary."""
    import pandas as pd

    rows = []
    for job in jobs:
        rows.append(
            {
                "Job ID": job.id,
                "Payment Reference": job.flat.payment_reference,
                "Flat Number": job.flat.flat_number or "No Flat No",
                "Address": job.flat.address,
                "Tenant": job.flat.tenant_name or "No Tenant",
                "Title": job.title,
                "Description": job.description or "",
                "Priority": job.priority,
                "Status": job.status,
                "Contractor": job.contractor.name if job.contractor else "Not Assigned",
                "Contractor Email": job.contractor.email if job.contractor else "",
                "Reported Date": job.reported_date.strftime("%Y-%m-%d"),
                "Scheduled Date": job.scheduled_date.strftime("%Y-%m-%d") if job.scheduled_date else "",
                "Completed Date": job.completed_date.strftime("%Y-%m-%d") if job.completed_date else "",
                "Estimated Cost": job.estimated_cost,
                "Actual Cost": job.actual_cost,
                "Notes": job.notes or "",
                "Follow-up Count": job.follow_up_count or 0,
                "Follow-up Date": job.follow_up_date.strftime("%Y-%m-%d") if job.follow_up_date else "",
                "Follow-up Notes": job.follow_up_notes or "",
            }
        )

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="All Jobs", index=False)

        statuses = ["Pending", "Scheduled", "In Progress", "Completed", "Cancelled"]
        for status in statuses:
            status_df = df[df["Status"] == status] if not df.empty else df
            if not status_df.empty:
                status_df.to_excel(writer, sheet_name=status, index=False)

        summary = pd.DataFrame(
            {
                "Status": statuses,
                "Job Count": [
                    len(df[df["Status"] == s]) if not df.empty else 0 for s in statuses
                ],
            }
        )
        summary["Percentage"] = (
            summary["Job Count"] / len(df) * 100 if len(df) else 0.0
        )
        summary.to_excel(writer, sheet_name="Summary", index=False)

    output.seek(0)
    return output
