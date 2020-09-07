# SPDX-License-Identifier: AGPL-3.0-only
import io
import os
import re
import json
import uuid
import datetime
import contextlib
from copy import deepcopy

import pytest
from flask import _app_ctx_stack as ctx_stack
from werkzeug.local import LocalProxy

import psef
import psef.models as m
from cg_dt_utils import DatetimeWithTimezone
from psef.permissions import CoursePermission as CPerm
from psef.permissions import GlobalPermission as GPerm


def test_data(*path):
    return os.path.join(os.path.dirname(__file__), '..', 'test_data', *path)


def get_id(obj):
    if isinstance(obj, dict):
        return obj['id']
    elif isinstance(obj, int):
        return obj
    else:
        return obj.id


def dict_without(dct, *keys):
    res = {**dct}
    for key in keys:
        del res[key]
    return res


def to_db_object(obj, cls):
    if isinstance(obj, LocalProxy):
        obj = obj._get_current_object()

    if isinstance(obj, cls):
        return obj
    return cls.query.get(get_id(obj))


def create_marker(marker):
    def outer(*vals, **kwargs):
        def inner(vals):
            if vals is not None and isinstance(vals, tuple):
                return pytest.param(*vals, marks=marker(**kwargs))
            else:
                return pytest.param(vals, marks=marker(**kwargs))

        if kwargs:
            return inner
        return inner(*vals)

    return outer


def create_lti_assignment(
    session, course, state='hidden', deadline='tomorrow'
):
    name = f'__NEW_LTI_ASSIGNMENT__-{uuid.uuid4()}'

    if deadline == 'tomorrow':
        deadline = DatetimeWithTimezone.utcnow() + datetime.timedelta(days=1)

    res = m.Assignment(
        name=name,
        course=course,
        deadline=deadline,
        lti_assignment_id=str(uuid.uuid4()),
        is_lti=True,
    )
    res.lti_grade_service_data = str(uuid.uuid4())
    res.set_state_with_string(state)
    session.add(res)
    session.commit()
    return res


def create_lti1p3_user(session, provider):
    n_id = str(uuid.uuid4())
    username = f'LTI1p3_USER_{uuid.uuid4()}'
    with psef.auth.as_current_user(None):
        user, _ = m.UserLTIProvider.get_or_create_user(
            n_id, provider, username, 'A LTI 1.3 user', 'user@lti.com'
        )
    session.commit()
    u_id = user.id
    return LocalProxy(lambda: m.User.query.get(u_id))


def create_lti1p3_assignment(session, course, state='hidden', deadline=None):
    course = to_db_object(course, m.Course)
    assert course.is_lti
    assig = psef.models.Assignment(
        course=course,
        name=f'LTI 1.3 ASSIG {uuid.uuid4()}',
        is_lti=True,
        visibility_state=psef.models.AssignmentVisibilityState.visible,
        lti_assignment_id=str(uuid.uuid4()),
    )
    assig.lti_grade_service_data = {
        'lineitem': f'http://{uuid.uuid4()}.com',
        'scope': ['https://purl.imsglobal.org/spec/lti-ags/scope/score'],
    }
    assig.set_state_with_string(state)
    assig.deadline = deadline
    session.add(assig)
    session.commit()
    return assig


def create_lti1p3_course(test_client, session, provider, membership_url=None):
    course = to_db_object(create_course(test_client), m.Course)
    course_lti_prov = m.CourseLTIProvider.create_and_add(
        course=course,
        lti_provider=provider,
        lti_context_id=str(uuid.uuid4()),
        deployment_id=str(uuid.uuid4()),
    )
    course_lti_prov.names_roles_claim = {
        'context_memberships_url': membership_url or str(uuid.uuid4()),
    }
    session.commit()
    return course, course_lti_prov


