# SPDX-License-Identifier: AGPL-3.0-only
import os
import re
import uuid

import pytest
from werkzeug.local import LocalProxy

import psef
import psef.models as m
from helpers import (
    create_group, create_marker, create_group_set, create_submission,
    create_user_with_perms
)
from psef.permissions import CoursePermission as CPerm

# http_err = pytest.mark.http_err
perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)


@pytest.mark.parametrize(
    'user_with_perms', [
        [CPerm.can_edit_group_set],
        perm_error([]),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'min_size,max_size', [
        [1, 4],
        [100, 101],
        data_error((-1, 1)),
        data_error((0, 101)),
        data_error((100, 99)),
        data_error((5, 'err')),
        data_error((None, 5)),
    ]
)
def test_create_group_set(
    test_client, logged_in, user_with_perms, min_size, max_size, course,
    request, error_template, teacher_user
):
    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    has_err = bool(perm_err or data_err)

    if data_err:
        status = 400
    elif perm_err:
        status = 403
    else:
        status = 200

    with logged_in(user_with_perms):
        res = test_client.req(
            'put',
            f'/api/v1/courses/{course.id}/group_sets/',
            data={
                'minimum_size': min_size,
                'maximum_size': max_size,
            },
            status_code=status,
            result=error_template if has_err else {
                'id': int,
                'maximum_size': max_size,
                'minimum_size': min_size,
                'assignment_ids': [],
            }
        )

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/courses/{course.id}/group_sets/',
            200,
            result=[] if has_err else [res]
        )


@pytest.mark.parametrize(
    'user_with_perms', [
        [CPerm.can_create_groups, CPerm.can_edit_own_groups],
        [CPerm.can_create_groups, CPerm.can_edit_others_groups],
        perm_error([]),
    ],
    indirect=True
)
@pytest.mark.parametrize('name', ['New NAme', None, data_error(5)])
@pytest.mark.parametrize('with_user', [True, False])
def test_create_simple_group(
    test_client, logged_in, user_with_perms, prog_course, request,
    error_template, teacher_user, name, with_user
):
    with logged_in(teacher_user):
        group_set = create_group_set(test_client, prog_course.id, 2, 4)

    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    has_err = bool(perm_err or data_err)

    if perm_err:
        status = 403
    elif data_err:
        status = 400
    else:
        status = 200

    with logged_in(user_with_perms) as user:
        data = {'member_ids': []}

        if name is not None:
            data['name'] = name
        if with_user:
            data['member_ids'].append(user.id)

        group = test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data=data,
            status_code=status,
            result=error_template if has_err else {
                'id': int,
                'members': list,
                'name': str,
                'created_at': str,
                'group_set_id': group_set['id'],
                'virtual_user': {
                    'id': int,
                    'name': re.compile(r'^Virtual - GROUP_'),
                    'username': re.compile(r'^VIRTUAL_USER_'),
                    '__allow_extra__': {'group'},
                },
            }
        )
        if not has_err:
            if with_user:
                assert [memb['id'] for memb in group['members']] == [user.id]
            else:
                assert group['members'] == []

            if name is not None:
                assert group['name'] == name
            else:
                assert len(group['name'].split(' ')) >= 3

            test_client.req(
                'get', f'/api/v1/groups/{group["id"]}', 200, result=group
            )


