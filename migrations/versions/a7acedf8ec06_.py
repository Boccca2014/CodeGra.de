"""Add comment_type column

Revision ID: a7acedf8ec06
Revises: 851948d545a1
Create Date: 2020-06-24 11:43:17.116461

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a7acedf8ec06'
down_revision = '851948d545a1'
branch_labels = None
depends_on = None

ENUM_NAME = 'commentreplycommenttype'

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    bind = op.get_bind()
    has_type = bind.execute((
        "select exists (select 1 from pg_type "
        "where typname='{enum_name}')"
    ).format(enum_name=ENUM_NAME)).scalar()
    if not has_type:
        op.execute(
            "CREATE TYPE {enum_name} AS ENUM ()".format(enum_name=ENUM_NAME)
        )

    ENUM_OPTS = [
        'normal',
        'peer_feedback',
    ]

    op.sync_enum_values(
        'public',
        ENUM_NAME,
        [],
        ENUM_OPTS,
    )

    op.add_column(
        'comment_reply',
        sa.Column(
            'comment_type',
            sa.Enum(
                *ENUM_OPTS,
                name=ENUM_NAME,
            ),
            nullable=False,
            server_default="normal"
        )
    )
    op.add_column(
        'comment_reply',
        sa.Column(
            'is_approved', sa.Boolean(), nullable=False, server_default='true'
        )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comment_reply', 'comment_type')
    op.drop_column('comment_reply', 'is_approved')
    bind = op.get_bind()
    bind.execute('DROP TYPE {enum_name}'.format(enum_name=ENUM_NAME))
    # ### end Alembic commands ###
