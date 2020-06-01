"""Add index on virtual column for user

Revision ID: bec486c454ff
Revises: aa2d0a3417a0
Create Date: 2018-09-18 01:38:59.177933

SPDX-License-Identifier: AGPL-3.0-only
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bec486c454ff'
down_revision = 'aa2d0a3417a0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_User_virtual'), 'User', ['virtual'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_User_virtual'), table_name='User')
    # ### end Alembic commands ###