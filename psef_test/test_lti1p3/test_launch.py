import copy
import json
import uuid
import pprint
from re import compile as regex
from random import randint
from datetime import timedelta

import jwt
import furl
import flask
import pytest
import freezegun
import jwcrypto.jwk
import pylti1p3.names_roles
import pylti1p3.assignments_grades
import pylti1p3.message_validators
from defusedxml.ElementTree import fromstring as defused_xml_fromstring

import psef
import helpers
import psef.models as m
import psef.signals as signals
import psef.lti.v1_3 as lti1p3
from cg_dt_utils import DatetimeWithTimezone

LTI_JWT_SECRET = str(uuid.uuid4())

DEEP_LINK = '__CG_EXPECT_DEEP_LINK__'

@pytest.fixture
def monkeypatched_open_at(stub_function):
    yield stub_function(psef.tasks, 'maybe_open_assignment_at')


@pytest.fixture
def monkeypatched_passback(monkeypatch, stub_function_class):
    stub = stub_function_class()
    monkeypatch.setattr(
        pylti1p3.assignments_grades.AssignmentsGradesService, 'put_grade', stub
    )
    yield stub


@pytest.fixture(autouse=True)
def monkeypatched_get_members(monkeypatch, stub_function_class):
    stub = stub_function_class(lambda: [])
    monkeypatch.setattr(
        pylti1p3.names_roles.NamesRolesProvisioningService, 'get_members', stub
    )
    yield stub


@pytest.fixture(autouse=True)
def monkeypatched_validate_jwt(monkeypatch, stub_function_class):
    stub = stub_function_class(
        lambda self: self, pass_self=True, with_args=True
    )
    monkeypatch.setattr(lti1p3.MessageLaunch, 'validate_jwt_signature', stub)
    yield stub


def remove_from(d1, key):
    res = copy.copy(d1)
    del res[key]
    return res


def merge(d1, d2):
    res = copy.copy(d1)

    for k, v2 in d2.items():
        v1 = d1.get(k)
        if isinstance(v1, dict) and isinstance(v2, dict):
            res[k] = merge(v1, v2)
        else:
            res[k] = v2

    return res


def replace_values(base_data, replace_dict):
    if isinstance(base_data, list):
        return [replace_values(item, replace_dict) for item in base_data]
    elif isinstance(base_data, dict):
        res = {}
        for key, value in base_data.items():
            if isinstance(value, list):
                res[key] = replace_values(value, replace_dict)
            elif isinstance(value, dict):
                res[key] = replace_values(value, replace_dict)
            elif value in replace_dict:
                res[key] = replace_dict[value]
            else:
                res[key] = value
        return res
    elif base_data in replace_dict:
        return replace_dict[base_data]
    return copy.copy(base_data)


BASE_LAUNCH_DATA = {
    'aud': 'client_id',
    'exp': (DatetimeWithTimezone.utcnow() + timedelta(days=1)).timestamp(),
    'nbf': 1590998156,
    'iat': 1590998156,
    'sub': 'User.id',
    'given_name': 'CodeGrade',
    'family_name': 'Administrator',
    'name': 'CodeGrade Administrator',
    'email': 'User@email.com',
    'https://purl.imsglobal.org/spec/lti/claim/message_type':
        'LtiResourceLinkRequest',
    'https://purl.imsglobal.org/spec/lti/claim/version': '1.3.0',
    'https://purl.imsglobal.org/spec/lti/claim/deployment_id': 'Deployment.id',
    'https://purl.imsglobal.org/spec/lti/claim/target_link_uri': 'Launch.url',
    'https://purl.imsglobal.org/spec/lti/claim/resource_link': {
        'id': 'Assignment.id',
        'title': 'Assignment.name',
        'description': None,
    },
    'https://purl.imsglobal.org/spec/lti/claim/roles': [
        'http://purl.imsglobal.org/vocab/lis/v2/membership#Administrator',
        'http://purl.imsglobal.org/vocab/lis/v2/institution/person#Student',
        'http://purl.imsglobal.org/vocab/lis/v2/institution/person#Learner',
        'http://purl.imsglobal.org/vocab/lis/v2/institution/person#Instructor',
        'http://purl.imsglobal.org/vocab/lis/v2/institution/person#Mentor',
        'http://purl.imsglobal.org/vocab/lis/v2/institution/person#Staff',
        'http://purl.imsglobal.org/vocab/lis/v2/institution/person#Administrator',
    ],
    'https://purl.imsglobal.org/spec/lti/claim/context': {
        'id': 'Course.id',
        'label': 'Course.label',
        'title': 'Course.title',
        'type': [
            'http://purl.imsglobal.org/vocab/lis/v2/course#CourseOffering',
        ],
    },
    'https://purl.imsglobal.org/spec/lti/claim/lis': {
        'course_offering_sourcedid': 'example_lms:CodeGrade1',
        'course_section_sourcedid': 'example_lms:CodeGrade1',
    },
    'https://purl.imsglobal.org/spec/lti/claim/launch_presentation': {
        'locale': 'en-us',
    },
    'https://purl.imsglobal.org/spec/lti-ags/claim/endpoint': {
        'scope': [
            'https://purl.imsglobal.org/spec/lti-ags/scope/lineitem',
            'https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly',
            'https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly',
            'https://purl.imsglobal.org/spec/lti-ags/scope/score',
        ],
        'lineitems': 'lineitems.endpoint',
    },
    'https://purl.imsglobal.org/spec/lti/claim/custom': {
        'cg_username_0': 'cg_username',
        'cg_deadline_0': 'cg_deadline',
        'cg_available_at_0': 'cg_available_at',
        'cg_resource_id_0': 'cg_resource_id',
        'cg_lock_date_0': 'cg_lock_date',
    },
    'https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice': {
        'context_memberships_url': 'context_memberships_url',
        'service_versions': ['2.0'],
    },
}

