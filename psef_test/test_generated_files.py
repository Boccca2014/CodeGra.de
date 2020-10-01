import os
import tempfile
from datetime import timedelta

import pytest

import psef as p
import helpers
from psef import models as m
from cg_dt_utils import DatetimeWithTimezone

_GITHUB_CLONE_URL = 'git@github.com:libre-man/TestRepo.git'


@pytest.fixture
def private_key():
    path = f'{os.path.dirname(__file__)}/../test_data/test_private_key'
    with open(path, 'rb') as f:
        yield f.read()


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


def test_git_submission_generated_files(
    basic, test_client, logged_in, describe, session, app, monkeypatch,
    private_key
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

            webhook._ssh_key = private_key
            session.commit()

        p.tasks._clone_commit_as_submission_1(
            unix_timestamp=stamp, clone_data_as_dict=clone_data
        )
        sub = next(
            sub for sub in assig.get_all_latest_submissions()
            if sub.user == student
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        m.File.restore_directory_structure(
            tmpdir,
            m.File.make_cache(sub),
        )
        root = f'{tmpdir}/{os.listdir(tmpdir)[0]}'

        with describe('cg-size-limit-exceeded'
                      ), open(f'{root}/cg-size-limit-exceeded') as f:
            content = f.read()
            assert content.endswith('\n')
            assert 'limit was exceeded' in content

        with describe('symbolic link replacement files'
                      ), open(f'{root}/aaa.pdf.link') as f:
            assert not os.path.islink(f'{root}/aaa.pdf.link')
            content = f.read()
            assert content.endswith('\n')
            assert 'symbolic link' in content
            assert 'test.pdf' in content


def test_archive_generated_files(basic, test_client, describe, logged_in):
    with describe('setup'):
        course, assig, teacher, student = basic

        with logged_in(student):
            helpers.create_submission(
                test_client,
                assignment_id=assig.id,
                submission_data=(
                    (
                        f'{os.path.dirname(__file__)}/../test_data/test_submissions/'
                        'single_symlink_archive.tar.gz'
                    ),
                    'f.tar.gz',
                ),
            )
        sub = next(
            sub for sub in assig.get_all_latest_submissions()
            if sub.user == student
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        m.File.restore_directory_structure(
            tmpdir,
            m.File.make_cache(sub),
        )
        root = f'{tmpdir}/{os.listdir(tmpdir)[0]}'

        with describe('symbolic link replacement files'
                      ), open(f'{root}/test_file') as f:
            assert not os.path.islink(f'{root}/test_file')
            content = f.read()
            assert content.endswith('\n')
            assert 'symbolic link' in content
            assert 'non_existing' in content