@pytest.mark.parametrize(
    'user_with_perms', [
        perm_error([CPerm.can_create_groups, CPerm.can_edit_own_groups]),
        [CPerm.can_create_groups, CPerm.can_edit_others_groups],
    ],
    indirect=True
)
@pytest.mark.parametrize('course_name', ['Programmeertalen'], indirect=True)
def test_create_extended_group(
    test_client, logged_in, user_with_perms, prog_course, request,
    error_template, teacher_user, session, bs_course
):
    with logged_in(teacher_user):
        group_set = create_group_set(test_client, prog_course.id, 2, 4)

    perm_err = request.node.get_closest_marker('perm_error')
    has_err = bool(perm_err)

    if perm_err:
        status = 403
    else:
        status = 200

    with logged_in(user_with_perms) as user:
        user1 = create_user_with_perms(session, [], prog_course)
        user2 = create_user_with_perms(session, [], prog_course)

        group = test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'member_ids': [user1.id]},
            status_code=status,
            result=error_template if has_err else {
                'id': int,
                'name': str,
                'members': list,
                'virtual_user': dict,
                'created_at': str,
                'group_set_id': group_set['id'],
            }
        )

        if not has_err:
            assert len(group['members']) == 1
            assert group['members'][0]['id'] == user1.id

        group = test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'member_ids': [user.id, user2.id]},
            status_code=status,
            result=error_template if has_err else {
                'id': int,
                'name': str,
                'members': list,
                'virtual_user': dict,
                'created_at': str,
                'group_set_id': group_set['id'],
            }
        )
        if not has_err:
            assert len(group['members']) == 2
    if has_err:
        return

    with logged_in(teacher_user) as user:
        user_not_in_course = create_user_with_perms(session, [], bs_course)
        # We should be able to create a normal group
        test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'member_ids': [user.id]},
            status_code=200
        )

        # But not with users that are not in this course
        test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'member_ids': [user_not_in_course.id]},
            status_code=400,
            result=error_template
        )

        # We can't be in a group twice
        test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'member_ids': [user.id]},
            status_code=400
        )

        # We can't add users that don't exist
        test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'member_ids': [10000000]},
            status_code=404
        )

        test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'member_ids': [None]},
            status_code=400,
            result=error_template
        )
        test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'name': ['not', 'a', 'string']},
            status_code=400,
            result=error_template
        )


def test_list_groups(
    test_client, logged_in, bs_course, error_template, teacher_user,
    assignment, session
):
    def make_empty_user():
        return create_user_with_perms(session, [], bs_course)

    user_others_too = create_user_with_perms(
        session,
        [CPerm.can_view_others_groups],
        bs_course,
    )
    user_no_perm = make_empty_user()

    with logged_in(teacher_user):
        group_set = create_group_set(test_client, bs_course.id, 2, 4)
        empty_groups = [
            create_group(test_client, group_set['id'], []) for _ in range(4)
        ]
        other_user_groups = [
            create_group(
                test_client, group_set['id'],
                [make_empty_user().id,
                 make_empty_user().id]
            )
        ]
        user_no_perm_group = [
            create_group(
                test_client, group_set['id'], [
                    make_empty_user().id,
                    make_empty_user().id,
                    user_no_perm.id,
                    make_empty_user().id,
                    make_empty_user().id,
                ]
            )
        ]

    with logged_in(user_no_perm):
        test_client.req(
            'get',
            f'/api/v1/group_sets/{group_set["id"]}/groups/',
            200,
            result=empty_groups + user_no_perm_group
        )

    with logged_in(user_others_too):
        test_client.req(
            'get',
            f'/api/v1/group_sets/{group_set["id"]}/groups/',
            200,
            result=empty_groups + other_user_groups + user_no_perm_group
        )


