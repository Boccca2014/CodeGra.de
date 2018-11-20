# SPDX-License-Identifier: AGPL-3.0-only
import os
import urllib
import datetime
import xml.etree.ElementTree as ET

import oauth2
import pytest
import dateutil.parser

import psef.auth as auth
import psef.models as m
from helpers import create_marker

perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)

SUCCESS_XML = open(
    os.path.join(
        os.path.dirname(__file__),
        '..',
        'test_data',
        'example_strings',
        'valid_replace_result.xml',
    )
).read()


@pytest.fixture(autouse=True)
def monkeypatch_oauth_check(monkeypatch):
    def valid_oauth(*args, **kwargs):
        return

    monkeypatch.setattr(auth, 'ensure_valid_oauth', valid_oauth)


def test_lti_config(test_client, error_template):
    test_client.req('get', '/api/v1/lti/', 400, result=error_template)
    test_client.req(
        'get', '/api/v1/lti/?lms=unkown', 400, result=error_template
    )
    res = test_client.get('/api/v1/lti/?lms=Canvas')
    assert res.status_code == 200
    assert res.content_type.startswith('application/xml')
    assert '$Canvas' in res.get_data(as_text=True)


def test_lti_new_user_new_course(test_client, app, logged_in, ta_user):
    due_at = datetime.datetime.utcnow() + datetime.timedelta(
        days=1, hours=1, minutes=2
    )
    due_at = due_at.replace(second=0, microsecond=0)

    def do_lti_launch(
        name='A the A-er',
        lti_id='USER_ID',
        source_id='',
        published='false',
        username='a-the-a-er',
        due=None
    ):
        with app.app_context():
            due_date = due or due_at.isoformat() + 'Z'
            data = {
                'custom_canvas_course_name': 'NEW_COURSE',
                'custom_canvas_course_id': 'MY_COURSE_ID',
                'custom_canvas_assignment_id': 'MY_ASSIG_ID',
                'custom_canvas_assignment_title': 'MY_ASSIG_TITLE',
                'roles': 'instructor',
                'custom_canvas_user_login_id': username,
                'custom_canvas_course_title': 'Common Lisp',
                'custom_canvas_assignment_due_at': due_date,
                'custom_canvas_assignment_published': published,
                'user_id': lti_id,
                'lis_person_contact_email_primary': 'a@a.nl',
                'lis_person_name_full': name,
                'context_id': 'NO_CONTEXT',
                'context_title': 'WRONG_TITLE',
                'oauth_consumer_key': 'my_lti',
                'lis_outcome_service_url': source_id,
            }
            if source_id:
                data['lis_result_sourcedid'] = source_id
            res = test_client.post('/api/v1/lti/launch/1', data=data)

            url = urllib.parse.urlparse(res.headers['Location'])
            jwt = urllib.parse.parse_qs(url.query)['jwt'][0]
            lti_res = test_client.req(
                'post',
                '/api/v1/lti/launch/2',
                200,
                data={'jwt_token': jwt},
            )
            if published == 'false':
                assert lti_res['assignment']['state'] == 'hidden'
            else:
                assert m.Assignment.query.get(
                    lti_res['assignment']['id']
                ).state == m._AssignmentStateEnum.open
            assert lti_res['assignment']['course']['name'] == 'NEW_COURSE'
            if due is None:
                assert lti_res['assignment']['deadline'] == due_at.isoformat()
            return lti_res['assignment'], lti_res.get('access_token', None)

    def get_user_info(token):
        with app.app_context():
            return test_client.req(
                'get',
                '/api/v1/login?extended',
                200,
                headers={'Authorization': f'Bearer {token}'} if token else {}
            )

    assig, token = do_lti_launch(due='WOW, wrong')
    assert (dateutil.parser.parse(assig['deadline']) - due_at).days == 363
    out = get_user_info(token)
    assert out['name'] == 'A the A-er'
    assert out['username'] == 'a-the-a-er'
    old_id = out['id']

    _, token = do_lti_launch()
    out = get_user_info(token)
    assert out['name'] == 'A the A-er'
    assert out['username'] == 'a-the-a-er'
    assert out['id'] == old_id

    user = m.User.query.filter_by(name=out['name']).one()
    assert len(user.courses) == 1
    assert list(user.courses.values())[0].name == 'Teacher'
    with logged_in(user):
        _, token = do_lti_launch()
        assert token is None
        out = get_user_info(False)
        assert out['name'] == 'A the A-er'
        assert out['username'] == 'a-the-a-er'

    with logged_in(ta_user):
        _, token = do_lti_launch()
        out = get_user_info(token)
        assert out['name'] == 'A the A-er'
        assert out['username'] == 'a-the-a-er'

    with logged_in(ta_user):
        assig, token = do_lti_launch(
            lti_id='THOMAS_SCHAPER',
            source_id='WOW',
            username='SOMETHING_ELSE',
            due='WOW_WRONG',
        )
        assert token is None
        out = get_user_info(False)
        assert out['name'] == ta_user.name
        assert out['username'] == ta_user.username
        assert m.User.query.get(ta_user.id).lti_user_id == 'THOMAS_SCHAPER'

        assert assig['id'] in ta_user.assignment_results

        assert dateutil.parser.parse(assig['deadline']) == due_at

        assig, token = do_lti_launch(
            lti_id='THOMAS_SCHAPER',
            source_id='WOW2',
            published='true',
            username='WOW33',
        )
        out = get_user_info(False)
        assert ta_user.assignment_results[assig['id']].sourcedid == 'WOW2'


