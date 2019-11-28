"""Make sure webhooks are unique

Revision ID: c9e2479be1b8
Revises: b5dca6f8efba
Create Date: 2019-11-05 15:47:31.867501

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9e2479be1b8'
down_revision = 'b5dca6f8efba'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint('_webhook_assig_user_type_uc', 'webhook_base', ['assignment_id', 'user_id', 'webhook_type'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('_webhook_assig_user_type_uc', 'webhook_base', type_='unique')
    # ### end Alembic commands ###