CANVAS_DATA = merge(
    BASE_LAUNCH_DATA, {
        'iss': 'https://canvas.instructure.com',
        'https://purl.imsglobal.org/spec/lti/claim/custom': {
            'cg_deadline_1': 'cg_deadline',
            'cg_is_published_0': 'cg_is_published',
            'cg_resource_id_1': 'cg_resource_id',
            'cg_lock_date_1': 'cg_lock_date',
        }
    }
)

BRIGHTSPACE_DATA = merge(
    BASE_LAUNCH_DATA,
    {
        'iss': 'https://partners.brightspace.com',
        'http://www.brightspace.com': {
            'tenant_id': '41b632b6-ff74-4288-b3f1-7ffb6eb14bb4',
            'org_defined_id': 'CodeGrade.A1',
            'user_id': 'User.id',
            'username': 'User.username',
            'ResourceLink.id.history': '',
            'Context.id.history': '',
        },
    },
)


def make_launch_data(base, provider, override_replace={}):
    provider = m.LTI1p3Provider.query.get(helpers.get_id(provider))

    return replace_values(
        base,
        {
            'cg_username': 'Test username',
            'cg_deadline': '',
            'cg_available_at': '',
            'cg_resource_id': '',
            'cg_lock_date': '',
            'Assignment.name': 'Test Assignment 1',
            'Course.label': 'Test Course 1',
            'Course.id': str(uuid.uuid4()),
            'User.id': str(uuid.uuid4()),
            'User.username': 'Test username',
            'Assignment.id': str(uuid.uuid4()),
            'iss': provider.iss,
            'client_id': provider.client_id,
            **override_replace,
        },
    )


def do_oidc_login(
    test_client, provider, with_id=False, redirect_to=None, override_data={}
):
    provider = m.LTI1p3Provider.query.get(helpers.get_id(provider))

    redirect_uri = str(uuid.uuid4())
    login_hint = str(uuid.uuid4())
    url = '/api/v1/lti1.3/login'
    if with_id:
        url += '/' + str(provider.id)

    redirect = test_client.post(
        url,
        data={
            'target_link_uri': redirect_uri,
            'iss': provider.iss,
            'client_id': provider.client_id,
            'login_hint': login_hint,
            **override_data,
        }
    )
    assert redirect.status_code == 303
    if redirect_to is None:
        assert redirect.headers['Location'].startswith(
            provider._auth_login_url
        )
    else:
        assert redirect.headers['Location'].startswith(redirect_to)
    return furl.furl(redirect.headers['Location'])


def do_lti_launch(
    test_client,
    provider,
    data,
    oidc_result,
    status,
    with_id=False,
    make_jwt=None,
):

    oidc_params = oidc_result.query.params
    url = '/api/v1/lti1.3/launch'
    if with_id:
        url += '/' + str(provider.id)
    if make_jwt is None:
        make_jwt = lambda d, oidc: jwt.encode(
            {**d, 'nonce': oidc['nonce']},
            LTI_JWT_SECRET,
            algorithm='HS256',
        )

    made_jwt = make_jwt(data, oidc_params)
    response = test_client.post(
        url,
        data={
            'id_token': made_jwt,
            'state': oidc_params['state'],
        },
    )
    if status == DEEP_LINK:
        return response
    assert response.status_code == 303
    url = furl.furl(response.headers['Location'])
    assert url.query.params['goto_latest_submission'] == 'False'
    blob_id = url.query.params['blob_id']
    return test_client.req(
        'post',
        '/api/v1/lti/launch/2?extended',
        status,
        data={
            'blob_id': blob_id,
        }
    )


