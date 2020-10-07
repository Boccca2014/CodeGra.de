# SPDX-License-Identifier: AGPL-3.0-only
import io
import os
import copy
import zipfile
import datetime

import pytest
from pytest import approx

import psef
import helpers
import psef.tasks as tasks
import psef.models as m
from helpers import (
    get_id, create_course, create_marker, create_assignment, create_submission,
    create_user_with_role
)
from cg_dt_utils import DatetimeWithTimezone

http_error = create_marker(pytest.mark.http_error)
perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)
list_error = create_marker(pytest.mark.list_error)


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize('grade', [
    4.5,
])
@pytest.mark.parametrize('feedback', [
    'Goed gedaan!',
])
def test_get_grade_history(
    assignment_real_works, ta_user, test_client, logged_in, request, grade,
    feedback, error_template, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    data = {}
    data['grade'] = grade
    data['feedback'] = feedback

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/grade_history/',
            200,
            result=[]
        )

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data=data,
            result=dict,
        )
        data['grade'] = grade + 1
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data=data,
            result=dict,
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/grade_history/',
            403,
            result=error_template
        )

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/grade_history/',
            200,
            result=[{
                'changed_at': str,
                'is_rubric': False,
                'grade': grade + 1,
                'passed_back': False,
                'user': dict,
                'origin': 'human',
            },
                    {
                        'changed_at': str,
                        'is_rubric': False,
                        'grade': grade,
                        'passed_back': False,
                        'user': dict,
                        'origin': 'human',
                    }]
        )

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': None},
            result=dict
        )

        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/grade_history/',
            200,
            result=[{
                'changed_at': str,
                'is_rubric': False,
                'grade': -1,
                'passed_back': False,
                'user': dict,
                'origin': 'human',
            },
                    {
                        'changed_at': str,
                        'is_rubric': False,
                        'grade': grade + 1,
                        'passed_back': False,
                        'user': dict,
                        'origin': 'human',
                    },
                    {
                        'changed_at': str,
                        'is_rubric': False,
                        'grade': grade,
                        'passed_back': False,
                        'user': dict,
                        'origin': 'human',
                    }]
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student1'),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'grade', [
        data_error(-1),
        data_error(11),
        data_error('err'),
        None,
        4,
        4.5,
    ]
)
@pytest.mark.parametrize(
    'feedback', [
        data_error(1),
        None,
        '',
        'Goed gedaan!',
    ]
)
def test_patch_submission(
    assignment_real_works, named_user, test_client, logged_in, request, grade,
    feedback, ta_user, error_template
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif data_err:
        error = 400
    else:
        error = False

    data = {}
    if grade is not None:
        data['grade'] = grade
    if feedback is not None:
        data['feedback'] = feedback

    expected_submission = {
        'id': work_id,
        'assignee': None,
        'user': dict,
        'created_at': str,
        'grade': None if error else grade,
        'comment': None if error else feedback,
        'comment_author': (None if error or 'feedback' not in data else dict),
        'grade_overridden': False,
        'assignment_id': int,
        'extra_info': None,
        'origin': 'uploaded_files',
        'rubric_result': None,
    }

    with logged_in(named_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            error or 200,
            data=data,
            result=error_template if error else expected_submission,
        )

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200,
            result=expected_submission
        )
        assert 'email' not in res['user']


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_delete_grade_submission(
    ta_user, test_client, logged_in, assignment_real_works
):
    assignment, work = assignment_real_works
    work_id = work['id']

    with logged_in(ta_user):
        res = test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': 5, 'feedback': ''},
            result=dict
        )
        assert res['grade'] == 5
        res = test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': None, 'feedback': 'ww'},
            result=dict
        )
        assert res['grade'] is None
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200,
            result={
                'id': work_id,
                'assignee': None,
                'user': dict,
                'created_at': str,
                'grade': None,
                'comment': 'ww',
                'comment_author': dict,
                'grade_overridden': False,
                'assignment_id': int,
                'extra_info': None,
                'origin': 'uploaded_files',
                'rubric_result': None,
            }
        )
        assert res['comment_author']['id'] == ta_user.id