def test_lti_no_roles_found(test_client, app, logged_in, ta_user, monkeypatch):
    due_at = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    no_course_role = True

    def do_lti_launch(
        username='A the A-er',
        lti_id='USER_ID',
        source_id='',
        published='false',
        parse=True,
        code=200
    ):
        with app.app_context():
            other_role = 'administrator' if no_course_role else 'instructor'
            data = {
                'custom_canvas_course_name': 'NEW_COURSE',
                'custom_canvas_course_id': 'MY_COURSE_ID',
                'custom_canvas_assignment_id': 'MY_ASSIG_ID',
                'custom_canvas_assignment_title': 'MY_ASSIG_TITLE',
                'roles': '{},non_existing'.format(other_role),
                'custom_canvas_user_login_id': username,
                'custom_canvas_course_title': 'Common Lisp',
                'custom_canvas_due_at': due_at.isoformat(),
                'custom_canvas_assignment_published': published,
                'user_id': lti_id,
                'lis_person_contact_email_primary': 'a@a.nl',
                'lis_person_name_full': username,
                'context_id': 'NO_CONTEXT',
                'context_title': 'WRONG_TITLE',
                'oauth_consumer_key': 'my_lti',
                'lis_outcome_service_url': source_id,
            }
            if source_id:
                data['lis_result_sourcedid'] = source_id
            res = test_client.post('/api/v1/lti/launch/1', data=data)

            url = urllib.parse.urlparse(res.headers['Location'])
            jwt = urllib.parse.parse_qs(url.query)['jwt'][0]
            lti_res = test_client.req(
                'post',
                '/api/v1/lti/launch/2',
                code,
                data={'jwt_token': jwt},
            )
            if not parse:
                return lti_res

            if published == 'false':
                assert lti_res['assignment']['state'] == 'hidden'
            else:
                assert m.Assignment.query.get(
                    lti_res['assignment']['id']
                ).state == m._AssignmentStateEnum.open
            assert lti_res['assignment']['course']['name'] == 'NEW_COURSE'
            return lti_res['assignment'], lti_res.get(
                'access_token', None
            ), lti_res

    def get_user_info(token):
        with app.app_context():
            return test_client.req(
                'get',
                '/api/v1/login',
                200,
                headers={'Authorization': f'Bearer {token}'} if token else {}
            )

    _, token, res = do_lti_launch()
    out = get_user_info(token)
    assert out['name'] == 'A the A-er'
    assert res['new_role_created']
    old_id = out['id']

    _, token, __ = do_lti_launch()
    out = get_user_info(token)
    assert out['name'] == 'A the A-er'
    assert out['id'] == old_id

    user = m.User.query.filter_by(name=out['name']).one()
    assert user.role.name == 'Admin'
    assert len(user.courses) == 1
    assert list(user.courses.values())[0].name == 'non_existing'

    monkeypatch.setitem(app.config['FEATURES'], 'AUTOMATIC_LTI_ROLE', False)

    _, __, res = do_lti_launch(username='NEW_USERNAME')
    assert not res['new_role_created']

    res = do_lti_launch(username='NEW_USER', lti_id='5', code=400, parse=False)
    assert res['message'].startswith('The given LTI role was not')

    no_course_role = False
    _, token, __ = do_lti_launch(
        username='NEW_USER1233', lti_id='6', code=200, parse=True
    )
    out = get_user_info(token)
    assert out['username'] == 'NEW_USER1233'
    assert m.User.query.get(out['id']).role is not None


