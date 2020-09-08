"""""Creating "can_edit_course_info" permission.

Revision ID: 3a74e01ebcbf9099d761
Revises: c5c579cd5488e219d5c7
Create Date: 2020-09-05 18:11:06.708683

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '3a74e01ebcbf9099d761'
down_revision = 'c5c579cd5488e219d5c7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    exists = conn.execute(text("""SELECT id from "Permission" where name = :perm_name"""), perm_name='can_edit_course_info').fetchall()
    if exists:
        return

    new_perm_id = conn.execute(text("""
    INSERT INTO "Permission" (name, default_value, course_permission)
    SELECT :perm_name, :default_value, :course_permission RETURNING id
    """), perm_name='can_edit_course_info', default_value=False, course_permission=True).scalar()

    old_perm_id = conn.execute(text("""
    SELECT id FROM "Permission" WHERE name = :perm_name LIMIT 1
    """), perm_name='can_edit_assignment_info').scalar()
    
    conn.execute(text("""
    INSERT INTO "course_roles-permissions" (permission_id, course_role_id)
            SELECT :new_perm_id, course_role_id FROM "course_roles-permissions"
                WHERE permission_id = :old_perm_id
    """), old_perm_id=old_perm_id, new_perm_id=new_perm_id)

def downgrade():
    pass