def test_patch_non_existing_submission(
    ta_user, test_client, logged_in, error_template
):
    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/0',
            404,
            data={'grade': 4, 'feedback': 'wow!'},
            result=error_template
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_negative_points(
    request, test_client, logged_in, error_template, teacher_user, ta_user,
    assignment_real_works, session
):
    assignment, work = assignment_real_works
    work_id = work['id']

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }, {
            'header': 'Compensation',
            'description': 'WOW',
            'items': [{
                'description': 'BLA',
                'header': 'Negative',
                'points': -1,
            }, {
                'description': 'BLA+',
                'header': 'Positive',
                'points': 0,
            }],
        }]
    }  # yapf: disable
    max_points = 10

    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )
        rubric = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': list, 'selected': [],
                'points': {'max': max_points, 'selected': 0}
            }
        )['rubrics']

    def get_rubric_item(head, desc):
        for row in rubric:
            if row['header'] == head:
                for item in row['items']:
                    if item['description'] == desc:
                        return item

    with logged_in(ta_user):
        to_select = [
            get_rubric_item('Compensation', 'BLA'),
        ]
        points = [-1]
        for item, point in zip(to_select, points):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work_id}/rubricitems/{item["id"]}',
                204,
                result=None
            )
            with logged_in(ta_user):
                work = test_client.req(
                    'get', f'/api/v1/submissions/{work_id}', 200
                )
                assert work['grade'] == 0

                test_client.req(
                    'get',
                    f'/api/v1/submissions/{work_id}/rubrics/',
                    200,
                    result={
                        'rubrics': rubric, 'selected': list,
                        'points': {'max': max_points, 'selected': point}
                    }
                )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403, can_get=True)('Student1'),
    ],
    indirect=True
)
def test_selecting_rubric(
    named_user, request, test_client, logged_in, error_template, ta_user,
    assignment_real_works, session, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
        can_get_rubric = perm_err.kwargs.get('can_get', False)
    else:
        can_get_rubric = True
        error = False

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }, {
            'header': 'My header2',
            'description': 'My description2',
            'items': [{
                'description': '1points',
                'header': 'bladie',
                'points': 1
            }, {
                'description': '2points',
                'header': 'bladie',
                'points': 2,
            }]
        }, {
            'header': 'Compensation',
            'description': 'WOW',
            'items': [{
                'description': 'BLA',
                'header': 'Never selected',
                'points': -1,
            }, {
                'description': 'BLA+',
                'header': 'Never selected 2',
                'points': 0,
            }],
        }]
    }  # yapf: disable
    max_points = 12

    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )
        rubric = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': list, 'selected': [],
                'points': {'max': max_points, 'selected': 0}
            }
        )['rubrics']

    def get_rubric_item(head, desc):
        for row in rubric:
            if row['header'] == head:
                for item in row['items']:
                    if item['description'] == desc:
                        return item

    with logged_in(named_user):
        to_select = [
            get_rubric_item('My header', '10points'),
            get_rubric_item('My header2', '2points'),
            get_rubric_item('My header', '5points'),
        ]
        points = [10, 10 + 2, 5 + 2]
        result_point = points[-1]
        for item, point in zip(to_select, points):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work_id}/rubricitems/{item["id"]}',
                error if error else 204,
                result=error_template if error else None
            )
            with logged_in(ta_user):
                work = test_client.req(
                    'get', f'/api/v1/submissions/{work_id}', 200
                )
                if error:
                    assert work['grade'] is None
                else:
                    assert approx(work['grade']) == approx(
                        min(10 * point / max_points, 10)
                    )

                test_client.req(
                    'get',
                    f'/api/v1/submissions/{work_id}/rubrics/',
                    200,
                    result={
                        'rubrics': rubric, 'selected': list, 'points': {
                            'max': max_points,
                            'selected': 0 if error else point
                        }
                    }
                )

        res = {'rubrics': rubric}
        if error:
            res.update({
                'selected': [],
                'points': {
                    'max': None,
                    'selected': None,
                },
            }, )
        else:
            res.update({
                'selected': list,
                'points': {'max': max_points, 'selected': result_point}
            })

        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200 if can_get_rubric else error,
            result=res if can_get_rubric else error_template
        )

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200 if can_get_rubric else error,
        )
        if not error:
            assert res['grade'] == pytest.approx(
                result_point / max_points * 10
            )

        if not error:
            with logged_in(teacher_user):
                rubric = test_client.req(
                    'delete',
                    f'/api/v1/assignments/{assignment.id}/rubrics/',
                    204,
                )
            res = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}',
                200 if can_get_rubric else error,
            )
            assert res['grade'] is None
            res = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/rubrics/',
                200,
            )
            assert res['selected'] == []


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_selecting_rubric_same_row_twice(
    test_client, logged_in, error_template, assignment_real_works, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }, {
            'header': 'My header2',
            'description': 'My description2',
            'items': [{
                'description': '1points',
                'header': 'bladie',
                'points': 1
            }, {
                'description': '2points',
                'header': 'bladie',
                'points': 2,
            }]
        }]
    }  # yapf: disable
    max_points = 12

    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )
        rubric = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': list, 'selected': [],
                'points': {'max': max_points, 'selected': 0}
            }
        )['rubrics']

    with logged_in(teacher_user):
        to_select = [rubric[0]['items'][0]['id'], rubric[0]['items'][1]['id']]
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/',
            400,
            data={'items': to_select},
            result=error_template,
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student1'),
    ],
    indirect=True
)
def test_clearing_rubric(
    named_user, request, test_client, logged_in, error_template, ta_user,
    assignment_real_works, session, teacher_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    rubric = {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
            'items': [{
                'description': '5points',
                'header': 'bladie',
                'points': 5
            }, {
                'description': '10points',
                'header': 'bladie',
                'points': 10,
            }]
        }, {
            'header': 'My header2',
            'description': 'My description2',
            'items': [{
                'description': '1points',
                'header': 'bladie',
                'points': 1
            }, {
                'description': '2points',
                'header': 'bladie',
                'points': 2,
            }]
        }]
    }  # yapf: disable
    max_points = 12

    def get_rubric_item(head, desc):
        for row in rubric:
            if row['header'] == head:
                for item in row['items']:
                    if item['description'] == desc:
                        return item

    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=rubric
        )

    with logged_in(ta_user):
        rubric = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': rubric, 'selected': [],
                'points': {'max': max_points, 'selected': 0}
            }
        )['rubrics']

        to_select = get_rubric_item('My header', '10points')
        to_select2 = get_rubric_item('My header2', '1points')
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/{to_select["id"]}',
            204,
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': rubric, 'selected': list, 'points': {
                    'max': max_points,
                    'selected': 10,
                }
            }
        )
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/{to_select2["id"]}',
            204,
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
            result={
                'rubrics': rubric, 'selected': list, 'points': {
                    'max': max_points,
                    'selected': 11,
                }
            }
        )

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200,
        )
        assert res['grade'] == pytest.approx(11 / max_points * 10)
        selected = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/rubrics/',
            200,
        )['selected']
        assert len(selected) == 2

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/submissions/{work_id}/rubricitems/{selected[0]["id"]}',
            error or 204,
            result=error_template if error else None,
        )
        # Make sure invalid items can't be deselected
        test_client.req(
            'delete',
            f'/api/v1/submissions/{work_id}/rubricitems/10000000000',
            error or 400,
            result=error_template,
        )

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}',
            200,
        )
        if error:
            assert res['grade'] == pytest.approx(11 / max_points * 10)
        else:
            assert res['grade'] == pytest.approx(1 / max_points * 10)
        assert len(
            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/rubrics/',
                200,
            )['selected']
        ) == (2 if error else 1)