@pytest.mark.parametrize('patch', [True, False])
@pytest.mark.parametrize('filename', [
    ('correct.tar.gz'),
])
def test_lti_grade_passback(
    test_client, app, logged_in, ta_user, filename, monkeypatch, patch,
    monkeypatch_celery, error_template, session
):
    due_at = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    assig_max_points = 8
    lti_max_points = assig_max_points / 2
    last_xml = None

    def _get_parsed(xml):
        assert xml is not None

        # Normal parsing should work
        out = ET.fromstring(xml)
        assert out
        ns = 'http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0'
        # Make sure the namespace is set correctly
        assert out.tag.split('}')[0].strip('{') == ns

        # Parse it without namespace for ease of testing
        xml_no_ns = xml.replace(f' xmlns="{ns}"', '', 1)
        res = ET.fromstring(xml_no_ns)
        assert res
        assert res.tag == 'imsx_POXEnvelopeRequest'
        print(ET.tostring(res))
        return res

    def assert_grade_deleted():
        nonlocal last_xml

        el = _get_parsed(last_xml)
        req_el = el.find('imsx_POXBody/deleteResultRequest')
        assert req_el
        assert el.find(
            'imsx_POXHeader/imsx_POXRequestHeaderInfo/imsx_messageIdentifier'
        ) is not None
        assert req_el.find(
            'resultRecord/sourcedGUID/sourcedId'
        ).text == patch_request.source_id
        last_xml = None

    def assert_grade_set_to(grade, raw, created_at):
        nonlocal last_xml
        assert isinstance(grade, (int, float))

        el = _get_parsed(last_xml)
        req_el = el.find('imsx_POXBody/replaceResultRequest/resultRecord')
        assert req_el

        assert req_el.find(
            'sourcedGUID/sourcedId'
        ).text == patch_request.source_id

        assert el.find(
            'imsx_POXHeader/imsx_POXRequestHeaderInfo/imsx_messageIdentifier'
        ) is not None
        if raw:
            score = req_el.find('result/resultTotalScore')
            assert score is not None
            assert score.find('language').text == 'en'
            assert score.find('textString').text == str(
                grade / 10 * lti_max_points
            )
            assert req_el.find('result/resultScore') is None
        else:
            score = req_el.find('result/resultScore')
            assert score is not None
            assert score.find('language').text == 'en'
            assert score.find('textString').text == str(grade / 10)
            assert req_el.find('result/resultTotalScore') is None

        assert el.find(
            'imsx_POXBody/replaceResultRequest/submissionDetails/submittedAt'
        ).text.startswith(created_at)

        last_xml = None

    def assert_initial_passback():
        nonlocal last_xml

        el = _get_parsed(last_xml)
        req_el = el.find('imsx_POXBody/replaceResultRequest/resultRecord')
        assert req_el

        assert req_el.find(
            'sourcedGUID/sourcedId'
        ).text == patch_request.source_id
        assert el.find(
            'imsx_POXHeader/imsx_POXRequestHeaderInfo/imsx_messageIdentifier'
        ) is not None

        # No grade should be passed back
        assert req_el.find('result/resultTotalScore') is None
        assert req_el.find('result/resultScore') is None

        # Result data should be passed back
        assert req_el.find('result/resultData') is not None

        last_xml = None

    class Patch:
        def __init__(self):
            self._called = False

        @property
        def called(self):
            old = self._called
            self._called = False
            return old

        def __call__(self, uri, method, body, headers):
            nonlocal last_xml
            self._called = True
            assert method == 'POST'
            assert isinstance(headers, dict)
            assert headers['Content-Type'] == 'application/xml'
            assert isinstance(body, bytes)
            last_xml = body.decode('utf-8')
            return '', SUCCESS_XML

    if patch:
        monkeypatch.setitem(app.config, '_USING_SQLITE', True)

    patch_request = Patch()
    monkeypatch.setattr(oauth2.Client, 'request', patch_request)

    def do_lti_launch(
        username='A the A-er',
        lti_id='USER_ID',
        source_id='NON_EXISTING2!',
        published='false',
        canvas_id='MY_COURSE_ID_100',
    ):
        with app.app_context():
            data = {
                'custom_canvas_course_name': 'NEW_COURSE',
                'custom_canvas_course_id': canvas_id,
                'custom_canvas_assignment_id': f'{canvas_id}_ASSIG_1',
                'custom_canvas_assignment_title': 'MY_ASSIG_TITLE',
                'roles': 'administrator,instructor',
                'custom_canvas_user_login_id': username,
                'custom_canvas_course_title': 'Common Lisp',
                'custom_canvas_due_at': due_at.isoformat(),
                'custom_canvas_assignment_published': published,
                'user_id': lti_id,
                'lis_person_contact_email_primary': 'a@a.nl',
                'lis_person_name_full': username,
                'context_id': 'NO_CONTEXT!!',
                'context_title': 'WRONG_TITLE!!',
                'oauth_consumer_key': 'my_lti',
                'lis_outcome_service_url': source_id,
                'custom_canvas_points_possible': lti_max_points,
            }
            if source_id:
                data['lis_result_sourcedid'] = source_id
            patch_request.source_id = source_id
            res = test_client.post('/api/v1/lti/launch/1', data=data)

            url = urllib.parse.urlparse(res.headers['Location'])
            jwt = urllib.parse.parse_qs(url.query)['jwt'][0]
            lti_res = test_client.req(
                'post',
                '/api/v1/lti/launch/2',
                200,
                data={'jwt_token': jwt},
            )
            if published == 'false':
                assert lti_res['assignment']['state'] == 'hidden'
            else:
                assert m.Assignment.query.get(
                    lti_res['assignment']['id']
                ).state == m._AssignmentStateEnum.open
            assert lti_res['assignment']['course']['name'] == 'NEW_COURSE'
            return lti_res['assignment'], lti_res.get('access_token', None)

    def get_upload_file(token, assig_id):
        full_filename = (
            f'{os.path.dirname(__file__)}/'
            f'../test_data/test_blackboard/{filename}'
        )
        with app.app_context():
            test_client.req(
                'post',
                f'/api/v1/assignments/{assig_id}/submission',
                201,
                real_data={'file': (full_filename, 'bb.tar.gz')},
                headers={'Authorization': f'Bearer {token}'},
            )
            res = test_client.req(
                'get', f'/api/v1/assignments/{assig_id}/submissions/', 200
            )
            assert len(res) == 1
            return res[0]

    def set_grade(token, grade, work_id):
        test_client.req(
            'patch',
            f'/api/v1/submissions/{work_id}',
            200,
            data={
                'grade': grade,
                'feedback': 'feedback'
            },
            headers={'Authorization': f'Bearer {token}'},
        )

    assig, token = do_lti_launch()
    work = get_upload_file(token, assig['id'])
    assert patch_request.called
    assert_initial_passback()

    # Assignment is not open so it should not passback the grade
    set_grade(token, 5.0, work['id'])
    assert not patch_request.called

    test_client.req(
        'patch',
        f'/api/v1/assignments/{assig["id"]}',
        204,
        data={
            'state': 'done',
        },
        headers={'Authorization': f'Bearer {token}'},
    )

    # After setting assignment open it should passback the grades.
    assert patch_request.called
    assert_grade_set_to(5.0, raw=False, created_at=work['created_at'])

    if patch:
        test_client.req(
            'get',
            f'/api/v1/submissions/{work["id"]}/grade_history/',
            200,
            result=[
                {
                    'changed_at': str,
                    'is_rubric': False,
                    'grade': float,
                    'passed_back': True,
                    'user': dict,
                }
            ],
            headers={'Authorization': f'Bearer {token}'},
        )

    # Updating while open shoudl passback straight away
    set_grade(token, 6, work['id'])
    assert patch_request.called
    assert_grade_set_to(6, raw=False, created_at=work['created_at'])

    # Setting grade to ``None`` should do a delete request
    set_grade(token, None, work['id'])
    assert patch_request.called
    assert_grade_deleted()

    with app.app_context():
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assig["id"]}',
            204,
            data={
                'max_grade': 11,
            },
            headers={'Authorization': f'Bearer {token}'},
        )

    # When ``max_grade`` is set it should start to do raw passbacks, but only
    # if the grade passeback is in fact > 10
    set_grade(token, 6, work['id'])
    assert patch_request.called
    assert_grade_set_to(6.0, raw=False, created_at=work['created_at'])

    # As this grade is >11 the ``raw`` option should be used
    set_grade(token, 11, work['id'])
    assert patch_request.called
    assert_grade_set_to(11.0, raw=True, created_at=work['created_at'])

    assig, token = do_lti_launch(
        username='NEW_USERNAME',
        lti_id='NEW_ID',
        source_id=False,
        canvas_id='NEW_CANVAS_ID',
    )
    full_filename = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{filename}'
    )
    with app.app_context():
        test_client.req(
            'post',
            f'/api/v1/assignments/{assig["id"]}/submission',
            400,
            real_data={'file': (full_filename, 'bb.tar.gz')},
            headers={'Authorization': f'Bearer {token}'},
            result=error_template
        )

    # When submitting fails no grades should be passed back
    assert not patch_request.called


