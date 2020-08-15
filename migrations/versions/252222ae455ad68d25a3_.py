"""Create SSO User role

Revision ID: 252222ae455ad68d25a3
Revises: b987d88cc27d
Create Date: 2020-08-03 11:25:34.772754

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

from psef.permissions import GlobalPermission as GPerm

# revision identifiers, used by Alembic.
revision = '252222ae455ad68d25a3'
down_revision = 'b987d88cc27d'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    has_perms = ["can_use_snippets"]

    exists = conn.execute(
        text("""SELECT id from "Role" where name = :name"""), name='SSO User'
    ).fetchall()
    if exists:
        return

    new_role_id = conn.execute(
        text(
            """
    INSERT INTO "Role" (name)
    VALUES (:name) RETURNING id
    """
        ),
        name='SSO User'
    ).scalar()

    for perm in GPerm:
        has = perm.name in has_perms
        if has != perm.value.default_value:
            conn.execute(
                text(
                    """INSERT INTO "roles-permissions" (role_id, permission_id)
                    VALUES (
                    :new_role_id,
                    (SELECT id from "Permission" where name = :perm_name)
                    )"""
                ),
                new_role_id=new_role_id,
                perm_name=perm.name,
            )


def downgrade():
    pass
