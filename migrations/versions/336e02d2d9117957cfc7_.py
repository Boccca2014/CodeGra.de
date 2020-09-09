"""""Creating "can_manage_sso_providers" permission.

Revision ID: 336e02d2d9117957cfc7
Revises: 252222ae455ad68d25a3
Create Date: 2020-08-03 13:59:12.930262

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '336e02d2d9117957cfc7'
down_revision = '252222ae455ad68d25a3'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    exists = conn.execute(text("""SELECT id from "Permission" where name = :perm_name"""), perm_name='can_manage_sso_providers').fetchall()
    if exists:
        return

    new_perm_id = conn.execute(text("""
    INSERT INTO "Permission" (name, default_value, course_permission)
    SELECT :perm_name, :default_value, :course_permission RETURNING id
    """), perm_name='can_manage_sso_providers', default_value=False, course_permission=False).scalar()



def downgrade():
    pass
