"""Add TaskResult table

Revision ID: e263d46b6c53
Revises: f6c2c9286d8644bbd411
Create Date: 2020-04-12 14:40:17.993972

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e263d46b6c53'
down_revision = 'f6c2c9286d8644bbd411'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'task_result',
        sa.Column(
            'id', sqlalchemy_utils.types.uuid.UUIDType(), nullable=False
        ),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            'state',
            sa.Enum(
                'not_started',
                'started',
                'finished',
                'failed',
                'crashed',
                name='taskresultstate'
            ),
            nullable=False
        ),
        sa.Column(
            'result',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True
        ), sa.Column('author_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['User.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('task_result')
    # ### end Alembic commands ###