@pytest.mark.parametrize('course_name', ['Besturingssystemen'], indirect=True)
def test_update_group_set(
    test_client, logged_in, bs_course, prog_course, request, error_template,
    teacher_user, ta_user, assignment, session
):
    with logged_in(teacher_user):
        group_set = test_client.req(
            'put',
            f'/api/v1/courses/{bs_course.id}/group_sets/',
            data={
                'minimum_size': 1,
                'maximum_size': 3,
            },
            status_code=200,
        )

        # Update should be done in place
        group_set = test_client.req(
            'put',
            f'/api/v1/courses/{bs_course.id}/group_sets/',
            data={
                'minimum_size': 3,
                'maximum_size': 10,
                'id': group_set['id'],
            },
            status_code=200,
            result={
                'id': group_set['id'],
                'minimum_size': 3,
                'maximum_size': 10,
                'assignment_ids': [],
            },
        )
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'group_set_id': group_set['id']}
        )
        group_set['assignment_ids'].append(assignment.id)

        test_client.req(
            'get',
            f'/api/v1/courses/{bs_course.id}/group_sets/',
            200,
            result=[group_set]
        )

        # You should not be able to change the course id
        test_client.req(
            'put',
            f'/api/v1/courses/{prog_course.id}/group_sets/',
            data={
                'minimum_size': 3,
                'maximum_size': 10,
                'id': group_set['id'],
            },
            status_code=400,
            result=error_template,
        )

        # The group set now has a group with 3 members
        user = create_user_with_perms(session, [], bs_course)
        group = test_client.req(
            'post',
            f'/api/v1/group_sets/{group_set["id"]}/group',
            data={'member_ids': [teacher_user.id, ta_user.id, user.id]},
            status_code=200
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/groups/{group["id"]}/member_states/',
            200,
            result={
                str(teacher_user.id): True,
                str(ta_user.id): True,
                str(user.id): True,
            }
        )
        # You should not be able to set the max size to lower than 3
        test_client.req(
            'put',
            f'/api/v1/courses/{bs_course.id}/group_sets/',
            data={
                'minimum_size': 1,
                'maximum_size': 2,
                'id': group_set['id'],
            },
            status_code=400,
            result=error_template,
        )

        # You SHOULD be able to set the min size to higher than 3 as there was
        # no submission by any group
        test_client.req(
            'put',
            f'/api/v1/courses/{bs_course.id}/group_sets/',
            data={
                'minimum_size': 4,
                'maximum_size': 10,
                'id': group_set['id'],
            },
            status_code=200,
            result={
                'minimum_size': 4,
                'maximum_size': 10,
                'id': group_set['id'],
                'assignment_ids': [assignment.id],
            }
        )

        # Reset back to minimum size of 3
        test_client.req(
            'put',
            f'/api/v1/courses/{bs_course.id}/group_sets/',
            data={
                'minimum_size': 3,
                'maximum_size': 4,
                'id': group_set['id'],
            },
            status_code=200,
        )

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'group_set_id': group_set['id']}
        )
        submission = create_submission(test_client, assignment.id)
        assert submission['user']['group']
        assert submission['user']['group']['id'] == group['id']

        # Now you should not be able to set the min size to higher than 3 as
        # there IS a submission by a group.
        test_client.req(
            'put',
            f'/api/v1/courses/{bs_course.id}/group_sets/',
            data={
                'minimum_size': 4,
                'maximum_size': 10,
                'id': group_set['id'],
            },
            status_code=400,
            result=error_template,
        )

        # You should also not be able to disconnect the group set for this
        # assignment
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            400,
            data={'group_set_id': None},
            result=error_template,
        )
        new_group_set = create_group_set(test_client, prog_course.id, 2, 4)
        # You should also not be able to change the group set for this
        # assignment
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            400,
            data={'group_set_id': new_group_set['id']},
            result=error_template,
        )


@pytest.mark.parametrize(
    'user_with_perms', [
        [CPerm.can_edit_group_set, CPerm.can_see_assignments],
        perm_error([]),
    ],
    indirect=True
)
def test_delete_group_set(
    test_client, logged_in, teacher_user, user_with_perms, prog_course,
    session, request, error_template
):
    assigs = list(prog_course.assignments)[:2]
    assert len(assigs) == 2
    with logged_in(teacher_user):
        group_set = create_group_set(test_client, prog_course.id, 2, 4)
        for assig in assigs:
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig.id}',
                200,
                data={'group_set_id': group_set['id']}
            )

        groups = [
            create_group(
                test_client, group_set["id"],
                [create_user_with_perms(session, [], prog_course).id]
            ) for _ in range(2)
        ]

    perm_err = request.node.get_closest_marker('perm_error')
    has_err = bool(perm_err)

    if perm_err:
        status = 403
    else:
        status = 400

    with logged_in(user_with_perms):
        test_client.req(
            'delete',
            f'/api/v1/group_sets/{group_set["id"]}',
            status,
            result=error_template
        )

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/group_sets/{group_set["id"]}',
            200,
        )

        for assig in assigs:
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig.id}',
                200,
                data={'group_set_id': None}
            )

    with logged_in(user_with_perms):
        # Still fails because there are groups
        test_client.req(
            'delete',
            f'/api/v1/group_sets/{group_set["id"]}',
            status,
            result=error_template
        )

    with logged_in(teacher_user):
        for group in groups:
            test_client.req(
                'delete',
                f'/api/v1/groups/{group["id"]}',
                204,
            )

    # Should now work as there are no groups anymore
    if perm_err:
        status = 403
    else:
        status = 204

    with logged_in(user_with_perms):
        test_client.req(
            'delete',
            f'/api/v1/group_sets/{group_set["id"]}',
            status,
            result=error_template if has_err else None
        )

    with logged_in(teacher_user):
        if not has_err:
            test_client.req(
                'get',
                f'/api/v1/group_sets/{group_set["id"]}',
                404,
            )


