# SPDX-License-Identifier: AGPL-3.0-only
import io
import os
import copy
import json
import uuid
import random
import tarfile
import datetime
import tempfile
import dataclasses
from collections import defaultdict

import flask
import pytest
from freezegun import freeze_time
from sqlalchemy.sql import func as sql_func

import psef
import helpers
import psef.models as m
from helpers import (
    get_id, create_course, create_marker, create_auto_test, create_assignment,
    create_submission, create_user_with_perms, get_newest_submissions
)
from cg_dt_utils import DatetimeWithTimezone
from psef.errors import APICodes, APIWarnings
from psef.ignore import SubmissionValidator
from psef.helpers import ensure_keys_in_dict
from psef.permissions import CoursePermission as CPerm
from psef.permissions import GlobalPermission as GPerm

# http_err = pytest.mark.http_err
perm_error = create_marker(pytest.mark.perm_error)
http_err = create_marker(pytest.mark.http_err)


def get_submission_archive(name):
    return f'{os.path.dirname(__file__)}/../test_data/test_submissions/{name}'


@pytest.fixture
def original_rubric_data():
    yield helpers.get_simple_rubric()


@pytest.fixture
def rubric(
    logged_in, teacher_user, test_client, original_rubric_data, assignment
):
    with logged_in(teacher_user):
        original = original_rubric_data
        yield test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data=original,
            result=[{
                'header': original['rows'][0]['header'],
                'description': original['rows'][0]['description'],
                'id': int,
                'items': list,
                'locked': False,
                'type': 'normal',
            }]
        )


@pytest.mark.parametrize(
    'named_user,hidden', [
        ('Thomas Schaper', True),
        ('Student1', False),
        ('nobody', False),
        perm_error(error=401)(('NOT_LOGGED_IN', False)),
    ],
    indirect=['named_user']
)
def test_get_all_assignments(
    named_user, hidden, test_client, logged_in, request, error_template
):
    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(named_user):
        assigs = test_client.req('get', '/api/v1/assignments/', error or 200)
        has_hidden = False
        if not error:
            for assig in assigs:
                ensure_keys_in_dict(
                    assig, [('id', int), ('state', str), ('description', str),
                            ('created_at', str), ('name', str),
                            ('deadline', str), ('is_lti', bool),
                            ('whitespace_linter', bool), ('course', dict)]
                )
                has_hidden = has_hidden or assig['state'] == 'hidden'
            assert has_hidden == hidden


@pytest.mark.parametrize(
    'named_user,course_name,state_is_hidden,perm_err,analytics', [
        ('Thomas Schaper', 'Project Software Engineering', True, True, False),
        (
            'Thomas Schaper',
            'Project Software Engineering',
            False,
            False,
            False,
        ),
        ('Thomas Schaper', 'Programmeertalen', True, False, False),
        ('Robin', 'Programmeertalen', True, False, True),
        ('Student1', 'Programmeertalen', False, False, False),
        ('Student1', 'Project Software Engineering', False, True, False),
        ('NOT_LOGGED_IN', 'Programmeertalen', False, True, False),
    ],
    indirect=['named_user', 'course_name', 'state_is_hidden']
)
@pytest.mark.parametrize('no_course', [True, False])
def test_get_assignment(
    named_user, course_name, state_is_hidden, perm_err, test_client, logged_in,
    session, error_template, assignment, analytics, no_course
):
    with logged_in(named_user):
        if named_user == 'NOT_LOGGED_IN':
            status = 401
        else:
            status = 403 if perm_err else 200
        if status == 200:
            res = {
                'id': assignment.id,
                'state': 'hidden' if state_is_hidden else 'submitting',
                'description': '',
                'created_at': assignment.created_at.isoformat(),
                'deadline': assignment.deadline.isoformat(),
                'name': assignment.name,
                'is_lti': False,
                'lms_name': None,
                'cgignore': None,
                'cgignore_version': None,
                'course': dict,
                'course_id': assignment.course_id,
                'whitespace_linter': False,
                'done_type': None,
                'reminder_time': None,
                'done_email': None,
                'fixed_max_rubric_points': None,
                'max_grade': None,
                'group_set': None,
                'division_parent_id': None,
                'auto_test_id': None,
                'webhook_upload_enabled': False,
                'files_upload_enabled': True,
                'cool_off_period': 0.0,
                'amount_in_cool_off_period': 1,
                'max_submissions': None,
                'analytics_workspace_ids': [int] if analytics else [],
                'peer_feedback_settings': None,
                'kind': 'normal',
                'send_login_links': False,
                'available_at': None,
            }
            if no_course:
                del res['course']
        else:
            res = error_template
        url = f'/api/v1/assignments/{assignment.id}'
        if no_course:

            url += '?no_course_in_assignment=true'

        show_warn = no_course or status != 200
        test_client.req(
            'get',
            url,
            status,
            result=res,
            expected_warning=(
                False if show_warn else 'course.*will be removed.*release.*'
            )
        )


def test_get_non_existing_assignment(
    teacher_user, test_client, logged_in, error_template
):
    with logged_in(teacher_user):
        test_client.req(
            'get', f'/api/v1/assignments/0', 404, result=error_template
        )


@pytest.mark.parametrize(
    'update_data', [{
        'name': 'NEW AND UPDATED NAME',
        'state': 'open',
        'deadline': DatetimeWithTimezone.utcnow().isoformat(),
    }]
)
@pytest.mark.parametrize('keep_name', [True, False])
@pytest.mark.parametrize('keep_deadline', [True, False])
@pytest.mark.parametrize('keep_state', [True, False])
@pytest.mark.parametrize(
    'changes,err_code', [
        ({'state': 'open'}, False),
        ({'state': 'done'}, False),
        ({'state': 'hidden'}, False),
        ({'state': 'wow'}, 400),
        ({
            'state': 2,
        }, 400),
        ({'deadline': 'nodate'}, 400),
        ({'deadline': []}, 400),
        ({'name': ''}, 400),
        ({'name': 1}, 400),
    ]
)
def test_update_assignment(
    changes, err_code, keep_name, keep_deadline, keep_state, teacher_user,
    test_client, logged_in, assignment, update_data, error_template
):
    with logged_in(teacher_user):
        data = copy.deepcopy(update_data)
        assig_id = assignment.id

        for val, name in [(keep_state, 'state'), (keep_name, 'name'),
                          (keep_deadline, 'deadline')]:
            if not val:
                data.pop(name)
                if name in changes:
                    changes.pop(name)

        if not changes:
            err_code = False

        data.update(changes)

        old_state = assignment.state.name
        old_name = assignment.name
        old_deadline = assignment.deadline

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            err_code if err_code else 200,
            data=data,
            result=error_template if err_code else None
        )
        if not err_code:
            new_assig = psef.helpers.get_or_404(m.Assignment, assig_id)
            if keep_state:
                assert new_assig.state.name == data['state']
            if keep_name:
                assert new_assig.name == data['name']
            if keep_deadline:
                assert new_assig.deadline == datetime.datetime.fromisoformat(
                    data['deadline']
                )
        else:
            new_assig = psef.helpers.get_or_404(m.Assignment, assig_id)
            assert new_assig.state.name == old_state
            assert new_assig.name == old_name
            assert new_assig.deadline == old_deadline


@pytest.mark.parametrize(
    'named_user',
    [http_err(error=403)('Student1'),
     http_err(error=401)('NOT_LOGGED_IN')],
    indirect=True
)
def test_update_assignment_wrong_permissions(
    assignment,
    named_user,
    logged_in,
    test_client,
    error_template,
    request,
):
    marker = request.node.get_closest_marker('http_err')
    with logged_in(named_user):
        is_logged_in = not isinstance(named_user, str)
        res = test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            marker.kwargs['error'],
            result=error_template,
            data={
                'name': 'name',
                'state': 'open',
                'deadline': DatetimeWithTimezone.utcnow().isoformat(),
            }
        )
        res['code'] = (
            APICodes.NOT_LOGGED_IN
            if is_logged_in else APICodes.INCORRECT_PERMISSION
        )


err400 = http_err(error=400)
err404 = http_err(error=404)


@pytest.mark.parametrize(
    'item_description',
    [err400(None), 'new idesc', err400(5)]
)
@pytest.mark.parametrize('item_header', [err400(None), 'new ihead', err400(5)])
@pytest.mark.parametrize(
    'item_points',
    [err400(None), 5.3, 11, err400(-2),
     err400('Wow')]
)
@pytest.mark.parametrize(
    'row_description',
    [err400(None), 'new rdesc', err400(5)]
)
@pytest.mark.parametrize(
    'row_header',
    [err400(None), 'new rheader',
     err400(5), err400('')]
)
def test_add_rubric_row(
    item_description, item_points, row_description, row_header, assignment,
    teacher_user, logged_in, test_client, error_template, request, item_header,
    rubric
):
    row = {}
    if row_header is not None:
        row['header'] = row_header
    if row_description is not None:
        row['description'] = row_description

    item = {}
    if item_header is not None:
        item['header'] = item_header
    if item_description is not None:
        item['description'] = item_description
    if item_points is not None:
        item['points'] = item_points

    row['items'] = [item, item]

    marker = request.node.get_closest_marker('http_err')
    code = 200 if marker is None else marker.kwargs['error']

    with logged_in(teacher_user):
        data = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            status_code=code,
            data={'rows': rubric + [row]},
            result=error_template if marker else rubric + [dict],
        )
        if marker is None:
            assert len(data) == len(rubric) + 1
            assert data[-1]['header'] == row_header
            assert data[-1]['description'] == row_description
            assert len(data[-1]['items']) == 2
            assert data[-1]['items'][0]['id'] > 0
            assert data[-1]['items'][0]['points'] == item_points
        else:
            test_client.req(
                'get',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                status_code=200,
                result=rubric,
            )


@pytest.mark.parametrize(
    'item_description',
    [err400(None), 'new idesc', err400(5)]
)
@pytest.mark.parametrize('item_header', [err400(None), 'new ihead', err400(5)])
@pytest.mark.parametrize('item_points', [err400(None), 5.3, 11, err400('Wow')])
@pytest.mark.parametrize('row_description', [None, 'new rdesc', err400(5)])
@pytest.mark.parametrize('row_header', [None, 'new rheader', err400(5)])
def test_update_rubric_row(
    item_description, item_points, row_description, row_header, assignment,
    teacher_user, logged_in, test_client, error_template, request, item_header,
    rubric
):
    row = {}
    if row_header is not None:
        row['header'] = row_header
    if row_description is not None:
        row['description'] = row_description

    item = {}
    if item_header is not None:
        item['header'] = item_header
    if item_description is not None:
        item['description'] = item_description
    if item_points is not None:
        item['points'] = item_points

    row['items'] = [item, item]

    marker = request.node.get_closest_marker('http_err')
    code = 200 if marker is None else marker.kwargs['error']

    with logged_in(teacher_user):
        new_rubric = copy.deepcopy(rubric)
        new_rubric[0].update(row)

        data = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            status_code=code,
            data={'rows': new_rubric},
            result=error_template if marker else [dict],
        )
        if marker is None:
            assert len(data) == len(rubric)
            assert data[0]['header'] == row_header or rubric[0]['header']
            assert data[0]['description'
                           ] == row_description or rubric[0]['description']
            assert len(data[0]['items']) == 2
            assert data[0]['items'][0]['id'] > 0
            assert data[0]['items'][0]['points'] == item_points
            assert data[0]['items'][0]['header'] == item_header
            assert data[0]['items'][0]['description'] == item_description
        else:
            test_client.req(
                'get',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                status_code=200,
                result=rubric,
            )


@pytest.mark.parametrize('item_id', [err404(-1), None, err404(1000)])
@pytest.mark.parametrize('item_description', [err400(None), 'new idesc'])
@pytest.mark.parametrize('item_header', [err400(None), 'new ihead'])
@pytest.mark.parametrize('item_points', [err400(None), 2])
def test_update_rubric_item(
    item_description, item_points, assignment, teacher_user, logged_in,
    test_client, error_template, request, rubric, item_id, item_header
):
    new_rubric = copy.deepcopy(rubric)
    old_rubric = copy.deepcopy(rubric)

    row = new_rubric[0]

    item = {}
    if item_header is not None:
        item['header'] = item_header
    if item_description is not None:
        item['description'] = item_description
    if item_points is not None:
        item['points'] = item_points
    if item_id is not None:
        item['id'] = item_id
    else:
        item['id'] = row['items'][0]['id']

    row['items'][0] = item

    marker = request.node.get_closest_marker('http_err')
    code = 200 if marker is None else marker.kwargs['error']

    with logged_in(teacher_user):
        data = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            status_code=code,
            data={'rows': new_rubric},
            result=error_template if marker else [dict],
        )
        if marker is None:
            assert len(data) == len(rubric)
            assert data[0]['items'][0]['id'] == old_rubric[0]['items'][0]['id']
            assert data[0]['items'][0]['points'] == item_points
            assert data[0]['items'][0]['header'] == item_header
            assert data[0]['items'][0]['description'] == item_description
        else:
            test_client.req(
                'get',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                status_code=200,
                result=rubric,
            )


@pytest.mark.parametrize(
    'row_type',
    [err404(None), 'normal', err404('unknown')]
)
@pytest.mark.parametrize('item_description', [err400(None), 'You did well'])
@pytest.mark.parametrize('item_header', [err400(None), 'You very well'])
@pytest.mark.parametrize('item_points', [err400(None), 5.3, 5, err400('Wow')])
@pytest.mark.parametrize(
    'row_description',
    [err400(None), 'A row desc', err400(5)]
)
@pytest.mark.parametrize(
    'row_header',
    [err400(None), 'A row header', err400(5)]
)
def test_get_and_add_rubric_row(
    item_description, item_points, row_description, row_header, assignment,
    teacher_user, logged_in, test_client, error_template, request, item_header,
    row_type
):
    row = {'type': row_type}
    if row_header is not None:
        row['header'] = row_header
    if row_description is not None:
        row['description'] = row_description
    item = {}
    if item_header is not None:
        item['header'] = item_header
    if item_description is not None:
        item['description'] = item_description
    if item_points is not None:
        item['points'] = item_points
    for item in [item] if item else [item, None]:
        if item is not None:
            row['items'] = [item]
        marker = request.node.get_closest_marker('http_err')
        code = 200 if marker is None else marker.kwargs['error']
        res = [{
            'id': int,
            'header': row['header'],
            'description': row['description'],
            'items': [{
                'id': int,
                'description': item['description'],
                'header': item['header'],
                'points': item['points'],
            }],
            'locked': False,
            'type': row['type'],
        }] if marker is None else error_template
        res = res if marker is None else error_template

        with logged_in(teacher_user):
            test_client.req(
                'put',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                code,
                result=res,
                data={'rows': [row]}
            )
            test_client.req(
                'get',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                200 if marker is None else 404,
                result=res,
            )


@pytest.mark.parametrize(
    'named_user', [
        'Robin',
        http_err(error=403)('Thomas Schaper'),
        http_err(error=403)('Student1'),
        http_err(error=401)('NOT_LOGGED_IN')
    ],
    indirect=True
)
def test_delete_rubric(
    assignment, named_user, logged_in, test_client, error_template, request,
    teacher_user, rubric
):
    marker = request.node.get_closest_marker('http_err')
    code = 204 if marker is None else marker.kwargs['error']

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            code,
            result=marker if marker is None else error_template,
        )
    if marker is None:
        with logged_in(named_user):
            test_client.req(
                'get',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                404,
                result=error_template,
            )
            test_client.req(
                'delete',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                404,
                result=error_template,
            )
    else:
        with logged_in(teacher_user):
            test_client.req(
                'get',
                f'/api/v1/assignments/{assignment.id}/rubrics/',
                200,
                result=rubric
            )


@pytest.mark.parametrize(
    'named_user',
    [http_err(error=403)('Student1'),
     http_err(error=401)('NOT_LOGGED_IN')],
    indirect=True
)
def test_update_add_rubric_wrong_permissions(
    assignment,
    named_user,
    logged_in,
    test_client,
    error_template,
    request,
    teacher_user,
):
    marker = request.node.get_closest_marker('http_err')
    rubric = {
        'header': f'My header', 'description': f'My description', 'items': [{
            'header': 'The header',
            'description': f'item description',
            'points': 2,
        }, ]
    }
    with logged_in(named_user):
        res = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            marker.kwargs['error'],
            result=error_template,
            data={'rows': [rubric]}
        )
        res['code'] = (
            APICodes.NOT_LOGGED_IN
            if marker.kwargs['error'] == 401 else APICodes.INCORRECT_PERMISSION
        )
    with logged_in(teacher_user):
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            data={'rows': [rubric]}
        )
    with logged_in(named_user):
        res = test_client.req(
            'put',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            marker.kwargs['error'],
            result=error_template,
            data=res
        )
        res['code'] = (
            APICodes.NOT_LOGGED_IN
            if marker.kwargs['error'] == 401 else APICodes.INCORRECT_PERMISSION
        )
    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/rubrics/',
            200,
            result=rubric
        )


