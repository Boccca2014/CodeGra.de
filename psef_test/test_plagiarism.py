# SPDX-License-Identifier: AGPL-3.0-only
import io
import os
import csv
import json
import math
import random
import tempfile
import itertools
import contextlib
import subprocess

import pytest
from sqlalchemy import func

import psef
import psef.models as models
from helpers import create_marker

http_err = create_marker(pytest.mark.http_err)

original_popen = subprocess.Popen


def make_popen_stub(callback, crash=False):
    class PopenStub:
        @contextlib.contextmanager
        def __call__(self, call, **kwargs):
            self.data_dir = call[3]
            self.progress_prefix = call[call.index('-progress') + 1]
            # assert not kwargs['shell']
            callback(call, **kwargs)
            amount = len(os.listdir(self.data_dir))
            with tempfile.NamedTemporaryFile('w+') as f:
                f.write(
                    '\n'.join([
                        f'{self.progress_prefix} 1 / {amount}',
                        f'{self.progress_prefix} 2 / {amount}',
                        f'{self.progress_prefix} {amount} / {amount}',
                        f'{self.progress_prefix} 1 / {amount}',
                        f'{self.progress_prefix} 1 / {amount}',
                        'My log\0!',
                    ])
                )
                f.flush()
                cmd = ['cat', f.name]
                if crash:
                    cmd.append(f.name + '_NON_EXISTING')

                yield original_popen(cmd, **kwargs)

    return PopenStub()


def nCr(n, r):
    f = math.factorial
    return f(n) / f(r) / f(n - r)


def get_random_path(d, upper):
    r = get_all_files_of_dir(d, upper)
    random.shuffle(r)
    return r[0][len(d):]


def get_all_files_of_dir(d, upper):
    res = []
    for entry in os.listdir(os.path.join(upper, d)):
        if os.path.isdir(os.path.join(upper, d, entry)):
            res.extend(get_all_files_of_dir(os.path.join(d, entry), upper))
        else:
            res.append(os.path.join(d, entry))

    return res