def test_delete_group(
    test_client, logged_in, prog_course, session, teacher_user, error_template,
    app, monkeypatch_celery
):
    user_only_own = create_user_with_perms(
        session, [
            CPerm.can_edit_own_groups, CPerm.can_submit_own_work,
            CPerm.can_see_assignments
        ], prog_course
    )
    user_other_too = create_user_with_perms(
        session, [CPerm.can_edit_others_groups, CPerm.can_see_assignments],
        prog_course
    )

    with logged_in(teacher_user):
        assig_id = [
            a for a in test_client.
            req('get', f'/api/v1/courses/{prog_course.id}/assignments/', 200)
            if a['state'] == 'submitting'
        ][0]['id']

    with logged_in(teacher_user):
        group_set = create_group_set(test_client, prog_course.id, 2, 4)
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            200,
            data={'group_set_id': group_set['id']}
        )

        group_own_id = create_group(
            test_client, group_set["id"], [
                create_user_with_perms(session, [], prog_course).id,
                user_only_own.id,
            ]
        )['id']
        group_others_id = create_group(
            test_client, group_set["id"], [
                create_user_with_perms(session, [], prog_course).id,
                create_user_with_perms(session, [], prog_course).id,
            ]
        )['id']
        group_empty_id = create_group(test_client, group_set["id"], [])['id']

    with logged_in(user_only_own):
        sub = create_submission(test_client, assig_id)
        assert sub['user']['group']

    with logged_in(user_only_own):
        # Cannot delete with submission
        test_client.req(
            'delete',
            f'/api/v1/groups/{group_own_id}',
            400,
            result=error_template
        )
        # Cannot delete non empty group of other members
        test_client.req(
            'delete',
            f'/api/v1/groups/{group_others_id}',
            403,
            result=error_template
        )
        # Can delete empty group
        test_client.req('delete', f'/api/v1/groups/{group_empty_id}', 204)

    with logged_in(user_other_too):
        # Cannot delete with submission
        test_client.req(
            'delete',
            f'/api/v1/groups/{group_own_id}',
            400,
            result=error_template
        )
        # Can delete non empty group of other members
        test_client.req('delete', f'/api/v1/groups/{group_others_id}', 204)

    with logged_in(teacher_user):
        test_client.req('delete', f'/api/v1/submissions/{sub["id"]}', 204)

    with logged_in(user_only_own):
        # Can delete now submission has been deleted
        test_client.req('delete', f'/api/v1/groups/{group_own_id}', 204)


def test_add_user_to_group(
    test_client, session, logged_in, teacher_user, prog_course, error_template
):
    user_only_own = create_user_with_perms(
        session, [CPerm.can_edit_own_groups], prog_course
    )
    user_other_too = create_user_with_perms(
        session, [CPerm.can_edit_others_groups], prog_course
    )
    nobody = create_user_with_perms(session, [], prog_course)

    with logged_in(teacher_user):
        g_set = create_group_set(test_client, prog_course.id, 2, 4)
        g1 = create_group(
            test_client,
            g_set['id'],
            [create_user_with_perms(session, [], prog_course).id],
        )
        g2 = create_group(test_client, g_set['id'], [])

    with logged_in(user_only_own) as u:
        # Can add to group with members not including the user.
        g1 = test_client.req(
            'post',
            f'/api/v1/groups/{g1["id"]}/member',
            200,
            data={'username': u.username},
        )

        # Cannot add other user to group
        test_client.req(
            'post',
            f'/api/v1/groups/{g2["id"]}/member',
            403,
            data={'username': nobody.username}
        )

    with logged_in(user_other_too) as u:
        # Can add to empty group
        g2 = test_client.req(
            'post',
            f'/api/v1/groups/{g2["id"]}/member',
            200,
            data={'username': u.username},
        )

        # Can other user to a group
        test_client.req(
            'post',
            f'/api/v1/groups/{g2["id"]}/member',
            200,
            data={'username': nobody.username}
        )

        # Cannot add virtual user to a group
        test_client.req(
            'post',
            f'/api/v1/groups/{g1["id"]}/member',
            400,
            data={
                'username': m.Group.query.get(g2['id']).virtual_user.username
            }
        )

        # user_only_own is already in g1 so we can't add this user to any group
        # too.
        for g in [g1, g2]:
            err = test_client.req(
                'post',
                f'/api/v1/groups/{g["id"]}/member',
                400,
                data={
                    'username': user_only_own.username,
                },
                result=error_template,
            )
            assert 'already in a group' in err['message']

        # Fill group g1
        for _ in range(2):
            test_client.req(
                'post',
                f'/api/v1/groups/{g1["id"]}/member',
                200,
                data={
                    'username':
                        create_user_with_perms(session, [],
                                               prog_course).username
                }
            )
        # Group is full so we can't add another user
        test_client.req(
            'post',
            f'/api/v1/groups/{g1["id"]}/member',
            400,
            data={
                'username':
                    create_user_with_perms(session, [], prog_course).username
            },
            result=error_template
        )


