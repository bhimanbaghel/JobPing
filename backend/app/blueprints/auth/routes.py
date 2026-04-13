from . import bp
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token
from datetime import datetime, timezone
from app.models import db, User
from app.validators import validate_email_format, validate_password_nist

"""
POST /api/auth/register
  Request:  { "name": str, "email": str, "password": str }
  Success:  201  { "message": "...", "access_token": "...", "user": { "id", "name", "email" } }
  Errors:   400  validation failures
            409  email already registered
"""


@bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)

    # ── 1. Require JSON body ────────────────────────────────────────
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    # ── 2. Presence checks ──────────────────────────────────────────
    missing = []
    if not email:
        missing.append("email")
    if not password:
        missing.append("password")
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    # ── 3. Email format validation ──────────────────────────────────
    email_err = validate_email_format(email)
    if email_err:
        return jsonify({"error": email_err}), 400

    # ── 4. Email uniqueness ─────────────────────────────────────────
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists."}), 409

    # ── 5. NIST SP 800-63B password validation ──────────────────────
    pw_err = validate_password_nist(password, email=email)
    if pw_err:
        return jsonify({"error": pw_err}), 400

    # ── 6. Hash password (Werkzeug 3.x defaults to scrypt,
    #        falls back to pbkdf2:sha256) ────────────────────────────
    password_hash = generate_password_hash(password)

    # ── 7. Create user ──────────────────────────────────────────────
    new_user = User(email=email, password_hash=password_hash)
    db.session.add(new_user)
    db.session.commit()

    # ── 8. Issue JWT access token ───────────────────────────────────
    access_token = create_access_token(identity=str(new_user.id))

    return jsonify({
        "message": "Registration successful.",
        "access_token": access_token,
        "user": {
            "id": new_user.id,
            "email": new_user.email,
        },
    }), 201

"""
POST /api/auth/login
  Request:  { "email": str, "password": str }
  Success:  200  { "message": "...", "access_token": "...", "refresh_token": "...", "user": { ... } }
  Errors:   400  validation failures
            401  invalid credentials
            403  account locked
"""

@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Missing email or password."}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Invalid email or password."}), 401

    if user.failed_login_attempts >= 5:
        return jsonify({"error": "Account locked due to too many failed attempts. Contact support."}), 403

    if not check_password_hash(user.password_hash, password):
        user.failed_login_attempts += 1
        db.session.commit()
        if user.failed_login_attempts >= 5:
            return jsonify({"error": "Account locked due to too many failed attempts. Contact support."}), 403
        else:
            return jsonify({"error": "Invalid email or password."}), 401

    # successful login
    user.failed_login_attempts = 0
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "message": "Login successful.",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "email": user.email,
        },
    }), 200