def test_creating_wrong_rubric(
    request,
    test_client,
    logged_in,
    error_template,
    teacher_user,
    assignment,
    session,
    course_name,
):
    assig_id = assignment.id

    with logged_in(teacher_user):
        rubric = {
            'rows': [{
                'header': 'My header',
                'description': 'My description',
                'items': [{
                    'description': '5points',
                    'points': 5
                }, {
                    'description': '10points',
                    'points': 10,
                }]
            }, {
                'header': 'My header2',
                'description': 'My description',
                'items': [{
                    'description': '10points',
                    'points': -10,
                }, {
                    'description': '5points',
                    'points': -15
                }],
            }]
        }  # yapf: disable
        test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            400,
            data=rubric,
            result=error_template,
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            404,
            result=error_template,
        )
        rubric = {
            'rows': [{
                'header': 'My header',
                'description': 'My description',
                'items': [{
                    'description': '5points',
                    'points': -5
                }, {
                    'description': '10points',
                    'points': -10,
                }]
            }]
        }  # yapf: disable
        test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            400,
            data=rubric,
            result=error_template,
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            404,
            result=error_template,
        )
        rubric = {
            'rows': [{
                'header': 'My header',
                'description': 'My description',
                'items': []
            }]
        }  # yapf: disable
        test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            400,
            data=rubric,
            result=error_template,
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            404,
            result=error_template,
        )
        rubric = {
            'rows': []
        }  # yapf: disable
        test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            400,
            data=rubric,
            result=error_template,
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            404,
            result=error_template,
        )


def test_updating_wrong_rubric(
    request,
    test_client,
    logged_in,
    error_template,
    teacher_user,
    assignment,
    session,
    course_name,
):
    assig_id = assignment.id
    with logged_in(teacher_user):
        rubric = {
            'rows': [{
                'header': 'My header',
                'description': 'My description',
                'items': [{
                    'description': '5points',
                    'header': 'head5',
                    'points': 5
                }, {
                    'description': '10points',
                    'header': 'head10',
                    'points': 10,
                }]
            }]
        }  # yapf: disable
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            200,
            data=rubric,
        )
        server_rubric = copy.deepcopy(rubric)

        rubric[0]['items'][1]['points'] = 7
        rubric.append({
            'header': 'head', 'description': '22', 'items': [{
                'description': '-7points',
                'points': -7,
            }]
        })
        test_client.req(
            'put',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            400,
            data=rubric,
            result=error_template,
        )
        rubric = test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/rubrics/',
            200,
            result=server_rubric
        )


@pytest.mark.parametrize(
    'max_points', [http_err(error=400)('err'),
                   http_err(error=400)(-1), 10, 2]
)
@pytest.mark.parametrize(
    'named_user', [
        http_err(error=403)('Student1'),
        http_err(error=401)('NOT_LOGGED_IN'), 'Robin'
    ],
    indirect=True
)
@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_set_fixed_max_points(
    rubric, named_user, test_client, logged_in, assignment_real_works,
    max_points, request, error_template, ta_user, session
):
    assignment, work = assignment_real_works
    work_id = work['id']
    assignment_id = assignment.id

    marker = request.node.get_closest_marker('http_err')
    code = 200 if marker is None else marker.kwargs['error']
    res = list if marker is None else error_template

    with logged_in(ta_user):
        item = rubric[0]['items'][0]
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}/rubricitems/{item["id"]}',
            204,
            result=None
        )

    if marker is None:
        with logged_in(ta_user):
            out = test_client.req('get', f'/api/v1/submissions/{work_id}', 200)
            old_grade = out['grade']

    with logged_in(named_user):
        test_client.req(
            'put',
            f'/api/v1/assignments/{assignment_id}/rubrics/',
            code,
            result=res,
            data={'max_points': max_points}
        )

    if marker is None:
        with logged_in(ta_user):
            out = test_client.req(
                'get',
                f'/api/v1/assignments/{assignment_id}',
                200,
            )
            assert out['fixed_max_rubric_points'] == max_points
            rubric = test_client.req(
                'get', f'/api/v1/submissions/{work_id}/rubrics/', 200
            )
            points = sum(i['points'] for i in rubric['selected'])
            assert out['fixed_max_rubric_points'] == rubric['points']['max']
            out = test_client.req('get', f'/api/v1/submissions/{work_id}', 200)
            assert out['grade'] == min((points / max_points) * 10, 10)

        with logged_in(named_user):
            test_client.req(
                'put',
                f'/api/v1/assignments/{assignment_id}/rubrics/',
                200,
                result=res,
                data={'max_points': None}
            )

        with logged_in(ta_user):
            out = test_client.req(
                'get',
                f'/api/v1/assignments/{assignment_id}',
                200,
            )
            assert out['fixed_max_rubric_points'] is None
            out = test_client.req('get', f'/api/v1/submissions/{work_id}', 200)
            assert out['grade'] == old_grade


# yapf: disable
@pytest.mark.parametrize(
    'name,entries,dirname,exts', [
        (
            'single_file_archive', [{
                'id': str,
                'name': 'single_file_work'
            }], 'single_file_archive', ['.tar.gz', '.tar.xz', '.zip']
        ), (
            'multiple_file_archive', [
                {
                    'id': str,
                    'name': 'single_file_work'
                }, {
                    'id': str,
                    'name': 'single_file_work_copy'
                }
            ], 'multiple_file_archive', ['.tar.gz', '.zip', '.7z']
        ), (
            'deheading_dir_archive', [
                {
                    'id': str,
                    'name': 'single_file_work'
                }, {
                    'id': str,
                    'name': 'single_file_work_copy'
                }
            ], 'dir', ['.tar.gz', '.zip', '.7z']
        ),
        (
            'single_dir_archive', [
                {
                    'id': str,
                    'name': 'single_file_work'
                }, {
                    'id': str,
                    'name': 'single_file_work_copy'
                }
            ], 'dir', ['.tar.gz', '.zip']
        ),
        (
            'rename_file_archive', [
                {
                    'id': str,
                    'name': '.cg-assignment-id-USER_PROVIDED'
                }, {
                    'id': str,
                    'name': 'single_file_work'
                }, {
                    'id': str,
                    'name': 'single_file_work_copy'
                }
            ], 'dir', ['.tar.gz']
        ),
        (
            'multiple_dir_archive', [
                {
                    'id': str,
                    'name': 'dir',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }, {
                    'id': str,
                    'name': 'dir2',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }
            ],
            'multiple_dir_archive', ['.tar.gz', '.zip', '.7z']
        ), (
            'single_file_work', [
                {
                    'name': 'single_file_work',
                    'id': str,
                }
            ],
            'top', ['']
        )
    ]
)
@pytest.mark.parametrize('assignment', ['new', 'old'], indirect=True)
@pytest.mark.parametrize('named_user', ['Student1', 'Devin Hillenius'],
                         indirect=True)
# yapf: enable
def test_upload_files(
    named_user, exts, test_client, logged_in, assignment, name, entries,
    dirname, error_template, teacher_user
):
    for ext in exts:
        print(f'Testing with extension "{ext}"')
        with logged_in(named_user):
            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission',
                400,
                real_data={},
                result=error_template
            )
            assert res['message'].startswith('No file in HTTP')

            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission',
                400,
                real_data={'err': (io.BytesIO(b'my file content'), 'ror')},
                result=error_template
            )
            assert res['message'].startswith('Request did not contain')

            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission',
                400,
                real_data={
                    'file': (get_submission_archive(f'{name}{ext}'), f'')
                },
                result=error_template
            )
            assert res['message'].startswith('Request did not contain')

            if assignment.is_open or named_user.has_permission(
                CPerm.can_upload_after_deadline, assignment.course_id
            ):
                res = test_client.req(
                    'post',
                    f'/api/v1/assignments/{assignment.id}/submission',
                    201,
                    real_data={
                        'file': (
                            get_submission_archive(f'{name}{ext}'),
                            f'{name}{ext}',
                        )
                    },
                    result={
                        'id': int,
                        'user': named_user.__to_json__(),
                        'created_at': str,
                        'assignee': None,
                        'grade': None,
                        'comment': None,
                        'comment_author': None,
                        'grade_overridden': False,
                        'assignment_id': assignment.id,
                        'origin': 'uploaded_files',
                        'extra_info': None,
                        'rubric_result': None,
                    }
                )

                test_client.req(
                    'get',
                    f'/api/v1/submissions/{res["id"]}/files/',
                    200,
                    result={
                        'entries': entries,
                        'id': str,
                        'name': f'{name}{ext}' if ext else 'top',
                    }
                )

            else:
                res = test_client.req(
                    'post',
                    f'/api/v1/assignments/{assignment.id}/submission',
                    403,
                    real_data={
                        'file': (
                            get_submission_archive(f'{name}{ext}'),
                            f'{name}{ext}'
                        )
                    },
                    result=error_template
                )


@pytest.mark.parametrize(
    'name,warning', [
        (
            'single_symlink_archive.tar.gz',
            APIWarnings.SYMLINK_IN_ARCHIVE.value
        ),
    ]
)
def test_archive_with_symlinks(
    student_user, test_client, logged_in, assignment, name, error_template,
    warning, session, app
):
    with logged_in(student_user):
        sub, res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            201,
            real_data={'file': (get_submission_archive(name), name)},
            result=dict,
            include_response=True
        )

        assert 'Warning' in res.headers
        assert res.headers['Warning'].startswith(f'{warning:03d}')

        tree = test_client.req(
            'get', f'/api/v1/submissions/{sub["id"]}/files/', 200, result=dict
        )

        file = tree['entries'][0]
        file = session.query(
            m.File
        ).filter(m.File.id == tree['entries'][0]['id']).first()
        file = os.path.join(app.config['UPLOAD_DIR'], file.filename)

        assert os.path.exists(file)
        assert not os.path.islink(file)
        assert open(file).read() != ''


@pytest.mark.parametrize('name', ['single_file_archive.tar.gz'])
@pytest.mark.parametrize('assignment', ['new', 'old'], indirect=True)
@pytest.mark.parametrize('after_deadline', [True, False])
@pytest.mark.parametrize(
    'author', [
        'student1',
        http_err(error=404)('DOES_NOT_EXIST'),
        http_err(error=403)('admin')
    ]
)
@pytest.mark.parametrize(
    'named_user',
    [
        http_err(error=403)('Student1'),
        'Devin Hillenius',
        http_err(error=403, stop=True)('admin'),
    ],
    indirect=True,
)
def test_upload_for_other(
    named_user, test_client, logged_in, assignment, name, error_template,
    teacher_user, after_deadline, author, session, request
):
    code = 201
    res = None
    marker = None
    for marker in request.node.iter_markers('http_err'):
        res = error_template
        code = marker.kwargs['error']
        if marker.kwargs.get('stop', False):
            break

    if (
        named_user.username == author and named_user.name == 'Student1' and
        assignment.deadline > DatetimeWithTimezone.utcnow()
    ):
        code = 201
        marker = None
        res = None

    if (
        marker is None and not after_deadline and
        assignment.deadline < DatetimeWithTimezone.utcnow()
    ):
        marker = True
        code = 403
        res = error_template
        named_user.courses[assignment.course_id].set_permission(
            CPerm.can_upload_after_deadline, False
        )

    with logged_in(named_user):
        res = test_client.req(
            'post', (
                f'/api/v1/assignments/{assignment.id}/submission?'
                f'extended&author={author}'
            ),
            code,
            real_data={'file': (get_submission_archive(name), name)},
            result=res
        )
        if not marker:
            assert res['user']['username'] == author


def test_incorrect_ingore_files_value(
    student_user, test_client, error_template, logged_in, assignment
):
    filestr = b'0' * 2 * 2 ** 3
    with logged_in(student_user):
        res = test_client.req(
            'post', (
                f'/api/v1/assignments/{assignment.id}/'
                'submission?ignored_files=err'
            ),
            400,
            real_data={'file': (io.BytesIO(filestr), f'filename')},
            result=error_template
        )
        assert res['message'].startswith('The given value for "ignored_files"')


@pytest.mark.parametrize(
    'get_data_func', [
        lambda: {'file': (io.BytesIO(b'0' * 2 * 2 ** 20), 'filename')},
        lambda: {
            'file1': (io.BytesIO(b'0' * int(0.9 * 2 ** 20)), 'filename1'),
            'file2': (io.BytesIO(b'0' * int(0.9 * 2 ** 20)), 'filename2'),
            'file3': (io.BytesIO(b'0' * int(0.9 * 2 ** 20)), 'filename3'),
            'file4': (io.BytesIO(b'0' * int(0.9 * 2 ** 20)), 'filename4'),
            'file5': (io.BytesIO(b'0' * int(0.9 * 2 ** 20)), 'filename5'),
        },
        lambda: {
            'file1': (get_submission_archive('larger_file.zip'), 'f1.zip'),
            'file2': (get_submission_archive('larger_file.zip'), 'f2.zip'),
            'file3': (get_submission_archive('larger_file.zip'), 'f3.zip'),
            'file4': (get_submission_archive('larger_file.zip'), 'f4.zip'),
            'file5': (get_submission_archive('larger_file.zip'), 'f5.zip'),
        },
        lambda:
        {'file': (get_submission_archive('too_large.tar.gz'), 'l.tar.gz')},
        lambda: {'file': (get_submission_archive('too_large.zip'), 'l.zip')},
        lambda: {'file': (get_submission_archive('too_large.7z'), 'l.7z')},
        lambda: {
            'file': (
                get_submission_archive('many_larger_files.tar.gz'), 'l.tar.gz'
            )
        },
        lambda:
        {'file': (get_submission_archive('many_larger_files.zip'), 'l.zip')},
        lambda:
        {'file': (get_submission_archive('many_larger_files.7z'), 'l.7z')},
        lambda: {
            'file': (
                get_submission_archive('archive_with_large_file.tar.gz'),
                'l.tar.gz'
            )
        },
        lambda: {
            'file': (
                get_submission_archive('archive_with_large_file.zip'), 'l.zip'
            )
        },
        lambda: {
            'file':
                (get_submission_archive('archive_with_large_file.7z'), 'l.7z')
        },
    ]
)
def test_upload_too_large_file(
    student_user, test_client, error_template, logged_in, assignment,
    get_data_func
):
    with logged_in(student_user):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            400,
            real_data=get_data_func(),
            result=error_template
        )
        assert 'larger than the maximum' in res['message']


def test_upload_archive_with_dev_file(
    student_user, test_client, error_template, logged_in, assignment
):
    with logged_in(student_user):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            400,
            real_data={
                'file': (
                    get_submission_archive('non_normal_files.tar.gz'),
                    'arch.tar.gz'
                )
            },
            result=error_template
        )
        assert res['message'].startswith(
            'The given archive contains invalid or too many'
        )


@pytest.mark.parametrize('ext', ['tar.gz', 'zip'])
def test_upload_archive_with_many_files(
    student_user, test_client, error_template, logged_in, assignment,
    monkeypatch, app, ext
):
    monkeypatch.setitem(app.config, 'MAX_NUMBER_OF_FILES', 4)
    with logged_in(student_user):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            400,
            real_data={
                'file': (
                    get_submission_archive(f'multiple_dir_archive.{ext}'),
                    f'arch.{ext}'
                )
            },
            result=error_template
        )
        assert res['message'].startswith(
            'The given archive contains invalid or too many'
        )


@pytest.mark.parametrize('ignored_files', ['keep', None, 'delete', 'error'])
def test_upload_empty_archive(
    student_user, test_client, error_template, logged_in, assignment,
    ignored_files
):
    filename = get_submission_archive('empty_submission.tar.gz')
    with logged_in(student_user):
        url = f'/api/v1/assignments/{assignment.id}/submission'
        if ignored_files is not None:
            url = f'{url}?ignored_files={ignored_files}'
        res = test_client.req(
            'post',
            url,
            400,
            real_data={'file': (filename, 'ar.tar.gz')},
            result=error_template
        )
        assert res['message'].startswith('No files found')


