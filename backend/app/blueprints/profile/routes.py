from app.blueprints.profile import bp


@bp.get("/health")
def health():
    return {"blueprint": "profile"}
