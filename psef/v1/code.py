"""
This module defines all API routes with the main directory "code". Thus the
APIs are used to manipulate student submitted code and the related feedback.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t

import werkzeug
import sqlalchemy.sql as sql
from flask import Response, request
from sqlalchemy.orm import make_transient

import cg_object_storage

from . import api
from .. import app, auth, files, models, helpers, current_user
from ..errors import APICodes, APIException
from ..models import FileOwner, db
from ..helpers import (
    JSONResponse, EmptyResponse, jsonify, ensure_keys_in_dict,
    make_empty_response
)
from ..permissions import CoursePermission as CPerm

_HumanFeedback = t.Mapping[str, object]
_LinterFeedback = t.MutableSequence[t.Tuple[str, models.LinterComment]]  # pylint: disable=invalid-name
_FeedbackMapping = t.Dict[str, t.Union[_HumanFeedback, _LinterFeedback]]  # pylint: disable=invalid-name


@api.route("/code/<int:code_id>/comments/<int:line>", methods=['PUT'])
@helpers.mark_as_deprecated_route(
    'Please update comments by id and create them by PUTting to'
    ' /api/v1/comments/'
)
def put_comment(code_id: int, line: int) -> EmptyResponse:
    """Create or change a single :class:`.models.Comment` of a code
    :class:`.models.File`.

    .. :quickref: Code; Add or change a comment.

    :param int code_id: The id of the code file
    :param int line: The line number of the comment
    :returns: An empty response with return code 204

    :<json str comment: The comment to add to the given file on the given line.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not can grade work in the
                                 attached course. (INCORRECT_PERMISSION)
    """
    file = helpers.filter_single_or_404(
        models.File,
        models.File.id == code_id,
        also_error=lambda f: f.deleted,
        with_for_update=True,
    )

    with helpers.get_from_request_transaction() as [get, _]:
        comment_text = get(
            'comment', str, transform=lambda x: x.replace('\0', '')
        )

    comment_base = models.CommentBase.create_if_not_exists(file, line)
    if comment_base.id is None:
        auth.FeedbackBasePermissions(  # type: ignore[unreachable]
            comment_base
        ).ensure_may_add()
        db.session.add(comment_base)
    reply = comment_base.first_reply

    if reply is not None:
        auth.FeedbackReplyPermissions(reply).ensure_may_edit()
        edit = reply.update(comment_text)
        if edit is not None:
            db.session.add(edit)
    else:
        reply = comment_base.add_reply(
            current_user,
            comment_text,
            models.CommentReplyType.plain_text,
            None,
        )
        checker = reply.perm_checker
        checker.ensure_may_add.or_(checker.ensure_may_add_as_peer).check()

    db.session.commit()

    return make_empty_response()


@api.route("/code/<int:code_id>/comments/<int:line>", methods=['DELETE'])
@helpers.mark_as_deprecated_route(
    'Please update comments by id and create them by PUTting to'
    ' /api/v1/comments/'
)
@auth.login_required
def remove_comment(code_id: int, line: int) -> EmptyResponse:
    """Removes the given :class:`.models.CommentBase` in the given
    :class:`.models.File`

    .. :quickref: Code; Remove a comment.

    :param int code_id: The id of the code file
    :param int line: The line number of the comment
    :returns: An empty response with return code 204

    :raises APIException: If there is no comment at the given line number.
                          (OBJECT_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not can grade work in the
                                 attached course. (INCORRECT_PERMISSION)
    """
    comment_base = helpers.filter_single_or_404(
        models.CommentBase,
        models.CommentBase.file_id == code_id,
        models.CommentBase.line == line,
        also_error=lambda c: c.first_reply is None or c.file.deleted,
    )

    reply = comment_base.first_reply
    assert reply is not None
    auth.FeedbackReplyPermissions(reply).ensure_may_delete()
    reply.delete()

    db.session.commit()

    return make_empty_response()


@api.route('/code/<uuid:file_id>', methods=['GET'])
@api.route("/code/<int:file_id>", methods=['GET'])
@auth.login_required
def get_code(file_id: t.Union[int, uuid.UUID]
             ) -> t.Union[werkzeug.wrappers.Response, JSONResponse[
                 t.Union[t.Mapping[str, str], models.File, _FeedbackMapping]]]:
    """Get data from a :class:`.models.File` or a
        :class:`.models.AutoTestOutputFile` with the given id.

    .. :quickref: Code; Get code or its metadata.

    The are several options to change the data that is returned. Based on the
    argument type in the request different functions are called.

    - If ``type == 'metadata'`` the JSON serialized :class:`.models.File` is
      returned.
    - If ``type == 'file-url'`` or ``type == 'pdf'`` (deprecated) an object
      with a single key, `name`, with as value the return values of
      :py:func:`.get_file_url`.
    - If ``type == 'feedback'`` or ``type == 'linter-feedback'`` see
      :py:func:`.code.get_feedback`. This will always return an empty mapping
      for :class:`.models.AutoTestOutputFiles` for now. This type is
      deprecated, please get all feedback of submission in one try using
      ``/api/v1/submissions/<submission_id>/feedbacks/``.
    - Otherwise the content of the file is returned as plain text.

    :param file_id: The id of the file if you want get the data for a
        `.models.File` it should be an integer, otherwise a uuid should be
        given.
    :returns: A response containing a plain text file unless specified
        otherwise.

    .. todo:

        Change the route to not take a type parameter anymore. All these things
        should simply be different endpoints.

    :raises APIException: If there is not file with the given id.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the file does not belong to user and the
                                 user can not view files in the attached
                                 course. (INCORRECT_PERMISSION)
    """
    f: t.Union[models.NestedFileMixin[int], models.NestedFileMixin[uuid.UUID]]

    if isinstance(file_id, int):
        f = helpers.filter_single_or_404(
            models.File,
            models.File.id == file_id,
            also_error=lambda f: f.deleted
        )

        auth.CodePermisisons(f).ensure_may_see()
    else:
        f = helpers.get_or_404(models.AutoTestOutputFile, file_id)
        auth.AutoTestResultPermissions(f.result).ensure_may_see_output_files()

        assig = f.suite.auto_test_set.auto_test.assignment
        if not assig.is_done:
            auth.ensure_permission(
                CPerm.can_view_autotest_output_files_before_done,
                assig.course_id
            )

    get_type = request.args.get('type', None)
    if get_type == 'metadata':
        return jsonify(f)
    elif get_type == 'feedback':
        feedback = {}
        if isinstance(f, models.File):
            feedback = get_feedback(f, linter=False)
        return jsonify(feedback)
    elif get_type in ('pdf', 'file-url'):
        return jsonify({'name': get_file_url(f)})
    elif get_type == 'linter-feedback':
        feedback = {}
        if isinstance(f, models.File):
            feedback = get_feedback(f, linter=True)
        return jsonify(feedback)
    else:
        res = Response(f.open())
        res.headers['Content-Type'] = 'application/octet-stream'
        return res


def get_file_url(file: models.FileMixin[object]) -> str:
    """Copies the given file to the mirror uploads folder and returns its name.

    To get this file, see the :func:`psef.v1.files.get_file` function.

    :param file: The file object
    :returns: The name of the newly created file (the copy).
    """
    with app.mirror_file_storage.putter() as putter, file.open() as src:
        result = putter.from_stream(src, max_size=app.max_single_file_size)

    return result.try_extract(
        lambda: helpers.make_file_too_big_exception(
            app.max_single_file_size, single_file=True
        )
    ).name


def get_feedback(file: models.File, linter: bool = False) -> _FeedbackMapping:
    """Returns the :class:`.models.CommentBase` objects attached to the given
    :class:`.models.File` if the user can see them, else returns an empty dict.

    .. note::

        This function will check if the current user has permission to see
        comments for this file.

    :param models.File file: The file object
    :param bool linter: If true returns linter comments instead
    :returns: Feedback for the given file. If ``linter`` is true it will be
        given in the form ``{line: [(linter_name, comment)]`` otherwise it is
        in the form ``{line: comment}``.
    """
    res: _FeedbackMapping = {}
    try:
        if linter:
            auth.WorkPermissions(file.work).ensure_may_see_linter_feedback()

            for linter_comment in db.session.query(
                models.LinterComment,
            ).filter_by(file_id=file.id):
                line = str(linter_comment.line)
                if line not in res:
                    res[line] = []
                name = linter_comment.linter.tester.name
                res[line].append((name, linter_comment))  # type: ignore
        else:
            for human_comment in db.session.query(
                models.CommentBase,
            ).filter_by(file_id=file.id):
                first_reply = human_comment.first_reply
                if first_reply is not None and auth.FeedbackReplyPermissions(
                    first_reply
                ).ensure_may_see.as_bool():
                    line = str(human_comment.line)
                    res[line] = first_reply.get_outdated_json()
        return res

    except auth.PermissionException:
        return res


@api.route('/code/<int:file_id>', methods=['DELETE'])
def delete_code(file_id: int) -> EmptyResponse:
    """Delete the given file.

    .. :quickref: Code; Delete the given file.

    If the file owner of the given file is the same as that of the user doing
    the request (so the file will be completely deleted) the given file should
    not have any comments (Linter or normal) associated with it. If it still
    has comments the request will fail with error code 400.

    :returns: Nothing.

    :raises APIException: If the request will result in wrong state.
        (INVALID_STATE)
    :raises APIException: If there is not file with the given id.
        (OBJECT_ID_NOT_FOUND)
    :raises APIException: If you do not have permission to delete the given
        file. (INCORRECT_PERMISSION)
    """
    code: models.File = helpers.get_or_404(
        models.File, file_id, also_error=lambda f: f.deleted
    )

    auth.CodePermisisons(code).ensure_may_edit()

    def _raise_invalid() -> None:
        raise APIException(
            'You cannot delete this file as you don\'t own it',
            f'File {file_id} is not owned by {current_user.id}',
            APICodes.INCORRECT_PERMISSION, 403
        )

    current, other = models.FileOwner.teacher, models.FileOwner.student

    # We already know that the Work exists, so we can safely use
    # child.self_deleted.
    if db.session.query(
        code.children.filter(
            ~models.File.self_deleted, models.File.fileowner != other
        ).exists(),
    ).scalar():
        raise APIException(
            'You cannot delete this directory as it has children',
            f'The file "{file_id}" has children with fileowner "{current}"',
            APICodes.INVALID_STATE, 400
        )

    if code.fileowner == other:
        _raise_invalid()
    elif code.fileowner == current:
        if db.session.query(
            sql.or_(
                models.CommentBase.query.filter(
                    models.CommentBase.file_id == code.id,
                    models.CommentBase.replies.any(),
                ).exists(),
                models.LinterComment.query.filter_by(file_id=code.id).exists(),
            )
        ).scalar():
            raise APIException(
                'You cannot delete this file as it has comments',
                f'The file "{file_id}" has comments associated with it.',
                APICodes.INVALID_STATE,
                400,
            )
        if db.session.query(
            models.PlagiarismMatch.query.filter(
                (models.PlagiarismMatch.file1_id == code.id)
                | (models.PlagiarismMatch.file2_id == code.id)
            ).exists()
        ).scalar():
            # TODO: This leaks information. The question is if this is really
            # a big issue. To stop leaking information all the other error
            # messages also need to be adjusted, and even then: the other
            # properties can probably be checked (if it has comments of
            # children) so we would still leak some information. Another better
            # option would be to only mark the file as deleted.
            raise APIException(
                (
                    'You cannot delete this code as it is implicated in'
                    ' plagiarism'
                ),
                f'The file "{file_id}" is implicated in a plagiarism match.',
                APICodes.INVALID_STATE, 400
            )

        code.delete()
    elif code.fileowner == models.FileOwner.both:
        code.fileowner = other

    db.session.commit()

    return make_empty_response()


def split_code(
    code: models.File, new_owner: FileOwner, old_owner: FileOwner,
    putter: cg_object_storage.Putter
) -> models.File:
    """Split the given ``code`` into multiple code objects.

    The old object in the database will be given a ``fileowner`` of
    ``old_owner`` and the newly created object will be given ``new_owner``. If
    ``code`` is a directory this directory is splitted (see
    :py:func:`redistribute_directory`), if it is a file the original content of
    the file is only copied if ``copy`` is ``True``.

    :param code: The file to split.
    :param new_owner: The new ``fileowner`` of the new file.
    :param old_owner: The new ``fileowner`` of the old file.
    :returns: The newly constructed file.
    """
    code.fileowner = old_owner
    old_id = code.id
    backing_file = code.backing_file
    db.session.flush()
    code = models.File.query.filter(models.File.id == code.id).one()

    db.session.expunge(code)
    make_transient(code)
    code.id = None  # type: ignore
    db.session.add(code)
    db.session.flush()

    code.fileowner = new_owner
    if backing_file.is_just:
        new_file = backing_file.value.copy(putter)
        code.update_backing_file(new_file, delete=False)
    else:
        redistribute_directory(
            code,
            t.cast(models.File, models.File.query.get(old_id)),
            putter=putter,
        )

    return code


def redistribute_directory(
    new_directory: models.File, old_directory: models.File,
    putter: cg_object_storage.Putter
) -> None:
    """Redistribute a given old directory between itself and a new directory.

    .. note::

        None of the given directories may be owned by ``both`` and they should
        not have the same owner.

    All files in the given ``old_directory`` are checked, if the file is owned
    by ``both`` it is split up (see :py:func:`split_code`), if it is owned by
    the owner of the ``new_directory`` its parent is changed and if it is owned
    by the owner of ``old_directory`` nothing is changed.

    :param new_directory: The directory files should be redistributed into.
    :param old_directory: The directory files should be redistributed out of.
    :returns: Nothing.
    """
    assert old_directory.fileowner != FileOwner.both
    assert new_directory.fileowner != FileOwner.both
    assert new_directory.fileowner != old_directory.fileowner

    for child in old_directory.children:
        if child.fileowner == new_directory.fileowner:
            child.parent = new_directory
        elif child.fileowner == old_directory.fileowner:
            pass
        else:
            code = split_code(
                child,
                new_directory.fileowner,
                old_directory.fileowner,
                putter=putter,
            )
            code.parent = new_directory
    db.session.flush()


@api.route('/code/<int:file_id>', methods=['PATCH'])
@auth.login_required
def update_code(file_id: int) -> JSONResponse[models.File]:
    """Update the content or name of the given file.

    .. :quickref: Code; Update the content or name of the given file.

    If a
    student does this request before the deadline, the owner of the file will
    be the student and the teacher (`both`), if the request is done after the
    deadline the owner of the new file will be the one doing the request while
    the old file will be removed or given to the other owner if the file was
    owned by `both`. You can give a request parameter ``operation`` to
    determine the operation:

    - If ``operation`` is ``rename`` the request should also contain a new path
      for the file under the key ``new_path``.
    - If ``operation`` is ``content`` the body of the request should contain
      the new content of the file. This operation is used if no or no valid
      operation was given.

    .. note::

      The id of the returned code object can change, but does not have to.

    :returns: The created code object.

    :raises APIException: If there is not file with the given id.
        (OBJECT_ID_NOT_FOUND)
    :raises APIException: If you do not have permission to change the given
        file. (INCORRECT_PERMISSION)
    :raises APIException: If the request is bigger than the maximum upload
        size. (REQUEST_TOO_LARGE)
    """
    # If the operation is rename it /can/ be a directory. If it is not a rename
    # (so an update of the contents) the target can **not** be a directory.
    dir_filter = None if request.args.get('operation') == 'rename' else True
    code = helpers.filter_single_or_404(
        models.File,
        models.File.id == file_id,
        models.File.is_directory != dir_filter,
        also_error=lambda f: f.deleted,
    )

    auth.CodePermisisons(code).ensure_may_edit()

    def _update_file(
        code: models.File, putter: cg_object_storage.Putter
    ) -> None:
        if request.args.get('operation', None) == 'rename':
            code.rename_code(new_name, new_parent, models.FileOwner.student)
            db.session.flush()
            code.parent = new_parent
        else:
            max_size = app.max_single_file_size
            stream = request.stream
            new_file = putter.from_stream(stream, max_size=max_size)
            if new_file.is_nothing:
                raise helpers.make_file_too_big_exception(max_size, True)

            code.update_backing_file(new_file.value, delete=True)

    if request.args.get('operation', None) == 'rename':
        ensure_keys_in_dict(request.args, [('new_path', str)])
        new_path = t.cast(str, request.args['new_path'])
        path_arr, _ = files.split_path(new_path)
        new_name = path_arr.pop()
        new_parent = code.work.search_file(
            '/'.join(path_arr) + '/',
            exclude=models.FileOwner.student,
        )

    if code.fileowner == models.FileOwner.teacher:
        with app.file_storage.putter() as putter:
            _update_file(code, putter)
    elif code.fileowner == models.FileOwner.both:
        with db.session.begin_nested(), app.file_storage.putter() as putter:
            code = split_code(
                code, models.FileOwner.teacher, models.FileOwner.student,
                putter
            )
            _update_file(code, putter)
    else:
        raise APIException(
            'This file does not belong to you',
            f'The file {code.id} belongs to {code.fileowner.name}',
            APICodes.INVALID_STATE, 403
        )

    db.session.commit()

    return jsonify(code)