def test_selecting_wrong_rubric(
    test_client, logged_in, error_template, session, admin_user, tomorrow,
    describe
):
    with describe('Setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, state='open', deadline=tomorrow
        )

        other_course = helpers.create_course(test_client)
        other_assignment = helpers.create_assignment(
            test_client, other_course, state='open', deadline=tomorrow
        )

        student_user = helpers.create_user_with_role(
            session, 'Student', [course, other_course]
        )
        with logged_in(student_user):
            _ = helpers.create_submission(test_client, assignment)
            other_work = helpers.create_submission(
                test_client, other_assignment
            )

        rubric = {
            'rows': [{
                'header': 'My header',
                'description': 'My description',
                'items': [{
                    'description': '5points',
                    'header': 'bladie',
                    'points': 5
                }, {
                    'description': '10points',
                    'header': 'bladie',
                    'points': 10,
                }]
            }]
        }  # yapf: disable

    with describe('Create rubric in one assignment'):
        with logged_in(admin_user):
            rubric = test_client.req(
                'put',
                f'/api/v1/assignments/{get_id(assignment)}/rubrics/',
                200,
                data=rubric
            )

    with describe('Cannot use rubric from other assignment'
                  ), logged_in(admin_user):
        # Note the use of `other_work` which is another course and in another
        # assignment.
        test_client.req(
            'patch', f'/api/v1/submissions/{get_id(other_work)}/'
            f'rubricitems/{rubric[0]["items"][0]["id"]}',
            400,
            result=error_template
        )


@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        'Student1',
        perm_error(error=403)('Student2'),
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_get_dir_contents(
    request, test_client, logged_in, named_user, error_template,
    assignment_real_works
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            error or 200,
            result=error_template if error else {
                'entries': [{'id': str, 'name': 'test.py'}], 'id': str, 'name':
                    'test_flake8.tar.gz'
            }
        )
        if not error:
            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/files/',
                200,
                query={'file_id': res["id"]},
                result=res,
            )

            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/files/',
                400,
                query={'file_id': res["entries"][0]["id"]},
                result=error_template
            )

            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/files/',
                404,
                query={'file_id': -1},
                result=error_template
            )


@pytest.mark.parametrize('user_type', ['student'])
@pytest.mark.parametrize(
    'named_user, get_own', [
        ('Thomas Schaper', False),
        ('Student1', False),
        ('Œlµo', True),
        perm_error(error=401)(('NOT_LOGGED_IN', False)),
        perm_error(error=403)(('admin', False)),
        perm_error(error=403)(('Student3', False)),
    ],
    indirect=['named_user']
)
@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
def test_get_zip_file(
    test_client, logged_in, assignment_real_works, error_template, named_user,
    request, user_type, get_own, session
):
    assignment, work = assignment_real_works
    assignment.name += '/hello'
    session.commit()

    if get_own:
        work_id = m.Work.query.filter_by(
            user=named_user, assignment=assignment
        ).order_by(m.Work.created_at.desc()).first().id
    else:
        work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        for url in [
            '/api/v1/files/{name}?name={output_name}',
            '/api/v1/files/{name}/{output_name}'
        ]:
            res = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}',
                error or 200,
                result=(
                    error_template
                    if error else {'name': str, 'output_name': str}
                ),
                query={'type': 'zip', 'owner': user_type},
            )

            if not error:
                assert '/' not in res['output_name']
                assert '_hello' in res['output_name']

                file_name = res['name']
                res = test_client.get(url.format(**res))

                assert res.status_code == 200
                zfiles = zipfile.ZipFile(io.BytesIO(res.get_data()))
                files = zfiles.infolist()
                files = set(f.filename for f in files)
                assert files == {
                    'multiple_dir_archive.zip/',
                    'multiple_dir_archive.zip/dir/single_file_work',
                    'multiple_dir_archive.zip/dir/single_file_work_copy',
                    'multiple_dir_archive.zip/dir2/single_file_work',
                    'multiple_dir_archive.zip/dir2/single_file_work_copy',
                }

                res = test_client.get(f'/api/v1/files/{file_name}')
                assert res.status_code == 404


