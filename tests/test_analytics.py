from datetime import date, timedelta

from app.models import JOB_PRIORITIES, JOB_STATUSES
from app.services import analytics

from .factories import make_contractor, make_flat, make_job


def _this_month() -> str:
    return date.today().strftime("%Y-%m")


class TestMonthKeys:
    def test_returns_requested_window_ending_this_month(self):
        keys = analytics.month_keys(12)
        assert len(keys) == 12
        assert keys[-1] == _this_month()
        assert keys == sorted(keys)

    def test_wraps_across_a_year_boundary(self):
        keys = analytics.month_keys(3, today=date(2026, 1, 15))
        assert keys == ["2025-11", "2025-12", "2026-01"]

    def test_month_display(self):
        assert analytics.month_display("2026-07") == "Jul 2026"


class TestMonthlyJobVolume:
    def test_counts_zero_fill_and_window(self, db):
        flat = make_flat()
        make_job(flat=flat)
        make_job(flat=flat)
        make_job(flat=flat, reported_date=date.today() - timedelta(days=400))

        volume = analytics.monthly_job_volume()
        assert len(volume) == 12
        by_month = {row["month"]: row["count"] for row in volume}
        assert by_month[_this_month()] == 2
        assert sum(by_month.values()) == 2  # old job outside the window

    def test_excludes_soft_deleted_jobs(self, db):
        job = make_job()
        make_job(flat=job.flat)
        job.soft_delete()
        db.session.commit()

        volume = analytics.monthly_job_volume()
        assert volume[-1]["count"] == 1


class TestCostTrend:
    def test_sums_completed_jobs_only(self, db):
        flat = make_flat()
        make_job(flat=flat, status="Completed", completed_date=date.today(),
                 estimated_cost=100.0, actual_cost=150.0)
        make_job(flat=flat, status="Completed", completed_date=date.today(),
                 estimated_cost=None, actual_cost=50.0)
        make_job(flat=flat, status="Pending", estimated_cost=999.0)

        trend = analytics.cost_trend()
        assert len(trend) == 12
        latest = trend[-1]
        assert latest["estimated"] == 100.0
        assert latest["actual"] == 200.0
        assert all(row["actual"] == 0.0 for row in trend[:-1])

    def test_excludes_soft_deleted_jobs(self, db):
        job = make_job(status="Completed", completed_date=date.today(), actual_cost=75.0)
        job.soft_delete()
        db.session.commit()

        assert analytics.cost_trend()[-1]["actual"] == 0.0


class TestBreakdowns:
    def test_status_breakdown_orders_and_zero_fills(self, db):
        flat = make_flat()
        make_job(flat=flat, status="Pending")
        make_job(flat=flat, status="Pending")
        make_job(flat=flat, status="Completed", completed_date=date.today())
        deleted = make_job(flat=flat, status="Pending")
        deleted.soft_delete()
        db.session.commit()

        breakdown = analytics.status_breakdown()
        assert [row["status"] for row in breakdown] == JOB_STATUSES
        counts = {row["status"]: row["count"] for row in breakdown}
        assert counts["Pending"] == 2
        assert counts["Completed"] == 1
        assert counts["Cancelled"] == 0

    def test_priority_breakdown_orders_and_zero_fills(self, db):
        flat = make_flat()
        make_job(flat=flat, priority="Urgent")
        make_job(flat=flat, priority="Urgent")
        make_job(flat=flat, priority="Low")

        breakdown = analytics.priority_breakdown()
        assert [row["priority"] for row in breakdown] == JOB_PRIORITIES
        counts = {row["priority"]: row["count"] for row in breakdown}
        assert counts["Urgent"] == 2
        assert counts["Low"] == 1
        assert counts["Medium"] == 0


class TestTopContractors:
    def test_ranks_by_completed_count_with_avg_cost(self, db):
        flat = make_flat()
        busy = make_contractor(name="Busy Ltd")
        quiet = make_contractor(name="Quiet Ltd")
        make_job(flat=flat, contractor_id=busy.id, status="Completed",
                 completed_date=date.today(), actual_cost=100.0)
        make_job(flat=flat, contractor_id=busy.id, status="Completed",
                 completed_date=date.today(), actual_cost=200.0)
        make_job(flat=flat, contractor_id=quiet.id, status="Completed",
                 completed_date=date.today(), actual_cost=None)
        make_job(flat=flat, contractor_id=quiet.id, status="Pending")

        top = analytics.top_contractors()
        assert [row["name"] for row in top] == ["Busy Ltd", "Quiet Ltd"]
        assert top[0]["completed"] == 2
        assert top[0]["avg_cost"] == 150.0
        assert top[1]["completed"] == 1
        assert top[1]["avg_cost"] is None

    def test_excludes_deleted_and_respects_limit(self, db):
        flat = make_flat()
        binned = make_contractor(name="Binned Ltd")
        make_job(flat=flat, contractor_id=binned.id, status="Completed",
                 completed_date=date.today())
        binned.soft_delete()
        keep = make_contractor(name="Keep Ltd")
        make_job(flat=flat, contractor_id=keep.id, status="Completed",
                 completed_date=date.today())
        make_job(flat=flat, contractor_id=keep.id, status="Completed",
                 completed_date=date.today())
        db.session.commit()

        top = analytics.top_contractors(limit=1)
        assert [row["name"] for row in top] == ["Keep Ltd"]


class TestSummary:
    def test_headline_figures(self, db):
        flat = make_flat()
        make_job(flat=flat, status="Completed", completed_date=date.today(),
                 actual_cost=80.0)
        make_job(flat=flat, status="Pending")

        stats = analytics.summary()
        assert stats["has_data"] is True
        assert stats["reported"] == 2
        assert stats["completed"] == 1
        assert stats["total_spend"] == 80.0
        assert stats["avg_cost"] == 80.0

    def test_empty_database(self, db):
        stats = analytics.summary()
        assert stats["has_data"] is False
        assert stats["reported"] == 0
        assert stats["total_spend"] == 0.0
        assert stats["avg_cost"] is None


class TestAnalyticsPage:
    def test_renders_empty_state_without_data(self, client):
        response = client.get("/analytics")
        assert response.status_code == 200
        assert b"No data to chart yet" in response.data
        assert b"analytics-data" not in response.data

    def test_renders_charts_with_data(self, client, db):
        contractor = make_contractor(name="Chart Trades Ltd")
        make_job(contractor_id=contractor.id, status="Completed",
                 completed_date=date.today(), estimated_cost=90.0, actual_cost=110.0)

        response = client.get("/analytics")
        assert response.status_code == 200
        assert b'id="analytics-data"' in response.data
        assert b"chart-volume" in response.data
        assert b"chart-costs" in response.data
        assert b"chart-status" in response.data
        assert b"chart-priority" in response.data
        assert b"chart-contractors" in response.data
        assert b"Chart Trades Ltd" in response.data
        assert "£110.00".encode() in response.data  # table twin uses gbp filter

    def test_sidebar_links_to_analytics(self, client):
        response = client.get("/")
        assert b'href="/analytics"' in response.data