@pytest.mark.parametrize('assignment', ['new'], indirect=True)
def test_submit_with_group(
    test_client, session, logged_in, teacher_user, course, error_template,
    assignment, monkeypatch_celery
):
    user_full_group = create_user_with_perms(
        session, [CPerm.can_submit_own_work, CPerm.can_see_assignments], course
    )
    user_empty_group = create_user_with_perms(
        session, [CPerm.can_submit_own_work, CPerm.can_see_assignments], course
    )
    user_no_group = create_user_with_perms(
        session, [CPerm.can_submit_own_work, CPerm.can_see_assignments], course
    )
    user_no_perms = create_user_with_perms(
        session, [CPerm.can_see_assignments], course
    )

    with logged_in(teacher_user):
        g_set = create_group_set(test_client, course.id, 2, 4)
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'group_set_id': g_set['id']}
        )
        g1 = create_group(
            test_client,
            g_set['id'],
            [user_full_group.id, user_no_perms.id],
        )
        create_group(test_client, g_set['id'], [user_empty_group.id])

    with logged_in(user_empty_group):
        err = create_submission(test_client, assignment.id, err=400)
        assert 'enough members' in err['message']

    with logged_in(user_no_perms):
        # Can't submit even if some users in the group can
        err = create_submission(test_client, assignment.id, err=403)

    with logged_in(user_no_group):
        # Can't submit as a user without group as the minimum size is 2
        err = create_submission(test_client, assignment.id, err=404)
        assert 'group was found' in err['message']

    with logged_in(user_full_group):
        # User can submit submission
        sub = create_submission(test_client, assignment.id)
        # Make sure submission is done as the group, not as the user
        assert sub['user']['group']['id'] == g1['id']

        # Make sure the user can see the just submitted submission
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/submissions/?extended',
            200,
            result=[sub]
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{sub["id"]}?extended',
            200,
            result=sub
        )
        files = test_client.req(
            'get', f'/api/v1/submissions/{sub["id"]}/files/', 200
        )
        while 'entries' in files:
            files = files['entries'][0]
        code_id = files['id']
        response = test_client.get(f'/api/v1/code/{code_id}')
        assert response.status_code == 200
    with logged_in(teacher_user):
        test_client.req(
            'put',
            f'/api/v1/code/{code_id}/comments/3',
            204,
            data={'comment': 'Lekker gewerkt pik!'}
        )
        # Set state to done so the student can see its feedback
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'state': 'done'}
        )
    with logged_in(user_full_group):
        # Make sure we can see comments on the files
        test_client.req(
            'get',
            f'/api/v1/code/{code_id}?type=feedback',
            200,
            result={'3': {'line': 3, 'msg': 'Lekker gewerkt pik!'}}
        )
    with logged_in(teacher_user):
        # Reset state back
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'state': 'open'}
        )


@pytest.mark.parametrize('assignment', ['new'], indirect=True)
def test_submit_with_small_group(
    test_client, session, logged_in, teacher_user, course, error_template,
    assignment
):
    user_no_group = create_user_with_perms(
        session, [CPerm.can_submit_own_work, CPerm.can_see_assignments], course
    )
    user_with_group = create_user_with_perms(
        session, [CPerm.can_submit_own_work, CPerm.can_see_assignments], course
    )

    with logged_in(teacher_user):
        g_set = create_group_set(test_client, course.id, 1, 1)
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'group_set_id': g_set['id']}
        )
        g1 = create_group(
            test_client,
            g_set['id'],
            [user_with_group.id],
        )

    with logged_in(user_no_group):
        # Can submit without group, you are simply the author (not a group)
        sub = create_submission(test_client, assignment.id)
        assert sub['user']['id'] == user_no_group.id

    with logged_in(user_with_group):
        # But when submitting as a user in a group the group should still be
        # the author
        sub = create_submission(test_client, assignment.id)
        assert sub['user']['group']['id'] == g1['id']


