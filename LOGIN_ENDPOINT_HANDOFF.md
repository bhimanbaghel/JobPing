# Login Endpoint Handoff — Task #7

## Task Spec

**Endpoint:** `POST /api/auth/login`
**Behavior:** Verify credentials with `check_password_hash`, track failed login attempts, lock account after 5 consecutive failures, return access + refresh tokens via Flask-JWT-Extended.

---

## Repo Setup

- **Branch:** Pull the latest from the branch with the registration endpoint changes.
- **Backend root:** `JobPing/backend/`
- **Activate venv:** `source .venv/bin/activate`
- **Run tests:** `PYTHONPATH=. pytest tests/test_auth_register.py -v` (or from `backend/` directly if test file is at top level)

---

## Project Structure (relevant files)

```
backend/
├── app/
│   ├── __init__.py          ← app factory, blueprint registration
│   ├── config.py            ← Config classes (Dev, Prod, Testing)
│   ├── models.py            ← User model
│   ├── validators.py        ← email/password validation (reusable)
│   └── blueprints/
│       └── auth/
│           ├── __init__.py  ← defines `bp = Blueprint("auth", __name__)`
│           └── routes.py    ← /register lives here, ADD /login here
├── migrations/
├── .env.example
├── requirements.txt
└── wsgi.py
```

---

## Conventions

- Blueprint variable is named **`bp`**, not `auth_bp`.
- `url_prefix="/api/auth"` is set in `create_app()` via `app.register_blueprint(bp, url_prefix="/api/auth")`, NOT in the Blueprint constructor.
- Routes use `@bp.route(...)`.
- All responses return `jsonify({...}), STATUS_CODE`.
- Errors use `{"error": "message"}` format.

---

## User Model (`backend/app/models.py`)

```python
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=..., nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
```

Key details:
- **`email`** is stored lowercase (registration normalizes it).
- **`password_hash`** is generated with `werkzeug.security.generate_password_hash` (defaults to scrypt). Verify with `check_password_hash(user.password_hash, password)`.
- **`failed_login_attempts`** is already in the model, defaults to 0. Use this for lockout tracking.

---

## Dependencies Already Available

| Package | Used for |
|---|---|
| `werkzeug.security` | `check_password_hash` for credential verification |
| `flask_jwt_extended` | `create_access_token`, `create_refresh_token` |
| `app.validators` | `validate_email_format` (optional, if you want to validate email format on login) |

All are in `requirements.txt` and initialized in `app/__init__.py`.

---

## JWT Config (`backend/app/config.py`)

```python
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
JWT_TOKEN_LOCATION = ["headers"]
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
```

Note: Refresh token expiry is not yet configured. You may want to add:
```python
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
```

---

## What to Implement

Add the `/login` route to `backend/app/blueprints/auth/routes.py` (same file as `/register`).

### Request

```json
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "their_password"
}
```

### Expected Logic

1. Parse and validate JSON body (email + password required).
2. Normalize email to lowercase.
3. Look up user by email. If not found → 401 (use a generic message like "Invalid email or password" to avoid leaking whether the email exists).
4. Check if account is locked (`failed_login_attempts >= 5`) → 403 with lockout message.
5. Verify password with `check_password_hash(user.password_hash, password)`.
6. If password wrong → increment `failed_login_attempts`, commit, return 401.
7. If password correct → reset `failed_login_attempts` to 0, commit, return access + refresh tokens.

### Success Response (200)

```json
{
  "message": "Login successful.",
  "access_token": "...",
  "refresh_token": "...",
  "user": {
    "id": 1,
    "name": "Lakshay",
    "email": "user@example.com"
  }
}
```

### Error Responses

| Status | Condition | Body |
|---|---|---|
| 400 | Missing fields or non-JSON body | `{"error": "..."}` |
| 401 | Wrong email or wrong password | `{"error": "Invalid email or password."}` |
| 403 | Account locked (5+ failures) | `{"error": "Account locked due to too many failed attempts. Contact support at bkb45@pitt.edu."}` |

---

## Imports You'll Need

```python
from flask import request, jsonify
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models import db, User
from . import bp
```

---

## Testing

- Use `create_app("testing")` in your test fixture — this uses in-memory SQLite (defined in `TestingConfig` in `config.py`).
- The registration endpoint works, so you can call it in test setup to create users before testing login.
- See `test_auth_register.py` for the fixture and helper pattern.

### Test cases to cover

1. Successful login returns 200 + both tokens.
2. Wrong password returns 401.
3. Nonexistent email returns 401 (same message as wrong password).
4. Missing email or password returns 400.
5. Account locks after 5 failed attempts → 403 on 6th.
6. Successful login resets `failed_login_attempts` to 0.
7. Locked account stays locked even with correct password.

---

## Migration Note

No new migration needed — `failed_login_attempts` is already on the User model. If you add `JWT_REFRESH_TOKEN_EXPIRES` to config, that's just a config change, no migration.
