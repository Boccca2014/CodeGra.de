# SPDX-License-Identifier: AGPL-3.0-only
import os
import copy
import uuid
import datetime

import pytest

import psef.models as m
from helpers import create_marker
from cg_dt_utils import DatetimeWithTimezone
from psef.permissions import CoursePermission

perm_error = create_marker(pytest.mark.perm_error)
data_error = create_marker(pytest.mark.data_error)
late_error = create_marker(pytest.mark.late_error)


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
@pytest.mark.parametrize('filename', ['test_flake8.tar.gz'], indirect=True)
def test_get_code_metadata(
    named_user, assignment_real_works, test_client, request, error_template,
    ta_user, logged_in
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': [{'id': str, 'name': 'test.py'}], 'id': str, 'name':
                    'test_flake8.tar.gz'
            }
        )

    with logged_in(named_user):
        test_client.req(
            'get',
            f'/api/v1/code/{res["id"]}',
            error if error else 200,
            result=error_template if error else {
                'name': 'test_flake8.tar.gz',
                'is_directory': True,
                'id': str,
            },
            query={'type': 'metadata'}
        )

        test_client.req(
            'get',
            f'/api/v1/code/{res["entries"][0]["id"]}',
            error if error else 200,
            result=error_template if error else {
                'name': 'test.py',
                'is_directory': False,
                'id': str,
            },
            query={'type': 'metadata'}
        )


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
    'filename,content', [
        ('test_flake8.tar.gz', 'def a(b):\n\tprint ( 5 )\n'),
        data_error(error=400)(
            ('../test_submissions/nested_dir_archive.tar.gz', 'SHOULD_ERROR')
        ),
        ('../test_submissions/pdf_in_dir_archive.tar.gz', False),
    ],
    indirect=['filename']
)
def test_get_code_plaintext(
    named_user, assignment_real_works, test_client, request, error_template,
    ta_user, logged_in, content
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

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': list,
                'id': str,
                'name': str,
            }
        )

    with logged_in(named_user):
        if error:
            test_client.req(
                'get',
                f'/api/v1/code/{res["entries"][0]["id"]}',
                error,
                result=error_template,
            )
        else:
            res = test_client.get(f'/api/v1/code/{res["entries"][0]["id"]}')
            assert res.status_code == 200
            if content:
                assert res.get_data(as_text=True) == content
            else:
                with pytest.raises(UnicodeDecodeError):
                    res.get_data(as_text=True)
                res.get_data()


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip']
)
def test_get_code_plaintext_revisions(
    assignment_real_works, test_client, request, error_template, ta_user,
    teacher_user, student_user, logged_in
):
    assignment, work = assignment_real_works
    assignment_id = assignment.id
    work_id = work['id']

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment_id}',
            200,
            data={'state': 'done'},
        )

    with logged_in(ta_user):
        files = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
        )
        student_file_id = files['entries'][0]['id']

        res = test_client.req(
            'patch',
            f'/api/v1/code/{student_file_id}',
            200,
            real_data='test',
        )
        teacher_file_id = res['id']
        assert teacher_file_id != student_file_id

    with logged_in(student_user):
        res = test_client.get(f'/api/v1/code/{student_file_id}')
        assert res.status_code == 200

        res = test_client.get(f'/api/v1/code/{teacher_file_id}')
        assert res.status_code == 200

    with logged_in(teacher_user):
        test_client.req(
            'patch',
            f'/api/v1/assignments/{assignment_id}',
            200,
            data={'state': 'open'},
        )

    with logged_in(student_user):
        res = test_client.get(f'/api/v1/code/{student_file_id}', )
        assert res.status_code == 200

        res = test_client.get(f'/api/v1/code/{teacher_file_id}', )
        assert res.status_code == 403


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
    'filename,mimetype', [
        ('../test_submissions/pdf_in_dir_archive.tar.gz', 'application/pdf'),
        ('../test_submissions/img_in_dir_archive.tar.gz', 'image/png'),
    ],
    indirect=['filename']
)
@pytest.mark.parametrize('query_type', ['pdf', 'file-url'])
def test_get_file_url(
    named_user, assignment_real_works, test_client, request, error_template,
    ta_user, logged_in, mimetype, query_type
):
    assignment, work = assignment_real_works
    work_id = work['id']

    perm_err = request.node.get_closest_marker('perm_error')
    if perm_err:
        error = perm_err.kwargs['error']
    else:
        error = False

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': list,
                'id': str,
                'name': str,
            }
        )
        file_id = res["entries"][0]["id"]

    with logged_in(named_user):
        if error:
            test_client.req(
                'get',
                f'/api/v1/code/{file_id}',
                error,
                query={'type': query_type},
                result=error_template
            )
        else:
            res = test_client.req(
                'get',
                f'/api/v1/code/{file_id}',
                200,
                query={'type': query_type},
                result={'name': str},
            )
            res = test_client.get(
                f'/api/v1/files/{res["name"]}',
                query_string={'mime': mimetype}
            )
            assert res.status_code == 200
            assert res.headers['Content-Type'] == mimetype


