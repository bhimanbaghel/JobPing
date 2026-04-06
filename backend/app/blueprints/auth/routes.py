from app.blueprints.auth import bp


@bp.get("/health")
def health():
    return {"blueprint": "auth"}