def test_lti_assignment_create(
    test_client, app, logged_in, ta_user, error_template
):
    def do_lti_launch(
        username='A the A-er',
        lti_id='USER_ID',
        source_id='NON_EXISTING2!',
        published='false',
        course_name='NEW_COURSE',
        assig_name='MY_ASSIG_TITLE',
    ):
        with app.app_context():
            data = {
                'custom_canvas_course_name': course_name,
                'custom_canvas_course_id': 'MY_COURSE_ID_100',
                'custom_canvas_assignment_id': 'MY_ASSIG_ID_100',
                'custom_canvas_assignment_title': assig_name,
                'roles': 'administrator,instructor',
                'custom_canvas_user_login_id': username,
                'custom_canvas_course_title': 'Common Lisp',
                'custom_canvas_assignment_published': published,
                'user_id': lti_id,
                'lis_person_contact_email_primary': 'a@a.nl',
                'lis_person_name_full': username,
                'context_id': 'NO_CONTEXT!!',
                'context_title': 'WRONG_TITLE!!',
                'oauth_consumer_key': 'my_lti',
                'lis_outcome_service_url': source_id,
            }
            if source_id:
                data['lis_result_sourcedid'] = source_id
            res = test_client.post('/api/v1/lti/launch/1', data=data)

            url = urllib.parse.urlparse(res.headers['Location'])
            jwt = urllib.parse.parse_qs(url.query)['jwt'][0]
            lti_res = test_client.req(
                'post',
                '/api/v1/lti/launch/2',
                200,
                data={'jwt_token': jwt},
            )
            if published == 'false':
                assert lti_res['assignment']['state'] == 'hidden'
            else:
                assert m.Assignment.query.get(
                    lti_res['assignment']['id']
                ).state == m._AssignmentStateEnum.open
            assert lti_res['assignment']['course']['name'] == course_name
            return lti_res['assignment'], lti_res.get('access_token', None)

    with app.app_context():
        assig, token = do_lti_launch()
        course = assig['course']
        test_client.req(
            'post',
            f'/api/v1/courses/{course["id"]}/assignments/',
            400,
            data={
                'name': 'wow',
            },
            headers={'Authorization': f'Bearer {token}'},
            result=error_template,
        )

        # Make sure name of course and assignment is updated with new launches
        course_name = 'NEW_NAME!!!!'
        assig_name = 'NEW_ASSIG_NAME!!!!'
        assig, _ = do_lti_launch(
            course_name=course_name, assig_name=assig_name
        )
        assert assig['name'] == assig_name
        assert assig['course']['name'] == course_name