@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
def test_delete_code_as_ta(
    assignment_real_works, test_client, request, error_template, ta_user,
    logged_in, session
):
    assignment, work = assignment_real_works
    work_id = work['id']

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': list,
                'id': str,
                'name': str,
            }
        )
        assert len(res['entries']) == 2

        test_client.req(
            'delete',
            f'/api/v1/code/{res["entries"][0]["entries"][0]["id"]}',
            403,
            result=error_template,
        )

        assignment.deadline = DatetimeWithTimezone.utcnow(
        ) - datetime.timedelta(days=1)
        session.commit()

        ents = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'owner': 'teacher'},
        )['entries']
        assert len(ents) == 2, 'It should not delete after an error'

        test_client.req(
            'delete',
            f'/api/v1/code/{res["entries"][0]["id"]}',
            400,
            result=None,
        )
        for ent in res['entries'][0]['entries'][:-1]:
            test_client.req(
                'delete',
                f'/api/v1/code/{ent["id"]}',
                204,
                result=None,
            )
            test_client.req(
                'delete',
                f'/api/v1/code/{res["entries"][0]["id"]}',
                400,
                result=None,
            )
        test_client.req(
            'delete',
            f'/api/v1/code/{res["entries"][0]["entries"][-1]["id"]}',
            204,
            result=None,
        )
        test_client.req(
            'delete',
            f'/api/v1/code/{res["entries"][0]["id"]}',
            204,
            result=None,
        )

        ents = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
        )['entries']

        assert len(ents) == 2, 'Only teacher files should be affected'

        ents = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'owner': 'teacher'},
        )['entries']

        assert len(ents) == 1, 'The teacher files should have a file less'


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
def test_delete_code_as_student(
    assignment_real_works,
    test_client,
    request,
    error_template,
    ta_user,
    logged_in,
    session,
    student_user,
):
    assignment, work = assignment_real_works
    work_id = work['id']

    with logged_in(student_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': list,
                'id': str,
                'name': str,
            }
        )
        assert len(res['entries']) == 2

        test_client.req(
            'delete',
            f'/api/v1/code/{res["entries"][0]["id"]}',
            403,
            result=None,
        )

        assignment.state = m.AssignmentStateEnum.done
        session.commit()

        test_client.req(
            'delete',
            f'/api/v1/code/{res["entries"][0]["id"]}',
            403,
            result=error_template,
        )

        ents = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
        )['entries']

        assert len(ents) == 2

        ents = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'owner': 'teacher'},
        )['entries']

        assert len(ents) == 2

        with logged_in(ta_user):
            test_client.req(
                'delete',
                f'/api/v1/code/{res["entries"][0]["id"]}',
                204,
                result=None,
            )

        ents = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'owner': 'teacher'},
        )['entries']
        assert len(ents) == 1


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
def test_delete_code_twice(
    assignment_real_works, test_client, request, error_template, ta_user,
    logged_in, session
):
    assignment, work = assignment_real_works
    work_id = work['id']

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': list,
                'id': str,
                'name': str,
            }
        )
        assert len(res['entries']) == 2

        assignment.deadline = DatetimeWithTimezone.utcnow(
        ) - datetime.timedelta(days=1)
        session.commit()

        test_client.req(
            'delete',
            f'/api/v1/code/{res["entries"][0]["id"]}',
            204,
            result=None,
        )

        ents = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'owner': 'teacher'},
        )['entries']

        assert len(ents) == 1, 'The teacher files should have a file less'

        test_client.req(
            'delete',
            f'/api/v1/code/{res["entries"][0]["id"]}',
            403,
            result=error_template,
        )

        ents = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'owner': 'teacher'},
        )['entries']

        assert len(ents) == 1, 'The teacher files should have a file less'


