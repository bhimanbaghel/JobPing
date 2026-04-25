import json
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import Text, TypeDecorator

db = SQLAlchemy()


# ─────────────────────────────────────────────────────────────────────────────
# Portable vector column
#
# Production runs on PostgreSQL with the `pgvector` extension and stores native
# `vector(N)` columns. Tests run on in-memory SQLite (see TestingConfig) which
# has no such type, so we serialize the embedding as a JSON-encoded list of
# floats. The recommender code always reads/writes Python lists so callers
# don't notice the difference.
# ─────────────────────────────────────────────────────────────────────────────
class VectorColumn(TypeDecorator):
    impl = Text
    cache_ok = True

    def __init__(self, dim: int):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value) if hasattr(value, "tolist") and not isinstance(value, list) else value
        if hasattr(value, "tolist"):
            value = value.tolist()
        return json.dumps(list(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value) if value is not None else None
        return json.loads(value)


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<User {self.email}>"


# ─────────────────────────────────────────────────────────────────────────────
# STUB MODELS — replace when teammates' real implementations land.
# These are here only so the recommender service can be developed end-to-end
# (and so Alembic can autogenerate sensible migrations for local dev).
# ─────────────────────────────────────────────────────────────────────────────
class Job(db.Model):
    """Owned by scraping pipeline + consumed by recommender.

    Keep field names in sync with the contract in
    `docs/contracts/jobs_table.md`.
    """

    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(255), nullable=False, index=True)
    company = db.Column(db.String(255), nullable=False, index=True)
    external_id = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(2048), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(120), nullable=True)
    country = db.Column(db.String(120), nullable=True)
    salary_usd = db.Column(db.Numeric(12, 2), nullable=True)
    posted_at = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_seen_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "company",
            "external_id",
            name="uq_jobs_company_external_id",
        ),
    )

    def __repr__(self):
        return f"<Job {self.id} {self.role}@{self.company}>"


class UserPreference(db.Model):
    """STUB: owned by the preferences teammate.

    Stores the arrays the recommender filters on.
    """

    __tablename__ = "user_preferences"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    roles = db.Column(db.JSON, nullable=False, default=list)
    companies = db.Column(db.JSON, nullable=False, default=list)
    locations = db.Column(db.JSON, nullable=False, default=list)
    is_locked = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class Resume(db.Model):
    """STUB: owned by the preferences teammate.

    Holds parsed resume text per user. The recommender only ever reads
    `parsed_text`; binary file storage is the teammate's responsibility.
    """

    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    parsed_text = db.Column(db.Text, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# RECOMMENDATION-OWNED TABLES (Bhiman)
# ─────────────────────────────────────────────────────────────────────────────
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


class JobEmbedding(db.Model):
    """Table 2 — cached vector for a job's description."""

    __tablename__ = "job_embeddings"
    job_id = db.Column(
        db.Integer,
        db.ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding = db.Column(VectorColumn(EMBEDDING_DIM), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class ResumeEmbedding(db.Model):
    """Table 4 — cached vector for a user's resume (or preferences fallback).

    `source` is `'resume'` when computed from the uploaded resume text and
    `'preferences'` when the user has no resume and we synthesize a query
    string from their role/company/location preferences (FR6.3).
    """

    __tablename__ = "resume_embeddings"
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding = db.Column(VectorColumn(EMBEDDING_DIM), nullable=False)
    source = db.Column(db.String(20), nullable=False, default="resume")
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class Recommendation(db.Model):
    """Table 3 — cross product of users × jobs with similarity score."""

    __tablename__ = "recommendations"
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    job_id = db.Column(
        db.Integer,
        db.ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    similarity_score = db.Column(db.Float, nullable=False, index=True)
    computed_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
