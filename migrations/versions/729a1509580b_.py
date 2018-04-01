"""Add 'can_submit_others_work' permission

Revision ID: 729a1509580b
Revises: 9924e6dccf52
Create Date: 2018-03-30 23:45:51.781723

"""
import os
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '729a1509580b'
down_revision = '9924e6dccf52'
branch_labels = None
depends_on = None

new_perm = 'can_submit_others_work'


def get_first(l):
    return list(map(lambda el: el[0], l))


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # ### end Alembic commands ###
    conn = op.get_bind()

    old_id_res = conn.execute(
        text(
            """
        SELECT id FROM "Permission" WHERE name='can_edit_others_work'
    """
        )
    )
    if old_id_res is None:
        return

    old_id = old_id_res.first()
    if old_id is None:
        return

    old_id = old_id[0]

    role_ids = get_first(
        conn.execute(
            text(
                """
            SELECT course_role_id FROM "course_roles-permissions"
            WHERE permission_id=:perm_id
        """
            ),
            perm_id=old_id,
        ).fetchall()
    )

    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/../../seed_data/permissions.json',
        'r'
    ) as perms:
        perms = json.load(perms)

        perm = perms[new_perm]
        conn.execute(
            text(
                """
                INSERT INTO "Permission" (name, default_value, course_permission)
                VALUES (:perm_name, :default_value, :course_permission)
            """
            ),
            perm_name=new_perm,
            default_value=perm['default_value'],
            course_permission=perm['course_permission'],
        )

        new_id = conn.execute(
            text(
                """
                SELECT id FROM "Permission" WHERE name=:perm_name
            """
            ),
            perm_name=new_perm,
        ).first()[0]

        for role_id in role_ids:
            conn.execute(
                text(
                    """
                    INSERT INTO "course_roles-permissions"
                    (course_role_id, permission_id)
                    VALUES (:role_id, :perm_id)
                """
                ),
                role_id=role_id,
                perm_id=new_id,
            )

    conn.execute(
        text("""DELETE FROM "Permission" WHERE id=:perm_id"""),
        perm_id=old_id,
    )


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # ### end Alembic commands ###
    conn = op.get_bind()

    new_ids = get_first(
        conn.execute(
            text("""SELECT id FROM "Permission" WHERE name=:name"""),
            name=new_perm,
        ).fetchall()
    )

    if len(new_ids) == 0:
        return

    role_ids = get_first(
        conn.execute(
            text(
                """
            SELECT DISTINCT course_role_id FROM "course_roles-permissions"
            WHERE permission_id=ANY(:ids)
        """
            ),
            ids=new_ids,
        ).fetchall()
    )

    conn.execute(
        text(
            """
        INSERT INTO "Permission" (name, default_value, course_permission)
        VALUES ('can_edit_others_work', false, true)
    """
        )
    )
    old_id = conn.execute(
        text(
            """
        SELECT id FROM "Permission" WHERE name='can_edit_others_work'
    """
        )
    ).first()[0]

    for role_id in role_ids:
        conn.execute(
            text(
                """
                INSERT INTO "course_roles-permissions"
                (course_role_id, permission_id)
                VALUES (:role_id, :perm_id)
            """
            ),
            role_id=role_id,
            perm_id=old_id,
        )

    conn.execute(
        text("""
        DELETE FROM "Permission" WHERE id=ANY(:ids)
    """),
        ids=new_ids
    )