def do_oidc_and_lti_launch(
    test_client, provider, data, status=200, with_id=False
):
    oidc = do_oidc_login(test_client, provider, with_id=with_id)
    launch = do_lti_launch(test_client, provider, data, oidc, status, with_id)
    return oidc, launch


@pytest.mark.parametrize(
    'launch_data,lms,iss', [
        (BRIGHTSPACE_DATA, 'Brightspace', 'https://partners.brightspace.com'),
        (CANVAS_DATA, 'Canvas', 'https://canvas.instructure.com'),
    ]
)
def test_do_simple_launch(
    test_client, describe, logged_in, admin_user, watch_signal, launch_data,
    lms, iss, monkeypatched_validate_jwt, monkeypatched_passback, yesterday,
    tomorrow, monkeypatched_open_at
):
    with describe('setup'), logged_in(admin_user):
        provider = helpers.create_lti1p3_provider(
            test_client,
            lms,
            iss=iss,
            client_id=str(uuid.uuid4()) + '_lms=' + lms
        )
        user_added = watch_signal(signals.USER_ADDED_TO_COURSE)
        assig_created = watch_signal(signals.ASSIGNMENT_CREATED)

        lti_user_id = str(uuid.uuid4())
        lti_assig_id = str(uuid.uuid4())
        lti_assig_id2 = str(uuid.uuid4())
        lti_course_id = str(uuid.uuid4())
        deadline = DatetimeWithTimezone.utcnow() + timedelta(
            days=randint(3, 10)
        )

    with describe('Initial launch creates assignment and course'):
        _, launch_result = do_oidc_and_lti_launch(
            test_client,
            provider,
            make_launch_data(
                launch_data,
                provider,
                {
                    'Assignment.id': lti_assig_id,
                    'Course.id': lti_course_id,

                    'cg_deadline': deadline.isoformat(),
                    'cg_available_at': tomorrow.isoformat(),
                    'User.id': lti_user_id,
                },
            ),
        )
        assert monkeypatched_validate_jwt.called_amount == 1
        assert monkeypatched_open_at.called_amount == 1

        assert user_added.was_send_once
        assert monkeypatched_passback.called_amount == 1
        passback_arg = monkeypatched_passback.all_args[0]
        assert len(passback_arg) == 1
        assert passback_arg[0].get_score_given() is None
        assert passback_arg[0].get_activity_progress() == 'Initialized'

        assert assig_created.was_send_once
        created_assig = m.Assignment.query.get(assig_created.signal_arg.id)
        assert created_assig.lti_assignment_id == lti_assig_id
        assert created_assig.deadline == deadline
        assert launch_result['data']['assignment']['state'] == 'hidden'

        assert launch_result['version'] == 'v1_3'
        assert launch_result['data']['type'] == 'normal_result'
        course = launch_result['data']['course']
        assig = launch_result['data']['assignment']
        assert assig['id'] == assig_created.signal_arg.id
        assert course['is_lti']

    with describe('Second launch does not create assignment again'):
        new_deadline = deadline + timedelta(days=1)
        _, launch_result2 = do_oidc_and_lti_launch(
            test_client,
            provider,
            make_launch_data(
                launch_data,
                provider,
                {
                    'Course.id': lti_course_id,
                    'Assignment.id': lti_assig_id,
                    'cg_deadline': new_deadline.isoformat(),
                    'cg_available_at': yesterday.isoformat(),
                    'User.id': lti_user_id,
                },
            ),
        )
        assert monkeypatched_validate_jwt.called_amount == 1
        assert monkeypatched_open_at.called_amount == 0

        assert user_added.was_not_send

        assert assig_created.was_not_send
        assert launch_result2['data']['course']['id'] == course['id']
        assert launch_result2['data']['assignment']['id'] == assig['id']
        # Deadline should be updated
        assert launch_result2['data']['assignment'
                                      ]['deadline'] == new_deadline.isoformat()
        assert launch_result2['data']['assignment']['state'] == 'submitting'

    with describe('New launch in same course only creates assignment'):
        _, launch_result3 = do_oidc_and_lti_launch(
            test_client,
            provider,
            make_launch_data(
                launch_data,
                provider,
                {
                    'Course.id': lti_course_id,
                    'Assignment.id': lti_assig_id2,
                    'User.id': lti_user_id,
                },
            ),
        )
        assert monkeypatched_validate_jwt.called_amount == 1

        assert user_added.was_not_send

        assert assig_created.was_send_once
        assert launch_result3['data']['course']['id'] == course['id']
        assert launch_result3['data']['assignment']['id'] != assig['id']
        # Deadline was not passed so it should not be set
        assert launch_result3['data']['assignment']['deadline'] is None


