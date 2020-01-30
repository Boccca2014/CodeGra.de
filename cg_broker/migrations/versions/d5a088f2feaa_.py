"""Add public_id and pass column to runner

Revision ID: d5a088f2feaa
Revises: b5db0fe05ae7
Create Date: 2020-01-15 16:58:00.158366

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd5a088f2feaa'
down_revision = 'b5db0fe05ae7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'runner',
        sa.Column(
            'public_id',
            sqlalchemy_utils.types.uuid.UUIDType(),
            server_default=sa.func.uuid_generate_v4(),
            nullable=False
        )
    )
    op.add_column(
        'runner',
        sa.Column(
            'pass',
            sa.Unicode(),
            server_default=sa.func.cast(
                sa.func.uuid_generate_v4(), sa.Unicode
            ),
            nullable=False
        )
    )
    op.create_unique_constraint('unique_public_id', 'runner', ['public_id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('unique_public_id', 'runner', type_='unique')
    op.drop_column('runner', 'public_id')
    op.drop_column('runner', 'pass')
    # ### end Alembic commands ###
