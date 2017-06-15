#!/usr/bin/env python3
from flask import jsonify, request
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy_utils.functions import dependent_objects

import psef.auth as auth
import psef.files
import psef.models as models
from psef import db, app
from psef.errors import APICodes, APIException


@app.route("/api/v1/code/<int:file_id>")
def get_code(file_id):
    # Code not used yet:

    code = db.session.query(models.File).filter(  # NOQA: F841
        models.File.id == file_id).first()
    line_feedback = {}
    for comment in db.session.query(models.Comment).filter_by(
            file_id=file_id).all():
        line_feedback[str(comment.line)] = comment.comment

    # TODO: Return JSON following API
    return jsonify(
        lang="python",  # TODO Detect the language automatically
        code=psef.files.get_file_contents(code),
        feedback=line_feedback)


@app.route("/api/v1/code/<int:id>/comments/<int:line>", methods=['PUT'])
def put_comment(id, line):
    content = request.get_json()

    comment = db.session.query(models.Comment).filter(
        models.Comment.file_id == id, models.Comment.line == line).first()
    if not comment:
        # TODO: User id 0 for now, change later on
        db.session.add(
            models.Comment(
                file_id=id, user_id=0, line=line, comment=content['comment']))
    else:
        comment.comment = content['comment']

    db.session.commit()

    return ('', 204)


@app.route("/api/v1/code/<int:id>/comments/<int:line>", methods=['DELETE'])
def remove_comment(id, line):
    comment = db.session.query(models.Comment).filter(
        models.Comment.file_id == id, models.Comment.line == line).first()

    if comment:
        db.session.delete(comment)
        db.session.commit()
    else:
        raise APIException('Feedback comment not found',
                           'The comment on line {} was not found'.format(line),
                           APICodes.OBJECT_ID_NOT_FOUND, 404)
    return ('', 204)


@app.route("/api/v1/submissions/<int:submission_id>/files/",
    methods=['GET'])
def get_dir_contents(submission_id):
    work = models.Work.query.get(submission_id)
    if work is None:
        raise APIException(
            'Submission not found',
            'The submission with code {} was not found'.format(submission_id),
            APICodes.OBJECT_ID_NOT_FOUND, 404)

    if (work.user.id != current_user.id):
        auth.ensure_permission('can_view_files', work.assignment.course.id)
    else:
        auth.ensure_permission('can_view_own_files', work.assignment.course.id)

    file_id = request.args.get('file_id')
    if file_id:
        file = models.File.query.get(file_id)
        if file is None:
            raise APIException(
                'File not found',
                'The file with code {} was not found'.format(file_id),
                APICodes.OBJECT_ID_NOT_FOUND, 404)
        if (file.work.id != submission_id):
            raise APIException(
                'Incorrect URL',
                'The identifiers in the URL do no match those related to the '
                'file with code {}'.format(file.id), APICodes.INVALID_URL, 400)
    else:
        file = models.File.query.filter(models.File.work_id == submission_id,
                                        models.File.parent_id == None).one()

    if not file.is_directory:
        raise APIException(
            'File is not a directory',
            'The file with code {} is not a directory'.format(file.id),
            APICodes.OBJECT_WRONG_TYPE, 400)

    dir_contents = jsonify(file.list_contents())

    return (dir_contents, 200)


@app.route("/api/v1/assignments/", methods=['GET'])
@login_required
def get_student_assignments():
    perm = models.Permission.query.filter_by(
        name='can_see_assignments').first()
    courses = []
    for course_role in current_user.courses.values():
        if course_role.has_permission(perm):
            courses.append(course_role.course_id)
    if courses:
        return jsonify([{
            'id': assignment.id,
            'name': assignment.name,
            'course_name': assignment.course.name,
            'course_id': assignment.course_id,
        }
            for assignment in models.Assignment.query.filter(
            models.Assignment.course_id.in_(courses)).all()])
    else:
        return jsonify([])


@app.route("/api/v1/assignments/<int:assignment_id>", methods=['GET'])
def get_assignment(assignment_id):
    assignment = models.Assignment.query.get(assignment_id)
    auth.ensure_permission('can_see_assignments', assignment.course_id)
    return jsonify({
        'name': assignment.name,
        'description': assignment.description,
        'course_name': assignment.course.name,
        'course_id': assignment.course_id,
    })


