"""Add old_connection flag to 'course_lti_provider' table

Revision ID: effc355fddff
Revises: 764550f52c2f
Create Date: 2020-06-16 14:58:37.560994

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlalchemy_utils

# revision identifiers, used by Alembic.
revision = 'effc355fddff'
down_revision = '764550f52c2f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('course_lti_provider', sa.Column('old_connection', sa.Boolean(), server_default='false', nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('course_lti_provider', 'old_connection')
    # ### end Alembic commands ###