@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
def test_get_teacher_zip_file(
    test_client, logged_in, assignment_real_works, error_template, ta_user,
    student_user, session
):
    def get_files(user, error):
        with logged_in(user):
            res = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}',
                error or 200,
                result=error_template
                if error else {'name': str, 'output_name': str},
                query={'type': 'zip', 'owner': 'teacher'},
            )
            if error:
                return object()

            file_name = res['name']
            res = test_client.get(f'/api/v1/files/{file_name}')

            assert res.status_code == 200
            files = zipfile.ZipFile(io.BytesIO(res.get_data())).infolist()
            files = set(f.filename for f in files)
            return files

    assignment, work = assignment_real_works
    work_id = work['id']

    assert get_files(ta_user, False) == {
        'multiple_dir_archive.zip/',
        'multiple_dir_archive.zip/dir/single_file_work',
        'multiple_dir_archive.zip/dir/single_file_work_copy',
        'multiple_dir_archive.zip/dir2/single_file_work',
        'multiple_dir_archive.zip/dir2/single_file_work_copy',
    }

    get_files(student_user, 403)
    m.File.query.filter_by(
        work_id=work_id,
        name="single_file_work",
    ).filter(
        m.File.parent != None,
    ).update({'fileowner': m.FileOwner.student})
    session.commit()
    assert get_files(ta_user, False) == {
        'multiple_dir_archive.zip/',
        'multiple_dir_archive.zip/dir/single_file_work_copy',
        'multiple_dir_archive.zip/dir2/single_file_work_copy'
    }
    m.Assignment.query.filter_by(
        id=m.Work.query.get(work_id).assignment_id,
    ).update({
        'deadline': DatetimeWithTimezone.utcnow() - datetime.timedelta(days=1)
    })
    session.commit()
    get_files(student_user, 403)

    m.Assignment.query.filter_by(
        id=m.Work.query.get(work_id).assignment_id,
    ).update({
        'state': m.AssignmentStateEnum.done,
    })
    session.commit()

    assert get_files(student_user, False) == {
        'multiple_dir_archive.zip/',
        'multiple_dir_archive.zip/dir/single_file_work_copy',
        'multiple_dir_archive.zip/dir2/single_file_work_copy',
    }


@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        'Student1',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student3'),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
@pytest.mark.parametrize(
    'to_search', [
        'multiple_dir_archive.zip/dir/single_file_work',
        '/multiple_dir_archive.zip/dir/single_file_work',
        data_error(error=404
                   )('multiple_dir_archive.zip/dir/single_file_work/'),
        data_error(error=404
                   )('/multiple_dir_archive.zip/dir/single_file_work/'),
        '/multiple_dir_archive.zip/dir2/',
        'multiple_dir_archive.zip/dir2/',
        data_error(error=404)('/multiple_dir_archive.zip/dir2'),
        data_error(error=404)('multiple_dir_archive.zip/dir2'),
    ]
)
def test_search_file(
    test_client, logged_in, assignment_real_works, error_template, named_user,
    request, to_search
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif data_err:
        error = data_err.kwargs['error']
    else:
        error = False

    is_dir = to_search[-1] == '/'

    with logged_in(named_user):
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            error or 200,
            query={'path': to_search},
            result=error_template if error else {
                'is_directory': is_dir, 'modification_date': int, 'size': int,
                'id': str
            },
        )


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
def test_add_file(
    test_client, logged_in, ta_user, assignment_real_works, error_template,
    student_user, session
):
    assignment, work = assignment_real_works
    work_id = work['id']
    session.query(
        m.Assignment
    ).filter_by(id=m.Work.query.get(work_id).assignment_id).update({
        'deadline': DatetimeWithTimezone.utcnow() - datetime.timedelta(days=1)
    })
    session.commit()

    def get_file_by_id(file_id):
        res = test_client.get(f'/api/v1/code/{file_id}')
        assert res.status_code == 200
        return res.get_data(as_text=True)

    with logged_in(ta_user):
        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': [{'id': str, 'name': 'single_file_work'},
                            {'id': str, 'name': 'single_file_work_copy'}],
                'id': str, 'name': 'single_dir_archive.zip'
            }
        )

        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            404,
            result=error_template,
            query={'path': '/non/existing/'}
        )
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            result=error_template,
            query={'path': '/too_short/'}
        )

        # Special files cannot be added anywhere
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            result=error_template,
            query={'path': '/single_dir_archive.zip/dir/dir2/.cg-grade'}
        )
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/single_dir_archive.zip/dir/dir2/wow/'},
        )
        assert res['is_directory'] is True
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            query={'path': '/single_dir_archive.zip/dir/dir2/wow/'},
            result=error_template,
        )
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/single_dir_archive.zip/dir/dir2/wow/dit/'},
        )
        assert res['is_directory'] is True

        # Make sure you cannot upload to large strings
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            query={
                'path':
                    '/single_dir_archive.zip/dir/dir2/this/is/to/large/file'
            },
            real_data=b'0' * 2 * 2 ** 20,
            result=error_template,
        )
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/single_dir_archive.zip/dir/dir2/file'},
            real_data='NEW_FILE',
        )
        assert get_file_by_id(res['id']) == 'NEW_FILE'
        assert res['size'] == len('NEW_FILE')
        assert res['is_directory'] is False
        test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            400,
            query={'path': '/single_dir_archive.zip/dir/dir2/file'},
            real_data='NEWER_FILE',
        )
        assert get_file_by_id(res['id']) == 'NEW_FILE'
        res = test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'path': '/single_dir_archive.zip/dir/dir2/dir3/file'},
            real_data='NEW_FILE',
        )
        assert get_file_by_id(res['id']) == 'NEW_FILE'
        assert res['size'] == len('NEW_FILE')
        assert not res['is_directory']

        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/?owner=teacher',
            200,
            result={
                'name': 'single_dir_archive.zip',
                'id': str,
                'entries': [
                    {
                        'name': 'dir',
                        'id': str,
                        'entries': [{
                            'name': 'dir2',
                            'id': str,
                            'entries': [
                                {
                                    'name': 'dir3',
                                    'id': str,
                                    'entries': [{
                                        'name': 'file',
                                        'id': str,
                                    }],
                                },
                                {
                                    'name': 'file',
                                    'id': str,
                                },
                                {
                                    'name': 'wow',
                                    'id': str,
                                    'entries': [{
                                        'name': 'dit',
                                        'id': str,
                                        'entries': [],
                                    }],
                                },
                            ],
                        }],
                    },
                    {
                        'name': 'single_file_work',
                        'id': str,
                    },
                    {
                        'name': 'single_file_work_copy',
                        'id': str,
                    },
                ],
            },
        )