@pytest.mark.parametrize('with_id', [True, False])
def test_do_oidc_with_get(test_client, lti1p3_provider, with_id, describe):
    with describe('setup'):
        redirect_uri = str(uuid.uuid4())
        login_hint = str(uuid.uuid4())
        url = '/api/v1/lti1.3/login'
        if with_id:
            url += '/' + str(lti1p3_provider.id)

    with describe('can do oidc launch with GET request'), test_client as c:
        redirect = c.get(
            furl.furl(url).add({
                'target_link_uri': redirect_uri,
                'iss': lti1p3_provider.iss,
                'login_hint': login_hint,
            }).tostr(),
        )
        assert redirect.status_code == 303
        assert redirect.headers['Location'].startswith(
            lti1p3_provider._auth_login_url
        )
        assert flask.session


def test_with_wrong_nonce(
    test_client, describe, logged_in, admin_user, monkeypatched_passback
):
    with describe('setup'), logged_in(admin_user):
        lti_assig_id = str(uuid.uuid4())
        lti_course_id = str(uuid.uuid4())
        lms = 'Canvas'
        provider = helpers.create_lti1p3_provider(
            test_client,
            lms,
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + lms
        )

    with describe('can do oidc launch with GET request'), test_client as c:
        oidc = do_oidc_login(c, provider)
        with c.session_transaction() as sess:
            s_service = lti1p3.flask.FlaskSessionService(
                lti1p3.flask.FlaskRequest(force_post=False)
            )
            sess[s_service._get_key('lti-nonce')] = 'Not correct'

        response = do_lti_launch(
            c,
            provider,
            make_launch_data(
                CANVAS_DATA,
                provider,
                {
                    'Assignment.id': lti_assig_id,
                    'Course.id': lti_course_id,
                },
            ),
            oidc,
            400,
        )
        assert response['message'] == 'Invalid Nonce'


def test_direct_deep_link_launch(test_client, describe, logged_in, admin_user):
    with describe('setup'), logged_in(admin_user):
        canvas_provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )
        return_url = f'https://{uuid.uuid4()}.com'
        deep_link_data = {
            lti1p3.claims.MESSAGE_TYPE: 'LtiDeepLinkingRequest',
            lti1p3.claims.DEEP_LINK: {
                'data': 'DP_DATA',
                'deep_link_return_url': return_url,
                'accept_types': ['ltiResourceLink'],
                'accept_presentation_document_targets': 'PRES',
            },
        }
        canvas_launch_data = make_launch_data(
            merge(CANVAS_DATA, deep_link_data), canvas_provider, {}
        )

    with describe('deep link to canvas should directly return resource'):
        _, launch = do_oidc_and_lti_launch(
            test_client, canvas_provider, canvas_launch_data, status=DEEP_LINK
        )
        form = launch.data
        parsed = defused_xml_fromstring(form.decode('utf8'))
        assert parsed.tag == 'html'
        form, = parsed.findall('body/form')
        assert form.attrib['action'] == return_url
        assert form.attrib['method'] == 'POST'
        child, = form.getchildren()
        assert child.attrib['name'] == 'JWT'
        assert child.attrib['type'] == 'hidden'
        jwt_value = child.attrib['value']
        assert jwt.decode(jwt_value, verify=False)


