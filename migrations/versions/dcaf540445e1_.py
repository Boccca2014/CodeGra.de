"""Add notifications table

Revision ID: dcaf540445e1
Revises: c76740c2b03c639a7e25
Create Date: 2020-03-25 16:06:09.628901

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'dcaf540445e1'
down_revision = 'c76740c2b03c639a7e25'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('receiver_id', sa.Integer(), nullable=False),
        sa.Column('comment_reply_id', sa.Integer(), nullable=False),
        sa.Column('email_sent_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ['comment_reply_id'],
            ['comment_reply.id'],
        ),
        sa.Column(
            'reasons',
            postgresql.ARRAY(sa.Unicode(), as_tuple=True, dimensions=1),
            nullable=False
        ),
        sa.ForeignKeyConstraint(['receiver_id'], ['User.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            'array_length(reasons, 1) > 0',
            name='notifications_addleastonereason'
        ),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('notification')
    # ### end Alembic commands ###