def test_reset_lti_email(test_client, app, logged_in, ta_user, session):
    due_at = datetime.datetime.utcnow() + datetime.timedelta(
        days=1, hours=1, minutes=2
    )
    due_at = due_at.replace(second=0, microsecond=0)

    def do_lti_launch(
        email,
        name='A the A-er',
        lti_id='USER_ID',
        source_id='',
        published='false',
        username='a-the-a-er',
        due=None
    ):
        with app.app_context():
            due_date = due or due_at.isoformat() + 'Z'
            data = {
                'custom_canvas_course_name': 'NEW_COURSE',
                'custom_canvas_course_id': 'MY_COURSE_ID',
                'custom_canvas_assignment_id': 'MY_ASSIG_ID',
                'custom_canvas_assignment_title': 'MY_ASSIG_TITLE',
                'roles': 'instructor',
                'custom_canvas_user_login_id': username,
                'custom_canvas_course_title': 'Common Lisp',
                'custom_canvas_assignment_due_at': due_date,
                'custom_canvas_assignment_published': published,
                'user_id': lti_id,
                'lis_person_contact_email_primary': email,
                'lis_person_name_full': name,
                'context_id': 'NO_CONTEXT',
                'context_title': 'WRONG_TITLE',
                'oauth_consumer_key': 'my_lti',
                'lis_outcome_service_url': source_id,
            }
            if source_id:
                data['lis_result_sourcedid'] = source_id
            res = test_client.post('/api/v1/lti/launch/1', data=data)

            url = urllib.parse.urlparse(res.headers['Location'])
            jwt = urllib.parse.parse_qs(url.query)['jwt'][0]
            lti_res = test_client.req(
                'post',
                '/api/v1/lti/launch/2',
                200,
                data={'jwt_token': jwt},
            )
            if published == 'false':
                assert lti_res['assignment']['state'] == 'hidden'
            else:
                assert m.Assignment.query.get(
                    lti_res['assignment']['id']
                ).state == m._AssignmentStateEnum.open
            assert lti_res['assignment']['course']['name'] == 'NEW_COURSE'
            if due is None:
                assert lti_res['assignment']['deadline'] == due_at.isoformat()
            return lti_res['assignment'], lti_res.get('access_token', None)

    def get_user_info(token):
        with app.app_context():
            return test_client.req(
                'get',
                '/api/v1/login?extended',
                200,
                headers={'Authorization': f'Bearer {token}'} if token else {}
            )

    assig, token = do_lti_launch('orig@example.com')
    out = get_user_info(token)
    assert out['name'] == 'A the A-er'
    assert out['username'] == 'a-the-a-er'
    old_id = out['id']

    _, token = do_lti_launch('new@example.com')
    out = get_user_info(token)
    assert out['name'] == 'A the A-er'
    assert out['username'] == 'a-the-a-er'
    assert out['email'] == 'orig@example.com'
    assert out['id'] == old_id

    m.User.query.filter_by(id=out['id']).update({'reset_email_on_lti': True})
    session.commit()
    _, token = do_lti_launch('new@example.com')
    out = get_user_info(token)
    assert out['name'] == 'A the A-er'
    assert out['username'] == 'a-the-a-er'
    assert out['email'] == 'new@example.com'
    assert out['id'] == old_id

    assert not m.User.query.get(out['id']).reset_email_on_lti, """
    This field should be reset
    """


