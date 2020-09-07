"""""Creating "can_see_archived_courses" permission.

Revision ID: e400b5d42ad68edf0d32
Revises: abd0b88b46e3
Create Date: 2020-09-04 12:19:50.002589

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'e400b5d42ad68edf0d32'
down_revision = 'abd0b88b46e3'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    exists = conn.execute(text("""SELECT id from "Permission" where name = :perm_name"""), perm_name='can_see_archived_courses').fetchall()
    if exists:
        return

    new_perm_id = conn.execute(text("""
    INSERT INTO "Permission" (name, default_value, course_permission)
    SELECT :perm_name, :default_value, :course_permission RETURNING id
    """), perm_name='can_see_archived_courses', default_value=False, course_permission=True).scalar()

    old_perm_id = conn.execute(text("""
    SELECT id FROM "Permission" WHERE name = :perm_name LIMIT 1
    """), perm_name='can_grade_work').scalar()
    
    conn.execute(text("""
    INSERT INTO "course_roles-permissions" (permission_id, course_role_id)
            SELECT :new_perm_id, course_role_id FROM "course_roles-permissions"
                WHERE permission_id = :old_perm_id
    """), old_perm_id=old_perm_id, new_perm_id=new_perm_id)

def downgrade():
    pass
