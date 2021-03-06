"""Add transip runner type

Revision ID: 329b236f5cb0
Revises: 56cf69b5d451
Create Date: 2019-05-23 16:51:42.345873

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '329b236f5cb0'
down_revision = '56cf69b5d451'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.sync_enum_values('public', 'autotestrunnertype', ['simple_runner'], ['simple_runner', 'transip_runner'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.sync_enum_values('public', 'autotestrunnertype', ['simple_runner', 'transip_runner'], ['simple_runner'])
    # ### end Alembic commands ###
