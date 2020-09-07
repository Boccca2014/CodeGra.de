import pytest

import psef
import helpers
import psef.models as m
from psef.permissions import CoursePermission as CPerm


@pytest.mark.parametrize(
    'perm', [CPerm.can_delete_assignments, CPerm.can_submit_own_work]
)
def test_has_permission_filter(
    describe, test_client, session, admin_user, logged_in, perm
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.to_db_object(
            helpers.create_course(test_client), m.Course
        )

        rol1 = m.CourseRole('rol1', course, hidden=False)
        rol2 = m.CourseRole('rol2', course, hidden=False)
        session.add(rol1)
        session.add(rol2)
        session.commit()

        user1 = helpers.create_user_with_role(session, 'rol1', course)
        user2 = helpers.create_user_with_role(session, 'rol2', course)

        rol1.set_permission(perm, True)
        rol2.set_permission(perm, False)
        session.commit()

    with describe('Role is include if (and only if) the permission is true'):
        roles = m.CourseRole.get_roles_with_permission(perm).all()
        assert rol1 in roles
        assert rol2 not in roles

    with describe('Can be filtered further'):
        roles = m.CourseRole.get_roles_with_permission(perm).filter(
            m.CourseRole.course == course
        ).all()
        assert all(r.course_id == course.id for r in roles)
        assert 'rol1' in [r.name for r in roles]
        assert 'Teacher' in [r.name for r in roles]

    with describe('User show up if permission is true not otherwise'):

        query = course.get_all_users_in_course(
            include_test_students=False,
            with_permission=perm,
        )
        assert sorted([user1.id,
                       admin_user.id]) == sorted(user.id for user, _ in query)
