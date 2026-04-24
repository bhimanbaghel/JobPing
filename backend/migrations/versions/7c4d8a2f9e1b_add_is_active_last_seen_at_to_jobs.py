"""add is_active and last_seen_at to jobs

Revision ID: 7c4d8a2f9e1b
Revises: 5b2e8f91c4d7
Create Date: 2026-04-23 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c4d8a2f9e1b'
down_revision = '5b2e8f91c4d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'is_active',
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                'last_seen_at',
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('last_seen_at')
        batch_op.drop_column('is_active')
