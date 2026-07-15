from flask import Blueprint, flash, redirect, render_template, url_for

from ..extensions import db
from ..models import Contractor, Flat, MaintenanceJob

bp = Blueprint("recycle", __name__, url_prefix="/recycle-bin")

_MODELS = {"job": MaintenanceJob, "flat": Flat, "contractor": Contractor}


@bp.route("")
def index():
    def deleted(model):
        return db.session.scalars(
            model.deleted_select().order_by(model.deleted_at.desc())
        ).all()

    return render_template(
        "recycle_bin.html",
        deleted_jobs=deleted(MaintenanceJob),
        deleted_flats=deleted(Flat),
        deleted_contractors=deleted(Contractor),
    )


@bp.route("/<any(job, flat, contractor):kind>/<int:item_id>/restore", methods=["POST"])
def restore(kind: str, item_id: int):
    item = db.get_or_404(_MODELS[kind], item_id)
    item.restore()
    if kind == "flat":
        # bring back only the jobs that were binned by the flat's cascade,
        # not ones the user deleted independently beforehand
        for job in item.maintenance_jobs:
            if job.is_deleted and job.deleted_by == "cascade:flat":
                job.restore()
    db.session.commit()
    flash(f"{kind.capitalize()} restored successfully!", "success")
    return redirect(url_for("recycle.index"))


@bp.route("/<any(job, flat, contractor):kind>/<int:item_id>/purge", methods=["POST"])
def purge(kind: str, item_id: int):
    item = db.get_or_404(_MODELS[kind], item_id)
    if kind == "flat":
        # jobs reference the flat with a NOT NULL FK; they go with it
        for job in list(item.maintenance_jobs):
            db.session.delete(job)
    db.session.delete(item)
    db.session.commit()
    flash(f"{kind.capitalize()} permanently deleted!", "warning")
    return redirect(url_for("recycle.index"))
