from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import re

from app.blueprints.profile import bp
from app.models import Job, Resume, UserPreference, db
from app.services.resume_parser import ResumeParseError, extract_text_from_pdf_bytes

MAX_RESUME_BYTES = 5 * 1024 * 1024
_ROLE_NOISE_RE = re.compile(r"\([^)]*\)")
_ROLE_SPLIT_RE = re.compile(r"\s*(?:\||/|,| - | — )\s*")


def _current_user_id() -> int | None:
    sub = get_jwt_identity()
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


def _normalize_roles(raw_roles) -> list[str]:
    if not isinstance(raw_roles, list):
        raise ValueError("roles must be an array")
    cleaned = []
    for role in raw_roles:
        if not isinstance(role, str):
            continue
        text = role.strip()
        if text:
            cleaned.append(text)
    if not cleaned:
        raise ValueError("At least one job role is required.")
    return cleaned


def _standardize_role(raw_role: str) -> str:
    text = (raw_role or "").strip()
    if not text:
        return ""
    text = _ROLE_NOISE_RE.sub("", text).strip()
    parts = [p.strip() for p in _ROLE_SPLIT_RE.split(text) if p.strip()]
    return parts[0] if parts else text


@bp.get("/health")
def health():
    return {"blueprint": "profile"}


@bp.get("/preferences/role-options")
@jwt_required()
def role_options():
    uid = _current_user_id()
    if uid is None:
        return jsonify({"error": "Invalid token subject."}), 422

    role_counts: dict[str, int] = {}
    rows = db.session.query(Job.role).filter(Job.role.isnot(None)).all()
    for (raw_role,) in rows:
        role = _standardize_role(raw_role)
        if not role:
            continue
        role_counts[role] = role_counts.get(role, 0) + 1

    ordered = sorted(role_counts.items(), key=lambda t: (-t[1], t[0].lower()))
    return jsonify({"roles": [role for role, _count in ordered]}), 200


@bp.get("/preferences/status")
@jwt_required()
def preferences_status():
    uid = _current_user_id()
    if uid is None:
        return jsonify({"error": "Invalid token subject."}), 422

    pref = db.session.query(UserPreference).filter_by(user_id=uid).one_or_none()
    resume = db.session.query(Resume).filter_by(user_id=uid).one_or_none()

    roles = list(pref.roles or []) if pref is not None else []
    companies = list(pref.companies or []) if pref is not None else []
    has_roles = any(isinstance(role, str) and role.strip() for role in roles)
    has_resume = bool(resume is not None and (resume.parsed_text or "").strip())
    is_locked = bool(pref.is_locked) if pref is not None else False

    return (
        jsonify(
            {
                "has_preferences": has_roles,
                "has_resume": has_resume,
                "roles": roles,
                "companies": companies,
                "is_locked": is_locked,
            }
        ),
        200,
    )


@bp.post("/preferences")
@jwt_required()
def upsert_preferences():
    uid = _current_user_id()
    if uid is None:
        return jsonify({"error": "Invalid token subject."}), 422

    pref = db.session.query(UserPreference).filter_by(user_id=uid).one_or_none()
    if pref is not None and pref.is_locked:
        return jsonify({"error": "Preferences are locked and cannot be modified."}), 403

    try:
        roles = _normalize_roles(request.form.getlist("roles"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    companies = []
    for c in request.form.getlist("companies"):
        if isinstance(c, str):
            c_text = c.strip()
            if c_text:
                companies.append(c_text)

    resume_file = request.files.get("resume")
    resume_text = None
    if resume_file and resume_file.filename:
        if (resume_file.mimetype or "").lower() not in {
            "application/pdf",
            "application/x-pdf",
        }:
            return jsonify({"error": "Resume must be a PDF file."}), 400

        file_bytes = resume_file.read()
        if len(file_bytes) >= MAX_RESUME_BYTES:
            return jsonify({"error": "Resume must be smaller than 5MB."}), 400
        try:
            resume_text = extract_text_from_pdf_bytes(file_bytes)
        except ResumeParseError as exc:
            return jsonify({"error": str(exc)}), 400

    pref = db.session.query(UserPreference).filter_by(user_id=uid).one_or_none()
    if pref is None:
        pref = UserPreference(
            user_id=uid,
            roles=roles,
            companies=companies,
            locations=[],
        )
        db.session.add(pref)
    else:
        pref.roles = roles
        pref.companies = companies

    # Check for is_locked form parameter
    is_locked_str = request.form.get("is_locked", "false").lower()
    if is_locked_str in ("true", "1", "yes"):
        pref.is_locked = True

    if resume_text is not None:
        resume = db.session.query(Resume).filter_by(user_id=uid).one_or_none()
        if resume is None:
            resume = Resume(user_id=uid, parsed_text=resume_text)
            db.session.add(resume)
        else:
            resume.parsed_text = resume_text

    db.session.commit()
    return jsonify({"message": "Preferences saved successfully."}), 200