@pytest.mark.parametrize(
    'lang', [
        'Python 3',
        http_err(error=400)('CODEGRA.LANG'),
        http_err(error=400)(None),
    ]
)
@pytest.mark.parametrize('simil', [
    None,
    http_err(error=400)('40'),
    40,
])
@pytest.mark.parametrize(
    'unknown_key', [
        None,
        http_err(error=400)('VALUE'),
    ]
)
@pytest.mark.parametrize(
    'suffixes', [
        None,
        http_err(error=400)(2),
        '*.py,*.PY',
    ]
)
@pytest.mark.parametrize(
    'old_assignments', [
        [],
        http_err(error=400)(['']),
        http_err(error=404)([-1]),
    ]
)
@pytest.mark.parametrize(
    'provider', [
        'JPlag',
        http_err(error=400)(None),
        http_err(error=404)('unknown'),
    ]
)
@pytest.mark.parametrize('bb_tar_gz', ['correct.tar.gz'])
def test_jplag(
    bb_tar_gz, logged_in, request, assignment, test_client, teacher_user,
    provider, old_assignments, lang, simil, suffixes, error_template,
    monkeypatch, monkeypatch_celery, session, unknown_key
):
    student_user = session.query(psef.models.User).filter_by(name='Student2'
                                                             ).one()
    bb_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{bb_tar_gz}'
    )
    marker = request.node.get_closest_marker('http_err')
    code = marker.kwargs['error'] if marker else 200

    call_arguments = None
    called_num = 0
    written_rows = None

    def callback(call, **kwargs):
        nonlocal call_arguments, called_num, written_rows
        assert not kwargs['shell']
        assert '-bc' not in call, (
            "Base code should not "
            "be given when not supplied"
        )
        assert '-a' in call, "Old submission should always be given"

        called_num += 1
        call_arguments = call

        f_p = os.path.join(call[call.index('-r') + 1], 'computer_matches.csv')
        data_dir = call[3]
        dirs = os.listdir(data_dir)
        random.shuffle(dirs)
        dir1 = dirs[0]
        dir2 = dirs[1]
        dir3 = dirs[2]

        with open(f_p, 'w') as f:
            writer = csv.writer(f, delimiter=';')
            written_rows = [[
                dir1,
                dir2,
                100,
                25,
                get_random_path(dir1, data_dir),
                0,
                10,
                get_random_path(dir2, data_dir),
                12,
                14,
                get_random_path(dir1, data_dir),
                2,
                10,
                get_random_path(dir2, data_dir),
                14,
                19,
            ],
                            [
                                dir2,
                                dir3,
                                75,
                                20,
                                get_random_path(dir2, data_dir),
                                5,
                                10,
                                get_random_path(dir3, data_dir),
                                0,
                                4,
                                get_random_path(dir2, data_dir),
                                5,
                                8,
                                get_random_path(dir3, data_dir),
                                24,
                                29,
                            ]]
            for row in written_rows:
                writer.writerow(row)

    monkeypatch.setattr(subprocess, 'Popen', make_popen_stub(callback))

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )

    data = {
        'provider': provider,
        'old_assignments': old_assignments,
        'lang': lang,
        'simil': simil,
        'suffixes': suffixes,
        'unknown_key': unknown_key,
        'has_old_submissions': False,
        'has_base_code': False,
    }
    data = {k: v for k, v in data.items() if v is not None}

    with logged_in(student_user):
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            403,
            data=data,
            result=error_template,
        )

    with logged_in(teacher_user):
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            code,
            query={'no_course_in_assignment': True},
            data=data,
            result=None if code >= 400 else {
                'id': int, 'state': str, 'provider_name': str, 'config': list,
                'created_at': str, 'assignment': dict, 'submissions_done': 0,
                'submissions_total': int, 'log': None, 'assignments': {
                    str(assignment.id): dict
                }, 'courses': {str(assignment.course_id): dict}
            }
        )
        if code >= 400:
            return

        assert plag['config'] == [list(v) for v in sorted(data.items())]

        # Cannot run twice with same config
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            400,
            data=data,
            result=error_template
        )
    with logged_in(teacher_user):
        plag = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            200,
            result={
                'id': int,
                'state': 'done',
                'provider_name': str,
                'config': list,
                'created_at': str,
                'assignment': dict,
                'submissions_total': 3,
                # This should be one as we output this in our Popen stub
                'submissions_done': 1,
                'log': str,
                'assignments': {str(assignment.id): dict},
                'courses': {str(assignment.course_id): dict},
            }
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/plagiarism/',
            200,
            result=[plag]
        )

        assert called_num == 1, "We only ran once"
        assert call_arguments[call_arguments.index('-l') +
                              1] == 'python3', "Correct language is python3"
        if simil is None:
            assert call_arguments[call_arguments.index('-m') +
                                  1] == '50%', "Given value differs"
        else:
            assert call_arguments[call_arguments.index('-m') +
                                  1] == f'{simil}%', "Given value differs"
        if suffixes is None:
            assert '-p' not in call_arguments, "Suffixes was not given"
        else:
            assert call_arguments[call_arguments.index('-p') +
                                  1] == str(suffixes), "Differs!"
        assert test_client.req(
            'get', f'/api/v1/plagiarism/{plag["id"]}?extended', 200
        )['log'] == 'My log!', "Wrong log was saved"
        cases = test_client.req(
            'get', f'/api/v1/plagiarism/{plag["id"]}/cases/', 200
        )
        assert len(cases) == len(written_rows), "Wrong amount of cases saved"
        for case in cases:
            assert 'id' in case, 'This needs to be present'
            assert 'assignments' in case, 'This needs to be present'
            assert 'submissions' in case, "This needs to be present"
            for i in range(len(written_rows)):
                if max(written_rows[i][2:4]) == case['match_max']:
                    row = written_rows.pop(i)
                    break
            else:
                assert False, "Row not found!"
            assert sum(row[2:4]) / 2 == case['match_avg'], "Wrong average"

            found_names = sorted([u['name'] for u in case['users']])
            row_names = sorted([col.split(' || ')[0] for col in row[:2]])
            assert found_names == row_names

            case = test_client.req(
                'get', f'/api/v1/plagiarism/{plag["id"]}/cases/{case["id"]}',
                200
            )
            assert len(case['matches']
                       ) == len(row[4:]) / 6, "Amount matches match"

        # Limit without offset should mean a offset of 0
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/?limit=1',
            200,
            result=cases[:1]
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/?limit=3&offset=2',
            200,
            result=cases[2:5]
        )

        # Offset higher than amount of results should return an empty list
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/?limit=3&offset=2000',
            200,
            result=[]
        )
        # Limit higher than amount results should return all results
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/?limit=3000',
            200,
            result=cases
        )

    # Make doing these calls as student fails with permission errors
    with logged_in(student_user):
        test_client.req(
            'delete',
            f'/api/v1/plagiarism/{plag["id"]}',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/{case["id"]}',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/plagiarism/',
            403,
            result=error_template
        )

    with logged_in(teacher_user):
        test_client.req(
            'delete', f'/api/v1/plagiarism/{plag["id"]}', 204, result=None
        )
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            404,
            result=error_template
        )
        # Needs to be gone here too
        test_client.req(
            'get',
            f'/api/v1/assignments/{assignment.id}/plagiarism/',
            200,
            result=[]
        )