@pytest.mark.parametrize('named_user', ['Robin'], indirect=True)
@pytest.mark.parametrize(
    'graders', [
        (['Thomas Schaper', 'Devin Hillenius']),
        (['Devin Hillenius']),
        http_err(error=400)(['Thomas Schaper', -1]),
        http_err(error=400)(['Thomas Schaper', 'Student1']),
        http_err(error=400)(['Student1']),
        http_err(error=400)(['Student1', 'Devin Hillenius']),
        http_err(error=400)(['Devin Hillenius', 'admin']),
    ]
)
@pytest.mark.parametrize('with_works', [True, False], indirect=True)
def test_divide_assignments(
    assignment, graders, named_user, logged_in, test_client, error_template,
    request, with_works
):
    marker = request.node.get_closest_marker('http_err')
    code = 204 if marker is None else marker.kwargs['error']
    res = None if marker is None else error_template

    grader_ids = []
    for grader in graders:
        if isinstance(grader, int):
            grader_ids.append(grader)
        else:
            grader_ids.append(m.User.query.filter_by(name=grader).one().id)
    with logged_in(named_user):
        assigs = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
        )
        for assig in assigs:
            assert assig['assignee'] is None
        assert with_works == bool(assigs)

        if code == 204:
            gid = grader_ids[0]
            for d in [{gid: '1'}, {gid: 'boe'}]:
                test_client.req(
                    'patch',
                    f'/api/v1/assignments/{assignment.id}/divide',
                    400,
                    result=error_template,
                    data={'graders': d}
                )

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            code,
            result=res,
            data={'graders': {i: 1
                              for i in grader_ids}}
        )
        assigs = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
        )
        seen = set()
        graders_seen = set()
        for assig in assigs:
            if assig['user']['username'] in seen:
                continue
            else:
                seen.add(assig['user']['username'])
            if marker is None:
                assert assig['assignee']['id'] in grader_ids
                graders_seen.add(assig['assignee']['id'])
            else:
                assert assig['assignee'] is None

        if with_works and marker is None:
            assert graders_seen == set(grader_ids)

        if with_works and code == 204 and len(grader_ids) == 2:
            grader_assigs = defaultdict(lambda: set())
            seen = set()
            for assig in assigs:
                if assig['user']['username'] in seen:
                    continue
                seen.add(assig['user']['username'])
                grader_assigs[assig['assignee']['id']].add(assig['id'])
            assert (
                len(grader_assigs[grader_ids[0]]) == len(
                    grader_assigs[grader_ids[1]]
                )
            )
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}/divide',
                code,
                result=res,
                data={
                    'graders': {i: j
                                for i, j in zip(grader_ids, [1.5, 3.0])}
                }
            )
            assigs = test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
            )
            grader_assigs2 = defaultdict(lambda: set())
            seen = set()
            for assig in assigs:
                if assig['user']['username'] in seen:
                    continue
                seen.add(assig['user']['username'])
                grader_assigs2[assig['assignee']['id']].add(assig['id'])
            assert (
                len(grader_assigs2[grader_ids[0]]) <
                len(grader_assigs2[grader_ids[1]])
            )
            assert grader_assigs[grader_ids[0]].issuperset(
                grader_assigs2[grader_ids[0]]
            )
            assert grader_assigs[grader_ids[1]].issubset(
                grader_assigs2[grader_ids[1]]
            )
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}/divide',
                code,
                result=res,
                data={'graders': {i: j
                                  for i, j in zip(grader_ids, [1.5, 3])}}
            )
            assert assigs == test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
            )

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            data={'graders': {}}
        )
        for assig in test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
        ):
            assert assig['assignee'] is None


def test_divide_assignment_negative_weights(
    teacher_user, logged_in, test_client, error_template, assignment
):
    users_roles = filter(
        lambda user_role: user_role[1].has_permission(CPerm.can_grade_work),
        assignment.course.get_all_users_in_course(
            include_test_students=False,
        ).all(),
    )
    users = [user_role[0] for user_role in users_roles]

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            400,
            result=error_template,
            data={
                'graders': {str(users[0].id): -1},
            },
        )

        res = test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            400,
            result=error_template,
            data={
                'graders': {
                    str(user.id): (i % 3) - 1
                    for i, user in enumerate(users)
                },
            },
        )
        negative_ids = [user.id for i, user in enumerate(users) if i % 3 == 0]
        positive_ids = [user.id for i, user in enumerate(users) if i % 3 != 0]
        for id in negative_ids:
            assert str(id) in res['description']
        for id in positive_ids:
            assert str(id) not in res['description']


def test_divide_non_existing_assignment(
    teacher_user, logged_in, test_client, error_template
):
    with logged_in(teacher_user):
        test_client.req(
            'patch', f'/api/v1/assignments/0/divide', 404, error_template
        )


def test_divide_test_student_submission(
    teacher_user, logged_in, test_client, assignment, describe, tomorrow
):
    users_roles = filter(
        lambda user_role: user_role[1].has_permission(CPerm.can_grade_work),
        assignment.course.get_all_users_in_course(
            include_test_students=False,
        ).all(),
    )
    users = [user_role[0] for user_role in users_roles]

    with logged_in(teacher_user):
        with describe('existing test submissions will not be divided'):
            test_sub = create_submission(
                test_client,
                assignment.id,
                is_test_submission=True,
            )

            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}/divide',
                204,
                data={
                    'graders': {str(user.id): 1
                                for user in users},
                },
            )

            res = test_client.req(
                'get',
                f'/api/v1/submissions/{test_sub["id"]}',
                200,
                result={
                    'assignee': None,
                    '__allow_extra__': True,
                },
            )

        with describe('new submissions will not be divided'):
            test_sub = create_submission(
                test_client,
                assignment.id,
                is_test_submission=True,
            )
            assert test_sub['assignee'] is None

        with describe(
            'connecting a division parent will not assign to test submission'
        ):
            assig2 = create_assignment(
                test_client, assignment.course.id, deadline=tomorrow
            )

            test_sub = create_submission(
                test_client,
                assig2['id'],
                is_test_submission=True,
            )

            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig2["id"]}/division_parent',
                204,
                data={
                    'parent_id': assignment.id,
                },
            )

            res = test_client.req(
                'get',
                f'/api/v1/submissions/{test_sub["id"]}',
                200,
                result={
                    'assignee': None,
                    '__allow_extra__': True,
                },
            )


@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_reminder_email_divide(
    teacher_user,
    logged_in,
    test_client,
    assignment,
    stubmailer,
    monkeypatch_celery,
):
    assig_id = assignment.id
    graders_done_query = m.AssignmentGraderDone.query.filter_by(
        assignment_id=assig_id
    )

    def get_graders():
        with logged_in(teacher_user):
            return test_client.req(
                'get',
                f'/api/v1/assignments/{assig_id}/graders/',
                200,
                result=list
            )

    graders = get_graders()

    with logged_in(teacher_user):
        graders = get_graders()
        random.shuffle(graders)
        grader_done = graders[0]['id']
        grader_done2 = graders[1]['id']
        print('grader_done:', graders[0])
        print('grader_done2:', graders[1])

        assert len(graders) > 2, (
            'To run this test we '
            'should have atleast 3 graders'
        )

        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done2}/done',
            204,
        )

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            data={'graders': {g['id']: 1
                              for g in graders[:2]}}
        )

        assert stubmailer.called == 2, (
            'Only the graders that were done should have been mailed'
        )
        assert not graders_done_query.all(), """
        Nobody should be done after this.
        """
        stubmailer.reset()

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            data={'graders': {g['id']: 1
                              for g in graders[:3]}}
        )
        assert not stubmailer.called, (
            'As the grader should have less assignments assigned (1/3 now '
            'instead of 1/2 before) no mail should have been send'
        )
        stubmailer.reset()

        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{graders[2]["id"]}/done',
            204,
        )

        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
        )
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            data={'graders': {grader_done: 1}}
        )
        assert stubmailer.called == 1, (
            'Make sure user is mailed even if it had assigned submissions '
            'and new submissions were from graders that were done'
        )

        new_graders = get_graders()
        for g in new_graders:
            if g['id'] in {grader_done, grader_done2}:
                assert not g['done'], (
                    'The done status of grader_done and grader_done2 should '
                    'be reset by the notification emails'
                )
            elif g['id'] == graders[2]['id']:
                assert g['done'], 'The third grader should still be done'
            else:
                assert not g['done'], "All the other graders shouldn't be done"


@pytest.mark.parametrize(
    'with_assignees',
    [['Devin Hillenius'], ['Thomas Schaper', 'Devin Hillenius'], []]
)
@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        http_err(error=403)('Student1'),
        http_err(error=401)('NOT_LOGGED_IN')
    ],
    indirect=True
)
@pytest.mark.parametrize('with_works', [True, False], indirect=True)
def test_get_all_graders(
    named_user,
    assignment,
    logged_in,
    test_client,
    with_works,
    teacher_user,
    with_assignees,
    request,
    error_template,
):
    with logged_in(teacher_user):
        graders = []
        for grader in with_assignees:
            graders.append(m.User.query.filter_by(name=grader).one().id)
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            data={'graders': {g: 1
                              for g in graders}}
        )

    with logged_in(named_user):
        marker = request.node.get_closest_marker('http_err')
        code = 200 if marker is None else marker.kwargs['error']
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/graders/',
            code,
            result=[
                {
                    'name': 'b',
                    'id': int,
                    'weight': 0,
                    'done': False,
                },
                {
                    'name': 'Devin Hillenius',
                    'id': int,
                    'weight': float('Devin Hillenius' in with_assignees),
                    'done': False,
                },
                {
                    'name': 'Robin',
                    'id': int,
                    'weight': 0,
                    'done': False,
                },
                {
                    'name': 'Thomas Schaper',
                    'id': int,
                    'weight': int('Thomas Schaper' in with_assignees),
                    'done': False,
                },
            ] if marker is None else error_template
        )


@pytest.mark.parametrize('state_is_hidden', [True, False])
@pytest.mark.parametrize('with_works', [True, False, 'single'])
@pytest.mark.parametrize(
    'named_user', [
        http_err(error=403)('admin'),
        http_err(error=401)('NOT_LOGGED_IN'),
        'Devin Hillenius',
        pytest.param(
            'Student1',
            marks=[
                pytest.mark.no_grade,
                pytest.mark.no_others,
                pytest.mark.no_hidden,
            ]
        ),
    ],
    indirect=True
)
@pytest.mark.parametrize('extended', [True, False])
def test_get_all_submissions(
    with_works,
    state_is_hidden,
    named_user,
    logged_in,
    test_client,
    request,
    assignment,
    error_template,
    extended,
):
    marker = request.node.get_closest_marker('http_err')
    no_hide = request.node.get_closest_marker('no_hidden')
    no_grade = request.node.get_closest_marker('no_grade')

    with logged_in(named_user):
        if no_hide and state_is_hidden:
            code = 403
        elif marker is None:
            code = 200
            works = m.Work.query.filter_by(assignment_id=assignment.id)
            if request.node.get_closest_marker('no_others') is not None:
                works = works.filter_by(user_id=named_user.id)

            res = []
            for work in sorted(
                works, key=lambda w: w.created_at, reverse=True
            ):
                res.append({
                    'assignee': None if no_hide else work.assignee,
                    'grade': None if no_grade else work.grade,
                    'id': work.id,
                    'user': dict,
                    'created_at': work.created_at.isoformat(),
                    'grade_overridden': False,
                    'origin': 'uploaded_files',
                    'extra_info': None,
                })
                if extended:
                    res[-1]['comment'] = None if no_grade else work.comment
                    res[-1]['comment_author'] = (
                        None if no_grade or not work.comment else dict
                    )
                    res[-1]['assignment_id'] = int
                    res[-1]['rubric_result'] = None
        else:
            code = marker.kwargs['error']

        print(named_user if isinstance(named_user, str) else named_user.name)
        url = f'/api/v1/assignments/{assignment.id}/submissions/'
        if extended:
            url += '?extended'
        test_client.req(
            'get', url, code, result=res if code == 200 else error_template
        )


# yapf: disable
@pytest.mark.parametrize(
    'named_user', ['Robin',
                   http_err(error=403)('Student1')],
    indirect=True
)
@pytest.mark.parametrize(
    'filename,result', [
        (
            'correct.tar.gz', {
                'Student1': {
                        'entries': [{
                                    'name': 'Single file',
                                    'id': str
                                }, {
                                    'name': 'Tuple_file_1',
                                    'id': str
                                }],
                        'name': 'top',
                        'id': str,
                        'username': '0000001',
                },
                'New User': {
                        'entries': [{
                                    'name': 'Single file',
                                    'id': str
                                }, {
                                    'name': 'Tuple_file_3',
                                    'id': str
                                }],
                        'name': 'top',
                        'id': str,
                        'username': '0000003',
                },
                'Student2': {
                        'entries': [{
                                    'name': 'Single file',
                                    'id': str
                                }, {
                                    'name': 'Tuple_file_2',
                                    'id': str
                                }],
                        'name': 'top',
                        'id': str,
                        'username': '0000002',
                },
            }
        ),
        (
            'correct_difficult.tar.gz', {
                'Student1': {
                        'entries': [{
                                    'name': '__WARNING__',
                                    'id': str,
                                }, {
                                    'name': '__WARNING__ (User)',
                                    'id': str,
                                }, {
                                    'name': 'Single file',
                                    'id': str
                                }, {
                                    'name': 'Tuple_file_1',
                                    'id': str
                                }, {
                                    'name': 'wrong_archive.tar.gz',
                                    'id': str
                                }],
                        'name': 'top',
                        'id': str,
                        'username': '0000001',
                },
                'New User': {
                        'entries': [{
                                    'name': 'Single file',
                                    'id': str
                                }, {
                                    'name': 'Tuple_file_3',
                                    'id': str
                                }],
                        'name': 'top',
                        'id': str,
                        'username': 'GEEN_INT',
                },
                'Student2': {
                        'entries': [{
                                    'name': 'Single file',
                                    'id': str
                                }, {
                                    'name': 'tar_file.tar.gz',
                                    'id': str,
                                    'entries': list,
                                }, {
                                    'name': 'Tuple_file_2',
                                    'id': str
                                }],
                        'name': 'top',
                        'id': str,
                        'username': '0000002',
                },
                'Student3': {
                        'entries': [{
                                    'name': 'Comment',
                                    'id': str
                                }],
                        'name': 'top',
                        'id': str,
                        'username': '0000004',
                },
            }
        ),
        ('incorrect_date.tar.gz', False),
        ('incorrect_filename.tar.gz', False),
        ('incorrect_info_file.tar.gz', False),
        ('incorrect_missing_files.tar.gz', False),
        ('incorrect_missing_index_files.tar.gz', False),
        ('incorrect_no_archive', False),
    ]
)
# yapf: enable
def test_upload_blackboard_zip(
    test_client, logged_in, named_user, assignment, filename, result,
    error_template, request, teacher_user, session, stubmailer
):
    course_id = assignment.course_id

    def get_student_users():
        users = test_client.req(
            'get', f'/api/v1/courses/{course_id}/users/', 200, list
        )
        return set(
            u['User']['name'] for u in users
            if u['CourseRole']['name'] == 'Student'
        )

    with logged_in(teacher_user):
        create_auto_test(test_client, assignment)

    marker = request.node.get_closest_marker('http_err')
    with logged_in(named_user):
        if marker is not None:
            code = marker.kwargs['error']
        elif result:
            code = 204
        else:
            code = 400

        if code == 204:
            crole = m.CourseRole.query.filter_by(
                name='Student', course_id=course_id
            ).one()
            session.query(
                m.user_course,
            ).filter(m.user_course.c.course_id == crole.id).delete(False)
            session.commit()
            session.query(m.User).filter_by(name='Student1').update({
                'username': result['Student1']['username']
            })
            assert get_student_users() == set()

        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            400 if marker is None else code,
            real_data={},
            result=error_template
        )
        if marker is None:
            assert res['message'].startswith('No file in HTTP')

        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            400 if marker is None else code,
            real_data={'err': (io.BytesIO(b'my file content'), 'ror')},
            result=error_template
        )

        filename = (
            f'{os.path.dirname(__file__)}/'
            f'../test_data/test_blackboard/{filename}'
        )
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            code,
            real_data={'file': (filename, 'bb.tar.gz')},
            result=error_template if code != 204 else None
        )
        res = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
        )

        assert not [
            r.work.assignment_id == assignment.id
            for r in m.AutoTestResult.query
        ]

        if marker is None and result:
            assert res
            assert len(res) == len(result)
            for item in res:
                assert item['user']['name'] in result
                name = item['user']['name']
                username = result[name]['username']
                del result[name]['username']
                test_client.req(
                    'get',
                    f'/api/v1/submissions/{item["id"]}/files/',
                    200,
                    result=result[name]
                )
                found_us = m.User.query.filter_by(name=name).all()
                assert any(u.username == username for u in found_us)

                with logged_in(teacher_user):
                    student_users = get_student_users()
                    print(student_users, result)
                    assert student_users == set(result.keys())
        else:
            assert not res

    assert not stubmailer.called, (
        'As we never divided no users should have been mailed'
    )
    assert not m.AssignmentGraderDone.query.filter_by(
        assignment_id=assignment.id
    ).all(), 'Nobody should be done'