def create_lti1p3_provider(
    test_client,
    lms,
    iss=None,
    client_id=None,
    auth_token_url=None,
    auth_login_url=None,
    key_set_url=None,
    auth_audience=None
):
    intended_use = 'A test provider'
    iss = iss or str(uuid.uuid4())
    prov = test_client.req(
        'post',
        '/api/v1/lti1.3/providers/',
        200,
        data={
            'lms': lms,
            'iss': iss,
            'intended_use': intended_use,
        },
        result={
            'id': str,
            'lms': lms,
            'intended_use': intended_use,
            'version': 'lti1.3',
            'iss': iss,
            'capabilities': dict,
            'edit_secret': str,
            'finalized': False,
            'auth_login_url': None,
            'auth_token_url': None,
            'client_id': None,
            'key_set_url': None,
            'auth_audience': None,
            'custom_fields': dict,
            'public_jwk': dict,
            'public_key': str,
            'created_at': str,
        },
    )

    def make_data(**data):
        return {k: v or 'http://' + str(uuid.uuid4()) for k, v in data.items()}

    return test_client.req(
        'patch',
        f'/api/v1/lti1.3/providers/{get_id(prov)}',
        200,
        data=make_data(
            client_id=client_id,
            auth_token_url=auth_token_url,
            auth_login_url=auth_login_url,
            auth_audience=auth_audience,
            key_set_url=key_set_url,
            finalize=True,
        ),
        result={
            'id': str,
            'lms': lms,
            'intended_use': intended_use,
            'version': 'lti1.3',
            'iss': iss,
            'capabilities': dict,
            'edit_secret': None,
            'finalized': True,
            'created_at': str,
        },
    )


def create_lti_course(session, app, user=None):
    name = f'__NEW_LTI_COURSE__-{uuid.uuid4()}'
    key = list(app.config['LTI_CONSUMER_KEY_SECRETS'].keys())[0]
    lti_provider = m.LTI1p1Provider(key=key)
    assert lti_provider is not None

    c = m.Course.create_and_add(name=name)

    if user:
        user = m.User.resolve(user)
        user.courses[c.id] = m.CourseRole.query.filter_by(
            course=c, name='Teacher'
        ).one()

    lti_context_id = str(uuid.uuid4())
    m.CourseLTIProvider.create_and_add(
        course=c,
        lti_provider=lti_provider,
        lti_context_id=lti_context_id,
        deployment_id=lti_context_id,
    )

    session.commit()
    return c


def create_course(test_client):
    name = f'__NEW_COURSE__-{uuid.uuid4()}'
    return test_client.req(
        'post',
        '/api/v1/courses/',
        200,
        data={'name': name},
        result={'name': name, '__allow_extra__': True},
    )


def create_assignment(
    test_client, course_id=None, state='hidden', deadline=None
):
    name = f'__NEW_ASSIGNMENT__-{uuid.uuid4()}'
    if course_id is None:
        course_id = create_course(test_client)

    if deadline == 'tomorrow':
        deadline = DatetimeWithTimezone.utcnow() + datetime.timedelta(days=1)

    res = test_client.req(
        'post',
        f'/api/v1/courses/{get_id(course_id)}/assignments/',
        200,
        data={'name': name},
        result={'name': name, '__allow_extra__': True},
    )
    data = {}
    if state != 'hidden':
        data['state'] = state
    if deadline is not None:
        if isinstance(deadline, datetime.datetime):
            deadline = deadline.isoformat()
        data['deadline'] = deadline
    res = test_client.req(
        'patch', f'/api/v1/assignments/{res["id"]}', 200, data=data
    )
    return res


def enable_peer_feedback(
    test_client,
    assignment,
    *,
    amount=1,
    days=6,
    auto_approved=False,
    err=False
):
    assignment_id = get_id(assignment)
    time = (
        None if days is None else datetime.timedelta(days=days).total_seconds()
    )
    return test_client.req(
        'put',
        f'/api/v1/assignments/{assignment_id}/peer_feedback_settings',
        err or 200,
        data={
            'amount': amount,
            'time': time,
            'auto_approved': auto_approved,
        },
        result=create_error_template() if err else {
            'amount': amount,
            'time': time,
            'auto_approved': auto_approved,
        }
    )


def create_submission(
    test_client,
    assignment_id=None,
    err=None,
    submission_data=(
        test_data('test_submissions', 'multiple_dir_archive.zip'),
        'f.zip',
    ),
    is_test_submission=False,
    for_user=None,
):
    status = err or 201
    err_t = create_error_template()
    err_t['__allow_extra__'] = True
    if assignment_id is None:
        assignment_id = create_assignment(test_client)['id']
    result = ({
        'id': int,
        'user': dict,
        'created_at': str,
        'assignee': None,
        'grade': None,
        'comment': None,
        'comment_author': None,
        'grade_overridden': False,
        'assignment_id': get_id(assignment_id),
        'extra_info': None,
        'origin': 'uploaded_files',
        'rubric_result': object,
    } if err is None else err_t)

    path = f'/api/v1/assignments/{get_id(assignment_id)}/submission'
    if is_test_submission:
        path += '?is_test_submission'
    elif for_user is not None:
        if isinstance(for_user, dict):
            for_user = for_user['username']
        elif hasattr(for_user, 'username'):
            for_user = for_user.username
        elif isinstance(for_user, int):
            for_user = m.User.query.get(for_user).username
        path += f'?author={for_user}'

    return test_client.req(
        'post',
        path,
        status,
        real_data={'file': submission_data},
        result=result,
    )


