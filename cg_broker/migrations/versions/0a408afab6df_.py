"""Add timezone to datetime columns

Revision ID: 0a408afab6df
Revises: d5a088f2feaa
Create Date: 2020-02-02 01:10:57.255870

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0a408afab6df'
down_revision = 'd5a088f2feaa'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        'job',
        'created_at',
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.TIMESTAMP(timezone=True),
        existing_nullable=False
    )
    op.alter_column(
        'job',
        'updated_at',
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.TIMESTAMP(timezone=True),
        existing_nullable=False
    )
    op.alter_column(
        'runner',
        'created_at',
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.TIMESTAMP(timezone=True),
        existing_nullable=False
    )
    op.alter_column(
        'runner',
        'started_at',
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.TIMESTAMP(timezone=True),
        existing_nullable=True
    )
    op.alter_column(
        'runner',
        'updated_at',
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.TIMESTAMP(timezone=True),
        existing_nullable=False
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        'runner',
        'updated_at',
        existing_type=sa.TIMESTAMP(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False
    )
    op.alter_column(
        'runner',
        'started_at',
        existing_type=sa.TIMESTAMP(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True
    )
    op.alter_column(
        'runner',
        'created_at',
        existing_type=sa.TIMESTAMP(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False
    )
    op.alter_column(
        'job',
        'updated_at',
        existing_type=sa.TIMESTAMP(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False
    )
    op.alter_column(
        'job',
        'created_at',
        existing_type=sa.TIMESTAMP(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False
    )
    # ### end Alembic commands ###
