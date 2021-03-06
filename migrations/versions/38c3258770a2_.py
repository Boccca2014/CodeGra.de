"""Add broker_setting table

Revision ID: 38c3258770a2
Revises: 29185910dfa7
Create Date: 2020-10-14 15:52:41.849379

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '38c3258770a2'
down_revision = '29185910dfa7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'broker_setting',
        sa.Column(
            'id', sqlalchemy_utils.types.uuid.UUIDType(), nullable=False
        ),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('url', sa.Unicode(), nullable=False),
        sa.Column('key', sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_broker_setting_url'), 'broker_setting', ['url'], unique=True
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_broker_setting_url'), table_name='broker_setting')
    op.drop_table('broker_setting')
    # ### end Alembic commands ###