@pytest.mark.parametrize('course_name', ['Programmeertalen'], indirect=True)
def test_remove_user_from_group(
    test_client, session, logged_in, teacher_user, prog_course, error_template,
    assignment, monkeypatch_celery
):
    def make_user():
        return create_user_with_perms(
            session, [
                CPerm.can_edit_own_groups, CPerm.can_submit_own_work,
                CPerm.can_see_assignments
            ], prog_course
        )

    u1 = make_user()
    u2 = make_user()
    u3 = make_user()
    u4 = make_user()

    with logged_in(teacher_user):
        g_set = create_group_set(test_client, prog_course.id, 2, 4)
        g1 = create_group(
            test_client,
            g_set['id'],
            [u1.id, u2.id, u3.id, u4.id],
        )
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'group_set_id': g_set['id']}
        )

    with logged_in(u3) as me:
        # Cannot remove other users from own group
        test_client.req(
            'delete',
            f'/api/v1/groups/{g1["id"]}/members/{u1.id}',
            403,
            result=error_template
        )

        # Can remove self from group
        g1 = test_client.req(
            'delete',
            f'/api/v1/groups/{g1["id"]}/members/{me.id}',
            200,
        )

        # Cannot remove self twice
        test_client.req(
            'delete',
            f'/api/v1/groups/{g1["id"]}/members/{me.id}',
            404,
        )

    with logged_in(u2) as me:
        # Make sure group has a submission
        sub = create_submission(test_client, assignment.id)
        assert sub['user']['group']['id'] == g1['id']

        # Cannot remove self from group as the group has submission
        test_client.req(
            'delete',
            f'/api/v1/groups/{g1["id"]}/members/{me.id}',
            403,
            result=error_template
        )

    with logged_in(teacher_user):
        # Group is has three members so this is possible
        g1 = test_client.req(
            'delete',
            f'/api/v1/groups/{g1["id"]}/members/{u1.id}',
            200,
        )
        # Group only has two member with and has a submission so this is not
        # possible
        test_client.req(
            'delete',
            f'/api/v1/groups/{g1["id"]}/members/{u2.id}',
            400,
            result=error_template
        )

        test_client.req('delete', f'/api/v1/submissions/{sub["id"]}', 204)

        # The submission is deleted so this is now possible
        g1 = test_client.req(
            'delete',
            f'/api/v1/groups/{g1["id"]}/members/{u4.id}',
            200,
        )
        g1 = test_client.req(
            'delete',
            f'/api/v1/groups/{g1["id"]}/members/{u2.id}',
            200,
        )
        assert g1['members'] == []


def test_change_name_of_group(
    test_client, logged_in, error_template, prog_course, session, teacher_user
):
    new_name = f'NEW_NAME-{uuid.uuid4()}'

    def check_name(name):
        name_to_check = g1['name'] if name is None else name
        with logged_in(teacher_user):
            assert g_model.get_readable_name() == f'group "{name_to_check}"'
            return test_client.req(
                'get',
                f'/api/v1/groups/{g1["id"]}',
                200,
                result={**g1, 'name': name_to_check}
            )

    u1 = create_user_with_perms(
        session, [CPerm.can_edit_own_groups], prog_course
    )
    u2 = create_user_with_perms(
        session, [CPerm.can_edit_own_groups], prog_course
    )
    u3 = create_user_with_perms(
        session, [CPerm.can_edit_own_groups], prog_course
    )

    with logged_in(teacher_user):
        g_set = create_group_set(test_client, prog_course.id, 2, 4)
        g1 = create_group(
            test_client,
            g_set['id'],
            [u1.id, u2.id],
        )
        g_model = LocalProxy(
            lambda: m.User.query.get(g1['virtual_user']['id'])
        )

    with logged_in(u3):
        test_client.req(
            'post',
            f'/api/v1/groups/{g1["id"]}/name',
            403,
            data={'name': new_name}
        )
        check_name(None)

    with logged_in(u1):
        # u1 is member so it can change the name
        old_name = g1['name']
        test_client.req(
            'post',
            f'/api/v1/groups/{g1["id"]}/name',
            200,
            data={'name': new_name}
        )
        check_name(new_name)

        # Reset back to old name
        test_client.req(
            'post',
            f'/api/v1/groups/{g1["id"]}/name',
            200,
            data={'name': old_name}
        )
        check_name(old_name)

        test_client.req(
            'post',
            f'/api/v1/groups/{g1["id"]}/name',
            400,
            data={'name': 'sh'},  # This name is too short
            result=error_template
        )
        check_name(None)