def test_real_deep_link_launch(test_client, describe, logged_in, admin_user):
    with describe('setup'), logged_in(admin_user):
        brightspace_provider = helpers.create_lti1p3_provider(
            test_client,
            'Brightspace',
            iss='https://partners.brightspace.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Lichtruimte'
        )
        return_url = f'https://{uuid.uuid4()}.com'
        deep_link_data = {
            lti1p3.claims.MESSAGE_TYPE: 'LtiDeepLinkingRequest',
            lti1p3.claims.DEEP_LINK: {
                'data': 'DP_DATA',
                'deep_link_return_url': return_url,
                'accept_types': ['ltiResourceLink'],
                'accept_presentation_document_targets': 'PRES',
            },
        }
        launch_data = make_launch_data(
            merge(BRIGHTSPACE_DATA, deep_link_data), brightspace_provider, {}
        )

        def get_new_deep_link():
            _, launch = do_oidc_and_lti_launch(
                test_client, brightspace_provider, launch_data
            )
            assert launch['data']['type'] == 'deep_link'
            blob_id = launch['data']['deep_link_blob_id']
            auth_token = launch['data']['auth_token']
            return auth_token, f'/api/v1/lti1.3/deep_link/{blob_id}'

    with describe('have to provide correct auth token to use blob id'):
        auth_token, url = get_new_deep_link()
        res = test_client.req(
            'post',
            url,
            403,
            data={
                'auth_token': f'WRONG_{auth_token}',
                'name': 'assig_name',
                'deadline': 'NOT A DEADLINE',
            },
            result={
                '__allow_extra__': True,
                'message': regex('not provide the correct token'),
            }
        )

    with describe('too old blob id is also rejected'):
        auth_token, url = get_new_deep_link()
        with freezegun.freeze_time(
            DatetimeWithTimezone.utcnow() + timedelta(days=2)
        ):
            test_client.req(
                'post',
                url,
                400,
                result={
                    '__allow_extra__': True,
                    'message': regex('^This deep linking session has expired'),
                }
            )

    with describe('returns deep link form if all is correct'):
        auth_token, url = get_new_deep_link()
        deadline = DatetimeWithTimezone.utcnow() + timedelta(days=4)
        res = test_client.req(
            'post',
            url,
            200,
            data={
                'auth_token': auth_token,
                'name': 'assig_name',
                'deadline': deadline.isoformat(),
            },
            result={
                'jwt': str,
                'url': return_url,
            }
        )
        jwt_parsed = jwt.decode(res['jwt'], verify=False)
        content_items = jwt_parsed[
            'https://purl.imsglobal.org/spec/lti-dl/claim/content_items']
        assert isinstance(content_items, list)
        assert len(content_items) == 1
        assert content_items[0]['title'] == 'assig_name'
        assert content_items[0]['submission']['endDateTime'
                                              ] == deadline.isoformat()


def test_launch_with_missing_data(
    test_client, describe, logged_in, admin_user, watch_signal
):
    with describe('setup'), logged_in(admin_user):
        user_added = watch_signal(
            signals.USER_ADDED_TO_COURSE, clear_all_but=[]
        )
        provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )

        data = make_launch_data(
            CANVAS_DATA,
            provider,
            {
                'Assignment.id': 'asdf',
                'Course.id': 'asdfs',
            },
        )

        def ensure_fails(data, err_msg):
            _, launch = do_oidc_and_lti_launch(
                test_client, provider, data, 400
            )
            assert err_msg in launch['message']
            assert user_added.was_not_send
            return launch

    with describe('should fail without email'):
        ensure_fails(
            remove_from(data, 'email'), 'requires the email of the user'
        )

    with describe('should fail without nrps'):
        ensure_fails(
            remove_from(data, lti1p3.claims.NAMESROLES),
            'NamesRoles Provisioning service is not enabled'
        )

    with describe('should fail without custom args'):
        ensure_fails(
            remove_from(data, lti1p3.claims.CUSTOM),
            'The LTI launch is missing required custom claims'
        )

    with describe('not fail without email for test student'):
        do_oidc_and_lti_launch(
            test_client,
            provider,
            remove_from(merge(data, {'name': 'Test Student'}), 'email'),
        )
        assert user_added.was_send_once
        assert user_added.signal_arg.user.email == 'test_student@codegra.de'


def test_error_when_no_cookies(test_client, describe, logged_in, admin_user):
    with describe('setup'), logged_in(admin_user):
        lti_assig_id = str(uuid.uuid4())
        lti_course_id = str(uuid.uuid4())
        lms = 'Canvas'
        provider = helpers.create_lti1p3_provider(
            test_client,
            lms,
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + lms
        )
        data = make_launch_data(
            CANVAS_DATA, provider,
            {'Assignment.id': lti_assig_id, 'Course.id': lti_course_id}
        )

        def assert_is_cookie_error(response):
            assert response['message'] == "Couldn't set needed cookies"
            assert response['code'] == 'LTI1_3_ERROR'
            assert response['original_exception']['code'
                                                  ] == 'LTI1_3_COOKIE_ERROR'

    with describe('error when no cookies are present at all'):
        oidc = do_oidc_login(test_client, provider)
        test_client.cookie_jar.clear()
        response = do_lti_launch(test_client, provider, data, oidc, 400)
        assert_is_cookie_error(response)

    with describe('error when old launch cookies are present'):
        oidc = do_oidc_login(test_client, provider)
        old_jar = copy.copy(test_client.cookie_jar)
        test_client.cookie_jar.clear()

        with freezegun.freeze_time(
            DatetimeWithTimezone.utcnow() + timedelta(hours=1)
        ):
            oidc = do_oidc_login(test_client, provider)
            test_client.cookie_jar = old_jar
            response = do_lti_launch(test_client, provider, data, oidc, 400)
            assert_is_cookie_error(response)

    with describe('error when cookie has bogus value'):
        oidc = do_oidc_login(test_client, provider)
        all_cookies = list(test_client.cookie_jar)
        test_client.cookie_jar.clear()
        for cook in all_cookies:
            cook.value = 'HAHA BOGUS VALUE'
            test_client.cookie_jar.set_cookie(cook)

        response = do_lti_launch(test_client, provider, data, oidc, 400)
        assert_is_cookie_error(response)