def create_group_set(
    test_client, course_id, min_size, max_size, assig_ids=None
):
    if assig_ids is None:
        assig_ids = []
    g_set = test_client.req(
        'put',
        f'/api/v1/courses/{get_id(course_id)}/group_sets/',
        data={'minimum_size': min_size, 'maximum_size': max_size},
        status_code=200,
        result={
            'id': int,
            'maximum_size': max_size,
            'minimum_size': min_size,
            'assignment_ids': [],
        },
    )
    for assig in assig_ids:
        assig_id = get_id(assig)
        test_client.req(
            'patch',
            f'/api/v1/assignments/{get_id(assig_id)}',
            200,
            data={'group_set_id': get_id(g_set)},
        )
    return g_set


def create_user_with_role(session, role, courses, gperms=None, name=None):
    if not isinstance(courses, list):
        courses = [courses]
    n_id = str(uuid.uuid4())
    new_role = m.Role(name=f'NEW_ROLE--{n_id}')
    if gperms is not None:
        for gperm in GPerm:
            new_role.set_permission(gperm, gperm in gperms)

    user = m.User(
        name=f'NEW_USER-{role}-{n_id}' if name is None else name,
        email=f'new_user_{role}-{n_id}@a.nl',
        password=n_id,
        active=True,
        username=f'a-the-a-er-{n_id}' if name is None else f'{name}{n_id}',
        role=new_role,
    )
    for course in courses:
        user.courses[get_id(course)] = m.CourseRole.query.filter_by(
            name=role, course_id=get_id(course)
        ).one()
    session.add(user)
    session.commit()
    u_id = user.id
    return LocalProxy(lambda: m.User.query.get(u_id))


def create_user_with_perms(session, perms, courses, gperms=None, name=None):
    role_name = f'NEW-COURSE-ROLE-{",".join(map(str, perms))}-{uuid.uuid4().hex}'
    courses = courses if isinstance(courses, list) else [courses]
    for course in courses:
        course = m.Course.query.get(get_id(course))
        crole = m.CourseRole(name=role_name, course=course, hidden=False)
        for perm in CPerm:
            crole.set_permission(perm, perm in perms)
        session.add(crole)
    session.flush()
    user = create_user_with_role(
        session, role_name, courses, name=name, gperms=gperms
    )
    print('Created user', user.id, 'with permissions:', perms)
    return user


def create_group(test_client, group_set_id, member_ids):
    return test_client.req(
        'post',
        f'/api/v1/group_sets/{get_id(group_set_id)}/group',
        data={'member_ids': list(map(get_id, member_ids))},
        status_code=200,
        result={
            'id': int,
            'name': str,
            'members': list,
            'created_at': str,
            'group_set_id': get_id(group_set_id),
            'virtual_user': {
                'id': int,
                'name': re.compile(r'^Virtual - GROUP_'),
                'username': re.compile(r'^VIRTUAL_USER_'),
                '__allow_extra__': {'group'},
            },
        },
    )


def create_error_template():
    return {'code': str, 'message': str, 'description': str}


def get_newest_submissions(test_client, assignment):
    # When duplicate keys occur last wins in dict comprehensions so
    # this makes sure we only have the latest submission for a user.
    return {
        s['user']['id']: s
        for s in reversed(
            test_client.req(
                'get',
                f'/api/v1/assignments/{get_id(assignment)}/submissions/', 200
            )
        )
    }


def create_sso_provider(
    test_client,
    stub_function,
    name,
    *,
    err=False,
    no_call=None,
    ui_info=None,
    description='A test SSO',
    no_stub=False,
):
    no_call = psef.helpers.handle_none(no_call, err)

    @contextlib.contextmanager
    def stubbed():
        if no_stub:
            yield None, None
        else:
            with stub_function.temp_stubs() as stubber:
                stub_parse = stubber.stub(
                    psef.models.saml_provider._MetadataParser,
                    'parse',
                    lambda: {
                        'idp': {
                            'ui_info':
                                ui_info or {
                                    'name': name,
                                    'description': name + ' ' + name,
                                    'logo': None,
                                }
                        }
                    },
                )
                stub_download = stubber.stub(
                    psef.models.saml_provider._MetadataParser,
                    'get_metadata', lambda: ''
                )
                yield stub_parse, stub_download

    with stubbed() as (stub_parse, stub_download):
        prov = test_client.req(
            'post',
            '/api/v1/sso_providers/',
            err or 200,
            real_data={
                'json': (
                    io.BytesIO(
                        json.dumps({
                            'metadata_url': 'test.com',
                            'name': name,
                            'description': description,
                        }).encode()
                    ), 'json'
                ),
                'logo': (test_data('test_images', 'codegrade.svg'), 'logo'),
            },
            result=create_error_template() if err else {
                'id': str,
                'metadata_url': 'test.com',
                'ui_info': dict,
            }
        )

        if not no_stub:
            assert stub_parse.called_amount == 0 if no_call else 1
            assert stub_download.called == 0 if no_call else 1
            for kwarg in stub_download.kwargs:
                assert kwarg['validate_cert'] is True

        return prov


