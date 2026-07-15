from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db

JOB_STATUSES = ["Pending", "Scheduled", "In Progress", "Completed", "Cancelled"]
ACTIVE_JOB_STATUSES = ["Pending", "Scheduled", "In Progress"]
JOB_PRIORITIES = ["Low", "Medium", "High", "Urgent"]


def utcnow() -> datetime:
    """Naive UTC timestamp, matching the pre-existing rows in the database."""
    return datetime.now(UTC).replace(tzinfo=None)


class SoftDeleteMixin:
    """Recycle-bin support. Deleting moves rows to the bin; only a purge
    from the bin removes them. Every list/count/export query must go
    through active_select() (or filter is_deleted itself)."""

    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_by: Mapped[str | None] = mapped_column(String(100))

    @classmethod
    def active_select(cls):
        return select(cls).where(cls.is_deleted == False)  # noqa: E712

    @classmethod
    def deleted_select(cls):
        return select(cls).where(cls.is_deleted == True)  # noqa: E712

    def soft_delete(self, by: str | None = None) -> None:
        self.is_deleted = True
        self.deleted_at = utcnow()
        self.deleted_by = by

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


class Flat(SoftDeleteMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    # Several flats share numbers across buildings; payment_reference is
    # the unique business identifier (Excel import upserts by it).
    flat_number: Mapped[str] = mapped_column(String(20))
    payment_reference: Mapped[str] = mapped_column(String(50), unique=True)
    address: Mapped[str] = mapped_column(Text)
    postcode: Mapped[str | None] = mapped_column(String(20))
    tenant_name: Mapped[str | None] = mapped_column(String(100))
    tenant_contact_details: Mapped[str | None] = mapped_column(Text)
    rent_amount: Mapped[float | None] = mapped_column(Float)
    rent_due_date: Mapped[int | None] = mapped_column(Integer)  # day of month, 1-31
    tenancy_start_date: Mapped[date | None] = mapped_column(Date)
    tenancy_end_date: Mapped[date | None] = mapped_column(Date)
    landlord: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    maintenance_jobs: Mapped[list[MaintenanceJob]] = relationship(back_populates="flat")


class Contractor(SoftDeleteMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    company: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    specialty: Mapped[str | None] = mapped_column(String(100))
    # NB: a legacy is_active column still exists in old SQLite files; it was
    # superseded by is_deleted and is no longer mapped (see db_migrate.py).
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    maintenance_jobs: Mapped[list[MaintenanceJob]] = relationship(back_populates="contractor")


class MaintenanceJob(SoftDeleteMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    flat_id: Mapped[int] = mapped_column(ForeignKey("flat.id"))
    contractor_id: Mapped[int | None] = mapped_column(ForeignKey("contractor.id"))

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="Medium")
    status: Mapped[str] = mapped_column(String(20), default="Pending")

    reported_date: Mapped[date] = mapped_column(Date, default=date.today)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[date | None] = mapped_column(Date)

    estimated_cost: Mapped[float | None] = mapped_column(Float)
    actual_cost: Mapped[float | None] = mapped_column(Float)

    notes: Mapped[str | None] = mapped_column(Text)
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    follow_up_date: Mapped[datetime | None] = mapped_column(DateTime)
    follow_up_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    flat: Mapped[Flat] = relationship(back_populates="maintenance_jobs")
    contractor: Mapped[Contractor | None] = relationship(back_populates="maintenance_jobs")

    __table_args__ = (
        Index("idx_maintenance_job_status", "status"),
        Index("idx_maintenance_job_priority", "priority"),
        Index("idx_maintenance_job_created_at", "created_at"),
        Index("idx_maintenance_job_flat_id", "flat_id"),
        Index("idx_maintenance_job_contractor_id", "contractor_id"),
        Index("idx_maintenance_job_reported_date", "reported_date"),
        Index("idx_maintenance_job_follow_up_count", "follow_up_count"),
        Index("idx_maintenance_job_is_deleted", "is_deleted"),
    )

    @property
    def is_open(self) -> bool:
        return self.status in ACTIVE_JOB_STATUSES