@pytest.mark.parametrize('bb_tar_gz', ['correct.tar.gz'])
def test_jplag_old_assignments(
    bb_tar_gz, logged_in, assignment, test_client, teacher_user,
    error_template, monkeypatch, session
):
    other_assignment = psef.models.Assignment(
        name='TEST COURSE', course=assignment.course, is_lti=False
    )
    session.add(other_assignment)
    other_course = psef.models.Course.create_and_add(name='Other course')
    other_course_assignment = psef.models.Assignment(
        name='OTHER COURSE ASSIGNMENT', course=other_course, is_lti=False
    )
    session.add(other_course_assignment)
    session.commit()

    bb_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{bb_tar_gz}'
    )

    def callback(call, **kwargs):
        f_p = os.path.join(call[call.index('-r') + 1], 'computer_matches.csv')
        archive_dir = call[call.index('-a') + 1]
        data_dir = call[3]
        data_dirs = os.listdir(data_dir)
        archive_dirs = os.listdir(archive_dir)
        dirs = data_dirs + archive_dirs
        with open(f_p, 'w') as f:
            writer = csv.writer(f, delimiter=';')
            for dir1, dir2 in itertools.product(dirs, dirs):
                writer.writerow([
                    dir1,
                    dir2,
                    75,
                    20,
                    get_random_path(
                        dir1, data_dir if dir1 in data_dirs else archive_dir
                    ),
                    5,
                    10,
                    get_random_path(
                        dir2, data_dir if dir2 in data_dirs else archive_dir
                    ),
                    0,
                    4,
                ])

    monkeypatch.setattr(subprocess, 'Popen', make_popen_stub(callback))
    print('next')

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )
        test_client.req(
            'post',
            f'/api/v1/assignments/{other_assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )

    with logged_in(teacher_user):
        data = {
            'provider': 'JPlag',
            'old_assignments': [other_assignment.id],
            'lang': 'Python 3',
            'has_old_submissions': False,
            'has_base_code': False,
        }

        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            200,
            data=data,
            result={
                'id': int,
                'state': str,
                'provider_name': str,
                'config': list,
                'created_at': str,
                'assignment': dict,
                'submissions_total': int,
                'submissions_done': 0,
                'log': None,
                'assignments': {str(assignment.id): dict},
                'courses': {str(assignment.course_id): dict},
            }
        )
        print('next2')
        plag = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}?extended',
            200,
            result={
                'id': int,
                'state': 'done',
                'provider_name': str,
                'config': list,
                'log': str,
                'cases': list,
                'created_at': str,
                'assignment': dict,
                'submissions_total': int,
                'submissions_done': 1,
                'assignments': {
                    str(assignment.id): dict,
                    str(other_assignment.id): dict,
                },
                'courses': {str(assignment.course_id): dict},
            }
        )
        amount_subs = assignment.get_from_latest_submissions(
            func.count(psef.models.Work.id)
        ).scalar()
        amount_other_subs = other_assignment.get_from_latest_submissions(
            func.count(psef.models.Work.id)
        ).scalar()
        assert (
            len(plag['cases']) == (
                nCr(amount_subs + amount_other_subs, 2) -
                nCr(amount_other_subs, 2)
            )
        ), "The amount of cases should be the maximum"
        for jcase in plag['cases']:
            case = session.query(psef.models.PlagiarismCase).get(jcase['id'])
            assert jcase['submissions'][0]['id'] != jcase['submissions'
                                                          ][1]['id']
            if case.work1.assignment_id == case.work2.assignment_id:
                assert case.work1.assignment_id == assignment.id

        data['old_assignments'].append(other_course_assignment.id)
        # We don't have permission to do this
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            403,
            data=data,
            result=error_template,
        )

        other_course_teacher_role = psef.models.CourseRole.query.filter_by(
            course_id=other_course.id, name='Teacher'
        ).one()
        teacher_user.courses[other_course.id] = other_course_teacher_role
        session.commit()

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{other_course_assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            200,
            data=data,
        )

    with logged_in(teacher_user):
        run = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            200,
        )
        cases = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            200,
            query={'no_assignment_in_case': True},
        )
        for idx, case in enumerate(cases):
            for idx2, assig_id in enumerate(case['assignment_ids']):
                if run['assignments'][str(assig_id)
                                      ]['course_id'] == other_course.id:
                    break
            else:
                continue
            break
        else:
            assert False
    old_case = cases[idx]

    other_course_teacher_role = psef.models.CourseRole.query.filter_by(
        course_id=other_course.id, name='Teacher'
    ).one()
    other_course_teacher_role.set_permission(
        psef.permissions.CoursePermission.can_view_plagiarism, False
    )
    session.commit()

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/{old_case["id"]}',
            200,
        )
        case = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            200,
            query={'no_assignment_in_case': True},
        )[idx]
        assert case == old_case

    other_course_teacher_role = psef.models.CourseRole.query.filter_by(
        course_id=other_course.id, name='Teacher'
    ).one()
    other_course_teacher_role.set_permission(
        psef.permissions.CoursePermission.can_see_assignments, False
    )
    session.commit()

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/{old_case["id"]}',
            403,
        )
        run = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}',
            200,
        )
        case = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            200,
        )[idx]
        assert case['id'] == old_case['id']
        assert case['submissions'] == old_case['submissions']

        assig = run['assignments'][str(case['assignment_ids'][idx2])]
        course = run['courses'][str(assig['course_id'])]
        assert sorted(list(assig.keys())) == ['course_id', 'id', 'name']
        assert sorted(list(course.keys())) == ['id', 'name', 'virtual']

    other_course_teacher_role = psef.models.CourseRole.query.filter_by(
        course_id=other_course.id, name='Teacher'
    ).one()
    other_course_teacher_role.set_permission(
        psef.permissions.CoursePermission.can_see_others_work, False
    )
    session.commit()

    with logged_in(teacher_user):
        test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/{old_case["id"]}',
            403,
        )
        case = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}/cases/',
            200,
            query={'no_assignment_in_case': True},
        )[idx]
        assert case['id'] == old_case['id']
        assert case['submissions'] is None

        assig = run['assignments'][str(case['assignment_ids'][idx2])]
        course = run['courses'][str(assig['course_id'])]
        assert sorted(list(assig.keys())) == ['course_id', 'id', 'name']
        assert sorted(list(course.keys())) == ['id', 'name', 'virtual']