def test_error_when_launching_without_resource_id(
    test_client, describe, logged_in, admin_user, stub_function
):
    with describe('setup'), logged_in(admin_user):
        # Make sure our own validation works, so don't use the one of pytli1p3
        stub_function(
            pylti1p3.message_validators.ResourceMessageValidator,
            'validate', lambda: True
        )
        provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )

        data = make_launch_data(
            CANVAS_DATA,
            provider,
            {
                'Assignment.id': None,
                'Course.id': 'asdfs',
            },
        )

    with describe('should fail without email'):
        _, err = do_oidc_and_lti_launch(test_client, provider, data, 400)
        assert 'No resource id was provided for this launch' in err['message']


def test_launch_with_incorrect_provider(
    test_client, describe, logged_in, admin_user, stub_function,
    monkeypatched_passback, session, app
):
    with describe('setup'), logged_in(admin_user):
        # Make sure our own validation works, so don't use the one of pytli1p3
        stub_function(
            pylti1p3.message_validators.ResourceMessageValidator,
            'validate', lambda: True
        )
        provider = helpers.to_db_object(
            helpers.create_lti1p3_provider(
                test_client,
                'Canvas',
                iss='https://canvas.instructure.com',
                client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
            ), m.LTI1p3Provider
        )

        def assert_launch_errors(msg, override, with_id=False):
            oidc = do_oidc_login(
                test_client,
                provider,
                redirect_to=app.config['EXTERNAL_URL'],
                override_data=override,
                with_id=with_id,
            )
            blob_id = oidc.query.params['blob_id']
            err = test_client.req(
                'post',
                '/api/v1/lti/launch/2?extended',
                400,
                data={'blob_id': blob_id}
            )
            assert msg in err['message']
            return err

    with describe('cannot launch with non finalized provider'):
        provider._finalized = False
        session.commit()
        assert_launch_errors('This LTI connection is not yet finalized', {})
        provider._finalized = True
        session.commit()

    with describe('cannot launch with incorrect iss'):
        for with_id in [True, False]:
            assert_launch_errors(
                'This LMS was not found as a LTIProvider',
                {'iss': 'OTHER ISS'},
                with_id=with_id,
            )


@pytest.mark.parametrize('monkeypatched_validate_jwt', ['NO_ERR'])
def test_validate_jwt_body(
    test_client, describe, logged_in, admin_user, stub_function, session, app,
    monkeypatched_validate_jwt, monkeypatched_passback
):
    with describe('setup'), logged_in(admin_user):
        stub_err = lambda: False

        super_decode = jwt.decode

        def maybe_err(*args, **kwargs):
            if stub_err() and not flask.request.path.endswith('launch/2'):
                raise jwt.InvalidTokenError('CG TEST ERROR')
            return super_decode(*args, **kwargs)

        stub_decode = stub_function(jwt, 'decode', maybe_err, with_args=True)

        key = jwcrypto.jwk.JWK.generate(kty='RSA')
        kid = str(uuid.uuid4())
        public_key = {
            'keys': [{**json.loads(key.export_public()), 'kid': kid}],
        }
        stub_fetch = stub_function(
            pylti1p3.message_launch.MessageLaunch,
            'fetch_public_key', lambda: public_key
        )

        provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )
        data = make_launch_data(
            CANVAS_DATA, provider,
            {'Assignment.id': 'a_id', 'Course.id': 'c_id'}
        )

        def make_jwt(data, oidc_params):
            return jwt.encode(
                {**data, 'nonce': oidc_params['nonce']},
                key.export_to_pem(private_key=True, password=None),
                algorithm='RS256',
                headers={'kid': kid},
            )

        def do_launch(status):
            oidc = do_oidc_login(test_client, provider)
            return do_lti_launch(
                test_client, provider, data, oidc, status, make_jwt=make_jwt
            )

    with describe('should not error when stub_decode does not error'):
        stub_err = lambda: False
        do_launch(200)
        assert stub_fetch.called_amount == 1

    with describe('should error when stub_decodes errors'):
        # Flush all cache so fetch count is correct
        app.inter_request_cache.lti_access_tokens._redis.flushall()

        stub_err = lambda: True
        err = do_launch(400)
        assert err['message'] == "Can't decode id_token: CG TEST ERROR"
        # Twice, as it should refresh the token after an error
        assert stub_fetch.called_amount == 2

    with describe('failing once should result in a successful launch'):
        # Flush all cache so fetch count is correct
        app.inter_request_cache.lti_access_tokens._redis.flushall()

        amount = 1

        def _err_once():
            nonlocal amount
            if amount > 0:
                amount -= 1
                return True
            return False

        stub_err = _err_once

        do_launch(200)
        assert stub_fetch.called_amount == 2


