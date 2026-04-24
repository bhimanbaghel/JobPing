import os

from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from app.config import config_by_name
from app.models import db




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