@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
def test_delete_dir_with_deleted_files_as_ta(
    assignment_real_works, test_client, request, error_template, ta_user,
    student_user, logged_in, session, describe
):
    assignment, work = assignment_real_works
    work_id = work['id']

    with logged_in(student_user), describe('delete some files as student'):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'id': str,
                'name': str,
                'entries': [
                    {
                        'entries': [dict, dict],
                        '__allow_extra__': True,
                    },
                    dict,
                ],
            },
        )
        dir = res['entries'][0]

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            query={'owner': 'teacher'},
            result={
                'id': str,
                'name': str,
                'entries': [
                    {
                        'entries': [dict, dict],
                        '__allow_extra__': True,
                    },
                    dict,
                ],
            },
        )
        dir = res['entries'][0]

        assignment.deadline = DatetimeWithTimezone.utcnow(
        ) - datetime.timedelta(days=1)
        session.commit()

        with describe('delete first file in a subdirectory'):
            test_client.req(
                'delete',
                f'/api/v1/code/{dir["entries"][0]["id"]}',
                204,
                result=None,
            )

        with describe(
            'check that it is still not possible to delete directory'
        ):
            test_client.req(
                'delete',
                f'/api/v1/code/{dir["id"]}',
                400,
                result=error_template,
            )

        with describe('delete second file in subdirectory'):
            test_client.req(
                'delete',
                f'/api/v1/code/{dir["entries"][1]["id"]}',
                204,
                result=None,
            )

        with describe('check that we can now delete directory'):
            test_client.req(
                'delete',
                f'/api/v1/code/{dir["id"]}',
                204,
                result=None,
            )

        with describe('check that directory is gone'):
            test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/files/',
                200,
                query={'owner': 'teacher'},
                result={
                    'id': str,
                    'name': str,
                    'entries': [dict],
                },
            )


