"""Add allow_register column

Revision ID: e8fd2984d6b9
Revises: 336e02d2d9117957cfc7
Create Date: 2020-08-03 16:29:23.363577

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e8fd2984d6b9'
down_revision = '336e02d2d9117957cfc7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'course_registration_link',
        sa.Column(
            'allow_register',
            sa.Boolean(),
            server_default='true',
            nullable=False
        )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('course_registration_link', 'allow_register')
    # ### end Alembic commands ###
