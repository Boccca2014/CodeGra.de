"""Add new check constrains for login links

Revision ID: d9b3486b2e52
Revises: a74d0e227051
Create Date: 2020-07-31 16:22:33.017996

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd9b3486b2e52'
down_revision = 'a74d0e227051'
branch_labels = None
depends_on = None

CONSTRAINTS = [
    (
        (
            'available_at IS NULL OR deadline IS NULL OR available_at <'
            ' deadline'
        ),
        'available_at_before_deadline',
    ),
    (
        'send_login_links_token IS NULL OR available_at IS NOT NULL',
        'send_login_links_only_valid_with_available_at',
    )
]


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    for check, name in CONSTRAINTS:
        op.create_check_constraint(name, 'Assignment', check)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    for _, name in CONSTRAINTS:
        op.drop_constraint(name)
    # ### end Alembic commands ###
