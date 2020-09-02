"""""Creating "can_receive_login_links" permission.

Revision ID: 860bf3135e0a23177739
Revises: e7015056e7e2
Create Date: 2020-08-12 10:02:52.724603

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '860bf3135e0a23177739'
down_revision = 'e7015056e7e2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    exists = conn.execute(
        text("""SELECT id from "Permission" where name = :perm_name"""),
        perm_name='can_receive_login_links'
    ).fetchall()
    if exists:
        return

    new_perm_id = conn.execute(
        text(
            """
    INSERT INTO "Permission" (name, default_value, course_permission)
    SELECT :perm_name, :default_value, :course_permission RETURNING id
    """
        ),
        perm_name='can_receive_login_links',
        default_value=True,
        course_permission=True
    ).scalar()

    old_perm_id = conn.execute(
        text(
            """
    SELECT id FROM "Permission" WHERE name = :perm_name LIMIT 1
    """
        ),
        perm_name='can_grade_work'
    ).scalar()

    # By creating a link the value will be reverted, so these users will not
    # have this new permission.
    conn.execute(
        text(
            """
    INSERT INTO "course_roles-permissions" (permission_id, course_role_id)
            SELECT :new_perm_id, course_role_id FROM "course_roles-permissions"
                WHERE permission_id = :old_perm_id
    """
        ),
        old_perm_id=old_perm_id,
        new_perm_id=new_perm_id
    )


def downgrade():
    pass