@pytest.mark.parametrize('with_works', [False], indirect=True)
def test_assigning_after_uploading(
    test_client, logged_in, assignment, error_template, teacher_user
):
    for user in ['Student1', 'Student2', 'Student3']:
        with logged_in(m.User.query.filter_by(name=user).one()):
            test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission',
                201,
                real_data={
                    'file': (
                        get_submission_archive('multiple_dir_archive.zip'),
                        f'single_file_work.zip'
                    )
                },
                result=dict,
            )
    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            data={
                'graders': {
                    i.id: 1
                    for i in m.User.query.
                    filter(m.User.name.in_(['Thomas Schaper', 'Robin']))
                }
            }
        )
        assigs = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
        )
        counts = defaultdict(lambda: 0)
        for assig in assigs:
            counts[assig['assignee']['id']] += 1

    amounts = list(counts.values())
    assert max(amounts) == 2
    assert abs(amounts[0] - amounts[1]) == 1
    counts = defaultdict(lambda: 0)

    with logged_in(m.User.query.filter_by(name=u'Œlµo').one()):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            201,
            real_data={
                'file': (
                    get_submission_archive('multiple_dir_archive.zip'),
                    'single_file_work.zip'
                )
            },
            result=dict,
        )

    with logged_in(teacher_user):
        olmo_by = None
        for assig in assigs:
            counts[assig['assignee']['id']] += 1
            if assig['user']['name'] == 'Œlµo':
                olmo_by = assig['assignee']['id']

    amounts = list(counts.values())
    assert max(amounts) == 2
    assert abs(amounts[0] - amounts[1]) == 1

    with logged_in(m.User.query.filter_by(name=u'Œlµo').one()):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            201,
            real_data={
                'file': (
                    get_submission_archive('multiple_dir_archive.zip'),
                    'single_file_work.zip'
                )
            },
            result=dict,
        )
    with logged_in(teacher_user):
        for assig in assigs:
            if assig['user']['name'] == 'Œlµo':
                assert olmo_by == assig['assignee']['id']


@pytest.mark.parametrize('with_works', [False], indirect=True)
def test_reset_grader_status_after_upload(
    test_client, logged_in, assignment, error_template, teacher_user, session,
    stubmailer, monkeypatch_celery
):
    graders_done_q = m.AssignmentGraderDone.query.filter_by(
        assignment_id=assignment.id
    )
    grader_done = session.query(m.User).filter_by(name='Robin').one().id

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            data={'graders': {grader_done: 1}}
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/graders/{grader_done}/done',
            204,
        )

    assert not stubmailer.called, 'No graders should have been notified now'
    assert len(graders_done_q.all()), 'But one should be done'
    stubmailer.reset()

    for user in session.query(m.User).filter(
        m.User.name.in_([
            'Œlµo',
            'Student1',
        ])
    ):
        with logged_in(user):
            test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission',
                201,
                real_data={
                    'file': (
                        get_submission_archive('multiple_dir_archive.zip'),
                        'single_file_work.zip'
                    )
                },
                result=dict,
            )

    with logged_in(teacher_user):
        res = test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/graders/',
            200,
        )
        for g in res:
            if g['id'] == grader_done:
                assert not g['done'], 'Grader should not be done anymore'
            else:
                assert not g['done'], 'Other grader should not be done anyway'

    assert stubmailer.called == 1, 'Grader should be notified once'
    stubmailer.reset()

    olmo = m.User.query.filter_by(name=u'Œlµo').one()
    with logged_in(olmo):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            201,
            real_data={
                'file': (
                    get_submission_archive('multiple_dir_archive.zip'),
                    f'single_file_work.zip'
                )
            },
            result=dict,
        )
    assert not stubmailer.called, """
    Grader was not done so no emails should be send
    """
    assert not graders_done_q.filter_by(
        user_id=olmo.id,
    ).all(), 'Olmo should not be assigned.'


@pytest.mark.parametrize('filename', [
    'large.tar.gz',
])
def test_assign_after_blackboard_zip(
    test_client,
    logged_in,
    assignment,
    filename,
    error_template,
    request,
    teacher_user,
    stubmailer,
    monkeypatch_celery,
):
    graders_done_q = m.AssignmentGraderDone.query.filter_by(
        assignment_id=assignment.id
    )
    with logged_in(teacher_user):
        graders = m.User.query.filter(
            m.User.name.in_(['Thomas Schaper', 'Robin'])
        ).order_by(m.User.name)
        grader_done = graders[0].id

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            data={'graders': {i.id: j
                              for i, j in zip(graders, [1, 2])}}
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/graders/{grader_done}/done',
            204
        )

        filename = (
            f'{os.path.dirname(__file__)}/'
            f'../test_data/test_blackboard/{filename}'
        )

        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (filename, 'bb.tar.gz')},
        )

        assert stubmailer.called == 1, """
        Only one grader was set as done, so only one should have been called
        """
        assert not graders_done_q.all(), 'Nobody should be done anymore'
        stubmailer.reset()

        res = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
        )
        amounts = defaultdict(lambda: 0)
        lookup = {}
        for sub in res:
            amounts[sub['assignee']['id']] += 1
            lookup[sub['user']['username']] = sub['assignee']['id']

        amounts_list = sorted(list(amounts.values()))
        assert amounts_list[1] / amounts_list[0] == 2

        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (filename, 'bb.tar.gz')},
        )

        assert not stubmailer.called, (
            'The grader_done should have already been reset to not done so '
            'no emails should have been send.'
        )

        res = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}/submissions/', 200
        )
        for sub in res:
            print(sub['id'])
            assert lookup[sub['user']['username']] == sub['assignee']['id']


# yapf: disable
@pytest.mark.parametrize(
    'name,entries,dirname,exts,ignored,entries_delete', [
        (
            'multiple_dir_archive', [
                {
                    'id': str,
                    'name': 'dir',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }, {
                    'id': str,
                    'name': 'dir2',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }
            ],
            'multiple_dir_archive', ['.tar.gz', '.zip'],
            [
                    'dir2/single_file_work',
                    'dir2/single_file_work_copy',
                    'dir2/',
                    'dir/single_file_work',
            ],
            {
                'name': 'dir',
                'id': str,
                'entries': [{'name': 'single_file_work_copy', 'id': str}]
            }
        ),
        (
            'gitignore_archive', [
                {
                    'id': str,
                    'name': 'bb[]',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }, {
                    'id': str,
                    'name': 'dir',
                    'entries': [{
                        'id': str,
                        'name': '\\wow'
                    }, {
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }, {
                        'id': str,
                        'name': 'something'
                    }, {
                        'id': str,
                        'name': 'wow\\wowsers'
                    }]
                }, {
                    'id': str,
                    'name': 'sub',
                    'entries': [{
                        'id': str,
                        'name': 'dir',
                        'entries': [{
                            'id': str,
                            'name': 'file'
                        }, {
                            'id': str,
                            'name': 'file2'
                        }]
                    }]
                }, {
                    'id': str,
                    'name': 'dir2',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }, {
                    'id': str,
                    'name': 'dirl',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }, {
                    'id': str,
                    'name': 'la',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }, {
                    'id': str,
                    'name': 'za',
                    'entries': [{
                        'id': str,
                        'name': 'single_file_work'
                    }, {
                        'id': str,
                        'name': 'single_file_work_copy'
                    }]
                }
            ],
            'gitignore_archive', ['.tar.gz'],
            [
                'dir/\\wow',
                'dir2/',
                'dir2/single_file_work',
                'dir2/single_file_work_copy',
                'dirl/',
                'dirl/single_file_work',
                'dirl/single_file_work_copy',
                'za/',
                'za/single_file_work',
                'za/single_file_work_copy',
                'la/',
                'la/single_file_work',
                'la/single_file_work_copy',
                'dir/single_file_work',
                'dir/something',
                'dir/wow\\wowsers',
                'sub/dir/file',
                'sub/dir/file2',
                'bb[]/',
                'bb[]/single_file_work',
                'bb[]/single_file_work_copy',
            ],
            {'name': 'gitignore_archive',
             'id': str,
             'entries': [{
                 'name': 'dir',
                 'id': str,
                 'entries': [{'name': 'single_file_work_copy', 'id': str}]
             }, {
                 'name': 'sub',
                 'id': str,
                 'entries': [{'name': 'dir', 'id': str, 'entries': []}]
             }]}
        )
    ]
)
@pytest.mark.parametrize('named_user', ['Student1'],
                         indirect=True)
# yapf: enable
def test_ignored_upload_files(
    named_user, exts, test_client, logged_in, assignment, name, entries,
    dirname, error_template, teacher_user, ignored, entries_delete
):
    entries.sort(key=lambda a: a['name'])

    with logged_in(teacher_user):
        assig = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )
        assert assig['cgignore'] is None

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={
                'ignore':
                    '# single_file_work_copy\n'
                    '/dir[l2]/ \n'
                    'single_file_work*\n'
                    '[^dbs]*/\n'
                    '[!dsb]*/\n'
                    'somethin?\n'
                    'wow\\wowsers\n'
                    '!*copy\n'
                    'bb[]/\n'
                    '**/file\n'
                    'sub/**/file2\n'
                    '\\\\wow\n'
            }
        )
        assig = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )
        assert isinstance(assig['cgignore'], str)

    for ext in exts:
        with logged_in(named_user):
            res = test_client.req(
                'post', f'/api/v1/assignments/{assignment.id}/submission?'
                'ignored_files=error',
                400,
                real_data={
                    'file': (
                        get_submission_archive(f'{name}{ext}'), f'{name}{ext}'
                    )
                },
                result={
                    'code': 'INVALID_FILE_IN_ARCHIVE',
                    'message': str,
                    'description': str,
                    'invalid_files': list,
                    '__allow_extra__': True,
                }
            )
            assert set(ignored) == set(r[0] for r in res['invalid_files'])

            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission?'
                'ignored_files=keep',
                201,
                real_data={
                    'file': (
                        get_submission_archive(f'{name}{ext}'), f'{name}{ext}'
                    )
                },
            )
            test_client.req(
                'get',
                f'/api/v1/submissions/{res["id"]}/files/',
                200,
                result={
                    'entries': entries, 'id': str, 'name': f'{dirname}{ext}'
                }
            )

            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission?'
                'ignored_files=delete',
                201,
                real_data={
                    'file': (
                        get_submission_archive(f'{name}{ext}'), f'{name}{ext}'
                    )
                },
            )
            test_client.req(
                'get',
                f'/api/v1/submissions/{res["id"]}/files/',
                200,
                result={
                    **entries_delete,
                    'name': f'{name}{ext}',
                }
            )

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'ignore': '*'}
        )

    with logged_in(named_user):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission?'
            'ignored_files=delete',
            400,
            real_data={
                'file':
                    (get_submission_archive(f'{name}{ext}'), f'{name}{ext}')
            },
        )

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'ignore': '*\n!dir/'}
        )

    with logged_in(named_user):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission?'
            'ignored_files=delete',
            201,
            real_data={
                'file':
                    (get_submission_archive(f'{name}{ext}'), f'{name}{ext}')
            },
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{res["id"]}/files/',
            200,
            result={'name': f'{name}{ext}', 'id': str, 'entries': list},
        )

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'ignore': '*'}
        )

    with logged_in(named_user):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission?'
            'ignored_files=error',
            400,
            real_data={
                'file': (
                    get_submission_archive(f'{name}{ext}'), f'{name}'
                    # Extension is not appended to the name, so the file
                    # won't get extracted.
                )
            },
            result={
                'code': 'INVALID_FILE_IN_ARCHIVE',
                'message': str,
                'description': str,
                'invalid_files': list,
                '__allow_extra__': True,
            }
        )
        # Make sure it works when not submitting an archive
        assert set([f'{name}']) == set(r[0] for r in res['invalid_files'])

        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission?'
            'ignored_files=delete',
            400,
            real_data={
                'file': (
                    get_submission_archive(f'{name}{ext}'), f'{name}'
                    # Test without extension
                )
            },
            result={
                'code': 'NO_FILES_SUBMITTED',
                'message': str,
                'description': str,
            }
        )

        res = test_client.req(
            'post', f'/api/v1/assignments/{assignment.id}/submission?'
            'ignored_files=delete',
            400,
            real_data={
                'file':
                    (get_submission_archive(f'{name}{ext}'), f'{name}{ext}')
            },
            result={
                'code': 'NO_FILES_SUBMITTED',
                'message': str,
                'description': str,
            }
        )

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'ignore': '# Nothing'}
        )

    with logged_in(named_user):
        res = test_client.req(
            'post',
            (
                f'/api/v1/assignments/{assignment.id}/submission?'
                'ignored_files=error'
            ),
            201,
            real_data={
                'file': (
                    get_submission_archive(f'{name}{ext}'), f'{name}'
                    # Test without extension
                )
            },
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{res["id"]}/files/',
            200,
            result={
                'entries': [{'name': name, 'id': str}],
                'id': str,
                'name': 'top',
            }
        )

    with logged_in(named_user):
        res = test_client.req(
            'post',
            (
                f'/api/v1/assignments/{assignment.id}/submission?'
                'ignored_files=error'
            ),
            201,
            real_data={
                'file':
                    (get_submission_archive(f'{name}{ext}'), f'{name}{ext}')
            },
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{res["id"]}/files/',
            200,
            result={'entries': entries, 'id': str, 'name': f'{name}{ext}'}
        )


def test_ignoring_file(
    logged_in, student_user, teacher_user, assignment, test_client
):
    filename = f'file-{uuid.uuid4()}.txt'
    with logged_in(teacher_user):
        assig = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )
        assert assig['cgignore'] is None

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'ignore': '*.txt'}
        )

    with logged_in(student_user):
        test_client.req(
            'post', f'/api/v1/assignments/{assignment.id}/submission?'
            'ignored_files=error',
            400,
            real_data={
                'file': (
                    get_submission_archive(f'multiple_dir_archive.zip'),
                    filename
                )
            },
            result={
                'code': 'INVALID_FILE_IN_ARCHIVE',
                'message': str,
                'description': str,
                'invalid_files': [[filename, '*.txt']],
                '__allow_extra__': True,
            }
        )


@pytest.mark.parametrize('ext', ['tar.gz', 'zip'])
def test_ignoring_dirs_tar_archives(
    logged_in, student_user, teacher_user, assignment, test_client, ext
):
    # This tests for bug #398
    with logged_in(teacher_user):
        assig = test_client.req(
            'get', f'/api/v1/assignments/{assignment.id}', 200
        )
        assert assig['cgignore'] is None

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={'ignore': 'dir/\n'}
        )

    with logged_in(student_user):
        res = test_client.req(
            'post', f'/api/v1/assignments/{assignment.id}/submission?'
            'ignored_files=error',
            400,
            real_data={
                'file': (
                    get_submission_archive(f'multiple_dir_archive.{ext}'),
                    f'multiple_dir_archive.{ext}'
                )
            },
            result={
                'code': 'INVALID_FILE_IN_ARCHIVE',
                'message': str,
                'description': str,
                'invalid_files': list,
                '__allow_extra__': True,
            }
        )
        for f in res['invalid_files']:
            assert f[1] == 'dir/'
        assert ('dir/', 'dir/') in ((r[0], r[1]) for r in res['invalid_files'])

        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission?'
            'ignored_files=delete',
            201,
            real_data={
                'file': (
                    get_submission_archive(f'multiple_dir_archive.{ext}'),
                    f'multiple_dir_archive.{ext}'
                )
            },
        )
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{res["id"]}/files/',
            200,
            result={'entries': list, 'id': str, 'name': str}
        )
        for entry in res['entries']:
            assert entry['name'] != 'dir'


def test_cgignore_permission(
    teacher_user, session, test_client, error_template, assignment, logged_in
):
    teacher_user.courses[assignment.course_id].set_permission(
        CPerm.can_edit_cgignore,
        False,
    )

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            403,
            data={'ignore': '*\n!dir/'},
            result=error_template,
        )