@app.route('/api/v1/assignments/<int:assignment_id>/submissions/')
def get_all_works_for_assignment(assignment_id):
    assignment = models.Assignment.query.get(assignment_id)
    if current_user.has_permission(
            'can_see_others_work', course_id=assignment.course_id):
        obj = models.Work.query.filter_by(assignment_id=assignment_id)
    else:
        auth.ensure_permission(
            'can_see_own_work', course_id=assignment.course_id)
        obj = models.Work.query.filter_by(
            assignment_id=assignment_id, user_id=current_user.id)
    res = obj.order_by(models.Work.created_at.desc()).all()

    return jsonify([{
        'id': work.id,
        'user_name': work.user.name if work.user else "Unknown",
        'user_id': work.user_id,
        'state': work.state,
        'edit': work.edit,
        'grade': work.grade,
        'comment': work.comment,
        'created_at': work.created_at.strftime("%d-%m-%Y %H:%M"),
    } for work in res])


@app.route("/api/v1/submissions/<int:submission_id>", methods=['GET'])
def get_submission(submission_id):
    work = db.session.query(models.Work).get(submission_id)
    auth.ensure_permission('can_grade_work', work.assignment.course.id)

    if work and work.is_graded:
        return jsonify({
            'id': work.id,
            'user_id': work.user_id,
            'state': work.state,
            'edit': work.edit,
            'grade': work.grade,
            'comment': work.comment,
            'created_at': work.created_at,
            })
    else:
        raise APIException(
            'Work submission not found',
            'The submission with code {} was not found'.format(submission_id),
            APICodes.OBJECT_ID_NOT_FOUND, 404)


@app.route(
    "/api/v1/submissions/<int:submission_id>", methods=['PATCH'])
def patch_submission(submission_id):
    work = db.session.query(models.Work).get(submission_id)
    content = request.get_json()

    if not work:
        raise APIException(
            'Submission not found',
            'The submission with code {} was not found'.format(submission_id),
            APICodes.OBJECT_ID_NOT_FOUND, 404)

    auth.ensure_permission('can_grade_work', work.assignment.course.id)
    if 'grade' not in content or 'feedback' not in content:
        raise APIException('Grade or feedback not provided',
                           'Grade and or feedback fields missing in sent JSON',
                           APICodes.MISSING_REQUIRED_PARAM, 400)

    if not isinstance(content['grade'], float):
        try:
            content['grade'] = float(content['grade'])
        except ValueError:
            raise APIException(
                'Grade submitted not a number',
                'Grade for work with id {} not a number'.format(submission_id),
                APICodes.INVALID_PARAM, 400)

    work.grade = content['grade']
    work.comment = content['feedback']
    work.state = 'done'
    db.session.commit()
    return ('', 204)


@app.route("/api/v1/login", methods=["POST"])
def login():
    data = request.get_json()

    if 'email' not in data or 'password' not in data:
        raise APIException('Email and passwords are required fields',
                           'Email or password was missing from the request',
                           APICodes.MISSING_REQUIRED_PARAM, 400)

    user = db.session.query(models.User).filter_by(email=data['email']).first()

    # TODO: Use bcrypt password validation (as soon as we got that)
    # TODO: Return error whether user or password is wrong
    if user is None or user.password != data['password']:
        raise APIException('The supplied email or password is wrong.', (
            'The user with email {} does not exist ' +
            'or has a different password').format(data['email']),
            APICodes.LOGIN_FAILURE, 400)

    if not login_user(user, remember=True):
        raise APIException('User is not active', (
            'The user with id "{}" is not active any more').format(user.id),
            APICodes.INACTIVE_USER, 403)

    return me()


@app.route("/api/v1/login", methods=["GET"])
@login_required
def me():
    return jsonify({
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email
    }), 200


@app.route("/api/v1/logout", methods=["POST"])
def logout():
    logout_user()
    return '', 204