@pytest.mark.parametrize('bb_tar_gz', ['correct.tar.gz'])
@pytest.mark.parametrize(
    'old_subs_tar_gz,amount_old_subs', [('correct.tar.gz', 2),
                                        ('difficult.tar.gz', 4)]
)
def test_jplag_old_submissions(
    bb_tar_gz, logged_in, assignment, test_client, teacher_user,
    error_template, monkeypatch, monkeypatch_celery, session, old_subs_tar_gz,
    request, student_user, amount_old_subs
):
    student_user = student_user._get_current_object()
    bb_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{bb_tar_gz}'
    )
    old_subs_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_old_sumbissions/{old_subs_tar_gz}'
    )

    code = 200

    def callback(call, **kwargs):
        f_p = os.path.join(call[call.index('-r') + 1], 'computer_matches.csv')
        archive_dir = call[call.index('-a') + 1]
        data_dir = call[3]
        data_dirs = os.listdir(data_dir)
        archive_dirs = os.listdir(archive_dir)
        dirs = data_dirs + archive_dirs
        with open(f_p, 'w') as f:
            writer = csv.writer(f, delimiter=';')
            for dir1, dir2 in itertools.product(dirs, dirs):
                writer.writerow([
                    dir1,
                    dir2,
                    75,
                    20,
                    get_random_path(
                        dir1, data_dir if dir1 in data_dirs else archive_dir
                    ),
                    5,
                    10,
                    get_random_path(
                        dir2, data_dir if dir2 in data_dirs else archive_dir
                    ),
                    0,
                    4,
                ])

    monkeypatch.setattr(subprocess, 'Popen', make_popen_stub(callback))

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )

    with logged_in(teacher_user):
        courses = test_client.req('get', '/api/v1/courses/', 200)
        data = {
            'provider': 'JPlag',
            'old_assignments': [],
            'lang': 'Python 3',
            'has_old_submissions': True,
            'has_base_code': False,
        }

        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            400,
            data=data,
            result=error_template
        )
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            code,
            real_data={
                'json': (io.BytesIO(json.dumps(data).encode()), 'j'),
                'old_submissions': (old_subs_tar_gz, 'old_subs.tar.gz'),
            },
        )
        if code >= 400:
            return

        plag = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}?extended',
            200,
            result={
                'id': int,
                'state': 'done',
                'provider_name': str,
                'config': list,
                'log': str,
                'cases': list,
                'created_at': str,
                'assignment': dict,
                'submissions_done': 1,
                'submissions_total': int,
                'assignments': {
                    str(assignment.id): dict,
                    # Allow the created extra assignment.
                    '__allow_extra__': True,
                },
                'courses': {
                    str(assignment.course_id): dict,
                    # Allow the created virtual course.
                    '__allow_extra__': True,
                },
            }
        )
        for jcase in plag['cases']:
            case = session.query(psef.models.PlagiarismCase).get(jcase['id'])
            assert jcase['submissions'][0]['id'] != jcase['submissions'
                                                          ][1]['id']
            if case.work1.assignment_id == case.work2.assignment_id:
                assert case.work1.assignment_id == assignment.id

        virtual_courses = psef.models.Course.query.filter_by(virtual=True
                                                             ).all()
        assert len(virtual_courses) == 1
        assert len(virtual_courses[0].assignments) == 1
        assert len(
            virtual_courses[0].assignments[0].submissions
        ) == amount_old_subs
        assert not any(
            f.name.endswith('.tar.gz')
            for sub in virtual_courses[0].assignments[0].submissions
            for f in models.File.query.filter_by(work=sub)
        )
        amount_subs = assignment.get_from_latest_submissions(
            func.count(psef.models.Work.id)
        ).scalar()
        assert (
            len(plag['cases']) ==
            (nCr(amount_subs + amount_old_subs, 2) - nCr(amount_old_subs, 2))
        ), "The amount of cases should be the maximum"

        # Make sure we can't find this virtual user
        test_client.req(
            'get',
            f'/api/v1/users/?q=pim de',
            200,
            result=[],
        )
        assert len(
            psef.models.User.query.filter(
                psef.models.User.name.ilike('%pim de%')
            ).all()
        ) == 1

        # Make sure we were not added to any course
        assert courses == test_client.req('get', '/api/v1/courses/', 200)

        for jcase in plag['cases']:
            case = session.query(psef.models.PlagiarismCase).get(jcase['id'])
            if case.work1.assignment_id != case.work2.assignment_id:
                break
        else:
            assert False

        assert test_client.get(
            f'/api/v1/code/{case.matches[0].file1_id}'
        ).status_code == 200
        assert test_client.get(
            f'/api/v1/code/{case.matches[0].file2_id}'
        ).status_code == 200
    with logged_in(student_user):
        test_client.req(
            'get',
            f'/api/v1/code/{case.matches[0].file2_id}',
            403,
            result=error_template
        )
        test_client.req(
            'get',
            f'/api/v1/code/{case.matches[0].file2_id}',
            403,
            result=error_template
        )