@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_change_grader_notification(
    logged_in, test_client, stubmailer, monkeypatch_celery, assignment,
    teacher_user, with_works, ta_user
):
    assig_id = assignment.id
    graders = m.User.query.filter(
        m.User.name.in_([
            'Thomas Schaper',
            'Devin Hillenius',
            'Robin',
        ]),
        ~m.User.name.in_(ta_user.name),
    ).all()
    grader_done = graders[0].id

    subs = m.Work.query.filter_by(assignment_id=assig_id).all()
    sub_id = subs[0].id
    sub2_id = subs[1].id

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub_id}/grader',
            204,
            data={'user_id': grader_done},
        )
        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub2_id}/grader',
            204,
            data={'user_id': teacher_user.id},
        )

        assert not stubmailer.called, """
        Setting a non done grader should not do anything
        """
        stubmailer.reset()

        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{ta_user.id}/done',
            204,
        )

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub_id}/grader',
            204,
            data={'user_id': ta_user.id},
        )

        assert not stubmailer.called, """
        Setting yourself as assigned should not trigger emails
        """
        assert not m.AssignmentGraderDone.query.filter_by(
            user_id=ta_user.id,
        ).all(), 'We should however not be marked as done any more.'
        stubmailer.reset()

        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub_id}/grader',
            204,
            data={'user_id': grader_done},
        )

        assert stubmailer.called == 1, """
        Setting somebody else as assigned should trigger a email even if this
        person was previously assigned.
        """
        assert not m.AssignmentGraderDone.query.filter_by(
            assignment_id=assig_id,
        ).all(), 'Make sure nobody is done at this point'


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
@pytest.mark.parametrize(
    'named_user',
    ['Thomas Schaper', http_error(error=403)('Student1')],
    indirect=True
)
@pytest.mark.parametrize('graders', [(['Thomas Schaper', 'Devin Hillenius'])])
def test_change_grader(
    graders, named_user, logged_in, test_client, error_template, request,
    assignment_real_works, ta_user
):
    marker = request.node.get_closest_marker('http_error')
    code = 204 if marker is None else marker.kwargs['error']
    res = None if marker is None else error_template

    assignment, _ = assignment_real_works

    grader_ids = []
    for grader in graders:
        if isinstance(grader, int):
            grader_ids.append(grader)
        else:
            grader_ids.append(m.User.query.filter_by(name=grader).one().id)

    with logged_in(named_user):
        with logged_in(ta_user):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}/divide',
                204,
                data={'graders': {g: 1
                                  for g in grader_ids}}
            )
            submission = test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
            )[0]

        old_grader = submission['assignee']['name']

        if marker is None:
            test_client.req(
                'patch',
                f'/api/v1/submissions/{submission["id"]}/grader',
                404,
                result=error_template,
                data={'user_id': 100000}
            )
            with logged_in(ta_user):
                submission = test_client.req(
                    'get', f'/api/v1/assignments/{assignment.id}/submissions/',
                    200
                )[0]
            assert submission['assignee']['name'] == old_grader

            student1_id = m.User.query.filter_by(name='Student1').first().id
            test_client.req(
                'patch',
                f'/api/v1/submissions/{submission["id"]}/grader',
                400,
                result=error_template,
                data={'user_id': student1_id}
            )
            with logged_in(ta_user):
                submission = test_client.req(
                    'get', f'/api/v1/assignments/{assignment.id}/submissions/',
                    200
                )[0]
            assert submission['assignee']['name'] == old_grader

        new_grader = [grader for grader in graders if grader != old_grader][0]
        new_grader_id = m.User.query.filter_by(name=new_grader).first().id

        test_client.req(
            'patch',
            f'/api/v1/submissions/{submission["id"]}/grader',
            code,
            result=res,
            data={'user_id': new_grader_id}
        )
        with logged_in(ta_user):
            submission = test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
            )[0]
        if marker is None:
            assert submission['assignee']['name'] == new_grader
        else:
            assert submission['assignee']['name'] == old_grader

        test_client.req(
            'delete',
            f'/api/v1/submissions/{submission["id"]}/grader',
            code,
            result=res
        )
        with logged_in(ta_user):
            submission = test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
            )[0]
        if marker is None:
            assert submission['assignee'] is None
        else:
            assert submission['assignee']['name'] == old_grader


def test_update_test_submission_grader(
    test_client, logged_in, teacher_user, ta_user, assignment, error_template
):
    with logged_in(teacher_user):
        test_sub = create_submission(
            test_client,
            assignment.id,
            is_test_submission=True,
        )

        test_client.req(
            'patch',
            f'/api/v1/submissions/{test_sub["id"]}/grader',
            400,
            result=error_template,
            data={
                'user_id': ta_user.id,
            },
        )


