import os
import hmac
import json
import uuid
import tempfile
import urllib.parse
from datetime import timedelta

import pytest

import psef as p
import helpers
from psef import models as m
from cg_dt_utils import DatetimeWithTimezone

_GITHUB_CLONE_URL = 'git@github.com:libre-man/TestRepo.git'


def _private_key():
    path = f'{os.path.dirname(__file__)}/../test_data/test_private_key'
    with open(path, 'rb') as f:
        return f.read()


def get_request_data(provider, event):
    base = f'{os.path.dirname(__file__)}/../test_data/test_webhooks/{provider}_{event}'
    with open(f'{base}.json', 'r') as f:
        return f.read().strip()


@pytest.fixture
def basic(logged_in, admin_user, test_client, session):
    with logged_in(admin_user):
        course = helpers.create_course(test_client)
        assig_id = helpers.create_assignment(
            test_client,
            course,
            deadline=DatetimeWithTimezone.utcnow() + timedelta(days=30),
            state='open',
        )['id']
        assig = m.Assignment.query.get(assig_id)
        assert assig is not None
        teacher = helpers.create_user_with_role(session, 'Teacher', [course])
        student = helpers.create_user_with_role(session, 'Student', [course])
        with logged_in(teacher):
            test_client.req(
                'patch',
                f'/api/v1/assignments/{assig_id}',
                200,
                data={
                    'files_upload_enabled': True,
                    'webhook_upload_enabled': True,
                },
            )
    yield course, assig, teacher, student


def test_disabling_files_upload(basic, test_client, logged_in, describe):
    with describe('setup'):
        course, assig, teacher, student = basic
        url = f'/api/v1/assignments/{assig.id}'
        query = {'no_course_in_assignment': True}

        with logged_in(student):
            helpers.create_submission(test_client, assig)

    with describe('disabling file upload makes it impossible to upload files'):
        with logged_in(teacher):
            _, rv = test_client.req(
                'patch',
                url,
                200,
                query=query,
                data={
                    'files_upload_enabled': False,
                    'webhook_upload_enabled': True,
                },
                include_response=True
            )
            assert 'warning' not in rv.headers

        with logged_in(student):
            helpers.create_submission(test_client, assig, err=400)

    with describe('you cannot disable both files and webhooks'):
        with logged_in(teacher):
            test_client.req(
                'patch',
                url,
                400,
                query=query,
                data={
                    'files_upload_enabled': False,
                    'webhook_upload_enabled': False,
                }
            )

    with describe('disabling wehbhooks when existing exists show a warning'
                  ), logged_in(teacher):
        _, rv = test_client.req(
            'patch',
            url,
            200,
                query=query,
            data={
                'files_upload_enabled': True,
                'webhook_upload_enabled': False,
            },
            include_response=True
        )
        assert 'warning' not in rv.headers

        test_client.req(
            'patch',
            url,
            200,
                query=query,
            data={
                'files_upload_enabled': True,
                'webhook_upload_enabled': True,
            }
        )

        with logged_in(student):
            old_webhook = test_client.req(
                'post',
                f'{url}/webhook_settings',
                200,
                query={'webhook_type': 'git', **query},
            )

        _, rv = test_client.req(
            'patch',
            url,
            200,
            data={
                'files_upload_enabled': True,
                'webhook_upload_enabled': False,
            },
            include_response=True,
        )
        assert 'warning' in rv.headers
        assert 'existing webhooks' in rv.headers.get('warning')

    with describe('New webhooks can no longer be created'), logged_in(teacher):
        test_client.req(
            'post', f'{url}/webhook_settings?webhook_type=git', 400
        )

    with describe('Old webhooks can also not be retrieved'
                  ), logged_in(student):
        test_client.req(
            'post', f'{url}/webhook_settings?webhook_type=git', 400
        )

    with describe('Old webhooks do still exist'):
        assert m.WebhookBase.query.get(old_webhook['id']) is not None


