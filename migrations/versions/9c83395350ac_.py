"""Add delete column for work

Revision ID: 9c83395350ac
Revises: 426a7ac23ea6
Create Date: 2019-10-03 13:25:21.641827

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

# revision identifiers, used by Alembic.
revision = '9c83395350ac'
down_revision = '426a7ac23ea6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('Work', sa.Column('deleted', sa.Boolean(), nullable=False, server_default='false'))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('Work', 'deleted')
    # ### end Alembic commands ###
