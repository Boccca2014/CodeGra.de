import uuid

from psef import models as m
from psef.models.user import User
from psef.permissions import CoursePermission, GlobalPermission


def test_user_has_permission():
    user_without_role = User('', '', '', '', active=True)
    user_not_active = User('', '', '', '', active=False)

    for user in [user_without_role, user_not_active]:
        assert not user.has_permission(GlobalPermission.can_edit_own_password)
        assert not user.has_permission(
            CoursePermission.can_submit_own_work, course_id=1
        )


def test_get_all_permissions(describe):
    with describe('Users without role should have no permissions'):
        user_without_role = User('', '', '', '', active=True)

        perms = user_without_role.get_all_permissions()

        assert set(list(GlobalPermission)) == set(perms.keys())
        assert not any(perms.values())

        cperms = user_without_role.get_all_permissions(
            course=m.Course.query.get(1)
        )
        assert not any(cperms.values())


def test_user_is_enrolled():
    user = User('', '', '', '', active=True)
    assert not user.virtual
    course = m.Course(id=5)
    crole = m.CourseRole(name='Hello', course=course, hidden=False)

    assert not user.is_enrolled(course)
    assert not user.is_enrolled(5)

    user.enroll_in_course(course_role=crole)

    assert course.id in user.courses
    assert user.is_enrolled(course)
    assert user.is_enrolled(5)
    assert not user.is_enrolled(6)

    user.virtual = True
    # Virtual users are never enrolled
    assert not user.is_enrolled(course)
    assert not user.is_enrolled(5)
    # But the connection still exists
    assert course.id in user.courses


def test_is_global_admin_user(app, monkeypatch):
    random_part = str(uuid.uuid4())
    username = f'username_{random_part}_1'
    user = User('', '', '', username, active=True)

    assert not user.is_global_admin_user

    monkeypatch.setitem(app.config, 'ADMIN_USER', username)

    # User is not in db so still False
    assert not user.is_global_admin_user

    user.id = 5
    assert user.is_global_admin_user

    monkeypatch.setitem(app.config, 'ADMIN_USER', f'username_{random_part}')
    # Should not match on some sort of prefix
    assert not user.is_global_admin_user

    monkeypatch.setitem(app.config, 'ADMIN_USER', '')
    user._username = ''
    # Should never be true for empty usernames
    assert not user.is_global_admin_user

    monkeypatch.setitem(app.config, 'ADMIN_USER', '1')
    user._username = '1'
    assert user.is_global_admin_user
