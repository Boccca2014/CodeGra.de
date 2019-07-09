"""Remove AutoTestRunner type column

Revision ID: 92d8eea8c48e
Revises: de751ecfe976
Create Date: 2019-06-11 15:43:09.316128

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '92d8eea8c48e'
down_revision = 'de751ecfe976'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('AutoTestRunner', 'type')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('AutoTestRunner', sa.Column('type', postgresql.ENUM('simple_runner', 'transip_runner', name='autotestrunnertype'), autoincrement=False, nullable=False))
    # ### end Alembic commands ###
