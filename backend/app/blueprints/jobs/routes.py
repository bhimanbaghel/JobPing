from app.blueprints.jobs import bp


@bp.get("/health")
def health():
    return {"blueprint": "jobs"}
