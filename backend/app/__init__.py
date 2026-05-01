import os
import logging

from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from app.config import config_by_name
from app.models import db
from app.services.embeddings import warmup_model




jwt = JWTManager()
migrate = Migrate()

def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    cfg = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(cfg)

    jwt.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.jobs import bp as jobs_bp
    from app.blueprints.profile import bp as profile_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")

    should_preload = (
        config_name != "testing"
        and os.environ.get("PRELOAD_EMBEDDING_MODEL", "1").strip().lower()
        not in {"0", "false", "no"}
    )
    if should_preload:
        try:
            if warmup_model():
                app.logger.info("SBERT model preloaded and cached on disk.")
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "SBERT preload failed; falling back to lazy load: %s",
                exc,
            )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.cli.command("run-scrapers")
    def _run_scrapers_cmd():
        """Run every registered scraper and write results to the DB."""
        import logging
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            )
        from scrapers.runner import run_all_scrapers
        run_all_scrapers()

    return app