@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_warning_grader_done(
    test_client, logged_in, request, assignment, teacher_user, session,
    monkeypatch_celery
):
    assig_id = assignment.id

    def get_graders():
        with logged_in(teacher_user):
            return test_client.req(
                'get',
                f'/api/v1/assignments/{assig_id}/graders/',
                200,
                result=list
            )

    graders = get_graders()
    random.shuffle(graders)
    grader_done = graders[-1]["id"]

    with logged_in(teacher_user):
        _, rv = test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
            result=None,
            include_response=True
        )
        assert 'Warning' not in rv.headers

        test_client.req(
            'delete',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
            result=None,
            include_response=True
        )

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}/divide',
            204,
            result=None,
            data={'graders': {grader_done: 1}}
        )

        _, rv = test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
            result=None,
            include_response=True
        )
        assert 'Warning' in rv.headers

        test_client.req(
            'delete',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
            result=None,
            include_response=True
        )

        session.query(m.Work).filter_by(
            assigned_to=grader_done, assignment_id=assig_id
        ).update({'_grade': 6})
        session.commit()
        _, rv = test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            204,
            result=None,
            include_response=True
        )
        assert 'Warning' not in rv.headers


@pytest.mark.parametrize(
    'named_user,toggle_self', [
        http_err(error=403)(('admin', None)),
        http_err(error=401)(('NOT_LOGGED_IN', None)),
        ('Thomas Schaper', True),
        ('Robin', False),
        http_err(error=403)(('Thomas Schaper', False)),
        http_err(error=403)(('Student1', None)),
    ],
    indirect=['named_user']
)
def test_grader_done(
    named_user, error_template, test_client, logged_in, request, assignment,
    teacher_user, session, stubmailer, toggle_self, monkeypatch_celery,
    stub_function_class, monkeypatch
):
    # Please note that we DO NOT monkey patch celery away here. This is because
    # some logic might be implemented in the celery task (this has already
    # happened a few times during development). We simply make sure the mailer
    # is called.
    stubtask = stub_function_class(
        ret_func=psef.tasks.send_grader_status_mail, with_args=True
    )
    monkeypatch.setattr(psef.tasks, 'send_grader_status_mail', stubtask)

    def assert_remind_email(called):
        assert stubmailer.called == called, (
            'Email should{}have been called'.format(
                ' not ' if not called else ' ',
            )
        )
        # Make sure the task is only called when the email should be send
        assert stubtask.called == called, (
            'Celery task should{}have been called'.format(
                ' not ' if not called else ' ',
            )
        )

        if called:
            assert len(stubtask.args) == 1, 'Task should be called once only'

        stubmailer.reset()
        stubtask.reset()

    assig_id = assignment.id
    course_id = assignment.course_id

    code = 204
    marker = request.node.get_closest_marker('http_err')
    if marker is not None:
        code = marker.kwargs['error']

    err = code >= 400

    def get_graders():
        with logged_in(teacher_user):
            return test_client.req(
                'get',
                f'/api/v1/assignments/{assig_id}/graders/',
                200,
                result=list
            )

    graders = get_graders()
    random.shuffle(graders)

    assert len(graders) > 1, 'We need at least 2 graders for this test'

    if not isinstance(named_user, str):
        if graders[-1]['id'] == named_user.id:
            graders[-1], graders[0] = graders[0], graders[-1]

    assert all(
        not g['done'] for g in graders
    ), 'Make sure all graders are not done by default'
    if toggle_self:
        grader_done = named_user.id
    else:
        if isinstance(named_user, str):
            grader_done = 1
        else:
            for grader in graders:
                if grader['id'] != named_user.id:
                    grader_done = grader['id']
                    break
            else:
                assert False

    with logged_in(named_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            code,
            result=error_template if err else None
        )

    graders = get_graders()
    if err:
        assert all(
            not g['done'] for g in graders
        ), 'Make sure all graders are still not done'
    else:
        assert all(
            g['done'] == (g['id'] == grader_done) for g in graders
        ), 'Make sure only changed grader is done'
        with logged_in(named_user):
            # Make sure you cannot reset this grader to done
            test_client.req(
                'post',
                f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
                400,
                result=error_template,
            )

    with logged_in(named_user):
        test_client.req(
            'delete',
            f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
            code,
            result=error_template if err else None
        )

    if not err:
        # Make sure an email was send if and only if we did not toggle
        # ourselves
        assert_remind_email(called=not toggle_self)

        with logged_in(named_user):
            # Make sure you cannot reset this grader to not done
            test_client.req(
                'delete',
                f'/api/v1/assignments/{assig_id}/graders/{grader_done}/done',
                400,
                result=error_template,
            )
        # When an error occurs we should not notify anybody
        assert_remind_email(False)
    else:
        # When an error occurred we should not send emails
        assert_remind_email(False)

    graders = get_graders()
    assert all(
        not g['done'] for g in graders
    ), 'Make sure all graders are again not done'

    with logged_in(teacher_user):
        test_client.req(
            'post', (
                f'/api/v1/assignments/{assig_id}/graders/' + str(
                    m.User.query.filter_by(name='Student1').first().id
                ) + '/done'
            ),
            400,
            result=error_template
        )

    if not err:
        new_user = m.User.query.filter_by(name='Student1').first()
        new_user.courses[course_id].set_permission(CPerm.can_grade_work, True)
        session.commit()

        with logged_in(new_user):
            # This should be the case for adding and deleting permissions
            for meth in ['post', 'delete']:
                # This user cannot set other users
                test_client.req(
                    meth,
                    f'/api/v1/assignments/{assig_id}/graders'
                    f'/{grader_done}/done',
                    403,
                    result=error_template,
                )
                # But this user can set his own perms
                test_client.req(
                    meth,
                    f'/api/v1/assignments/{assig_id}/graders'
                    f'/{new_user.id}/done',
                    204,
                    result=None,
                )

            # Errors should not trigger emails and neither should toggling
            # yourself
            assert_remind_email(False)


@pytest.mark.parametrize(
    'named_user', [
        http_err(error=403)('admin'),
        http_err(error=401)('NOT_LOGGED_IN'),
        'Devin Hillenius',
        http_err(error=403)('Student1'),
    ],
    indirect=True
)
@pytest.mark.parametrize(
    'with_type,with_time,with_email', [
        (True, True, True),
        (True, True, False),
        (False, True, True),
        (True, False, False),
        (True, 'wrong', True),
        ('wrong', True, True),
        (True, True, 'wrong'),
    ]
)
@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_reminder_email(
    test_client, session, error_template, teacher_user, monkeypatch, app,
    stub_function_class, assignment, named_user, with_type, with_time, request,
    logged_in, with_email, monkeypatch_celery
):
    assig_id = assignment.id

    all_graders = m.User.query.filter(
        m.User.name.in_([
            'Thomas Schaper',
            'Devin Hillenius',
            'Robin',
            'b',
        ])
    ).all()
    assigned_graders = all_graders[2:3]
    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}/divide',
            204,
            result=None,
            data={'graders': {u.id: 1
                              for u in assigned_graders}}
        )

        sub = assignment.get_all_latest_submissions()[0]
        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub.id}/grader',
            204,
            data={'user_id': all_graders[0].id},
        )
    assigned_graders.append(all_graders[0])

    # Monkeypatch the actual mailer away as we don't really want to send emails
    mailer = stub_function_class()

    def test_mail(users):
        psef.tasks._send_reminder_mails_1(assig_id)

        user_mails = [u.email for u in users]
        user_mails.sort()

        for body, subject, recipients, conn in mailer.args:
            assert body, 'A non empty body is required'
            assert subject, 'A non empty subject is required'
            assert len(recipients) == 1, (
                'Make sure only one recipients '
                'is used per email'
            )
            assert conn, 'Make sure a connection was passed'

        assert sorted(
            [arg[2][0] for arg in mailer.args]
        ) == user_mails, ('Make sure only the correct'
                          ' users were emailed')
        mailer.reset()

    monkeypatch.setattr(psef.mail, '_send_mail', mailer)
    # Make sure no grader status emails are sent as these also use the
    # `_send_mail` function
    monkeypatch.setattr(
        psef.mail,
        'send_grader_status_changed_mail',
        stub_function_class(),
    )

    class StubTask:
        def __init__(self, id):
            self.id = id

    # Monkey patch celery away as an ETA task will block the test for a long
    # time.
    task = stub_function_class(lambda: StubTask(str(uuid.uuid4())))
    monkeypatch.setattr(psef.tasks, 'send_reminder_mails', task)
    revoker = stub_function_class()
    monkeypatch.setattr(psef.tasks.celery.control, 'revoke', revoker)

    time = DatetimeWithTimezone.utcnow() + datetime.timedelta(days=1)
    data = {
        'done_type': 'assigned_only', 'reminder_time': time.isoformat(),
        'done_email': '"thomas schaper" <thomas@example>, aa@example.com'
    }
    code = 204

    if not with_type:
        del data['done_type']
        code = 400
    if not with_time:
        del data['reminder_time']
        code = 400
    if not with_email:
        del data['done_email']
        code = 400

    if with_type == 'wrong':
        data['done_type'] = 'WRONG_TYPE'
        code = 400
    if with_time == 'wrong':
        data['reminder_time'] = 'WRONG_TIME'
        code = 400
    if with_email == 'wrong':
        data['done_email'] = 'not_a_email'
        code = 400

    marker = request.node.get_closest_marker('http_err')
    if marker is not None:
        code = marker.kwargs['error']

    err = code >= 400

    def set_to_done(grader, method='post'):
        with logged_in(teacher_user):
            test_client.req(
                method,
                (
                    f'/api/v1/assignments/{assig_id}/'
                    f'graders/{grader.id}/done'
                ),
                204,
                result=None,
            )

    def test_done_email():
        set_to_done(all_graders[3])

        for assigned_grader in assigned_graders:
            set_to_done(assigned_grader)

        if data['done_type'
                ] == 'assigned_only' and data['done_email'] is not None:
            assert mailer.called
            mailer.reset()
        else:
            assert not mailer.called

        for grader in all_graders[:-1]:
            if grader not in assigned_graders:
                set_to_done(grader)

        if data['done_type'
                ] == 'all_graders' and data['done_email'] is not None:
            assert mailer.called
        else:
            assert not mailer.called

        mailer.reset()

        for grader in all_graders:
            set_to_done(grader, 'delete')

    def check_assig_state():
        with logged_in(teacher_user):
            assig = test_client.req(
                'get', f'/api/v1/assignments/{assig_id}', 200, result=dict
            )
            assert assig['done_type'] == data[
                'done_type'], 'Make sure state is the same as in the data sent'

            if assig['done_type'] is None:
                assert assig['reminder_time'] is None, """
                Reminder time should have been reset
                """
                assert assig['done_email'] is None, """
                Done email should be reset to None
                """
            else:
                assert assig['reminder_time'] == data[
                    'reminder_time'
                ], 'Make sure time is the same as in the data sent'
                assert assig['done_email'] == data[
                    'done_email'], 'Make sure email is correct'

    if not err:
        code = 200
    with logged_in(named_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            code,
            data=data,
            result=error_template if err else None
        )

        assert not revoker.called, 'No task should have been revoked'
        assert not mailer.called, 'The mailer should not be called directly'
        assert task.called != err, "Schedule the task if no there's no error"

        if err:
            return
        check_assig_state()
        test_mail(assigned_graders)
        test_done_email()

        assert task.args == [((assig_id, ), )
                             ], 'The correct task should be scheduled.'
        assert task.kwargs == [{'eta': time}
                               ], 'The time should be preserved directly.'
        task_id = task.rets[-1].id

        revoker.reset()
        task.reset()

        data['done_type'] = None

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            code,
            data=data,
            result=None
        )

        check_assig_state()
        assert revoker.called, 'The previous task should be revoked'
        assert not mailer.called, 'The mailer should not be called directly'
        assert not task.called, (
            'Nothing should be scheduled as the type '
            'was none'
        )
        assert revoker.args == [(task_id, )
                                ], 'Assert the correct task was revoked'
        test_mail([])
        test_done_email()
        revoker.reset()
        task.reset()

        data['done_type'] = 'all_graders'

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            code,
            data=data,
            result=None
        )
        check_assig_state()
        assert not revoker.called, (
            'The previous task should be not be revoked '
            'as the type was none'
        )
        assert not mailer.called, 'The mailer should not be called'
        assert task.called, 'A new task should be scheduled '
        test_mail(all_graders)
        test_done_email()
        revoker.reset()
        task.reset()

        old_email = data['done_email']
        data['done_email'] = None
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            code,
            data=data,
            result=None
        )
        check_assig_state()
        assert task.called, 'A new task should be scheduled '
        assert revoker.called, 'The previous task should be revoked'
        test_mail(all_graders)
        test_done_email()
        revoker.reset()
        task.reset()
        data['done_email'] = old_email

        set_to_done(all_graders[-1])
        # Make sure done grader will not get an email.
        test_mail(all_graders[:-1])
        set_to_done(all_graders[-1], 'delete')

        data['reminder_time'] = None
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            code,
            data=data,
            result=None
        )
        check_assig_state()
        assert revoker.called, 'Task should revoked as no time was none'
        assert not mailer.called, 'The mailer should not be called'
        assert not task.called, 'A new task should not be scheduled '
        test_mail([])
        test_done_email()

        # This date is not far enough in the future so it should error
        data['reminder_time'] = DatetimeWithTimezone.utcnow().isoformat()
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            400,
            data=data,
            result=error_template
        )


@pytest.mark.parametrize('with_works', [True], indirect=True)
def test_warning_grading_done_email(
    test_client, session, error_template, monkeypatch, app, logged_in,
    monkeypatch_celery, stub_function_class, assignment, teacher_user
):
    assig_id = assignment.id
    task = stub_function_class()
    monkeypatch.setattr(psef.tasks, 'send_done_mail', task)
    all_graders = m.User.query.filter(
        m.User.name.in_([
            'Thomas Schaper',
            'Devin Hillenius',
            'Robin',
            'b',
        ])
    ).all()

    def set_to_done(grader, method='post'):
        with logged_in(teacher_user):
            test_client.req(
                method,
                (
                    f'/api/v1/assignments/{assig_id}/'
                    f'graders/{grader.id}/done'
                ),
                204,
                result=None,
            )

    for grader in all_graders:
        set_to_done(grader)

    with logged_in(teacher_user):
        _, rv = test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            200,
            data={
                'done_type': 'all_graders', 'reminder_time': None,
                'done_email': 'thomas@example.com'
            },
            include_response=True
        )
    assert rv.headers
    assert 'warning' in rv.headers


def test_notification_permission(
    test_client, session, teacher_user, logged_in, assignment, error_template
):
    assig_id = assignment.id
    teacher_user.courses[assignment.course_id].set_permission(
        CPerm.can_update_course_notifications,
        False,
    )
    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            403,
            data={
                'done_type': 'all_graders', 'reminder_time': None,
                'done_email': 'thomas@example.com'
            },
            result=error_template,
        )


