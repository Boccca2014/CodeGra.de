"""Add started state to runner state

Revision ID: 16d3300cd15b
Revises: 97027e00242a
Create Date: 2019-09-11 12:41:47.299900

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '16d3300cd15b'
down_revision = '97027e00242a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.sync_enum_values(
        'public', 'runnerstate',
        ['cleaned', 'cleaning', 'creating', 'not_running', 'running'], [
            'cleaned', 'cleaning', 'creating', 'not_running', 'running',
            'started'
        ]
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.sync_enum_values(
        'public', 'runnerstate', [
            'cleaned', 'cleaning', 'creating', 'not_running', 'running',
            'started'
        ], ['cleaned', 'cleaning', 'creating', 'not_running', 'running']
    )
    # ### end Alembic commands ###