def test_add_test_student_to_group(
    session, test_client, logged_in, assignment, teacher_user, error_template,
    describe, monkeypatch_celery
):
    c_id = assignment.course.id

    with logged_in(teacher_user):
        g_set = create_group_set(test_client, c_id, 1, 4)

        res = create_submission(
            test_client,
            assignment.id,
            is_test_submission=True,
        )
        test_student = res['user']

        with describe('new group with a test student cannot be created'):
            res = test_client.req(
                'post',
                f'/api/v1/group_sets/{g_set["id"]}/group',
                400,
                result=error_template,
                data={
                    'member_ids': [test_student['id']],
                },
            )

        with describe(
            'new group with a test student and other students cannot be created'
        ):
            u1 = create_user_with_perms(
                session, [CPerm.can_edit_own_groups], assignment.course
            )
            res = test_client.req(
                'post',
                f'/api/v1/group_sets/{g_set["id"]}/group',
                400,
                result=error_template,
                data={
                    'member_ids': [test_student['id'], u1.id],
                },
            )

        with describe('test student can not be added to existing group'):
            g1 = create_group(
                test_client,
                g_set['id'],
                [],
            )
            res = test_client.req(
                'post',
                f'/api/v1/groups/{g1["id"]}/member',
                400,
                result=error_template,
                data={
                    'username': test_student['username'],
                },
            )


@pytest.mark.parametrize('assignment', ['new'], indirect=True)
def test_seeing_teacher_revision_in_group(
    test_client, session, logged_in, teacher_user, course, error_template,
    assignment, describe
):
    with describe('setup'):
        user_other_group = create_user_with_perms(
            session, [
                CPerm.can_submit_own_work, CPerm.can_view_own_teacher_files,
                CPerm.can_see_assignments
            ], course
        )
        user_with_perm = create_user_with_perms(
            session, [
                CPerm.can_submit_own_work, CPerm.can_view_own_teacher_files,
                CPerm.can_see_assignments
            ], course
        )
        user_without_perm = create_user_with_perms(
            session, [CPerm.can_submit_own_work, CPerm.can_see_assignments],
            course
        )

        with logged_in(teacher_user):
            g_set = create_group_set(test_client, course.id, 1, 2)
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}',
                200,
                data={'group_set_id': g_set['id']}
            )
            g1 = create_group(
                test_client,
                g_set['id'],
                [user_with_perm, user_without_perm],
            )

        with logged_in(user_with_perm):
            sub = create_submission(test_client, assignment.id)
            # Submission is by the group
            assert sub['user']['group']['id'] == g1['id']

            student_files = test_client.req(
                'get', f'/api/v1/submissions/{sub["id"]}/files/', 200
            )

    with describe('Cannot view teacher files while assig is open'
                  ), logged_in(user_with_perm):
        test_client.req(
            'get',
            f'/api/v1/submissions/{sub["id"]}/files/?owner=teacher',
            403,
            result=error_template,
        )

    with describe('Can see teacher files after assig is done'
                  ), logged_in(user_with_perm):
        assignment.set_state_with_string('done')
        session.commit()

        test_client.req(
            'get',
            f'/api/v1/submissions/{sub["id"]}/files/?owner=teacher',
            200,
            result=student_files,
        )

        # This marks all files as from the student revision, i.e. there are no
        # teacher files.
        m.File.query.filter(
            m.File.work_id == sub['id'], m.File.parent_id.isnot(None)
        ).update({'fileowner': m.FileOwner.student})

        test_client.req(
            'get',
            f'/api/v1/submissions/{sub["id"]}/files/?owner=teacher',
            200,
            result={
                **student_files,
                'entries': [],
            }
        )

    with describe(
        'User without permission to see own teacher files gets an error'
    ), logged_in(user_without_perm):
        test_client.req(
            'get',
            f'/api/v1/submissions/{sub["id"]}/files/?owner=teacher',
            403,
            result=error_template,
        )

    with describe('User from other group cannot see teacher files'
                  ), logged_in(user_other_group):
        test_client.req(
            'get',
            f'/api/v1/submissions/{sub["id"]}/files/?owner=teacher',
            403,
            result=error_template,
        )