def test_division_parent(
    test_client, session, teacher_user, logged_in, error_template
):
    def handin(user, assig, new, new_grader=False):
        with logged_in(user):
            if new:
                assert get_id(user) not in get_newest_submissions(
                    test_client, assig
                )
            else:
                assert get_id(user) in get_newest_submissions(
                    test_client, assig
                )

            sub = create_submission(test_client, get_id(assig))
            if new_grader:
                set_grader(sub, make_new_grader())
            return sub

    def assert_sub_grader(sub, grader):
        with logged_in(teacher_user):
            sub_id = get_id(sub)

            sub = test_client.req('get', f'/api/v1/submissions/{sub_id}', 200)
            if grader is None:
                assert sub['assignee'] is None
            else:
                assert sub['assignee'] is not None
                assert isinstance(sub['assignee'], dict)

                assert sub['assignee']['id'] == get_id(grader)

    def assert_all_subs_same_grader(
        assig1, assig2, exceptions=None, complete=True
    ):
        if exceptions is None:
            exceptions = set()
        with logged_in(teacher_user):
            subs1 = get_newest_submissions(test_client, assig1)
            subs2 = get_newest_submissions(test_client, assig2)

            for user, s1 in subs1.items():
                # If this user handed in anything it should be assigned to the
                # same user.
                if user in subs2:
                    assert ((subs2[user]['assignee'] !=
                             s1['assignee']) == (user in exceptions)
                            ), 'The grader of {} is not correct'.format(
                                s1['user']['name']
                            )
                    del subs2[user]
            # This shouldn't be possible but just to make sure
            assert not any(u in subs1 for u in subs2)

            if complete:
                assert not subs2

    def set_grader(sub, grader):
        with logged_in(teacher_user):
            test_client.req(
                'patch',
                f'/api/v1/submissions/{get_id(sub)}/grader',
                204,
                data={'user_id': get_id(grader)},
            )

    def connect_divisions(first, second):
        with logged_in(teacher_user):
            parent_id = None if second is None else get_id(second)
            test_client.req(
                'patch',
                f'/api/v1/assignments/{get_id(first)}/division_parent',
                204,
                data={'parent_id': parent_id}
            )
            test_client.req(
                'get',
                f'/api/v1/assignments/{get_id(first)}',
                200,
                result={
                    'division_parent_id': parent_id,
                    '__allow_extra__': True,
                }
            )

    def make_new_student(name):
        return create_user_with_perms(
            session,
            [
                CPerm.can_submit_own_work, CPerm.can_see_assignments,
                CPerm.can_upload_after_deadline
            ],
            courses=[course],
            name=name,
        )

    def make_new_grader():
        return create_user_with_perms(
            session, [
                CPerm.can_submit_own_work, CPerm.can_see_assignments,
                CPerm.can_upload_after_deadline, CPerm.can_grade_work
            ],
            courses=[course]
        )

    teacher_user.role.set_permission(GPerm.can_create_courses, True)
    with logged_in(teacher_user):
        course = create_course(test_client)
        assigs = [
            create_assignment(
                test_client,
                get_id(course),
                state='open',
                deadline=DatetimeWithTimezone.utcnow() +
                datetime.timedelta(days=1)
            ) for _ in range(9)
        ]
        a1, a2, a3, a4, a5, a6, a7, a8, a9 = assigs

        jan = make_new_student('jan')
        piet = make_new_student('piet')
        klaas = make_new_student('klaas')
        all_subs = defaultdict(dict)

        for assig in assigs:
            for user in [jan, piet, klaas]:
                all_subs[get_id(assig)][get_id(user)] = handin(
                    user, assig, new=True
                )

    # Set some random graders are assignment 1 (the master)
    for sub in all_subs[get_id(a1)].values():
        set_grader(sub, make_new_grader())

    connect_divisions(a2, a1)
    assert_all_subs_same_grader(a1, a2)

    # Jan already handed in an assignment so the grader should be the same as
    # for a1
    handin(jan, a2, new=False)
    assert_all_subs_same_grader(a1, a2)

    # Make sure karijn gets the same grader in the parent as for the child.
    karijn = make_new_student('karijn')
    handin(karijn, a2, new=True)
    handin(karijn, a1, new=True)
    assert_all_subs_same_grader(a1, a2)

    # Even though peggy didn't hand in anything for assignment 1 the grader for
    # a3 should be the same as for a2
    peggy = make_new_student('peggy')
    handin(peggy, a2, new=True, new_grader=True)
    handin(peggy, a3, new=True)
    handin(karijn, a3, new=True)
    connect_divisions(a3, a1)
    assert_all_subs_same_grader(a2, a3)

    achmed = make_new_student('achmed')
    connect_divisions(a4, a1)

    # The most common grader should be used when there is are duplicates among
    # the children.
    connect_divisions(a5, a1)
    sub1 = handin(achmed, a2, new=True)
    sub2 = handin(achmed, a3, new=True)
    sub3 = handin(achmed, a4, new=True)
    g1 = make_new_grader()
    g2 = make_new_grader()
    set_grader(sub1, g1)
    set_grader(sub2, g2)
    set_grader(sub3, g2)
    sub4 = handin(achmed, a5, new=True)
    assert_sub_grader(sub4, g2)

    don = make_new_student('don')
    sub4 = handin(don, a6, new=True)
    connect_divisions(a6, a1)
    # Shouldn't be auto assigned as no weights are set
    assert_sub_grader(sub4, None)

    # After connecting again we shouldn't copy graders
    g3 = make_new_grader()
    set_grader(sub4, g3)
    sub5 = handin(klaas, a6, new=False)
    set_grader(sub5, g3)
    connect_divisions(a6, a1)
    assert_sub_grader(sub4, g3)
    assert_sub_grader(sub5, g3)

    # After disconnecting we shouldn't copy graders
    connect_divisions(a6, None)
    sub6 = handin(don, a1, new=True)
    assert_sub_grader(sub4, g3)
    assert_sub_grader(sub6, None)

    assigned_graders = [make_new_grader() for _ in range(2)]
    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(a7)}/divide',
            204,
            result=None,
            data={'graders': {get_id(g): 1
                              for g in assigned_graders}}
        )
    connect_divisions(a8, a7)
    assert_all_subs_same_grader(a7, a8)

    # The next tests could pass just by chance so we run them a few times to be
    # more sure that this isn't the case.
    for _ in range(10):
        connect_divisions(a9, None)

        # Connecting an automatically divided assignment should mean that the
        # weights are also copied. So if we let grader[0] have more work and we
        # have a 'unknown' submission in the child this unknown submission
        # should be assigned to other grader.
        for i in range(3):
            temp_user = make_new_student(f'temp_user{i}')
            handin(temp_user, a9, new=True)
            set_grader(handin(temp_user, a7, new=True), assigned_graders[0])
        fatima = make_new_student('fatima')
        sub7 = handin(fatima, a9, new=True)
        connect_divisions(a9, a7)
        assert_sub_grader(sub7, assigned_graders[1])

        # The balance is still biased towards assigned_graders[0] so a new
        # assignment to a9 should be assigned to assigned_graders[1]
        saskia = make_new_student('saskia')
        sub8 = handin(saskia, a9, new=True)
        assert_sub_grader(sub8, assigned_graders[1])

        # This should still be copied from its children
        sub9 = handin(saskia, a8, new=True)
        assert_sub_grader(sub9, assigned_graders[1])


def test_division_connect_error_conditions(
    test_client, session, admin_user, logged_in, error_template
):
    with logged_in(admin_user):
        course = create_course(test_client)
        assigs = [
            create_assignment(
                test_client,
                get_id(course),
                state='open',
                deadline=DatetimeWithTimezone.utcnow() +
                datetime.timedelta(days=1)
            ) for _ in range(9)
        ]

        students = [
            create_user_with_perms(
                session,
                [
                    CPerm.can_submit_own_work, CPerm.can_see_assignments,
                    CPerm.can_upload_after_deadline
                ],
                courses=[course],
            ) for _ in range(10)
        ]

    for stud in students:
        for assig in assigs:
            with logged_in(stud):
                create_submission(test_client, get_id(assig))

    with logged_in(students[0]):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[0])}/division_parent',
            403,
            data={'parent_id': get_id(assigs[1])},
            result=error_template,
        )

        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[0])}/division_parent',
            403,
            data={'parent_id': None},
            result=error_template,
        )

    with logged_in(admin_user):
        for a in assigs:
            # The default should be None for all assignments
            test_client.req(
                'patch',
                f'/api/v1/assignments/{get_id(a)}',
                200,
                data={
                    'division_parent_id': None,
                    '__allow_extra__': True,
                }
            )
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[1])}/division_parent',
            204,
            data={'parent_id': get_id(assigs[0])}
        )

        # The teacher should be able to see this
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[1])}',
            200,
            data={
                'division_parent_id': get_id(assigs[0]),
                '__allow_extra__': True,
            }
        )
        with logged_in(students[0]):
            # However the student should not be
            test_client.req(
                'patch',
                f'/api/v1/assignments/{get_id(assigs[1])}',
                200,
                data={
                    'division_parent_id': None,
                    '__allow_extra__': True,
                }
            )

        # You shouldn't be able to change the divide settings for parents nor
        # children.
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[0])}/divide',
            400,
            result=error_template,
            data={'graders': {get_id(admin_user): 1}}
        )
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[1])}/divide',
            400,
            result=error_template,
            data={'graders': {get_id(admin_user): 1}}
        )

        # The parent of a parent can be set to None
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[0])}/division_parent',
            204,
            data={'parent_id': None}
        )
        # The parent of a parent cannot be set to an actual value
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[0])}/division_parent',
            400,
            data={'parent_id': get_id(assigs[1])},
            result=error_template,
        )

    with logged_in(admin_user):
        _, response = test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assigs[2])}/division_parent',
            204,
            data={'parent_id': get_id(assigs[0])},
            include_response=True,
        )
        assert 'warning' in response.headers
        assert 'Some submissions were not' in response.headers['warning']


def test_duplicating_rubric(
    test_client, session, error_template, admin_user, logged_in,
    original_rubric_data
):
    with logged_in(admin_user):
        base_assignment = create_assignment(test_client, state='open')
        base_assignment_no_rubric = create_assignment(
            test_client, base_assignment['course']['id'], state='open'
        )
        base_assignment_hidden = create_assignment(
            test_client, base_assignment['course']['id'], state='hidden'
        )
        no_permission_assignment = create_assignment(test_client, state='open')

        new_assignment = create_assignment(test_client, state='open')

    user = create_user_with_perms(
        session, [CPerm.can_see_assignments],
        courses=[
            base_assignment['course'],
            new_assignment['course'],
        ]
    )
    user.courses[new_assignment['course']['id']].set_permission(
        CPerm.manage_rubrics, True
    )
    session.commit()

    def assert_rubric_empty():
        with logged_in(user):
            test_client.req(
                'get', f'/api/v1/assignments/{new_assignment["id"]}/rubrics/',
                404
            )

    assert_rubric_empty()

    for assig in [
        no_permission_assignment, base_assignment, base_assignment_hidden
    ]:
        with logged_in(
            create_user_with_perms(
                session, [
                    CPerm.manage_rubrics, CPerm.can_see_assignments,
                    CPerm.can_see_hidden_assignments
                ],
                courses=[assig['course']]
            )
        ):
            test_client.req(
                'put',
                f'/api/v1/assignments/{assig["id"]}/rubrics/',
                200,
                data=original_rubric_data
            )
            test_client.req(
                'get', f'/api/v1/assignments/{assig["id"]}/rubrics/', 200
            )

    with logged_in(user):
        for assig, code in [(base_assignment_no_rubric, 404),
                            (base_assignment_hidden, 403),
                            (no_permission_assignment, 403),
                            (new_assignment, 404)]:
            test_client.req(
                'get', f'/api/v1/assignments/{assig["id"]}/rubrics/', code
            )
            test_client.req(
                'post',
                f'/api/v1/assignments/{new_assignment["id"]}/rubric',
                code,
                data={'old_assignment_id': assig["id"]}
            )
            assert_rubric_empty()

        result = test_client.req(
            'post',
            f'/api/v1/assignments/{new_assignment["id"]}/rubric',
            200,
            data={'old_assignment_id': base_assignment["id"]},
            result=[{
                'header': original_rubric_data['rows'][0]['header'],
                'description': original_rubric_data['rows'][0]['description'],
                'id': int,
                'items': list,
                'locked': False,
                'type': 'normal',
            }]
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{new_assignment["id"]}/rubrics/',
            200,
            result=result
        )

        # You cannot import into an assignment which has a rubric.
        test_client.req(
            'post',
            f'/api/v1/assignments/{new_assignment["id"]}/rubric',
            400,
            data={'old_assignment_id': base_assignment["id"]}
        )


def test_get_all_assignments_with_rubric(
    test_client, session, error_template, admin_user, logged_in,
    original_rubric_data
):
    with logged_in(admin_user):
        assig_no_perms = create_assignment(test_client, state='open')
        assig_perms_no_rubric = create_assignment(test_client, state='open')
        assig_perms_rubric = create_assignment(test_client, state='open')
    user = create_user_with_perms(
        session, [
            CPerm.can_see_assignments,
            CPerm.manage_rubrics,
            CPerm.can_view_analytics,
        ],
        courses=[
            assig_perms_no_rubric['course'],
            assig_perms_rubric['course'],
        ]
    )
    with logged_in(user):
        test_client.req(
            'put',
            f'/api/v1/assignments/{assig_perms_rubric["id"]}/rubrics/',
            200,
            data=original_rubric_data
        )

        test_client.req(
            'get',
            '/api/v1/assignments/',
            200,
            result=[
                assig_perms_rubric,
                assig_perms_no_rubric,
            ]
        )

        test_client.req(
            'get',
            '/api/v1/assignments/?only_with_rubric',
            200,
            result=[assig_perms_rubric]
        )


def test_prevent_submitting_to_assignment_without_deadline(
    test_client, session, assignment, logged_in, admin_user, error_template
):
    test_sub_msg = 'You can still upload a test submission.'

    with logged_in(admin_user):
        course = create_course(test_client)
        assig = create_assignment(test_client, get_id(course), state='open')
        student = create_user_with_perms(
            session,
            [CPerm.can_submit_own_work, CPerm.can_see_assignments],
            courses=[course],
        )
        teacher = create_user_with_perms(
            session,
            [
                CPerm.can_submit_others_work, CPerm.can_upload_after_deadline,
                CPerm.can_see_assignments
            ],
            courses=[course],
        )

    with logged_in(student):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assig["id"]}/submission',
            400,
            real_data={
                'file': (
                    f'{os.path.dirname(__file__)}/../test_data/'
                    'test_submissions/multiple_dir_archive.zip', 'f.zip'
                )
            },
            result=error_template,
        )
        assert not res['message'].endswith(test_sub_msg)

    with logged_in(teacher):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assig["id"]}/submission',
            400,
            real_data={
                'file': (
                    f'{os.path.dirname(__file__)}/../test_data/'
                    'test_submissions/multiple_dir_archive.zip', 'f.zip'
                )
            },
        )
        assert res['message'].endswith(test_sub_msg)


def parse_ignore_v2_test_files():
    @dataclasses.dataclass
    class IgnoreTestCase:
        f: str
        data: dict
        in_format: list
        out_format: list
        missing_error: bool

        def __str__(self) -> str:
            return f'Ignore: {self.f}'

        def get_expected(self, root_name):
            def build_tree(tree, path):
                if not path or path == '/':
                    return

                splitted = [x for x in path.split('/') if x]
                for idx, e in enumerate(tree['entries']):
                    if e['name'] == splitted[0]:
                        break
                else:
                    entry = {
                        'name': splitted[0],
                        'id': str,
                    }
                    if path[-1] == '/' or len(splitted) > 1:
                        entry['entries'] = []
                    tree['entries'].append(entry)
                    tree['entries'].sort(key=lambda el: el['name'].lower())
                    idx = -1

                new_path = '/'.join(splitted[1:])
                if path[-1] == '/':
                    new_path += '/'
                build_tree(tree['entries'][idx], new_path)

            res = {
                'name': root_name,
                'id': str,
                'entries': [],
            }
            for path in sorted(self.out_format, key=lambda el: el.lower()):
                build_tree(res, path)
            print('build tree', res)
            return res

    res = []

    base_dir = f'{os.path.dirname(__file__)}/../test_data/ignore_v2_cases/'
    for filename in sorted(os.listdir(base_dir)):
        with open(os.path.join(base_dir, filename), 'r') as f:
            content = f.read().strip()
        data = {}

        ignore, input_dir, expected = content.split('\n\n')
        ignore = ignore.split('\n')
        assert ignore[0].startswith('policy: ')
        data['policy'] = (
            'allow_all_files' if 'allow' in ignore[0] else 'deny_all_files'
        )
        assert ignore[1].startswith('options: ')
        data['options'] = [{'key': k, 'value': v} for k, v in {
            'allow_override': False,
            **json.loads(ignore[1][len('options: '):].strip()),
        }.items()]
        data['rules'] = [{
            'rule_type': typ.strip(':'),
            'file_type': 'directory' if fname[-1] == '/' else 'file',
            'name': fname,
        } for typ, fname in (i.split(' ', 1) for i in ignore[2:])]
        input_dir = [l.lstrip('/') for l in input_dir.split('\n')]
        expected = expected.split('\n')

        missing_error = False
        if expected == ['SAME']:
            expected = copy.deepcopy(input_dir)
        elif expected[0] == 'MISSING':
            expected.pop(0)
            missing_error = True

        res.append(
            IgnoreTestCase(filename, data, input_dir, expected, missing_error)
        )

    return res