@pytest.mark.parametrize('bb_tar_gz', ['correct.tar.gz'])
@pytest.mark.parametrize('base_code_tar_gz', ['correct.tar.gz'])
def test_jplag_base_code(
    bb_tar_gz,
    logged_in,
    assignment,
    test_client,
    teacher_user,
    error_template,
    monkeypatch,
    monkeypatch_celery,
    session,
    base_code_tar_gz,
):
    bb_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{bb_tar_gz}'
    )
    base_code_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_old_sumbissions/{base_code_tar_gz}'
    )

    def callback(call, **kwargs):
        f_p = os.path.join(call[call.index('-r') + 1], 'computer_matches.csv')
        assert call[call.index('-bc') + 1].startswith('/tmp/')
        assert os.listdir(call[call.index('-bc') + 1]) == ['dir']
        assert len(
            os.listdir('{}/dir'.format(call[call.index('-bc') + 1]))
        ) > 1
        open(f_p, 'w').close()

    monkeypatch.setattr(subprocess, 'Popen', make_popen_stub(callback))

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )

    with logged_in(teacher_user):
        data = {
            'provider': 'JPlag',
            'old_assignments': [],
            'lang': 'Python 3',
            'has_old_submissions': False,
            'has_base_code': True,
        }

        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            400,
            data=data,
            result=error_template
        )
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            400,
            real_data={
                'json': (io.BytesIO(json.dumps(data).encode()), 'j'),
                'base_code': (base_code_tar_gz, 'base_code.no_arch'),
            },
        )
        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            200,
            real_data={
                'json': (io.BytesIO(json.dumps(data).encode()), 'j'),
                'base_code': (base_code_tar_gz, 'base_code.tar.gz'),
            },
        )

        plag = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}?extended',
            200,
            result={
                'id': int,
                'state': 'done',
                'provider_name': str,
                'config': list,
                'log': 'My log!',
                'cases': list,
                'created_at': str,
                'assignment': dict,
                'submissions_done': 1,
                'submissions_total': int,
                'assignments': {str(assignment.id): dict},
                'courses': {str(assignment.course_id): dict},
            }
        )