@app.route("/api/v1/assignments/<int:assignment_id>/submission", methods=['POST'])
def upload_work(assignment_id):
    """
    Saves the work on the server if the request is valid.

    For a request to be valid there needs to be:
        - at least one file starting with key 'file' in the request files
        - all files must be named
    """

    files = []

    if (request.content_length and
            request.content_length > app.config['MAX_UPLOAD_SIZE']):
        raise APIException('Uploaded files are too big.', (
            'Request is bigger than maximum ' +
            'upload size of {}.').format(app.config['MAX_UPLOAD_SIZE']),
            APICodes.REQUEST_TOO_LARGE, 400)

    if len(request.files) == 0:
        raise APIException("No file in HTTP request.",
                           "There was no file in the HTTP request.",
                           APICodes.MISSING_REQUIRED_PARAM, 400)

    for key, file in request.files.items():
        if not key.startswith('file'):
            raise APIException('The parameter name should start with "file".',
                               'Expected ^file.*$ got {}.'.format(key),
                               APICodes.INVALID_PARAM, 400)

        if file.filename == '':
            raise APIException('The filename should not be empty.',
                               'Got an empty filename for key {}'.format(key),
                               APICodes.INVALID_PARAM, 400)

        files.append(file)

    assignment = models.Assignment.query.get(assignment_id)
    if assignment is None:
        raise APIException(
            'Assignment not found',
            'The assignment with code {} was not found'.format(assignment_id),
            APICodes.OBJECT_ID_NOT_FOUND, 404)

    auth.ensure_permission('can_submit_own_work', assignment.course.id)

    work = models.Work(assignment_id=assignment_id, user_id=current_user.id)
    db.session.add(work)

    tree = psef.files.process_files(files)
    work.add_file_tree(db.session, tree)

    db.session.commit()

    return ('', 204)


@app.route('/api/v1/permissions/', methods=['GET'])
@login_required
def get_permissions():
    if 'course_id' in request.args:
        try:
            course_id = int(request.args['course_id'])
        except ValueError:
            raise APIException(
                'The specified course id was invalid',
                'The course id should be a number but '
                '{} is not a number'.format(request.args['course_id']),
                APICodes.INVALID_PARAM, 400)
    else:
        course_id = None

    if 'permission' in request.args:
        perm = request.args['permission']
        try:
            return jsonify(current_user.has_permission(perm,
                                                       course_id))
        except KeyError:
            raise APIException('The specified permission does not exist',
                               'The permission '
                               '"{}" is not real permission'.format(perm),
                               APICodes.OBJECT_NOT_FOUND, 404)
    else:
        return jsonify(current_user.get_all_permissions(course_id=course_id))

@app.route('/api/v1/update_user', methods=['PUT'])
def get_user_update():
    data = request.get_json()

    if 'email' not in data or 'password' not in data or 'username' not in data:
        raise APIException('Email, username and password are required fields',
                           'Email, username or password was missing from the request',
                           APICodes.MISSING_REQUIRED_PARAM, 400)

    user = models.User.query.get(current_user.id)
    if user is None:
        raise APIException(
            'User_id not found',
            'The user with id {} was not found'.format(current_user.id),
            APICodes.OBJECT_ID_NOT_FOUND, 404)

    if user.password != data['o_password']:
        raise APIException('Incorrect password.',
            'The supplied old password was incorrect',
            APICodes.INVALID_CREDENTIALS, 422)

    auth.ensure_permission('can_edit_own_name')
    auth.ensure_permission('can_edit_own_email')
    auth.ensure_permission('can_edit_own_password')

    errors = {}
    errors['password'] = validate_password(data['n_password'])
    errors['username'] = validate_username(data['username'])

    if errors['password'] != '' or errors['username'] != '':
        raise APIException('Invalid password or username.',
            'The supplied username or password did not meet the requirements',
            APICodes.INVALID_PARAM, 422, errors)

    user.username = data['username']
    user.email = data['email']
    user.password = data['password']

    db.session.commit()
    return ('', 204)

def validate_username(username):
    min_len = 1
    if len(username) < min_len:
        return('use at least ' + str(min_len) + ' chars')
    else:
        return('')

def validate_password(password):
    min_len = 1
    if len(password) < min_len:
        return('use at least ' + str(min_len) + ' chars')
    else:
        return('')