@pytest.mark.parametrize('test_case', parse_ignore_v2_test_files())
def test_ignore_v2(
    test_client, logged_in, teacher_user, test_case, assignment, error_template
):
    with tempfile.TemporaryDirectory() as tmpdir, tempfile.NamedTemporaryFile(
        suffix='.tar.gz'
    ) as archive_file:
        print(dataclasses.asdict(test_case), archive_file.name)
        for f in test_case.in_format:
            assert f
            full_path = os.path.join(tmpdir, f)
            assert full_path.startswith(tmpdir)
            if full_path[-1] == '/':
                os.makedirs(full_path)
            else:
                basedir = os.path.dirname(full_path)
                os.makedirs(basedir, exist_ok=True)
                with open(full_path, 'w') as f:
                    pass
        with tarfile.open(archive_file.name, mode='w:gz') as archive:
            for f in os.listdir(tmpdir):
                archive.add(os.path.join(tmpdir, f), f, recursive=True)

        with logged_in(teacher_user):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assignment.id}',
                200,
                data={
                    'ignore': test_case.data,
                    'ignore_version': 'SubmissionValidator',
                },
            )
            assig = test_client.req(
                'get', f'/api/v1/assignments/{assignment.id}', 200
            )
            assert assig['cgignore'] == test_case.data

            if test_case.missing_error:
                err = test_client.req(
                    'post',
                    f'/api/v1/assignments/{assignment.id}/submission?'
                    'ignored_files=delete',
                    400,
                    real_data={'file': (archive_file.name, archive_file.name)},
                    result={**error_template, '__allow_extra__': True},
                )
                assert set(r['name'] for r in err['missing_files']) == set(
                    test_case.out_format
                )
                return

            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission?'
                'ignored_files=delete',
                201,
                real_data={'file': (archive_file.name, archive_file.name)},
            )

            test_client.req(
                'get',
                f'/api/v1/submissions/{res["id"]}/files/',
                200,
                result=test_case.get_expected(
                    archive_file.name.split('/')[-1]
                )
            )

            # This is not allowed as override is set to False.
            test_client.req(
                'post',
                f'/api/v1/assignments/{assignment.id}/submission?'
                'ignored_files=keep',
                400,
                real_data={'file': (archive_file.name, archive_file.name)},
            )


def test_setting_cgignore(
    test_client, logged_in, teacher_user, assignment, error_template
):
    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            400,
            data={
                'ignore': [],
                'ignore_version': 'SubmissionValidator',
            },
            result=error_template
        )
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            400,
            data={
                'ignore': 'hello',
                'ignore_version': ['Wrong Type'],
            },
            result=error_template
        )
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            400,
            data={
                'ignore': ['hello'],
                'ignore_version': 'IgnoreFilterManager',
            },
            result=error_template
        )

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            404,
            data={
                'ignore': [],
                'ignore_version': 'NotKnown',
            },
            result=error_template
        )

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment.id}',
            200,
            data={
                'ignore': '',
                'ignore_version': 'EmptySubmissionFilter',
            },
        )
        test_client.req(
            'post',
            (
                f'/api/v1/assignments/{assignment.id}'
                '/submission?ignored_files=delete'
            ),
            201,
            real_data={
                'file': (
                    get_submission_archive('multiple_file_archive.tar.gz'),
                    'test.tar.gz'
                )
            },
        )


def test_upload_files_with_duplicate_filenames(
    test_client, logged_in, assignment, error_template, teacher_user
):
    with logged_in(teacher_user):
        res = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submission',
            201,
            real_data={
                'file1': (
                    get_submission_archive('single_file_archive.zip'),
                    f'duplicate_name.zip',
                ),
                'file2': (
                    get_submission_archive('multiple_file_archive.zip'),
                    f'duplicate_name.zip',
                ),
                'file3': (
                    get_submission_archive('single_file_archive.zip'),
                    'other_name',
                ),
                'file4': (
                    get_submission_archive('single_file_archive.zip'),
                    f'duplicate_name.zip (2)',
                ),
                'file5': (
                    get_submission_archive('single_file_archive.zip'),
                    f'duplicate_name.zip',
                ),
            },
            result={
                'id': int,
                'user': teacher_user.__to_json__(),
                'created_at': str,
                'assignee': None,
                'grade': None,
                'comment': None,
                'comment_author': None,
                '__allow_extra__': True,
            }
        )

        test_client.req(
            'get',
            f'/api/v1/submissions/{res["id"]}/files/',
            200,
            result={
                'entries': [
                    {
                        'name': 'duplicate_name.zip',
                        'entries': [{'id': str, 'name': 'single_file_work'}],
                        'id': str,
                    },
                    {
                        'name': 'duplicate_name.zip (1)',
                        'entries':
                            [{'id': str, 'name': 'single_file_work'},
                             {'id': str, 'name': 'single_file_work_copy'}],
                        'id': str,
                    },
                    {
                        'name': 'duplicate_name.zip (2)',
                        # This has no entries as its original name was
                        # `duplicate_name.zip (2)` so it is not detected as
                        # .zip file.
                        'id': str,
                    },
                    {
                        'name': 'duplicate_name.zip (3)',
                        'entries': [{'id': str, 'name': 'single_file_work'}],
                        'id': str,
                    },
                    {
                        'name': 'other_name',
                        'id': str,
                    }
                ],
                'id': str,
                'name': 'top',
            }
        )


def test_get_latest_submissions_only(
    logged_in, session, test_client, admin_user, tomorrow, describe
):
    with describe('setup'):
        with logged_in(admin_user):
            course = helpers.create_course(test_client)

        student1 = helpers.create_user_with_role(session, 'Student', course)
        student2 = helpers.create_user_with_role(session, 'Student', course)
        teacher = helpers.create_user_with_role(session, 'Teacher', course)

        with logged_in(teacher):
            assig_id = helpers.create_assignment(
                test_client, course, 'open', deadline=tomorrow
            )['id']

        with logged_in(student1):
            sub1 = helpers.create_submission(test_client, assig_id)
            sub2 = helpers.create_submission(test_client, assig_id)
        with logged_in(student2):
            sub3 = helpers.create_submission(test_client, assig_id)

        base_url = f'/api/v1/assignments/{assig_id}/submissions/?extended'

    with describe('Getting all submissions'), logged_in(teacher):
        # By default you get all the submissions
        test_client.req('get', base_url, 200, result=[sub3, sub2, sub1])

    with describe('Getting latest only'), logged_in(teacher):
        # With latest_only you get all the latest submissions by each user, so
        # in this case sub2 is the latest by student1, while sub1 is not.
        test_client.req(
            'get', f'{base_url}&latest_only', 200, result=[sub3, sub2]
        )

    with describe('Setting up group assignment'), logged_in(teacher):
        g_set = helpers.create_group_set(test_client, course, 1, 2, [assig_id])
        helpers.create_group(test_client, g_set, [student1, student2])

        with logged_in(student1):
            group_sub = helpers.create_submission(test_client, assig_id)

    with describe('API still gives student submissions'), logged_in(teacher):
        test_client.req(
            'get',
            f'{base_url}&latest_only',
            200,
            result=[group_sub, sub3, sub2]
        )

    with describe('But method only gives group submission by default'):
        assig = m.Assignment.query.get(assig_id)
        subs = assig.get_all_latest_submissions().all()
        assert len(subs) == 1
        assert subs[0].id == group_sub['id']

        # And the single function should do the same
        for user_id in [sub2['user']['id'], sub3['user']['id']]:
            found_sub = assig.get_latest_submission_for_user(
                m.User.query.get(user_id)
            ).one()
            assert found_sub.id == group_sub['id']

    with describe(
        'Group submission is always returned, even if user submission is newer'
    ):
        m.Work.query.filter_by(id=sub2['id']).update({'created_at': tomorrow})
        session.commit()
        subs = assig.get_all_latest_submissions().all()
        assert len(subs) == 1
        assert subs[0].id == group_sub['id']

        # And the single function should do the same
        for user_id in [sub2['user']['id'], sub3['user']['id']]:
            found_sub = assig.get_latest_submission_for_user(
                m.User.query.get(user_id)
            ).one()
            assert found_sub.id == group_sub['id']

    with describe(
        'When the assignment is deleted no submissions should be found'
    ):
        assig.mark_as_deleted()
        session.flush()

        # No latest submissions should be found
        assert not assig.get_all_latest_submissions().all()

        for user in [sub2['user'], sub3['user']]:
            # Each individual user should also not have a latest submission
            assert assig.get_latest_submission_for_user(
                m.User.query.get(helpers.get_id(user))
            ).first() is None

        assig.visibility_state = m.AssignmentVisibilityState.visible
        session.flush()

    with describe(
        'After deleting group submission we get student submissions again'
    ):
        with logged_in(teacher):
            test_client.req(
                'delete', f'/api/v1/submissions/{group_sub["id"]}', 204
            )
        subs = m.Assignment.query.get(assig_id
                                      ).get_all_latest_submissions().all()
        assert len(subs) == 2
        assert {s.id for s in subs} == {sub3['id'], sub2['id']}

        # And the single function should do the same
        for sub in [sub2, sub3]:
            user_id = sub['user']['id']
            found_sub = assig.get_latest_submission_for_user(
                m.User.query.get(user_id)
            ).one()
            assert found_sub.id == sub['id']


def test_all_submissions_by_a_user(
    logged_in, session, test_client, admin_user, tomorrow
):
    with logged_in(admin_user):
        course = helpers.create_course(test_client)

    student1 = helpers.create_user_with_role(session, 'Student', course)
    student2 = helpers.create_user_with_role(session, 'Student', course)
    teacher = helpers.create_user_with_role(session, 'Teacher', course)

    with logged_in(teacher):
        assig_id = helpers.create_assignment(
            test_client, course, 'open', deadline=tomorrow
        )['id']

    with logged_in(student1):
        sub1 = helpers.create_submission(test_client, assig_id)
        sub2 = helpers.create_submission(test_client, assig_id)
    with logged_in(student2):
        sub3 = helpers.create_submission(test_client, assig_id)

    def fix_subs(*subs):
        for sub in subs:
            sub['user'] = dict

    fix_subs(sub1, sub2, sub3)

    with logged_in(teacher):
        # A teacher can get all the submissions of a student
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/users/{student1.id}/submissions/',
            200,
            result=[sub2, sub1]
        )
    with logged_in(student2):
        # A student cannot get all the submissions by another student.
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/users/{student1.id}/submissions/',
            403,
        )

        # A student can get all the submissions by itself
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/users/{student2.id}/submissions/',
            200,
            result=[sub3]
        )

    with logged_in(teacher):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig_id}',
            200,
            data={
                'state': 'hidden',
            }
        )

    with logged_in(student2):
        # We don't have permission to see hidden assignments, so we can no
        # longer see our submissions.
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig_id}/users/{student2.id}/submissions/',
            403,
        )


def test_upload_test_submission(
    logged_in, session, error_template, test_client, request, admin_user,
    tomorrow, describe
):
    with logged_in(admin_user):
        course = helpers.create_course(test_client)

    student = helpers.create_user_with_role(session, 'Student', course)
    teacher = helpers.create_user_with_role(session, 'Teacher', course)
    test_student = None

    with logged_in(teacher):
        assig_id = helpers.create_assignment(test_client, course, 'open')['id']

        with describe('Fails if the "author" query is given'):
            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assig_id}/submission?is_test_submission&author={student.username}',
                400,
                real_data={
                    'file': (
                        get_submission_archive('single_file_archive.tar.gz'),
                        'single_file_archive',
                    )
                },
                result=error_template,
            )

        def assert_submitted(data=None, real_data=None):
            nonlocal test_student

            res = test_client.req(
                'post',
                f'/api/v1/assignments/{assig_id}/submission?is_test_submission',
                201,
                real_data={
                    'file': (
                        get_submission_archive('single_file_archive.tar.gz'),
                        'single_file_archive',
                    ),
                },
                result={
                    'id': int,
                    # Check that multiple submissions yield the same test
                    # student.
                    'user': dict if test_student is None else test_student,
                    'created_at': str,
                    'assignee': None,
                    'grade': None,
                    'comment': None,
                    'comment_author': None,
                    'grade_overridden': False,
                    'assignment_id': assig_id,
                    'extra_info': None,
                    'origin': 'uploaded_files',
                    'rubric_result': None,
                }
            )

            if test_student is None:
                test_student = res['user']

            assert res['user']['username'].startswith('TEST_STUDENT_')
            assert res['user']['is_test_student']

        with describe('Succeeds even if no deadline is set'):
            assert_submitted()

        with describe(
            'Succeeds after the deadline is set and is submitted by TEST_STUDENT_'
        ):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig_id}',
                200,
                data={
                    'deadline': tomorrow.isoformat(),
                },
            )

            assert_submitted()


def test_delete_assignment(
    test_client, admin_user, describe, session, logged_in
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assig = helpers.create_assignment(
            test_client, course, 'open', 'tomorrow'
        )['id']
        stud1 = helpers.create_user_with_role(session, 'Student', [course])
        with logged_in(stud1):
            sub1 = helpers.create_submission(test_client, assig)

    with describe('Can get submissions when not deleted'), logged_in(stud1):
        test_client.req(
            'get',
            f'/api/v1/assignments/{assig}/submissions/',
            200,
            result=[{
                '__allow_extra__': True,
                'id': sub1['id'],
            }]
        )
        test_client.req(
            'get', f'/api/v1/submissions/{sub1["id"]}', 200, result=sub1
        )

    with describe('Students cannot delete assignment'), logged_in(stud1):
        test_client.req('delete', f'/api/v1/assignments/{assig}', 403)

    with describe('Teacher can delete assignment'), logged_in(admin_user):
        test_client.req('delete', f'/api/v1/assignments/{assig}', 204)

    with describe('Cannot get submissions from delete assig'
                  ), logged_in(stud1):
        test_client.req('get', f'/api/v1/assignments/{assig}', 404)
        test_client.req(
            'get', f'/api/v1/assignments/{assig}/submissions/', 404
        )
        test_client.req('get', f'/api/v1/submissions/{sub1["id"]}', 404)


def test_continuous_rubrics(
    test_client, admin_user, describe, session, logged_in
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assig = helpers.create_assignment(
            test_client, course, 'open', 'tomorrow'
        )['id']
        stud1 = helpers.create_user_with_role(session, 'Student', [course])
        with logged_in(stud1):
            sub1 = helpers.create_submission(test_client, assig)['id']

    with describe('cannot create continuous with multiple items rubrics'
                  ), logged_in(admin_user):
        test_client.req(
            'put',
            f'/api/v1/assignments/{assig}/rubrics/',
            409,
            data={
                'rows': [{
                    'header': 'My header', 'description': 'My description',
                    'type': 'continuous', 'items': []
                }]
            }
        )

        test_client.req(
            'put',
            f'/api/v1/assignments/{assig}/rubrics/',
            409,
            data={
                'rows': [{
                    'header': 'My header',
                    'description': 'My description',
                    'type': 'continuous',
                    'items': [
                        {
                            'description': 'item description',
                            'header': 'header',
                            'points': 4,
                        },
                        {
                            'description': 'item description',
                            'header': 'header',
                            'points': 5,
                        },
                    ],
                }]
            }
        )

    with describe('unknown rubric types are rejected'), logged_in(admin_user):
        test_client.req(
            'put',
            f'/api/v1/assignments/{assig}/rubrics/',
            404,
            data={
                'rows': [{
                    'header': 'My header', 'description': 'My description',
                    'type': 'unknown', 'items': []
                }]
            }
        )

    with describe('can create continuous rubrics with one item'
                  ), logged_in(admin_user):
        # yapf: disable
        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{assig}/rubrics/',
            200,
            data={
                'rows': [
                    {
                        'header': 'My header',
                        'description': 'My description',
                        'type': 'normal',
                        'items': [{
                            'description': 'item description',
                            'header': 'header',
                            'points': 4,
                        }, {
                            'description': 'item description',
                            'header': 'header',
                            'points': 5,
                        }],
                    }, {
                        'header': 'My cont',
                        'description': 'continuous',
                        'type': 'continuous',
                        'items': [{
                            'description': 'item description',
                            'header': 'header',
                            'points': 8,
                        }],
                    }]
            }
        )
        # yapf: enable

    with describe('can grade with continuous rubrics'), logged_in(admin_user):
        # yapf: disable
        expected_rubric_result = {
            'rubrics': rubric,
            'selected': [{
                'id': rubric[0]['items'][0]['id'],
                'achieved_points': 4,
                'points': 4,
                '__allow_extra__': True,
            }, {
                'id': rubric[1]['items'][-1]['id'],
                'achieved_points': 0.8,
                'points': 8,
                '__allow_extra__': True,
            }],
            'points': {
                'max': 13,
                'selected': 4 + 0.8,
            }
        }
        # yapf: enable

        test_client.req(
            'patch',
            f'/api/v1/submissions/{sub1}/rubricitems/',
            200,
            data={
                'items': [
                    {
                        'row_id': rubric[0]['id'],
                        'item_id': rubric[0]['items'][0]['id'],
                        # Default multiplier should be 1
                    },
                    {
                        'row_id': rubric[1]['id'],
                        'item_id': rubric[1]['items'][-1]['id'],
                        'multiplier': 0.1,
                    }
                ]
            },
            result={
                '__allow_extra__': True,
                # Brackets are important for rounding here.
                'grade': 10 * ((4 + 0.8) / 13),
                'rubric_result': expected_rubric_result,
            },
        )
        test_client.req(
            'get',
            f'/api/v1/submissions/{sub1}/rubrics/',
            200,
            result=expected_rubric_result,
        )

    with describe('the points attribute should also work in sql'):
        assert len(
            session.query(m.WorkRubricItem
                          ).filter_by(work_id=sub1, points=0.8).all()
        ) == 1


def test_limiting_submissions(
    test_client, admin_user, describe, session, logged_in, assert_similar
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assig = helpers.create_assignment(
            test_client, course, 'open', 'tomorrow'
        )['id']
        stud = helpers.create_user_with_role(session, 'Student', [course])
        teacher = helpers.create_user_with_role(session, 'Teacher', [course])
        limited_ta = helpers.create_user_with_perms(
            session, [CPerm.can_submit_others_work, CPerm.can_see_assignments],
            [course]
        )

    with describe('Only teachers can set max submissions'):
        for user, code in [(stud, 403), (teacher, 200)]:
            with logged_in(user):
                res, rv = test_client.req(
                    'patch',
                    f'/api/v1/assignments/{assig}?no_course_in_assignment=1',
                    code,
                    data={'max_submissions': 2},
                    include_response=True,
                )
                if code == 200:
                    assert 'Warning' not in rv.headers
                    assert_similar(
                        res, {'__allow_extra__': True, 'max_submissions': 2}
                    )

    with describe('Can submit once'), logged_in(stud):
        helpers.create_submission(test_client, assig)

    with describe('Cannot submit after limit'), logged_in(stud):
        # Limit is two, exactly the limit is possible
        helpers.create_submission(test_client, assig)

        err = helpers.create_submission(test_client, assig, err=403)
        assert 'reached the maximum amount of 2' in err['message']

    with describe('Teacher can submit after the limit'), logged_in(teacher):
        helpers.create_submission(test_client, assig)

    with describe('We can unset the limit again'):
        with logged_in(teacher):
            _, rv = test_client.req(
                'patch',
                f'/api/v1/assignments/{assig}?no_course_in_assignment=1',
                200,
                data={'max_submissions': None},
                include_response=True,
                result={
                    '__allow_extra__': True,
                    'max_submissions': None,
                }
            )
            assert 'Warning' not in rv.headers

        with logged_in(stud):
            helpers.create_submission(test_client, assig)

    with describe('When we lower the limit a warning is displayed'
                  ), logged_in(teacher):
        _, rv = test_client.req(
            'patch',
            f'/api/v1/assignments/{assig}?no_course_in_assignment=1',
            200,
            data={'max_submissions': 1},
            include_response=True,
            result={
                '__allow_extra__': True,
                'max_submissions': 1,
            }
        )

        assert 'Warning' in rv.headers
        assert 'with more submission than the' in rv.headers['Warning']

        _, rv = test_client.req(
            'patch',
            f'/api/v1/assignments/{assig}?no_course_in_assignment=1',
            200,
            data={'max_submissions': 10},
            include_response=True,
            result={
                '__allow_extra__': True,
                'max_submissions': 10,
            }
        )
        assert 'Warning' not in rv.headers

    with describe('Enabling webhooks gives a warning'), logged_in(teacher):
        _, rv = test_client.req(
            'patch',
            f'/api/v1/assignments/{assig}?no_course_in_assignment=1',
            200,
            data={'webhook_upload_enabled': True},
            include_response=True,
        )
        assert 'Warning' in rv.headers
        assert 'combining a limit on submissions and webhooks' in rv.headers[
            'Warning']

    with describe('Cannot set amount to <= 0'), logged_in(teacher):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig}',
            400,
            data={'max_submissions': 0},
        )

    with describe('limits apply to the group, not user'):
        with logged_in(teacher):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig}',
                200,
                data={'max_submissions': 2},
            )

        with logged_in(stud):
            helpers.create_submission(test_client, assig, err=403)

        with logged_in(teacher):
            gset = helpers.create_group_set(test_client, course, 1, 2, [assig])
            group = helpers.create_group(test_client, gset, [stud])

        with logged_in(stud):
            new_sub = helpers.create_submission(test_client, assig)
            assert new_sub['user']['id'] == group['virtual_user']['id']

            helpers.create_submission(test_client, assig)

            # Reached maximum
            helpers.create_submission(test_client, assig, err=403)

        # TA without permission can also not submit
        with logged_in(limited_ta):
            err = helpers.create_submission(
                test_client, assig, for_user=stud, err=403
            )
            assert f'The group "{group["name"]}" has reached the maximum' in err[
                'message']


