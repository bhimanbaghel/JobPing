"""Recommendations schema (jobs, prefs, resume + embeddings + recommendations).

Revision ID: a1b2c3d4e5f6
Revises: f3a9c2b101ef
Create Date: 2026-04-23

Idempotent on purpose: the `jobs`, `user_preferences`, and `resumes` tables
are owned by other teammates. If their migrations land first, we skip
re-creating those tables here. We always create the embedding/recommendation
tables (Tables 2, 3, 4) which are owned by Bhiman.
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f3a9c2b101ef"
branch_labels = None
depends_on = None


EMBEDDING_DIM = 384


def _embedding_col(bind):
    if bind.dialect.name == "postgresql":
        from pgvector.sqlalchemy import Vector
        return sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False)
    return sa.Column("embedding", sa.Text(), nullable=False)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── stub tables (skip if a teammate's migration already created them) ──
    if "jobs" not in existing:
        op.create_table(
            "jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=255), nullable=False),
            sa.Column("company", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("link", sa.String(length=2048), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("state", sa.String(length=120), nullable=True),
            sa.Column("country", sa.String(length=120), nullable=True),
            sa.Column("salary_usd", sa.Numeric(12, 2), nullable=True),
            sa.Column("posted_at", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_jobs_role", "jobs", ["role"])
        op.create_index("ix_jobs_company", "jobs", ["company"])

    if "user_preferences" not in existing:
        op.create_table(
            "user_preferences",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("roles", sa.JSON(), nullable=False),
            sa.Column("companies", sa.JSON(), nullable=False),
            sa.Column("locations", sa.JSON(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])

    if "resumes" not in existing:
        op.create_table(
            "resumes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("parsed_text", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_resumes_user_id", "resumes", ["user_id"])

    # ── owned tables (always create) ───────────────────────────────────────
    op.create_table(
        "job_embeddings",
        sa.Column("job_id", sa.Integer(), nullable=False),
        _embedding_col(bind),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )

    op.create_table(
        "resume_embeddings",
        sa.Column("user_id", sa.Integer(), nullable=False),
        _embedding_col(bind),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "recommendations",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "job_id"),
    )
    op.create_index(
        "ix_recommendations_user_score",
        "recommendations",
        ["user_id", "similarity_score"],
    )


def downgrade():
    op.drop_index("ix_recommendations_user_score", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_table("resume_embeddings")
    op.drop_table("job_embeddings")
    # leave stub tables in place — teammates may own them by the time we
    # downgrade