@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        perm_error(error=403)('Thomas Schaper'),
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403)('Student1'),
    ],
    indirect=True
)
def test_delete_submission(
    named_user, request, test_client, logged_in, error_template, teacher_user,
    assignment_real_works, session, monkeypatch_celery, app
):
    assignment, work = assignment_real_works
    work_id = work['id']
    other_work = m.Work.query.filter_by(assignment=assignment
                                        ).filter(m.Work.id != work_id).first()
    assert other_work, "Other work should exist"

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    files = [f.id for f in m.File.query.filter_by(work_id=work_id).all()]
    assert files
    code = m.File.query.filter_by(work_id=work_id, is_directory=False).first()

    found_file = code.backing_file
    assert found_file.is_just
    assert found_file.value.exists

    other_code = m.File.query.filter_by(
        work_id=other_work.id, is_directory=False
    ).first()

    p_run = m.PlagiarismRun(
        assignment=assignment, json_config='[]', old_assignments=[]
    )
    p_case = m.PlagiarismCase(
        work1_id=work_id, work2_id=other_work.id, match_avg=50, match_max=50
    )
    p_match = m.PlagiarismMatch(
        file1=code,
        file2=other_code,
        file1_start=0,
        file1_end=1,
        file2_start=0,
        file2_end=1
    )
    p_case.matches.append(p_match)
    p_run.cases.append(p_case)
    session.add(p_run)
    session.commit()
    p_case_id = p_case.id
    p_run_id = p_run.id

    assert p_case_id
    assert p_run_id

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'feedback': 'waaa', 'grade': 5.65},
            result=dict,
        )

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/submissions/{work_id}',
            error or 204,
            result=error_template if error else None
        )

    if error:
        assert code.backing_file.value.exists
        for f in files:
            assert m.File.query.get(f)
        assert not m.Work.query.get(work_id).deleted
    else:
        assert m.Work.query.get(work_id).deleted
        with logged_in(teacher_user):
            test_client.req('get', f'/api/v1/submissions/{work_id}', 404)


def test_delete_submission_with_other_work(
    test_client, logged_in, admin_user, session, describe, monkeypatch,
    stub_function_class, app, make_function_spy, canvas_lti1p1_provider,
    watch_signal
):
    # TODO: Split up this test. The test does way too much. It was written
    # before we had signals, so it not only tests that those are dispatched
    # correctly, it also tests that we handle the signals correctly.

    with describe('setup'), logged_in(admin_user):
        course = create_course(test_client)
        assignment = m.Assignment.query.get(
            create_assignment(
                test_client, course, 'open', deadline='tomorrow'
            )['id']
        )
        student = create_user_with_role(session, 'Student', course)

        signal = watch_signal(psef.signals.WORK_DELETED)

        stub_passback = stub_function_class(lambda: 0)
        monkeypatch.setattr(
            psef.lti.v1_1.LTI, '_passback_grade', stub_passback
        )

        stub_delete_submission = make_function_spy(
            m.LTI1p1Provider, '_delete_submission'
        )

        stub_adjust = stub_function_class(lambda: 0)
        monkeypatch.setattr(tasks, 'adjust_amount_runners', stub_adjust)

        monkeypatch.setattr(
            tasks, 'update_latest_results_in_broker', stub_function_class()
        )

        stub_clear = stub_function_class(lambda: 0)
        monkeypatch.setattr(
            m.AutoTestResult, 'clear', lambda *args: stub_clear(*args)
        )

        with logged_in(student):
            super_oldest = create_submission(test_client, assignment)['id']
            very_oldest = create_submission(test_client, assignment)['id']
            oldest = create_submission(test_client, assignment)['id']
            middle = create_submission(test_client, assignment)['id']
            newest = create_submission(test_client, assignment)['id']

        with logged_in(admin_user):
            from_test_student_oldest = create_submission(
                test_client, assignment, is_test_submission=True
            )['id']
            from_test_student_newest = create_submission(
                test_client, assignment, is_test_submission=True
            )['id']

        monkeypatch.setattr(m.AutoTest, 'has_hidden_steps', True)
        assignment.auto_test = m.AutoTest(results_always_visible=True)
        run = m.AutoTestRun(
            batch_run_done=False, auto_test=assignment.auto_test
        )
        session.flush()
        with app.test_request_context('/', {}):
            assignment.auto_test.add_to_run(m.Work.query.get(very_oldest))
        run.batch_run_done = True

        assignment.set_state_with_string('done')
        assignment.lti_grade_service_data = 'a url'
        assignment.is_lti = True
        course_lti_connection = m.CourseLTIProvider.create_and_add(
            course=assignment.course,
            lti_provider=canvas_lti1p1_provider,
            lti_context_id='HALLO',
            deployment_id=''
        )
        session.commit()
        assignment.assignment_results[student.id] = m.AssignmentResult(
            user_id=student.id, sourcedid='5', assignment_id=assignment.id
        )
        session.commit()

    with describe('delete not newest submission'), logged_in(admin_user):
        test_client.req('delete', f'/api/v1/submissions/{middle}', 204)
        assert signal.was_send_once
        assert signal.signal_arg.deleted_work.id == middle
        assert not signal.signal_arg.was_latest
        assert signal.signal_arg.new_latest is None

        assert not stub_delete_submission.called
        assert not stub_adjust.called
        assert not stub_clear.called

    with describe('delete newest submission'), logged_in(admin_user):
        test_client.req('delete', f'/api/v1/submissions/{newest}', 204)
        assert signal.was_send_once
        assert signal.signal_arg.deleted_work.id == newest
        assert signal.signal_arg.was_latest
        # Not the middle as that one is already deleted
        assert signal.signal_arg.new_latest.id == oldest

        assert stub_passback.called
        assert not stub_delete_submission.called
        assert stub_adjust.called
        assert not stub_clear.called

        result = m.AutoTestResult.query.filter_by(work_id=oldest).one()
        assert result
        assert result.final_result is True

    with describe('delete submission by test student'), logged_in(admin_user):
        test_client.req(
            'delete', f'/api/v1/submissions/{from_test_student_newest}', 204
        )
        assert signal.was_send_once
        assert signal.signal_arg.deleted_work.id == from_test_student_newest
        assert signal.signal_arg.was_latest
        assert signal.signal_arg.new_latest.id == from_test_student_oldest

        assert not stub_passback.called
        assert not stub_delete_submission.called

    with describe('delete submission with other existing result'
                  ), logged_in(admin_user):
        assert m.AutoTestResult.query.filter_by(work_id=very_oldest
                                                ).one().final_result is False
        test_client.req('delete', f'/api/v1/submissions/{oldest}', 204)

        assert signal.was_send_once
        assert signal.signal_arg.deleted_work.id == oldest
        assert signal.signal_arg.was_latest
        assert signal.signal_arg.new_latest.id == very_oldest

        assert not stub_delete_submission.called
        assert stub_adjust.called

        # Make sure this old result was cleared first
        assert stub_clear.called
        assert stub_clear.all_args[0][0].work_id == very_oldest

        assert m.AutoTestResult.query.filter_by(work_id=very_oldest
                                                ).one().final_result is True

    with describe('without AutoTest run or lti'), logged_in(admin_user):
        assignment.auto_test._runs = []
        session.delete(course_lti_connection)
        assignment.is_lti = False
        session.commit()
        test_client.req('delete', f'/api/v1/submissions/{very_oldest}', 204)

        # Should still be send
        assert signal.was_send_once
        assert signal.signal_arg.deleted_work.id == very_oldest
        assert signal.signal_arg.was_latest
        assert signal.signal_arg.new_latest.id == super_oldest

        assert not stub_delete_submission.called
        assert not stub_adjust.called
        assert not stub_clear.called

        assert m.AutoTestResult.query.filter_by(work_id=super_oldest
                                                ).one_or_none() is None