@pytest.mark.parametrize(
    'filename', ['../test_submissions/multiple_dir_archive.zip'],
    indirect=True
)
def test_invalid_delete_code(
    assignment_real_works, test_client, request, error_template, ta_user,
    logged_in, session, monkeypatch_celery
):
    assignment, work = assignment_real_works
    work_id = work['id']
    other_work = m.Work.query.filter_by(assignment=assignment
                                        ).filter(m.Work.id != work_id).first()
    other_code = m.File.query.filter_by(
        work_id=other_work.id, is_directory=False
    ).first()

    with logged_in(ta_user):
        res = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': list,
                'id': str,
                'name': str,
            }
        )
        assignment.deadline = DatetimeWithTimezone.utcnow(
        ) - datetime.timedelta(
            days=1,
        )
        session.commit()

        f = res['entries'][0]['entries'][0]
        code_id = f['id']
        new_f = test_client.req(
            'patch',
            f'/api/v1/code/{code_id}',
            200,
            query={'operation': 'content'},
            result={'name': f['name'], 'id': str, 'is_directory': False},
            real_data='WOWSERS123',
        )
        new_code_id = new_f['id']

        assert new_code_id != code_id, 'Should have a new file'

        test_client.req(
            'put',
            f'/api/v1/code/{new_code_id}/comments/0',
            204,
            data={'comment': 'GOED!'},
        )

        req = test_client.get(f'/api/v1/code/{new_code_id}')
        assert req.status_code == 200, 'Request had no errors'
        assert req.get_data(
            as_text=True
        ) == 'WOWSERS123', 'The teacher revision was used'

        test_client.req(
            'delete',
            f'/api/v1/code/{new_code_id}',
            400,
            result=error_template,
        )

        # Delete comment
        test_client.req(
            'delete',
            f'/api/v1/code/{new_code_id}/comments/0',
            204,
        )

        p_run = m.PlagiarismRun(
            assignment=assignment, json_config='[]', old_assignments=[]
        )
        p_case = m.PlagiarismCase(
            work1_id=work_id,
            work2_id=other_work.id,
            match_avg=50,
            match_max=50
        )
        p_match = m.PlagiarismMatch(
            file1_id=new_f['id'],
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

        # Still not possible
        test_client.req(
            'delete',
            f'/api/v1/code/{new_code_id}',
            400,
            result=error_template,
        )

        session.delete(p_case)
        session.commit()

        # Not it should work as there is no comment and not plagiarism case
        test_client.req(
            'delete',
            f'/api/v1/code/{new_code_id}',
            204,
        )

        assert test_client.get(
            f'/api/v1/code/{new_code_id}'
        ).status_code == 404
        assert test_client.get(f'/api/v1/code/{code_id}').status_code == 200

        test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result=res,
        )


@pytest.mark.parametrize(
    'filename', ['../test_submissions/single_dir_archive.zip'], indirect=True
)
def test_update_code(
    assignment_real_works, test_client, request, error_template, ta_user,
    logged_in, session, student_user
):
    assignment, work = assignment_real_works
    work_id = work['id']

    def get_code_data(code_id):
        r = test_client.get(f'/api/v1/code/{code_id}')
        assert r.status_code == 200
        try:
            return r.get_data(as_text=True)
        except:
            return r.get_data()

    def adjust_code(code_id, status, data=None):
        if data is None:
            data = str(uuid.uuid4())
        with logged_in(ta_user):
            old = get_code_data(code_id)

        res = test_client.req(
            'patch',
            f'/api/v1/code/{code_id}',
            status,
            real_data=data,
            result=error_template if status >= 400 else None
        )
        if status >= 400:
            with logged_in(ta_user):
                assert get_code_data(code_id) == old
            return

        assert get_code_data(res['id']) == data
        return res['id']

    with logged_in(ta_user):
        code_id = test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/',
            200,
            result={
                'entries': list,
                'id': str,
                'name': str,
            }
        )['entries'][0]['id']

    with logged_in(student_user):
        adjust_code(code_id, 403)

        m.Assignment.query.filter_by(id=assignment.id).update({
            'state': m.AssignmentStateEnum.done
        })
        session.commit()

        adjust_code(code_id, 403)

    with logged_in(ta_user):
        old = get_code_data(code_id)
        new_id = adjust_code(code_id, 200)
        assert new_id != code_id
        # Make sure id only changes once
        assert adjust_code(new_id, 200) == new_id
        assert old == get_code_data(code_id)

        # You cannot change the student rev more than once
        adjust_code(code_id, 403)

        # Make sure you cannot upload to large strings
        adjust_code(new_id, 400, b'0' * 2 * 2 ** 20)

    # Cannot change code if state is done
    with logged_in(student_user):
        adjust_code(code_id, 403)

    m.Assignment.query.filter_by(id=assignment.id).update({
        'state': m.AssignmentStateEnum.open
    })
    # Cannot adjust teacher rev as student
    with logged_in(student_user):
        adjust_code(new_id, 403)

    m.Assignment.query.filter_by(id=assignment.id).update({
        'state': m.AssignmentStateEnum.open,
        'deadline': DatetimeWithTimezone.utcnow() - datetime.timedelta(days=1),
    })
    # Cannot change code after deadline as student
    with logged_in(student_user):
        adjust_code(code_id, 403, 'AAH_CON')

    role = m.CourseRole.query.filter_by(
        course_id=assignment.course_id, name='Student'
    ).one()
    role.set_permission(CoursePermission.can_upload_after_deadline, True)
    session.commit()
    # CAN change code after deadline as student if you have the permission for
    # this.
    with logged_in(ta_user):
        old = get_code_data(new_id)
    with logged_in(student_user):
        adjust_code(code_id, 403)
    with logged_in(ta_user):
        assert old == get_code_data(new_id)

    # Make sure invalid utf-8 can be uploaded
    with logged_in(ta_user):
        data = b'\x00' + os.urandom(12) + b'\xff'
        # Make sure we sent a string that is not valid utf-8
        with pytest.raises(UnicodeDecodeError):
            data.decode('utf-8')
        adjust_code(new_id, 200, data)
        assert data == get_code_data(new_id)


