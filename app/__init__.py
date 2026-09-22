import os

from flask import Flask, render_template, request
from flask_login import current_user
from sqlalchemy.engine import make_url
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import DEV_SECRET_KEY, Config
from .extensions import csrf, db, login_manager

# Reachable without signing in. Everything else requires a login.
PUBLIC_ENDPOINTS = {"auth.login", "health", "static"}


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    if app.config["PRODUCTION"]:
        _check_production_config(app)
        # The host terminates HTTPS at its proxy; trust its forwarded headers
        # so url_for(..., _external=True) and redirects use https.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from .blueprints import (
        analytics,
        auth,
        contractors,
        dashboard,
        flats,
        jobs,
        message_templates,
        recycle,
        settings,
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(jobs.bp)
    app.register_blueprint(flats.bp)
    app.register_blueprint(contractors.bp)
    app.register_blueprint(message_templates.bp)
    app.register_blueprint(recycle.bp)
    app.register_blueprint(settings.bp)

    from . import cli, seed

    cli.register(app)
    seed.register(app)

    _register_login_guard(app)
    _register_template_filters(app)
    _register_error_handlers(app)

    @app.route("/healthz")
    def health():
        return {"status": "ok"}

    if app.config["RUN_SCHEMA_SYNC"]:
        from .db_migrate import ensure_schema
        from .services.accounts import ensure_initial_user

        with app.app_context():
            ensure_schema()
            if ensure_initial_user(app.config):
                app.logger.info("Created the initial account from INITIAL_USER_EMAIL")

    return app


def _check_production_config(app: Flask) -> None:
    """Refuse to start in production with settings that would leak sessions
    or lose data on the next deploy."""
    secret = app.config.get("SECRET_KEY") or ""
    if secret in (DEV_SECRET_KEY, "change-me") or len(secret) < 32:
        raise RuntimeError(
            "APP_ENV=production needs a strong SECRET_KEY (32+ random characters). Generate "
            'one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
    if url.drivername.startswith("sqlite") and not os.path.isabs(url.database or ""):
        raise RuntimeError(
            "APP_ENV=production needs DATABASE_URL to be an absolute path on the persistent "
            "volume, e.g. sqlite:////data/maintenance_tracker.db - a relative path lives in "
            "the container and is wiped on every deploy."
        )


def _register_login_guard(app: Flask) -> None:
    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        user = db.session.get(User, int(user_id)) if user_id.isdigit() else None
        # A disabled account is signed out on its next request.
        return user if user is not None and user.is_enabled else None

    @app.before_request
    def require_login():
        if request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        return None

    if app.config["AUTO_BACKUP"]:
        from .services.backup import ensure_daily_backup

        @app.before_request
        def daily_backup():
            if request.endpoint != "static":
                ensure_daily_backup()


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

    @app.template_global("url_with_page")
    def url_with_page(page: int) -> str:
        """Current URL with the page query param swapped (keeps filters)."""
        from flask import request, url_for

        args = request.args.to_dict()
        args["page"] = page
        return url_for(request.endpoint, **args)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500