@pytest.mark.parametrize('old_format', [True, False])
@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        perm_error(error=401)('NOT_LOGGED_IN'),
        perm_error(error=403)('admin'),
        perm_error(error=403, can_get=True)('Student1'),
    ],
    indirect=True
)
def test_selecting_multiple_rubric_items(
    named_user, request, test_client, logged_in, error_template, ta_user,
    assignment_real_works, session, bs_course, teacher_user, old_format,
    describe
):
    with describe('setup'):
        assignment, work = assignment_real_works
        work_id = work['id']

        perm_err = request.node.get_closest_marker('perm_error')
        if perm_err:
            error = perm_err.kwargs['error']
        else:
            error = False

        rubric = {
            'rows': [{
                'header': 'My header',
                'description': 'My description',
                'items': [{
                    'description': '5points',
                    'header': 'bladie',
                    'points': 5
                }, {
                    'description': '10points',
                    'header': 'bladie',
                    'points': 10,
                }]
            }, {
                'header': 'My header2',
                'description': 'My description2',
                'items': [{
                    'description': '1points',
                    'header': 'bladie',
                    'points': 1
                }, {
                    'description': '2points',
                    'header': 'bladie',
                    'points': 2,
                }]
            }]
        }  # yapf: disable
        max_points = 12

        with logged_in(teacher_user):
            bs_rubric = test_client.req(
                'put',
                f'/api/v1/assignments/{bs_course.id}/rubrics/',
                200,
                data=rubric
            )
            rubric = test_client.req(
                'put',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                200,
                data=rubric
            )
            rubric = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/rubrics/',
                200,
                result={
                    'rubrics': list, 'selected': [],
                    'points': {'max': max_points, 'selected': 0}
                }
            )['rubrics']

        def get_rubric_item(head, desc, multiplier=1.0, rubric=rubric):
            for row in rubric:
                if row['header'] == head:
                    for item in row['items']:
                        if item['description'] == desc:
                            if old_format:
                                return item['id']
                            else:
                                return {
                                    'row_id': row['id'],
                                    'item_id': item['id'],
                                    'multiplier': multiplier,
                                }

    with describe('can select if perms correct'), logged_in(named_user):
        to_select = [
            get_rubric_item('My header', '5points'),
            get_rubric_item('My header2', '2points'),
        ]
        points = 7
        expected_rubric_result = {
            'rubrics': list,
            'selected': list,
            'points': {
                'max': max_points,
                'selected': 0 if error else points,
            },
        }

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/',
            error if error else 200,
            data={'items': to_select},
            result=error_template if error else {
                '__allow_extra__': True,
                'rubric_result': expected_rubric_result,
            },
        )

        with logged_in(ta_user):
            selected = test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/rubrics/',
                200,
                result=expected_rubric_result
            )['selected']
            if error:
                assert not selected
            else:
                selected = [s['id'] for s in selected]
                if old_format:
                    assert all(item in selected for item in to_select)
                else:
                    assert all(
                        item in selected
                        for item in set(i['item_id'] for i in to_select)
                    )

        with describe('cannot select unkown rubric items'), logged_in(ta_user):
            if old_format:
                test_client.req(
                    'patch',
                    f'/api/v1/submissions/{work_id}/rubricitems/',
                    404,
                    data={'items': to_select + [-1]},
                    result=error_template,
                )
            else:
                # Unknown row id
                test_client.req(
                    'patch',
                    f'/api/v1/submissions/{work_id}/rubricitems/',
                    404,
                    data={
                        'items': [
                            to_select[0],
                            {**to_select[-1], 'row_id': -1},
                        ]
                    },
                    result=error_template,
                )

                # Unknown item id
                test_client.req(
                    'patch',
                    f'/api/v1/submissions/{work_id}/rubricitems/',
                    404,
                    data={
                        'items': [
                            to_select[0],
                            {**to_select[-1], 'item_id': -1},
                        ]
                    },
                    result=error_template,
                )

            # Cannot select from a rubric of a different assignment.
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work_id}/rubricitems/',
                400,
                data={
                    'items':
                        to_select + [
                            get_rubric_item(
                                'My header', '5points', rubric=bs_rubric
                            )
                        ]
                },
                result=error_template,
            )

    if not old_format:
        with describe('cannot use multiplier on normal rows'
                      ), logged_in(ta_user):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work_id}/rubricitems/',
                400,
                data={'items': [{**to_select[0], 'multiplier': 0.5}]},
                result=error_template,
            )

        with describe(
            'cannot use a multiplier of higher than 1.0 or lower than 0.0'
        ), logged_in(ta_user):
            for mult in [-0.5, 1.5]:
                test_client.req(
                    'patch',
                    f'/api/v1/submissions/{work_id}/rubricitems/',
                    400,
                    data={'items': [{**to_select[0], 'multiplier': mult}]},
                    result={
                        **error_template,
                        'message':
                            'A multiplier has to be between 0.0 and 1.0.',
                    }
                )