@pytest.mark.parametrize(
    'filename,extension', [
        ('../test_submissions/multiple_dir_archive.tar.gz', '.tar.gz'),
        ('../test_submissions/multiple_dir_archive.zip', '.zip'),
        ('../test_submissions/multiple_dir_archive.7z', '.7z'),
    ],
    indirect=['filename']
)
def test_rename_code(
    assignment_real_works, test_client, request, error_template, ta_user,
    logged_in, session, student_user, extension, filename
):
    # Sanity check to make sure the extension was set correctly
    assert filename.endswith(extension)

    assignment, work = assignment_real_works
    work_id = work['id']

    def get_code_data(code_id):
        with logged_in(ta_user):
            r = test_client.get(f'/api/v1/code/{code_id}')
            assert r.status_code == 200
            return r.get_data(as_text=True)

    def adjust_code(code_id, status, data=None):
        if data is None:
            data = str(uuid.uuid4())
        with logged_in(ta_user):
            old = get_code_data(code_id)

        res = test_client.req(
            'patch',
            f'/api/v1/code/{code_id}',
            status,
            real_data=data,
            result=error_template if status >= 400 else None
        )
        if status >= 400:
            assert get_code_data(code_id) == old
            return

        assert get_code_data(res['id']) == data
        return res['id']

    def create_file(path):
        return test_client.req(
            'post',
            f'/api/v1/submissions/{work_id}/files/?path={path}',
            200,
        )['id']

    def rename(code_id, new_name, status):
        if status < 400:
            test_client.req(
                'patch',
                f'/api/v1/code/{code_id}?operation=rename',
                400,
                result=error_template
            )
        res = test_client.req(
            'patch',
            f'/api/v1/code/{code_id}?operation=rename&new_path={new_name}',
            status,
            result=error_template if status >= 400 else None
        )
        if status < 400:
            return res['id']

    def get_file_tree(owner='auto'):
        return test_client.req(
            'get',
            f'/api/v1/submissions/{work_id}/files/?owner={owner}',
            200,
            result={
                'entries': list,
                'id': str,
                'name': str,
            }
        )

    with logged_in(ta_user):
        files = get_file_tree()
        original_tree = copy.deepcopy(files)
        assert files['name'] == f'multiple_dir_archive{extension}'
        assert len(files['entries']) == 2
        assert files['entries'][0]['name'] == 'dir'
        assert files['entries'][1]['name'] == 'dir2'
        old_data0 = get_code_data(files['entries'][0]['entries'][0]['id'])
        code_id = files['entries'][0]['entries'][0]['id']

        m.Assignment.query.filter_by(id=assignment.id).update({
            'state': m.AssignmentStateEnum.done
        })
        session.commit()

    with logged_in(ta_user):
        added_file4 = adjust_code(
            create_file(
                f'/multiple_dir_archive{extension}/dir3/sub_dir/file4'
            ),
            200,
            'CONTENT',
        )

        files = get_file_tree()
        ff = files['entries'][-1]['entries']
        assert len(ff) == 1
        assert ff[-1]['name'] == 'sub_dir'
        assert ff[-1]['entries'][0]['id'] == added_file4
        assert len(ff[-1]['entries']) == 1
        del ff

        rename(
            files['entries'][-1]['id'],
            f'/multiple_dir_archive{extension}/dir4', 200
        )
        files = get_file_tree()

        assert len(files['entries']) == 3

        assert files['entries'][-1]['name'] == 'dir4'
        assert files['entries'][-2]['name'] == 'dir2'

        ff = files['entries'][-1]['entries']
        assert len(ff) == 1
        assert ff[-1]['name'] == 'sub_dir'
        assert ff[-1]['entries'][0]['id'] == added_file4
        assert len(ff[-1]['entries']) == 1
        del ff

        assert len(files['entries'][0]['entries']) == 2

    with logged_in(student_user):
        files = get_file_tree()
        assert files == original_tree

    with logged_in(ta_user):
        files = get_file_tree()
        rename(
            files['entries'][0]['id'],
            f'/multiple_dir_archive{extension}/dir4/sub_dir/dir', 200
        )
        files = get_file_tree()
        assert len(files['entries']) == 2
        assert files['entries'][-1]['name'] == 'dir4'
        assert len(files['entries'][-1]['entries']) == 1


