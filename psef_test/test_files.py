# SPDX-License-Identifier: AGPL-3.0-only
import os
import datetime
import tempfile

import pytest
from freezegun import freeze_time
from werkzeug.datastructures import FileStorage

import psef
from helpers import create_marker

perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)


@pytest.mark.parametrize(
    'named_user', [
        'Thomas Schaper',
        'Student1',
        perm_error(error=401)('NOT_LOGGED_IN'),
    ],
    indirect=True
)
@pytest.mark.parametrize('size', [10, data_error(int(1.5 * 2 ** 20))])
def test_get_code_metadata(
    named_user, test_client, request, error_template, logged_in, size,
    monkeypatch, stub_function_class
):
    filestr = 'a' * size
    monkeypatch.setattr(
        psef.tasks, 'delete_file_at_time', stub_function_class()
    )

    perm_err = request.node.get_closest_marker('perm_error')
    data_err = request.node.get_closest_marker('data_error')
    if perm_err:
        error = perm_err.kwargs['error']
    elif data_err:
        error = 400
    else:
        error = False

    with logged_in(named_user):
        res = test_client.req(
            'post',
            '/api/v1/files/',
            error or 201,
            real_data=filestr,
            result=error_template if error else str,
        )
        fname = error or res

        if not data_err:
            if error:
                test_client.req(
                    'get',
                    f'/api/v1/files/{fname}',
                    404,
                    result=error_template,
                )
            else:
                res = test_client.get(f'/api/v1/files/{fname}')
                assert res.status_code == 200

                assert res.get_data(as_text=True) == filestr

                res = test_client.get(f'/api/v1/files/{fname}')
                assert res.status_code == 404


def test_get_code_with_head(
    student_user, test_client, request, logged_in, app, monkeypatch,
    stub_function_class
):
    filestr = 'a' * 10
    monkeypatch.setattr(
        psef.tasks, 'delete_file_at_time', stub_function_class()
    )

    with logged_in(student_user):
        fname = test_client.req(
            'post',
            '/api/v1/files/',
            201,
            real_data=filestr,
            result=str,
        )
        path = os.path.join(app.config['MIRROR_UPLOAD_DIR'], fname)
        assert os.path.isfile(path)

        head = test_client.head(f'/api/v1/files/{fname}')
        assert head.status_code == 200
        assert os.path.isfile(path)

        res = test_client.get(f'/api/v1/files/{fname}')
        assert res.status_code == 200
        assert res.get_data(as_text=True) == filestr
        assert not os.path.isfile(path)

        res = test_client.get(f'/api/v1/files/{fname}')
        assert res.status_code == 404
        assert not os.path.isfile(path)


def test_code_gets_deleted_automatically(
    test_client, request, student_user, logged_in, monkeypatch, describe,
    stub_function_class, yesterday, tomorrow, app
):
    with describe('setup'):
        filestr = 'a' * 10
        new_file_at_time = stub_function_class()
        orig_file_at_time = psef.tasks._delete_file_at_time_1
        monkeypatch.setattr(
            psef.tasks, 'delete_file_at_time', new_file_at_time
        )
        apply_async = stub_function_class()
        monkeypatch.setattr(
            psef.tasks._delete_file_at_time_1, 'apply_async', apply_async
        )

    with describe('upload'), logged_in(student_user):
        upload_time = datetime.datetime.utcnow()
        fname = test_client.req(
            'post',
            '/api/v1/files/',
            201,
            real_data=filestr,
            result=str,
        )
        path = os.path.join(app.config['MIRROR_UPLOAD_DIR'], fname)
        assert os.path.isfile(path)
        new_file_args, = new_file_at_time.all_args

    with describe('calling API too late will return a 404'
                  ), freeze_time(tomorrow), logged_in(student_user):
        res = test_client.get(f'/api/v1/files/{fname}')
        assert res.status_code == 404
        assert os.path.isfile(path)

    with describe('task should not delete file directly'
                  ), freeze_time(upload_time):
        assert not apply_async.all_args

        # Should be delayed again
        orig_file_at_time(**new_file_args)
        assert os.path.isfile(path)
        assert apply_async.called
        assert apply_async.all_args[0]['kwargs'] == new_file_args

    with describe('task should delete file at one point'
                  ), freeze_time(tomorrow):
        assert not apply_async.called
        # Should not be delayed again

        orig_file_at_time(**new_file_args)
        assert not os.path.isfile(path)
        assert not apply_async.called


def test_save_stream(describe, monkeypatch, app):
    with tempfile.TemporaryDirectory() as upload_dir:
        monkeypatch.setitem(app.config, "UPLOAD_DIR", upload_dir)

        with describe('not too large file'), open(__file__, 'rb') as f:
            filename = psef.files.save_stream(FileStorage(f))
            filepath = f'{upload_dir}/{filename}'
            f.seek(0, 0)

            assert os.path.exists(filepath)
            assert f.read() == open(filepath, 'rb').read()

        with describe('too large file'), open(__file__, 'rb') as f:
            monkeypatch.setitem(app.config, 'MAX_FILE_SIZE', 10)

            old_files = os.listdir(upload_dir)

            with pytest.raises(psef.errors.APIException):
                psef.files.save_stream(FileStorage(f))

            assert os.listdir(upload_dir) == old_files
