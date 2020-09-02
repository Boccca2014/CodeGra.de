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

        role = m.CourseRole('rol1', course, hidden=False)
        session.add(role)

        session.flush()

    with describe('Shows up if permission is true'):
        role.set_permission(perm, True)
        session.flush()

        assert role in m.CourseRole.query.filter(
            m.CourseRole.course == course,
            m.CourseRole.get_has_permission_filter(perm),
        ).all()

    with describe('Does not show up if permission is true'):
        role.set_permission(perm, False)
        session.flush()

        assert role not in m.CourseRole.query.filter(
            m.CourseRole.course == course,
            m.CourseRole.get_has_permission_filter(perm),
        ).all()
