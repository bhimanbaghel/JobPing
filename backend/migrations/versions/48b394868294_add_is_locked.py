"""add is_locked

Revision ID: 48b394868294
Revises: 887b493ef9b2
Create Date: 2026-04-27 23:58:29.199021

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '48b394868294'
down_revision = '887b493ef9b2'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite doesn't generate names like `resumes_user_id_key` for inline
    # UniqueConstraint("user_id"); only Postgres does. Skip those drops on
    # SQLite — batch_alter_table's table-recreation already drops the inline
    # constraint when the new schema (with a unique index) replaces it.
    is_postgres = op.get_bind().dialect.name == "postgresql"

    with op.batch_alter_table('recommendations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recommendations_user_score'))
        batch_op.create_index(batch_op.f('ix_recommendations_similarity_score'), ['similarity_score'], unique=False)

    with op.batch_alter_table('resumes', schema=None) as batch_op:
        if is_postgres:
            batch_op.drop_constraint(batch_op.f('resumes_user_id_key'), type_='unique')
        batch_op.drop_index(batch_op.f('ix_resumes_user_id'))
        batch_op.create_index(batch_op.f('ix_resumes_user_id'), ['user_id'], unique=True)

    with op.batch_alter_table('user_preferences', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_locked', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        if is_postgres:
            batch_op.drop_constraint(batch_op.f('user_preferences_user_id_key'), type_='unique')
        batch_op.drop_index(batch_op.f('ix_user_preferences_user_id'))
        batch_op.create_index(batch_op.f('ix_user_preferences_user_id'), ['user_id'], unique=True)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_users_email', ['email'])


def downgrade():
    is_postgres = op.get_bind().dialect.name == "postgresql"

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_email', type_='unique')

    with op.batch_alter_table('user_preferences', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_preferences_user_id'))
        batch_op.create_index(batch_op.f('ix_user_preferences_user_id'), ['user_id'], unique=False)
        if is_postgres:
            batch_op.create_unique_constraint(batch_op.f('user_preferences_user_id_key'), ['user_id'], postgresql_nulls_not_distinct=False)
        batch_op.drop_column('is_locked')

    with op.batch_alter_table('resumes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resumes_user_id'))
        batch_op.create_index(batch_op.f('ix_resumes_user_id'), ['user_id'], unique=False)
        if is_postgres:
            batch_op.create_unique_constraint(batch_op.f('resumes_user_id_key'), ['user_id'], postgresql_nulls_not_distinct=False)

    with op.batch_alter_table('recommendations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recommendations_similarity_score'))
        batch_op.create_index(batch_op.f('ix_recommendations_user_score'), ['user_id', 'similarity_score'], unique=False)
