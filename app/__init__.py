from flask import Flask, render_template

from .config import Config
from .extensions import db


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    db.init_app(app)

    from .blueprints import contractors, dashboard, flats, jobs, recycle

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(jobs.bp)
    app.register_blueprint(flats.bp)
    app.register_blueprint(contractors.bp)
    app.register_blueprint(recycle.bp)

    from . import cli

    cli.register(app)

    _register_template_filters(app)
    _register_error_handlers(app)

    if app.config["RUN_SCHEMA_SYNC"]:
        from .db_migrate import ensure_schema

        with app.app_context():
            ensure_schema()

    return app


def _register_template_filters(app: Flask) -> None:
    @app.template_filter("gbp")
    def gbp(value) -> str:
        if value is None:
            return "—"
        return f"£{value:,.2f}"

    @app.template_filter("ukdate")
    def ukdate(value) -> str:
        if not value:
            return "—"
        return value.strftime("%d/%m/%Y")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500
