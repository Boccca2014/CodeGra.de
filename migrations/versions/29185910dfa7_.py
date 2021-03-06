"""Add enum values for new ui_preferences

Revision ID: 29185910dfa7
Revises: 7fcd8994afe9
Create Date: 2020-10-12 20:01:40.559996

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '29185910dfa7'
down_revision = '7fcd8994afe9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.sync_enum_values(
        'public', 'ui_preference_name', ['rubric_editor_v2'],
        ['no_msg_for_mosaic_1', 'no_msg_for_mosaic_2', 'rubric_editor_v2']
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.sync_enum_values(
        'public', 'ui_preference_name',
        ['no_msg_for_mosaic_1', 'no_msg_for_mosaic_2', 'rubric_editor_v2'],
        ['rubric_editor_v2']
    )
    # ### end Alembic commands ###