def get_simple_rubric():
    return {
        'rows': [{
            'header': 'My header',
            'description': 'My description',
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


def get_auto_test_io_step():
    return {
        'type': 'io_test',
        'data': {
            'inputs': [
                {
                    'name': 'without name',
                    'weight': 0.5,
                    'args': '',
                    'stdin': '',
                    'output': 'hello stranger!',
                    'options': [],
                },
                {
                    'name': 'with name',
                    'weight': 0.5,
                    'args': 'Thomas',
                    'stdin': '',
                    'output': 'hello Thomas',
                    'options': ['substring'],
                },
            ],
            'program': 'python3 test.py',
        },
        'name': 'Simple io test',
        'hidden': False,
        'weight': 1,
    }


def get_auto_test_custom_output_step():
    return {
        'type': 'custom_output',
        'data': {'program': 'echo 1.0', 'regex': '\\f'},
        'name': 'Custom output',
        'weight': 1,
        'hidden': False,
    }


def get_auto_test_check_points_step(hidden=False):
    return {
        'type': 'check_points',
        'data': {'min_points': 0.5},
        'name': 'Check points',
        'weight': 0,
        'hidden': hidden,
    }


def get_auto_test_run_program_step(sleep_time=5):
    return {
        'type': 'run_program',
        'data': {'program': f'sleep {sleep_time}'},
        'name': 'Simple run program',
        'weight': 1,
        'hidden': False,
    }


def create_auto_test(
    test_client,
    assignment,
    amount_sets=1,
    amount_suites=1,
    stop_points=None,
    grade_calculation=None,
    amount_fixtures=0,
    results_always_visible=False,
    prefer_teacher_revision=False,
    has_hidden_steps=False,
):
    a_id = get_id(assignment)

    test = test_client.req(
        'post',
        '/api/v1/auto_tests/',
        data={
            'assignment_id': a_id,
            'setup_script': 'ls',
            'run_setup_script': 'echo 1',
        },
        status_code=200,
        result={
            'id': int,
            'fixtures': [],
            'setup_script': 'ls',
            'run_setup_script': 'echo 1',
            'finalize_script': '',
            'sets': [],
            'assignment_id': a_id,
            'runs': [],
            'grade_calculation': None,
            'results_always_visible': None,
            'prefer_teacher_revision': None,
        },
    )

    if grade_calculation is not None:
        test_client.req(
            'patch',
            f'/api/v1/auto_tests/{get_id(test)}',
            200,
            data={
                'grade_calculation': grade_calculation,
                'results_always_visible': results_always_visible,
                'prefer_teacher_revision': prefer_teacher_revision,
            },
            result={
                'grade_calculation': grade_calculation,
                '__allow_extra__': True,
                'results_always_visible': results_always_visible,
                'prefer_teacher_revision': prefer_teacher_revision,
            }
        )

    def get_test():
        t_id = get_id(test)
        return test_client.req('get', f'/api/v1/auto_tests/{t_id}', 200)

    if amount_sets * amount_suites > 0:
        rubric_data = get_simple_rubric()
        rubric_data['rows'] = [
            deepcopy(rubric_data['rows'][0])
            for _ in range(amount_suites * amount_sets)
        ]

        rubric = test_client.req(
            'put',
            f'/api/v1/assignments/{a_id}/rubrics/',
            200,
            data=rubric_data
        )

    for idx1 in range(amount_sets):
        s = test_client.req(
            'post', f'/api/v1/auto_tests/{get_id(test)}/sets/', 200
        )

        if stop_points is not None and stop_points[idx1] is not None:
            test_client.req(
                'patch',
                f'/api/v1/auto_tests/{get_id(test)}/sets/{get_id(s)}',
                200,
                data={'stop_points': stop_points[idx1]}
            )

        for idx2 in range(amount_suites):
            rubric_index = idx1 * amount_suites + idx2

            test_client.req(
                'patch',
                f'/api/v1/auto_tests/{get_id(test)}/sets/{get_id(s)}/suites/',
                200,
                data={
                    'steps': [
                        get_auto_test_io_step(),
                        get_auto_test_check_points_step(has_hidden_steps),
                        get_auto_test_custom_output_step(),
                        get_auto_test_run_program_step(5 if idx1 else 0),
                    ],
                    'rubric_row_id': rubric[rubric_index]['id'],
                    'network_disabled': bool(idx2),
                    'submission_info': bool(idx2),
                },
            )

    for i in range(amount_fixtures):
        test_client.req(
            'patch',
            f'/api/v1/auto_tests/{get_id(test)}',
            200,
            real_data={
                'json': (
                    io.BytesIO(
                        json.dumps({
                            'has_new_fixtures': True,
                        }).encode()
                    ), 'json'
                ),
                'fixture': (io.BytesIO(f'hello{i}'.encode()), 'fixture1'),
            }
        )

    return get_test()


def create_auto_test_from_dict(test_client, assig, at_dict):
    a_id = get_id(assig)

    test = test_client.req(
        'post',
        '/api/v1/auto_tests/',
        data={
            'assignment_id': a_id,
            'setup_script': at_dict.get('setup_script', ''),
            'run_setup_script': at_dict.get('run_setup_script', ''),
            'grade_calculation': at_dict.get('grade_calculation', 'full'),
            'prefer_teacher_revision':
                at_dict.get('prefer_teacher_revision', False),
            'results_always_visible':
                at_dict.get('results_always_visible', True),
        },
        status_code=200,
    )

    rubric_data = []
    for at_set in at_dict['sets']:
        for at_suite in at_set['suites']:
            rubric_type = at_suite.pop('rubric_type', 'normal')
            row = {
                'header': at_suite.get('rubric_header', 'My header'),
                'description': at_suite.get('rubric_desc', 'My description'),
                'type': rubric_type,
            }
            if rubric_type == 'normal':
                row['items'] = ([{
                    'description': 'initial item', 'header': 'zero points',
                    'points': 0
                }] + [{
                    'description': 'item description',
                    'header': item['name'],
                    'points': idx + 1,
                } for idx, item in enumerate(at_suite['steps'])])
            else:
                row['items'] = [{
                    'description': 'item description',
                    'header': 'continuous rubric header',
                    'points':
                        sum(s.get('weight', 1) for s in at_suite['steps']),
                }]
            rubric_data.append(row)

    assert rubric_data, 'You need at least one suite'
    rubric = test_client.req(
        'put',
        f'/api/v1/assignments/{a_id}/rubrics/',
        200,
        data={'rows': rubric_data}
    )

    def prepare_steps(steps):
        res = []
        for step in steps:
            if 'type' not in step and 'run_p' in step:
                step = {
                    'type': 'run_program',
                    'data': {'program': step.pop('run_p')},
                    **step,
                }
            elif 'type' not in step and 'run_c' in step:
                step = {
                    'type': 'custom_output',
                    'data': {'program': step.pop('run_c'), 'regex': r'\f'},
                    **step,
                }
            res.append({'weight': 1, 'hidden': False, **step})
        return res

    rubric_index = 0
    for at_set in at_dict['sets']:
        s = test_client.req(
            'post', f'/api/v1/auto_tests/{get_id(test)}/sets/', 200
        )

        stop_points = at_set.get('stop_points', None)
        if stop_points is not None:
            test_client.req(
                'patch',
                f'/api/v1/auto_tests/{get_id(test)}/sets/{get_id(s)}',
                200,
                data={'stop_points': stop_points}
            )

        for at_suite in at_set['suites']:
            test_client.req(
                'patch',
                f'/api/v1/auto_tests/{get_id(test)}/sets/{get_id(s)}/suites/',
                200,
                data={
                    'steps': prepare_steps(at_suite['steps']),
                    'rubric_row_id': get_id(rubric[rubric_index]),
                    'network_disabled': at_suite.get('network_disabled', True),
                    'submission_info': at_suite.get('submission_info', False),
                },
            )
            rubric_index += 1

    for fixture in at_dict.get('fixtures', []):
        test_client.req(
            'patch',
            f'/api/v1/auto_tests/{get_id(test)}',
            200,
            real_data={
                'json': (
                    io.BytesIO(
                        json.dumps({
                            'has_new_fixtures': True,
                        }).encode()
                    ), 'json'
                ),
                'fixture': (fixture, 'fixture1'),
            }
        )

    return test_client.req('get', f'/api/v1/auto_tests/{get_id(test)}', 200)
