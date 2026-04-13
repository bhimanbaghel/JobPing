"""Users.name nullable (add column if missing).

Revision ID: f3a9c2b101ef
Revises: 72141e8076c0
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa


revision = 'f3a9c2b101ef'
down_revision = '72141e8076c0'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = insp.get_columns('users')
    col_names = [c['name'] for c in columns]

    if 'name' not in col_names:
        with op.batch_alter_table('users') as batch_op:
            batch_op.add_column(sa.Column('name', sa.String(length=100), nullable=True))
        return

    col = next(c for c in columns if c['name'] == 'name')
    if col['nullable']:
        return

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'name',
            existing_type=sa.String(length=100),
            nullable=True,
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'name' not in [c['name'] for c in insp.get_columns('users')]:
        return
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'name',
            existing_type=sa.String(length=100),
            nullable=False,
        )
