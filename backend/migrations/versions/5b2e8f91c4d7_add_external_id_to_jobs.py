"""add external_id to jobs

Revision ID: 5b2e8f91c4d7
Revises: 1845a468133d
Create Date: 2026-04-23 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b2e8f91c4d7'
down_revision = '1845a468133d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('external_id', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint(
            'uq_jobs_company_external_id',
            ['company', 'external_id'],
        )


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_constraint('uq_jobs_company_external_id', type_='unique')
        batch_op.drop_column('external_id')