def test_copying_email_from_launch(
    test_client, describe, logged_in, admin_user, stub_function,
    monkeypatched_passback, session
):
    with describe('setup'), logged_in(admin_user):
        email1 = str(uuid.uuid4())
        email2 = str(uuid.uuid4())
        provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )

        lti_user_id = str(uuid.uuid4())
        data = make_launch_data(
            CANVAS_DATA,
            provider,
            {
                'Assignment.id': 'assig id',
                'Course.id': 'asdfs',
                'User.id': lti_user_id,
            },
        )

    with describe('should create a user with the given email'):
        do_oidc_and_lti_launch(
            test_client, provider, merge(data, {'email': email1}), 200
        )
        user = m.UserLTIProvider.query.filter_by(lti_user_id=lti_user_id
                                                 ).one().user
        assert user.email == email1

    with describe('should not always copy the new email'):
        _, launch = do_oidc_and_lti_launch(
            test_client, provider, merge(data, {'email': email2}), 200
        )
        user2 = m.UserLTIProvider.query.filter_by(lti_user_id=lti_user_id
                                                  ).one().user
        assert user2 == user
        assert user2.email == email1
        assert launch['data']['updated_email'] is None

    with describe('should copy the email if instructed'):
        user.reset_email_on_lti = True
        session.commit()
        _, launch = do_oidc_and_lti_launch(
            test_client, provider, merge(data, {'email': email2}), 200
        )
        user3 = m.UserLTIProvider.query.filter_by(lti_user_id=lti_user_id
                                                  ).one().user
        assert user2 == user
        assert user3.email == email2
        assert not user3.reset_email_on_lti
        assert launch['data']['updated_email'] == email2


def test_cannot_do_second_launch_with_any_blob(test_client, describe, session):
    with describe('setup'):
        blob = m.BlobStorage(json={'hi': 'he'})
        session.add(blob)
        session.commit()

    with describe('cannot use other blob for second part of the launch'):
        test_client.req(
            'post',
            '/api/v1/lti/launch/2?extended',
            400,
            data={'blob_id': str(blob.id)},
            result={
                '__allow_extra__': True,
                'message': regex('^Decoding given JWT token failed,.*'),
            },
        )


def test_wrong_launch_to_oidc_login(
    test_client, describe, session, app, logged_in, admin_user
):
    with describe('setup'), logged_in(admin_user):
        provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='other iss',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )
    with describe('incorrect oidc login shows a nice error page'):
        oidc = do_oidc_login(
            test_client,
            provider,
            redirect_to=app.config['EXTERNAL_URL'],
            override_data={'iss': None}
        )
        blob_id = oidc.query.params['blob_id']
        test_client.req(
            'post',
            '/api/v1/lti/launch/2?extended',
            400,
            data={'blob_id': blob_id},
            result={
                '__allow_extra__': True, 'message': 'Could not find issuer'
            },
        )


def test_launch_to_latest_submission(
    test_client, describe, logged_in, admin_user
):
    with describe('setup'), logged_in(admin_user):
        provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )
        data = make_launch_data(
            CANVAS_DATA,
            provider,
            {
                'Assignment.id': 'assig id',
                'Course.id': 'asdfs',
            },
        )
    with describe('incorrect oidc login shows a nice error page'):
        oidc = do_oidc_login(test_client, provider)

        oidc_params = oidc.query.params
        url = '/api/v1/lti1.3/launch_to_latest_submission'
        made_jwt = jwt.encode(
            {**data, 'nonce': oidc_params['nonce']},
            LTI_JWT_SECRET,
            algorithm='HS256',
        )

        response = test_client.post(
            url,
            data={
                'id_token': made_jwt,
                'state': oidc_params['state'],
            },
        )
        assert response.status_code == 303
        url = furl.furl(response.headers['Location'])
        assert url.query.params['goto_latest_submission'] == 'True'