def test_invalid_jwt(
    test_client, app, logged_in, ta_user, session, error_template
):
    due_at = datetime.datetime.utcnow() + datetime.timedelta(
        days=1, hours=1, minutes=2
    )
    due_at = due_at.replace(second=0, microsecond=0)

    email = 'thomas@example.com'
    name = 'A the A-er'
    lti_id = 'USER_ID'
    source_id = ''
    published = 'false'
    username = 'a-the-a-er'
    due = None
    with app.app_context():
        due_date = due or due_at.isoformat() + 'Z'
        data = {
            'custom_canvas_course_name': 'NEW_COURSE',
            'custom_canvas_course_id': 'MY_COURSE_ID',
            'custom_canvas_assignment_id': 'MY_ASSIG_ID',
            'custom_canvas_assignment_title': 'MY_ASSIG_TITLE',
            'roles': 'instructor',
            'custom_canvas_user_login_id': username,
            'custom_canvas_course_title': 'Common Lisp',
            'custom_canvas_assignment_due_at': due_date,
            'custom_canvas_assignment_published': published,
            'user_id': lti_id,
            'lis_person_contact_email_primary': email,
            'lis_person_name_full': name,
            'context_id': 'NO_CONTEXT',
            'context_title': 'WRONG_TITLE',
            'oauth_consumer_key': 'my_lti',
            'lis_outcome_service_url': source_id,
        }
        if source_id:
            data['lis_result_sourcedid'] = source_id
        res = test_client.post('/api/v1/lti/launch/1', data=data)

        url = urllib.parse.urlparse(res.headers['Location'])
        urllib.parse.parse_qs(url.query)['jwt'][0]
        test_client.req(
            'post',
            '/api/v1/lti/launch/2',
            400,
            data={'jwt_token': 'INVALID_JWT'},
            result=error_template
        )