def test_creating_webhooks(basic, test_client, logged_in, describe, session):
    with describe('setup'):
        course, assig, teacher, student = basic
        url = f'/api/v1/assignments/{assig.id}/webhook_settings'
        other_user = helpers.create_user_with_perms(session, [], [])

    with describe('Posting twice results in the same hook twice'
                  ), logged_in(student):
        student_webhook = test_client.req(
            'post',
            f'{url}?webhook_type=git',
            200,
            result={
                'id': str,
                'public_key': str,
                'assignment_id': assig.id,
                'user_id': student.id,
                'secret': str,
                'default_branch': 'master',
            }
        )
        assert test_client.req(
            'post', f'{url}?webhook_type=git', 200
        ) == student_webhook

    with describe('A different users gets different data'), logged_in(teacher):
        teacher_webhook = test_client.req(
            'post', f'{url}?webhook_type=git', 200
        )
        assert all(
            v != teacher_webhook[k] for k, v in student_webhook.items()
            if k not in ['assignment_id', 'default_branch']
        )
        assert student_webhook['assignment_id'
                               ] == teacher_webhook['assignment_id']

    with describe('Webhook type should exist'), logged_in(teacher):
        test_client.req('post', url, 404)
        test_client.req('post', f'{url}?webhook_type=nope', 404)

    with describe('Can submit for other users'), logged_in(teacher):
        test_client.req(
            'post', f'{url}?webhook_type=git&author={student.username}', 200
        ) == student_webhook

    with describe('Users not in the course cannot hand in using it'):
        with logged_in(teacher):
            test_client.req(
                'post', f'{url}?webhook_type=git&author={other_user.username}',
                403
            )
        with logged_in(other_user):
            test_client.req('post', f'{url}?webhook_type=git', 403)


def test_github_webhooks(
    basic, test_client, logged_in, describe, stub_function_class, monkeypatch,
    app
):
    with describe('setup'):
        course, assig, teacher, student = basic
        stub_clone = stub_function_class()
        monkeypatch.setattr(p.tasks, 'clone_commit_as_submission', stub_clone)
        assig_url = f'/api/v1/assignments/{assig.id}'
        with logged_in(student):
            webhook_id = test_client.req(
                'post', (f'{assig_url}/webhook_settings?webhook_'
                         'type=git'), 200
            )['id']
            webhook = m.WebhookBase.query.get(webhook_id)
        url = f'/api/v1/webhooks/{webhook_id}'

    with describe('It should throw an error for a wrong signature'):
        data = {'payload': get_request_data('github', 'ping')}
        sig1 = 'sha1', hmac.new(
            (webhook.secret * 2).encode(),
            urllib.parse.urlencode(data).encode(),
            'sha1',
        ).hexdigest()

        # Only sha1 is used by github so only use that
        sig2 = 'md5', hmac.new(
            webhook.secret.encode(),
            urllib.parse.urlencode(data).encode(),
            'md5',
        ).hexdigest()

        for digest, signature in [sig1, sig2]:
            test_client.req(
                'post',
                url,
                400,
                real_data=data,
                headers={'X-Hub-Signature': f'{digest}={signature}'}
            )

    def do_request(event, use_json, extra_url='', status=201):
        data = get_request_data('github', event)
        if use_json:
            kwargs = {'content_type': 'application/json'}
        else:
            kwargs = {}
            data = {'payload': data}

        signature = hmac.new(
            webhook.secret.encode(),
            (data if use_json else urllib.parse.urlencode(data)).encode(),
            'sha1',
        ).hexdigest()

        return test_client.req(
            'post',
            url + extra_url,
            status,
            real_data=data,
            headers={
                'X-GitHub-Delivery': str(uuid.uuid4()),
                'X-GitHub-Event': event,
                'X-Hub-Signature': f'sha1={signature}',
            },
            **kwargs,
        )

    with describe('it should work for json requests'):
        do_request('ping', True)
        assert not stub_clone.called

    with describe('doing a push to the correct branch should clone'):
        do_request('push', True, '?branch=stable&branch=master', 200)
        assert stub_clone.called
        stub_clone.reset()

        do_request('push', True, '?branch=stable&branch=submit_v2', 202)
        assert not stub_clone.called

    with describe('it should work for form request'):
        do_request('ping', False)
        assert not stub_clone.called

        # Default branch is master
        do_request('push', False, '', 200)
        assert stub_clone.called
        args, = stub_clone.all_args
        cdata = args['clone_data_as_dict']
        assert cdata['sender_username'] == 'libre-man'
        assert cdata['clone_url'] == _GITHUB_CLONE_URL
        assert cdata['type'] == 'github'
        assert cdata['webhook_id'] == webhook_id

    with describe('If assignment is hidden the webhook stops working'):
        with logged_in(teacher):
            test_client.req(
                'patch', assig_url, 200, data={
                    'state': 'hidden',
                }
            )

        do_request('push', True, status=403)