@pytest.mark.parametrize(
    'filename', [
        ('../test_submissions/deep_nested_dirs.tar.gz'),
    ],
    indirect=['filename']
)
def test_rename_nested_dir(
    assignment_real_works, test_client, student_user, error_template, ta_user,
    logged_in, session, describe, assert_similar
):
    with describe('setup'):
        assignment, work = assignment_real_works
        work_id = work['id']

        def rename(code_id, new_name):
            return test_client.req(
                'patch',
                f'/api/v1/code/{code_id}?operation=rename&new_path={new_name}',
                200,
            )['id']

        def find_file(files, name):
            if isinstance(name, str):
                return find_file(files, list(reversed(name.split('/'))))
            cur_name = name.pop()
            res, = [f for f in files['entries'] if f['name'] == cur_name]
            if name:
                return find_file(res, name)
            return res

        def get_file_tree(owner='auto'):
            return test_client.req(
                'get',
                f'/api/v1/submissions/{work_id}/files/?owner={owner}',
                200,
                result={
                    'entries': list,
                    'id': str,
                    'name': str,
                }
            )

        m.Assignment.query.filter_by(id=assignment.id).update({
            'state': m.AssignmentStateEnum.done
        })
        session.commit()
        with logged_in(ta_user):
            orig_tree = get_file_tree()

    with describe('rename dir with mixed ownership'), logged_in(ta_user):
        dir3 = find_file(get_file_tree(), 'dir1/dir2/dir3')['id']
        dir3_id = rename(
            dir3, '/deep_nested_dirs.tar.gz/dir1/dir2/dir3_new'
        )
        dir2 = find_file(get_file_tree(), 'dir1/dir2')['id']
        dir2_id = rename(
            dir2, '/deep_nested_dirs.tar.gz/dir1/dir2_new'
        )

    with describe('dir should have expected shape'), logged_in(ta_user):
        new_ta_tree = get_file_tree()
        assert_similar(
            new_ta_tree,
            {
                'name': 'deep_nested_dirs.tar.gz',
                'id': orig_tree['id'],
                'entries': [
                    {'id': find_file(orig_tree, 'a')['id'], 'name': 'a'},
                    {
                        'id': find_file(orig_tree, 'dir1')['id'],
                        'name': 'dir1',
                        'entries': [
                            {'name': 'b', 'id': str},
                            {
                                'name': 'dir2_new',
                                'id': dir2_id,
                                'entries': [
                                    {'name': 'b', 'id': str},
                                    {
                                        'name': 'dir3_new',
                                        'id': dir3_id,
                                        'entries': [],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        )
        # The ``b`` file should also have a new id
        assert (
            find_file(new_ta_tree, 'dir1/dir2_new/b')['id'] !=
            find_file(orig_tree, 'dir1/dir2/b')['id']
        )

    with describe('student tree should not be altered'
                  ), logged_in(student_user):
        assert get_file_tree() == orig_tree
