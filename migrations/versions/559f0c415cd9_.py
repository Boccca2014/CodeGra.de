"""empty message

Revision ID: 559f0c415cd9
Revises: 46964ce1a243f3453181
Create Date: 2019-05-07 13:52:16.484456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '559f0c415cd9'
down_revision = '46964ce1a243f3453181'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('AutoTestResult', sa.Column('setup_stderr', sa.Unicode(), nullable=True))
    op.add_column('AutoTestResult', sa.Column('setup_stdout', sa.Unicode(), nullable=True))
    op.add_column('AutoTestResult', sa.Column('state', sa.Enum('not_started', 'running', 'passed', 'failed', name='autoteststepresultstate'), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('AutoTestResult', 'state')
    op.drop_column('AutoTestResult', 'setup_stdout')
    op.drop_column('AutoTestResult', 'setup_stderr')
    # ### end Alembic commands ###