def test_gitlab_webhooks(
    basic, test_client, logged_in, describe, stub_function_class, monkeypatch,
    app
):
    with describe('setup'):
        course, assig, teacher, student = basic
        stub_clone = stub_function_class()
        monkeypatch.setattr(p.tasks, 'clone_commit_as_submission', stub_clone)
        with logged_in(student):
            webhook_id = test_client.req(
                'post', (
                    f'/api/v1/assignments/{assig.id}/webhook_settings?webhook_'
                    'type=git'
                ), 200
            )['id']
            webhook = m.WebhookBase.query.get(webhook_id)
        url = f'/api/v1/webhooks/{webhook_id}'

    def do_request(extra_url, status, token=None, event='push'):
        if token is None:
            token = webhook.secret

        if event == 'push':
            data = get_request_data('gitlab', 'push')
        else:
            data = json.dumps({'object_kind': event})

        return test_client.req(
            'post',
            url + extra_url,
            status,
            real_data=data,
            content_type='application/json',
            headers={
                'X-Gitlab-Event': 'Push Hook' if event == 'push' else event,
                'X-Gitlab-Token': token,
            },
        )

    with describe('It should throw an error for a wrong signature'):
        do_request('', 400, 'NOT_THE_TOKEN')

    with describe('It should give 201 for a different event'):
        do_request('', 201, event='ping')

    with describe('doing a push to the correct branch should clone'):
        do_request('?branch=stable&branch=master', 200)
        assert stub_clone.called
        args, = stub_clone.all_args
        cdata = args['clone_data_as_dict']
        assert cdata['sender_username'] == '10175490'
        assert cdata['clone_url'] == (
            'ssh://git@gitlab-fnwi.uva.nl:1337/10812350/COSMPC.git'
        )
        assert cdata['type'] == 'gitlab'
        assert cdata['webhook_id'] == webhook_id

        stub_clone.reset()
        do_request('?branch=stable&branch=submit_v2', 202)
        assert not stub_clone.called


def test_unknown_webhook_type(basic, test_client, logged_in, describe):
    with describe('setup'):
        course, assig, teacher, student = basic
        with logged_in(student):
            webhook_id = test_client.req(
                'post', (
                    f'/api/v1/assignments/{assig.id}/webhook_settings?webhook_'
                    'type=git'
                ), 200
            )['id']
        url = f'/api/v1/webhooks/{webhook_id}'

    with describe('wrong type should give an error'):
        test_client.req('post', url, 400)


def test_clone_git_repo(
    basic, test_client, logged_in, describe, session, app, monkeypatch
):
    with describe('setup'):
        course, assig, teacher, student = basic
        with logged_in(student):
            webhook_id = test_client.req(
                'post', (
                    f'/api/v1/assignments/{assig.id}/webhook_settings?webhook_'
                    'type=git'
                ), 200
            )['id']
            webhook = m.WebhookBase.query.get(webhook_id)

            now = DatetimeWithTimezone.utcnow()
            stamp = now.timestamp()

            monkeypatch.setitem(app.config, 'MAX_NORMAL_UPLOAD_SIZE', 90000)
            clone_data = {
                'type': 'github',
                'url': 'MY_URL',
                'commit': 'bda573b5553e6938e4bb1e78a281939d4581e2fe',
                'ref': 'refs/heads/not_master',
                'sender_username': 'MY_USERNAME',
                'sender_name': 'MY_NAME',
                'webhook_id': str(webhook.id),
                'clone_url': _GITHUB_CLONE_URL,
                'repository_name': 'MY_REPO',
                'event': 'push',
                'branch': 'master',
            }

        def get_sub(user=student):
            all_subs = assig.get_all_latest_submissions()
            for sub in all_subs:
                if sub.user == user:
                    return sub
            return None

    with describe('should fail for none existing clone data id'):
        p.tasks._clone_commit_as_submission_1(
            unix_timestamp=stamp,
            clone_data_as_dict={**clone_data, 'webhook_id': str(uuid.uuid4())}
        )
        assert get_sub() is None

    with describe('should fail with wrong private key'):
        p.tasks._clone_commit_as_submission_1(
            unix_timestamp=stamp, clone_data_as_dict=clone_data
        )
        assert get_sub() is None

    webhook._ssh_key = _private_key()
    session.commit()
    with describe('written private key should create a PEM file'):
        with webhook.written_private_key() as fname:
            assert open(fname, 'rb').read().strip() == _private_key().strip()

    with describe('should work with correct private key'):
        assert get_sub() is None
        p.tasks._clone_commit_as_submission_1(
            unix_timestamp=stamp, clone_data_as_dict=clone_data
        )

        sub = get_sub()
        assert sub is not None
        assert sub.created_at == now
        with tempfile.TemporaryDirectory() as tmpdir:
            p.files.restore_directory_structure(sub, tmpdir)

            root = f'{tmpdir}/{os.listdir(tmpdir)[0]}'
            print(os.listdir(root))
            assert os.path.isdir(f'{root}/.git')

            with open(f'{root}/cg-size-limit-exceeded') as f:
                assert 'limit was exceeded' in f.read()

            assert not os.path.islink(f'{root}/aaa.pdf.link')
            with open(f'{root}/aaa.pdf.link') as f:
                assert 'symbolic link' in f.read()

            # This file should be too large
            assert not os.path.isfile(f'{root}/zzz.pdf')