def test_cool_off_period(
    test_client, admin_user, describe, session, logged_in, assert_similar
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assig = helpers.create_assignment(
            test_client, course, 'open', 'tomorrow'
        )['id']
        assig2 = helpers.create_assignment(
            test_client, course, 'open', 'tomorrow'
        )['id']
        stud = helpers.create_user_with_role(session, 'Student', [course])
        teacher = helpers.create_user_with_role(session, 'Teacher', [course])
        submit_time = DatetimeWithTimezone.utcnow()

    with describe('Only teachers can set cool off period'):
        for user, code in [(stud, 403), (teacher, 200)]:
            with logged_in(user):
                res, rv = test_client.req(
                    'patch',
                    f'/api/v1/assignments/{assig}?no_course_in_assignment=1',
                    code,
                    data={'cool_off_period': 15},
                    include_response=True,
                )
                assert 'Warning' not in rv.headers
                if code == 200:
                    assert_similar(
                        res,
                        {'__allow_extra__': True, 'cool_off_period': 15.0}
                    )

    with freeze_time(submit_time):
        with describe('Cannot submit again within cool off period'):
            with logged_in(teacher):
                helpers.create_submission(test_client, assig, for_user=stud)

            with logged_in(stud):
                err = helpers.create_submission(test_client, assig, err=403)

            assert 'submit again yet' in err['message']

        with describe('Teacher can submit again within period'):
            with logged_in(teacher):
                helpers.create_submission(test_client, assig, for_user=stud)

    with freeze_time(submit_time + datetime.timedelta(seconds=16)):
        with describe('Can submit after cool off period'), logged_in(stud):
            helpers.create_submission(test_client, assig)

    with describe('Enabling webhooks gives a warning'), logged_in(teacher):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig2}',
            200,
            data={'webhook_upload_enabled': True},
        )
        _, rv = test_client.req(
            'patch',
            f'/api/v1/assignments/{assig2}?no_course_in_assignment=1',
            200,
            data={'cool_off_period': 5.5},
            include_response=True,
        )
        assert 'Warning' in rv.headers
        assert 'combining a cool off period' in rv.headers['Warning']


def test_cool_off_period_larger_amount(
    test_client, admin_user, describe, session, logged_in, assert_similar
):
    with describe('setup'), logged_in(admin_user):
        course = helpers.create_course(test_client)
        assig = helpers.create_assignment(
            test_client, course, 'open', 'tomorrow'
        )['id']
        stud = helpers.create_user_with_role(session, 'Student', [course])

        first_submit_time = DatetimeWithTimezone.utcnow()
        next_submit_time = first_submit_time + datetime.timedelta(minutes=5)
        final_submit_time = first_submit_time + datetime.timedelta(minutes=10)

        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig}',
            200,
            data={
                'cool_off_period': 15 * 60,
                'amount_in_cool_off_period': 2,
            }
        )

    with describe('Can submit twice very fast'):
        with freeze_time(first_submit_time), logged_in(stud):
            helpers.create_submission(test_client, assig)

        with freeze_time(next_submit_time), logged_in(stud):
            helpers.create_submission(test_client, assig)

    with describe('Cannot submit for a third time'
                  ), freeze_time(final_submit_time), logged_in(stud):
        err = helpers.create_submission(test_client, assig, err=403)
        assert 'you have to wait at least 5 minutes' in err['message']

    with describe('The minimum amount should be one'), logged_in(admin_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig}',
            400,
            data={'amount_in_cool_off_period': 0}
        )

    with describe('Students cannot change the amount'), logged_in(stud):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig}',
            403,
            data={'amount_in_cool_off_period': 1}
        )


def test_get_assigned_grader_ids(
    describe, session, test_client, logged_in, admin_user
):
    with describe('Setup'), logged_in(admin_user):
        course = create_course(test_client)
        assig_id = create_assignment(
            test_client,
            course,
            state='open',
            deadline=(
                DatetimeWithTimezone.utcnow() + datetime.timedelta(days=1)
            )
        )['id']

        students = [
            create_user_with_perms(
                session,
                [
                    CPerm.can_submit_own_work, CPerm.can_see_assignments,
                    CPerm.can_upload_after_deadline
                ],
                courses=[course],
            ) for _ in range(10)
        ]
        tas = [
            create_user_with_perms(
                session, [
                    CPerm.can_submit_own_work, CPerm.can_see_assignments,
                    CPerm.can_upload_after_deadline, CPerm.can_grade_work
                ],
                courses=[course]
            ) for _ in range(15)
        ]

        subs = []
        for student in students:
            with logged_in(student):
                subs.append(create_submission(test_client, assig_id))

        # Don't assign one submission. We do this to make sure that even when
        # there are unassigned submissions `get_assigned_grader_ids` never
        # returns `None`.
        subs_to_assign = subs[:-1]

        for sub, ta in zip(subs_to_assign, tas):
            m.Work.query.get(sub['id']).assigned_to = ta.id

        session.commit()

    with describe('All assigned graders should be returned'):
        assig = m.Assignment.query.get(assig_id)
        grader_ids = list(assig.get_assigned_grader_ids())
        assert None not in grader_ids
        assert sorted(grader_ids) == sorted(
            ta.id for ta in tas[:len(subs_to_assign)]
        )


def test_available_at(
    describe, admin_user, logged_in, test_client, session, yesterday, tomorrow,
    stub_function
):
    with describe('setup'), logged_in(admin_user):
        orig_open_at = psef.tasks.maybe_open_assignment_at
        open_at = stub_function(psef.tasks, 'maybe_open_assignment_at')
        course = helpers.create_course(test_client)
        assig = helpers.create_assignment(
            test_client,
            course,
            deadline=(tomorrow + datetime.timedelta(days=1))
        )
        teacher = helpers.create_user_with_perms(
            session, [
                CPerm.can_see_assignments,
                CPerm.can_see_hidden_assignments,
                CPerm.can_view_analytics,
                CPerm.can_edit_assignment_info,
            ], course
        )
        no_perm = helpers.create_user_with_perms(
            session, [
                CPerm.can_see_assignments,
                CPerm.can_see_hidden_assignments,
                CPerm.can_view_analytics,
            ], course
        )
        url = f'/api/v1/assignments/{helpers.get_id(assig)}'

    with describe('cannot set garbage data'), logged_in(teacher):
        test_client.req('patch', url, 400, data={'available_at': 'NOT A DATE'})
        assert not open_at.called

    with describe('cannot set after (or equal) deadline'), logged_in(teacher):
        test_client.req(
            'patch',
            url,
            409,
            data={
                'available_at':
                    (tomorrow + datetime.timedelta(days=1)).isoformat()
            }
        )
        assert not open_at.called

    with describe('permissions are checker'), logged_in(no_perm):
        test_client.req(
            'patch', url, 403, data={'available_at': yesterday.isoformat()}
        )
        assert not open_at.called

    with describe('can set available_at in the past'), logged_in(teacher):
        test_client.req(
            'patch',
            url,
            200,
            data={'available_at': yesterday.isoformat()},
            result={
                **assig,
                'available_at': yesterday.isoformat(),
                'state': 'submitting',
            }
        )
        # Don't schedule a task, as the available_at has already passed
        assert not open_at.called

    with describe('can set available_at in the future'), logged_in(teacher):
        test_client.req(
            'patch',
            url,
            200,
            data={'available_at': tomorrow.isoformat()},
            result={
                **assig,
                'available_at': tomorrow.isoformat(),
                'state': 'hidden',
            }
        )
        assert open_at.called
        assert open_at.called_amount == 1

        with freeze_time(tomorrow):
            del flask.g.request_start_time
            orig_open_at(*open_at.args[0], **open_at.kwargs[0])

        test_client.req(
            'get',
            url,
            200,
            result={
                **assig,
                'available_at': tomorrow.isoformat(),
                'state': 'submitting',
            }
        )

    with describe(
        'setting available_at when assignment is done has no effect'
    ), logged_in(teacher):
        test_client.req(
            'patch', url, 200, data={'state': 'done', 'available_at': None}
        )
        test_client.req(
            'patch',
            url,
            200,
            data={'available_at': tomorrow.isoformat()},
            result={
                **assig, 'state': 'done', 'available_at': tomorrow.isoformat()
            }
        )
        assert open_at.called
        assert open_at.called_amount == 1

        with freeze_time(tomorrow):
            del flask.g.request_start_time
            orig_open_at(*open_at.args[0], **open_at.kwargs[0])

        test_client.req(
            'get',
            url,
            200,
            result={
                **assig,
                'available_at': tomorrow.isoformat(),
                'state': 'done',
            }
        )


def test_changing_kind_of_assignment(
    describe, test_client, logged_in, admin_user, tomorrow, yesterday, session
):
    with describe('setup'), logged_in(admin_user):
        assig = helpers.create_assignment(test_client)
        student = helpers.create_user_with_role(
            session, 'Student', assig['course']
        )
        url = f'/api/v1/assignments/{helpers.get_id(assig)}'

    with describe('cannot change to exam without deadline and available at'
                  ), logged_in(admin_user):
        test_client.req('patch', url, 409, data={'kind': 'exam'})
        test_client.req(
            'patch', url, 200, data={'deadline': tomorrow.isoformat()}
        )
        test_client.req('patch', url, 409, data={'kind': 'exam'})
        test_client.req(
            'patch',
            url,
            200,
            data={'available_at': yesterday.isoformat(), 'kind': 'exam'},
            result={'__allow_extra__': True, 'kind': 'exam'}
        )

    with describe('students cannot change'), logged_in(student):
        test_client.req('patch', url, 200, data={'kind': 'normal'})

    with describe('can change back to normal'), logged_in(admin_user):
        test_client.req(
            'patch',
            url,
            200,
            data={'kind': 'normal'},
            result={'__allow_extra__': True, 'kind': 'normal'}
        )


def test_changing_kind_of_lti_assignment(
    describe, test_client, logged_in, admin_user, tomorrow, yesterday, session,
    lti1p3_provider, error_template
):
    with describe('setup'), logged_in(admin_user):
        course, _ = helpers.create_lti1p3_course(
            test_client, session, lti1p3_provider
        )
        assig = helpers.create_lti1p3_assignment(session, course)
        assig.deadline = tomorrow
        assig.available_at = yesterday
        url = f'/api/v1/assignments/{helpers.get_id(assig)}'
        session.commit()

    with describe('cannot change mode to exam'), logged_in(admin_user):
        test_client.req(
            'patch',
            url,
            409,
            data={'kind': 'exam'},
            result={
                **error_template,
                'message': 'Exam mode is not available for LTI assignments',
            }
        )


def test_set_available_at_for_lti_assignment(
    describe, test_client, logged_in, admin_user, error_template, app,
    yesterday, session
):
    with describe('setup'), logged_in(admin_user):
        canvas_course = helpers.create_lti_course(session, app, admin_user)
        canvas_assig = helpers.create_lti_assignment(session, canvas_course)
        canvas_url = f'/api/v1/assignments/{helpers.get_id(canvas_assig)}'

        bb_course = helpers.create_lti_course(
            session, app, admin_user, lms='Blackboard'
        )
        bb_assig = helpers.create_lti_assignment(session, bb_course)
        bb_url = f'/api/v1/assignments/{helpers.get_id(bb_assig)}'

        lti1p3_prov = helpers.create_lti1p3_provider(
            test_client, lms='Brightspace'
        )
        lti1p3_course, _ = helpers.create_lti1p3_course(
            test_client, session, lti1p3_prov
        )
        lti1p3_assig = helpers.create_lti_assignment(session, lti1p3_course)
        lti1p3_url = f'/api/v1/assignments/{helpers.get_id(lti1p3_assig)}'

    with describe('cannot change available at for canvas assignment'
                  ), logged_in(admin_user):
        test_client.req(
            'patch',
            canvas_url,
            400,
            data={'available_at': yesterday.isoformat()},
            result={
                **error_template,
                'message': (
                    'The available at of this assignment should be set in'
                    ' Canvas.'
                ),
            }
        )

    with describe('can change available at for bb assignment'
                  ), logged_in(admin_user):
        test_client.req(
            'patch',
            bb_url,
            200,
            data={'available_at': yesterday.isoformat()},
        )

    with describe(
        'cannot change available at for lti1p3 brightspace assignment'
    ), logged_in(admin_user):
        test_client.req(
            'patch',
            lti1p3_url,
            400,
            data={'available_at': yesterday.isoformat()},
            result={
                **error_template,
                'message': (
                    'The available at of this assignment should be set in'
                    ' Brightspace.'
                ),
            }
        )
