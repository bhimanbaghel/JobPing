"""HTTP surface for the recommendation feature (FR6, FR8, FR9).

All endpoints require a valid JWT and operate on the calling user.
"""
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.blueprints.jobs import bp
from app.models import Job, db
from app.services.recommender import (
    MissingRolePreferences,
    get_existing_recommendations,
    recommend_for_user,
)


def _current_user_id() -> int | None:
    sub = get_jwt_identity()
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


@bp.get("/health")
def health():
    return {"blueprint": "jobs"}


@bp.get("/recommendations")
@jwt_required()
def list_recommendations():
    """FR6 / FR6.4 — return Table 3 rows for the current user, sorted by score.

    If the user has never been scored we trigger a one-shot computation so
    the page is never empty just because the cache is cold.

    Query params:
      - ``recompute=1`` forces a fresh computation before returning.
    """
    uid = _current_user_id()
    if uid is None:
        return jsonify({"error": "Invalid token subject."}), 422

    force = request.args.get("recompute", "").lower() in {"1", "true", "yes"}
    try:
        if force:
            recs = recommend_for_user(uid)
        else:
            recs = get_existing_recommendations(uid)
            if not recs:
                recs = recommend_for_user(uid)
    except MissingRolePreferences as exc:
        # FR6.1 — surface the precondition to the UI as a 400.
        return (
            jsonify(
                {
                    "error": str(exc),
                    "code": "missing_role_preferences",
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "count": len(recs),
                "items": [r.to_dict() for r in recs],
            }
        ),
        200,
    )


@bp.post("/recommendations/recompute")
@jwt_required()
def recompute_recommendations():
    """Force a recomputation; useful after preferences/resume change."""
    uid = _current_user_id()
    if uid is None:
        return jsonify({"error": "Invalid token subject."}), 422

    try:
        recs = recommend_for_user(uid)
    except MissingRolePreferences as exc:
        return (
            jsonify(
                {
                    "error": str(exc),
                    "code": "missing_role_preferences",
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                "count": len(recs),
                "items": [r.to_dict() for r in recs],
            }
        ),
        200,
    )


@bp.get("/<int:job_id>")
@jwt_required()
def get_job(job_id: int):
    """FR8 — full details for a single job (used by the frontend modal)."""
    job = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "Job not found."}), 404

    return (
        jsonify(
            {
                "job_id": job.id,
                "role": job.role,
                "company": job.company,
                "description": job.description,
                "link": job.link,
                "location": {
                    "city": job.city,
                    "state": job.state,
                    "country": job.country,
                },
                "salary_usd": (
                    float(job.salary_usd) if job.salary_usd is not None else None
                ),
                "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            }
        ),
        200,
    )
