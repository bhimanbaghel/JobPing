"""add jobs table

Revision ID: 1845a468133d
Revises: f3a9c2b101ef
Create Date: 2026-04-23 10:16:07.256080

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1845a468133d'
down_revision = 'f3a9c2b101ef'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=255), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('link', sa.String(length=2048), nullable=True),
        sa.Column('city', sa.String(length=120), nullable=True),
        sa.Column('state', sa.String(length=120), nullable=True),
        sa.Column('country', sa.String(length=120), nullable=True),
        sa.Column('salary_usd', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('posted_at', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_jobs_company'), ['company'], unique=False)
        batch_op.create_index(batch_op.f('ix_jobs_role'), ['role'], unique=False)


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_jobs_role'))
        batch_op.drop_index(batch_op.f('ix_jobs_company'))

    op.drop_table('jobs')
