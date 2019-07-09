"""Add creating state to runner state

Revision ID: 4188b4e91a76
Revises: 977953e3aefd
Create Date: 2019-06-13 15:23:55.828107

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '4188b4e91a76'
down_revision = '977953e3aefd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.sync_enum_values(
        'public', 'runnerstate',
        ['cleaned', 'cleaning', 'not_running', 'running'],
        ['cleaned', 'cleaning', 'creating', 'not_running', 'running']
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.sync_enum_values(
        'public', 'runnerstate',
        ['cleaned', 'cleaning', 'creating', 'not_running', 'running'],
        ['cleaned', 'cleaning', 'not_running', 'running']
    )
    # ### end Alembic commands ###