@pytest.mark.parametrize('subprocess_exception', [True, False])
@pytest.mark.parametrize('bb_tar_gz', ['correct.tar.gz'])
def test_chrased_jplag(
    bb_tar_gz, logged_in, assignment, test_client, teacher_user,
    error_template, monkeypatch, monkeypatch_celery, session,
    subprocess_exception
):
    bb_tar_gz = (
        f'{os.path.dirname(__file__)}/'
        f'../test_data/test_blackboard/{bb_tar_gz}'
    )

    monkeypatch.setattr(
        subprocess, 'Popen',
        make_popen_stub(lambda *_, **__: None, crash=True)
    )

    with logged_in(teacher_user):
        test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/submissions/',
            204,
            real_data={'file': (bb_tar_gz, 'bb.tar.gz')},
        )

    with logged_in(teacher_user):
        data = {
            'provider': 'JPlag',
            'old_assignments': [],
            'lang': 'Python 3',
            'has_old_submissions': False,
            'has_base_code': False,
        }

        plag = test_client.req(
            'post',
            f'/api/v1/assignments/{assignment.id}/plagiarism',
            200,
            data=data,
            result={
                'id': int,
                'state': str,
                'provider_name': str,
                'config': list,
                'created_at': str,
                'assignment': dict,
                'submissions_done': 0,
                'submissions_total': int,
                'log': None,
                'assignments': {str(assignment.id): dict},
                'courses': {str(assignment.course_id): dict},
            }
        )
        plag = test_client.req(
            'get',
            f'/api/v1/plagiarism/{plag["id"]}?extended',
            200,
            data=data,
            result={
                'id': int,
                'state': 'crashed',
                'provider_name': str,
                'config': list,
                'log': str,
                'cases': [],
                'created_at': str,
                'assignment': dict,
                'submissions_done': 1,
                'submissions_total': int,
                'assignments': {str(assignment.id): dict},
                'courses': {str(assignment.course_id): dict},
            }
        )
        if subprocess_exception:
            assert plag['log'].startswith('My log!')


def test_get_plagiarism_providers(test_client):
    test_client.req(
        'get',
        '/api/v1/plagiarism/',
        200,
        result=[
            {
                'name': 'JPlag',
                'base_code': True,
                'progress': True,
                'options': [{
                    'name': 'lang',
                    'title': 'Language',
                    'description': str,
                    'type': 'singleselect',
                    'mandatory': bool,
                    'possible_options': list,
                    'placeholder': None,
                },
                            {
                                'name': 'suffixes',
                                'title': 'Suffixes to include',
                                'description': str,
                                'type': 'strvalue',
                                'mandatory': bool,
                                'placeholder': '.xxx, .yyy',
                            },
                            {
                                'name': 'simil',
                                'title': 'Minimal similarity',
                                'description': str,
                                'type': 'numbervalue',
                                'mandatory': bool,
                                'placeholder': 'default: 50',
                            }],
            },
        ],
    )