def test_git_in_groups(
    basic, describe, logged_in, session, test_client, monkeypatch,
    stub_function_class
):
    with describe('setup'):
        course, assig, teacher, student = basic
        student2 = helpers.create_user_with_role(session, 'Student', [course])
        stub_clone = stub_function_class()
        monkeypatch.setattr(p.tasks, 'clone_commit_as_submission', stub_clone)
        url = f'/api/v1/assignments/{assig.id}'

        with logged_in(student):
            student1_webhook_id = test_client.req(
                'post', f'{url}/webhook_settings?webhook_type=git', 200
            )['id']

        with logged_in(teacher):
            group_set = helpers.create_group_set(
                test_client, course, 1, 2, [assig]
            )
            group = m.Group.query.get(
                helpers.create_group(test_client, group_set, [student2])['id']
            )

        with logged_in(student2):
            group_webhook_id = test_client.req(
                'post', f'{url}/webhook_settings?webhook_type=git', 200
            )['id']

    def do_request(webhook_id, user_id, status=200):
        data = get_request_data('github', 'push')
        kwargs = {'content_type': 'application/json'}
        webhook = m.WebhookBase.query.get(webhook_id)
        assert webhook is not None
        assert user_id == webhook.user_id

        signature = hmac.new(webhook.secret.encode(), data.encode(),
                             'sha1').hexdigest()

        return test_client.req(
            'post',
            f'/api/v1/webhooks/{webhook_id}',
            status,
            real_data=data,
            headers={
                'X-GitHub-Delivery': str(uuid.uuid4()),
                'X-GitHub-Event': 'push',
                'X-Hub-Signature': f'sha1={signature}',
            },
            **kwargs,
        )

    with describe('It should work for users not in a group'):
        do_request(student1_webhook_id, student.id)
        assert stub_clone.called

    with describe('It should work for users in a group'):
        do_request(group_webhook_id, group.virtual_user.id)
        assert stub_clone.called

    with describe('After joining group old webhook stops working'):
        with logged_in(student):
            _, rv = test_client.req(
                'post',
                f'/api/v1/groups/{group.id}/member',
                200,
                data={'username': student.username},
                include_response=True
            )
            assert 'warning' in rv.headers
            assert 'existing webhook for ' in rv.headers['warning']

        do_request(student1_webhook_id, student.id, status=400)
        assert not stub_clone.called