@pytest.mark.parametrize('ext', ['tar.gz'])
def test_uploading_unsafe_archive(
    logged_in, student_user, teacher_user, assignment, test_client, ext,
    error_template
):
    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            400,
            real_data={
                'file': (
                    f'{os.path.dirname(__file__)}/../test_data/'
                    f'test_submissions/unsafe.{ext}', f'unsafe.{ext}'
                )
            },
            result=error_template,
        )

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={
                'ignore': 'a\n',
            }
        )

    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission'
            '?ignored_files=error',
            400,
            real_data={
                'file': (
                    f'{os.path.dirname(__file__)}/../test_data/'
                    f'test_submissions/unsafe.{ext}', f'unsafe.{ext}'
                )
            },
            result=error_template,
        )


@pytest.mark.parametrize('ignore', [True, False])
@pytest.mark.parametrize('ext', ['tar.gz', 'zip'])
def test_uploading_invalid_file(
    logged_in, student_user, teacher_user, assignment, test_client, ignore,
    error_template, ext
):
    if ignore:
        with logged_in(teacher_user):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}',
                200,
                data={
                    'ignore': 'a\n',
                }
            )

    with logged_in(student_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission' +
            ('?ignored_files=error' if ignore else ''),
            400,
            real_data={
                'file': (
                    f'{os.path.dirname(__file__)}/../test_data/'
                    f'test_submissions/single_file_work', f'arch.{ext}'
                )
            },
            result=error_template,
        )


@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        http_error(error=403)('Student2'),
        http_error(error=403)('Thomas Schaper'),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'max_grade',
    [10, 4, 15,
     http_error(error=400)('Hello'),
     http_error(error=400)(-2)],
)
@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_maximum_grade(
    logged_in, named_user, ta_user, assignment_real_works, error_template,
    max_grade, test_client, request
):
    assignment, work = assignment_real_works
    work_id = work['id']

    marker = request.node.get_closest_marker('http_error')
    code = 200 if marker is None else marker.kwargs['error']

    data = {'grade': 11}

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            400,
            data=data,
            result=error_template,
        )

    with logged_in(named_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            code,
            data={'max_grade': max_grade},
            result=error_template if code >= 400 else None
        )

    if code >= 400:
        with logged_in(ta_user):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{work_id}',
                400,
                data=data,
                result=error_template,
            )
        return

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': max_grade},
        )

        assert test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )['max_grade'] == max_grade

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            400,
            data={'grade': max_grade + 0.5},
            result=error_template
        )

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            400,
            data={'grade': -0.5},
        )

        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': max_grade},
        )

    with logged_in(named_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'max_grade': None},
        )
        assert test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )['max_grade'] is None

    with logged_in(ta_user):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            400,
            data={'grade': 10.5},
        )
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={'grade': 10},
        )


def test_all_all_file_trees(
    test_client, logged_in, admin_user, describe, session, tomorrow,
    error_template
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assignment = helpers.create_assignment(
            test_client, course, state='open', deadline=tomorrow
        )
        student1 = helpers.create_user_with_role(session, 'Student', course)
        student2 = helpers.create_user_with_role(session, 'Student', course)
        ta = helpers.create_user_with_role(session, 'TA', course)
        teacher = helpers.create_user_with_role(session, 'Teacher', course)
        sub = helpers.create_submission(
            test_client, assignment, for_user=student1
        )
        base_url = f'/api/v1/submissions/{helpers.get_id(sub)}'

        def get_trees(err=False, teacher=None, student=dict):
            return test_client.req(
                'get',
                f'{base_url}/root_file_trees/',
                err or 200,
                result=error_template if err else {
                    'student': student,
                    'teacher': teacher,
                }
            )

    with describe('Before editing both trees are the same'), logged_in(ta):
        res = get_trees(teacher=dict)
        assert res['student'] == res['teacher']
        orig_student = res['student']

    with describe('Students may not see teacher tree iff not done'):
        with logged_in(student1):
            res = get_trees(teacher=None, student=orig_student)
        with logged_in(teacher):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{helpers.get_id(assignment)}',
                200,
                data={'state': 'done'},
            )
        with logged_in(student1):
            get_trees(teacher=orig_student, student=orig_student)

    with describe('Changes in teacher tree are visible'):
        with logged_in(teacher):
            test_client.req(
                'post',
                f'/api/v1/submissions/{helpers.get_id(sub)}/files/',
                200,
                query={'path': '/f.zip/dir2/teacher_file'},
                real_data='NEW_FILE',
            )
            teacher_tree = copy.deepcopy(orig_student)
            teacher_tree['entries'][1]['entries'].append({
                'name': 'teacher_file',
                'id': str,
            })

        with logged_in(ta):
            get_trees(teacher=teacher_tree, student=orig_student)
        with logged_in(student1):
            get_trees(teacher=teacher_tree, student=orig_student)

    with describe('Other students receive do not receive any tree'
                  ), logged_in(student2):
        get_trees(err=403)