def test_launch_redirect_to_given_page(
    test_client, describe, logged_in, admin_user, app
):
    with describe('setup'), logged_in(admin_user):
        red_url = f'https://{uuid.uuid4()}.com'
        provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )
        data = make_launch_data(
            CANVAS_DATA,
            provider,
            {
                'Assignment.id': 'assig id',
                'Course.id': 'asdfs',
            },
        )
        url = furl.furl('/api/v1/lti1.3/launch').add({
            'platform_redirect_url': red_url,
            'full_win_launch_requested': '1',
        }).tostr()
        oidc = do_oidc_login(test_client, provider)
        oidc_params = oidc.query.params

    with describe('should redirect to url given in launch request'):
        made_jwt = jwt.encode(
            {**data, 'nonce': oidc_params['nonce']},
            LTI_JWT_SECRET,
            algorithm='HS256',
        )

        response = test_client.post(
            url,
            data={
                'id_token': made_jwt,
                'state': oidc_params['state'],
            },
        )
        assert response.status_code == 302
        # Should redirect to the given get parameter url
        assert response.headers['Location'] == red_url

    with describe('should check jwt before redirecting'):
        oidc = do_oidc_login(test_client, provider)

        response = test_client.post(
            url,
            data={
                'id_token': 'NOT_VALID_JWT',
                'state': oidc_params['state'],
            },
        )
        assert response.status_code == 303
        assert response.headers['Location'] != red_url
        assert response.headers['Location'].startswith(
            app.config['EXTERNAL_URL']
        )


@pytest.mark.parametrize('connect', [True, False])
@pytest.mark.parametrize('add_user_data', [True, False])
@pytest.mark.parametrize('add_course_data', [True, False])
@pytest.mark.parametrize('add_assig_data', [True, False])
def test_connecting_users_and_courses_lti1p1_provider(
    test_client, describe, logged_in, admin_user, stub_function,
    monkeypatched_passback, session, connect, canvas_lti1p1_provider,
    watch_signal, add_user_data, add_course_data, add_assig_data
):
    with describe('setup'), logged_in(admin_user):
        watch_signal(signals.USER_ADDED_TO_COURSE, clear_all_but=[])

        old_lti_context_id = str(uuid.uuid4())
        new_lti_context_id = str(uuid.uuid4())
        old_resource_id = str(uuid.uuid4())
        new_resource_id = str(uuid.uuid4())

        original_user = helpers.create_user_with_role(session, 'Student', [])
        session.commit()

        old_lti_user_id = str(uuid.uuid4())
        assert original_user
        session.add(
            m.UserLTIProvider(
                user=original_user,
                lti_provider=canvas_lti1p1_provider,
                lti_user_id=old_lti_user_id
            )
        )
        course = m.Course.create_and_add(name='LTI COURSE JEE')
        m.CourseLTIProvider.create_and_add(
            course=course,
            lti_provider=canvas_lti1p1_provider,
            lti_context_id=old_lti_context_id,
            deployment_id=old_lti_context_id,
        )
        assig = m.Assignment(
            course=course,
            name='Name',
            is_lti=True,
            lti_assignment_id=old_resource_id
        )
        session.add(assig)
        session.commit()

        provider = helpers.create_lti1p3_provider(
            test_client,
            'Canvas',
            iss='https://canvas.instructure.com',
            client_id=str(uuid.uuid4()) + '_lms=' + 'Canvas'
        )
        provider = helpers.to_db_object(provider, m.LTI1p3Provider)
        if connect:
            provider._updates_lti1p1 = canvas_lti1p1_provider
            session.commit()

        lti_user_id = str(uuid.uuid4())
        data = make_launch_data(
            CANVAS_DATA,
            provider,
            {
                'Assignment.id': new_resource_id,
                'Course.id': new_lti_context_id,
                'User.id': lti_user_id,
            },
        )
        to_merge = {}
        if add_course_data:
            to_merge['context_id'] = old_lti_context_id
        if add_user_data:
            to_merge['user_id'] = old_lti_user_id
        if add_assig_data:
            to_merge['resource_link_id'] = old_resource_id
        extra_data = {
            "https://purl.imsglobal.org/spec/lti/claim/lti1p1": to_merge,
        }

    with describe('should create a user with the given email'):
        complete_data = merge(data, extra_data)

        _, launch = do_oidc_and_lti_launch(
            test_client, provider, complete_data, 200
        )
        new_user = m.UserLTIProvider.query.filter_by(lti_user_id=lti_user_id
                                                     ).one().user

        if connect and add_user_data:
            assert new_user.id == original_user.id
        else:
            assert new_user.id != original_user.id

        if connect and add_course_data:
            assert launch['data']['course']['id'] == course.id
        else:
            assert launch['data']['course']['id'] != course.id

        if connect and add_assig_data and add_course_data:
            assert launch['data']['assignment']['id'] == assig.id
            assert m.Assignment.query.get(
                assig.id
            ).lti_assignment_id == new_resource_id
        else:
            assert launch['data']['assignment']['id'] != assig.id