def test_webhooks_group_join_lti(
    describe, logged_in, session, test_client, monkeypatch,
    stub_function_class, admin_user, app
):
    with describe('setup'):
        course = helpers.create_lti_course(session, app)
        assig = helpers.create_lti_assignment(session, course, state='open')
        teacher = helpers.create_user_with_role(session, 'Teacher', [course])
        student1 = helpers.create_user_with_role(session, 'Student', [course])
        student2 = helpers.create_user_with_role(session, 'Student', [course])
        url = f'/api/v1/assignments/{assig.id}'

        with logged_in(teacher):
            group_set = helpers.create_group_set(
                test_client, course, 1, 2, [assig]
            )
            group = m.Group.query.get(
                helpers.create_group(test_client, group_set, [])['id']
            )
            test_client.req(
                'patch',
                url,
                200,
                data={
                    'files_upload_enabled': True,
                    'webhook_upload_enabled': True,
                },
            )

    with describe('Can join group without webhook'):
        with logged_in(student2):
            test_client.req(
                'post',
                f'/api/v1/groups/{group.id}/member',
                200,
                data={'username': student2.username},
            )

    with describe('Cannot make webhook with unfinished group'):
        with logged_in(student2):
            test_client.req(
                'post', f'{url}/webhook_settings?webhook_type=git', 400
            )

        session.add(
            m.AssignmentResult(
                user_id=student2.id,
                assignment_id=assig.id,
                sourcedid=str(uuid.uuid4()),
            )
        )
        session.commit()

        with logged_in(student2):
            group_webhook = test_client.req(
                'post', f'{url}/webhook_settings?webhook_type=git', 200
            )

    with describe(
        'Cannot join group as it has a webhook but user does not have sourcedid'
    ):
        with logged_in(student1):
            test_client.req(
                'post',
                f'/api/v1/groups/{group.id}/member',
                400,
                data={'username': student1.username},
            )

        with logged_in(student1):
            # Cannot create individual webhook
            test_client.req(
                'post', f'{url}/webhook_settings?webhook_type=git', 400
            )

        session.add(
            m.AssignmentResult(
                user_id=student1.id,
                assignment_id=assig.id,
                sourcedid=str(uuid.uuid4()),
            )
        )
        session.commit()

        with logged_in(student1):
            _, rv = test_client.req(
                'post',
                f'/api/v1/groups/{group.id}/member',
                200,
                data={'username': student1.username},
                include_response=True,
            )
            assert 'warning' not in rv.headers

        with logged_in(student1):
            # And we now get the group webhook config.
            test_client.req(
                'post',
                f'{url}/webhook_settings?webhook_type=git',
                200,
                result=group_webhook
            )


def test_get_warning_with_git_and_ignore_file(
    basic, test_client, logged_in, describe
):
    with describe('setup'):
        course, assig, teacher, student = basic
        url = f'/api/v1/assignments/{assig.id}'
        ignore_data = {
            'ignore': {
                'policy': 'allow_all_files',
                'options': [{
                    'key': 'allow_override',
                    'value': False,
                }],
                'rules': [{
                    'rule_type': 'require',
                    'file_type': 'file',
                    'name': 'a.py',
                }],
            },
            'ignore_version': 'SubmissionValidator',
        }

    with describe("enabling git doesn't give a warning"):
        with logged_in(teacher):
            _, rv = test_client.req(
                'patch',
                url,
                200,
                query={'no_course_in_assignment': True},
                data={
                    'files_upload_enabled': False,
                    'webhook_upload_enabled': True,
                },
                include_response=True
            )
            assert 'warning' not in rv.headers

    with describe('enabling ignore files gives warning'), logged_in(teacher):
        _, rv = test_client.req(
            'patch', url, 200, data=ignore_data, include_response=True
        )

        assert 'warning' in rv.headers
        assert 'currently ignored' in rv.headers['warning']

    with describe('enabling git gives warning'), logged_in(teacher):
        _, rv = test_client.req(
            'patch',
            url,
            200,
            data={
                'files_upload_enabled': False, 'webhook_upload_enabled': True
            },
            include_response=True
        )

        assert 'warning' in rv.headers
        assert 'currently ignored' in rv.headers['warning']

    with describe('removing ignore gives no warning'), logged_in(teacher):
        _, rv = test_client.req(
            'patch',
            url,
            200,
            query={'no_course_in_assignment': True},
            data={'ignore': '', 'ignore_version': 'EmptySubmissionFilter'},
            include_response=True
        )

        assert 'warning' not in rv.headers

    with describe('enabling ignore with no git gives no warning'
                  ), logged_in(teacher):
        test_client.req(
            'patch',
            url,
            200,
            data={
                'files_upload_enabled': True, 'webhook_upload_enabled': False
            },
        )

        _, rv = test_client.req(
            'patch',
            url,
            200,
            query={'no_course_in_assignment': True},
            data=ignore_data,
            include_response=True,
        )
        assert 'warning' not in rv.headers
