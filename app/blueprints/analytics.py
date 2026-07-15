from flask import Blueprint, render_template

from ..services import analytics

bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@bp.route("")
def index():
    stats = analytics.summary()
    volume = analytics.monthly_job_volume()
    costs = analytics.cost_trend()
    statuses = analytics.status_breakdown()
    priorities = analytics.priority_breakdown()
    contractors = analytics.top_contractors()

    return render_template(
        "analytics.html",
        stats=stats,
        volume=volume,
        costs=costs,
        statuses=statuses,
        priorities=priorities,
        contractors=contractors,
        chart_data={
            "volume": volume,
            "costs": costs,
            "statuses": statuses,
            "priorities": priorities,
            "contractors": contractors,
        },
    )
