"""Add job metadata column

Revision ID: 97027e00242a
Revises: f8b56bf0ce3b
Create Date: 2019-09-05 15:07:28.958271

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

# revision identifiers, used by Alembic.
revision = '97027e00242a'
down_revision = 'f8b56bf0ce3b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('job', sa.Column('job_metadata', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('job', 'job_metadata')
    # ### end Alembic commands ###
