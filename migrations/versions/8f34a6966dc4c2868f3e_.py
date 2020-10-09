"""""Creating "can_manage_site_settings" permission.

Revision ID: 8f34a6966dc4c2868f3e
Revises: a7dff76ad19f
Create Date: 2020-10-09 19:49:47.696729

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '8f34a6966dc4c2868f3e'
down_revision = 'a7dff76ad19f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    exists = conn.execute(text("""SELECT id from "Permission" where name = :perm_name"""), perm_name='can_manage_site_settings').fetchall()
    if exists:
        return

    new_perm_id = conn.execute(text("""
    INSERT INTO "Permission" (name, default_value, course_permission)
    SELECT :perm_name, :default_value, :course_permission RETURNING id
    """), perm_name='can_manage_site_settings', default_value=False, course_permission=False).scalar()



def downgrade():
    pass
