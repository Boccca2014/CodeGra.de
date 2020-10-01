"""
This module defines all API routes with the main directory "submissions". The
APIs allow the retrieving, and patching of :class: Work objects. Furthermore
functions are defined to get related objects and information.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import numbers
import itertools
from collections import Counter, defaultdict

import structlog
import sqlalchemy.sql as sql
from flask import request
from sqlalchemy.orm import selectinload, contains_eager
from typing_extensions import Protocol, TypedDict

import psef.files
from psef import app, current_user
from cg_sqlalchemy_helpers.types import ColumnProxy

from . import api
from .. import auth, models, helpers, features
from ..models import DbColumn, FileOwner, db
from ..helpers import (
    JSONResponse, EmptyResponse, ExtendedJSONResponse, jsonify,
    ensure_json_dict, extended_jsonify, ensure_keys_in_dict,
    make_empty_response
)
from ..signals import WORK_DELETED, WorkDeletedData
from ..exceptions import APICodes, APIException, PermissionException
from ..permissions import CoursePermission as CPerm

logger = structlog.get_logger()

LinterComments = t.Dict[int,
                        t.Dict[int, t.List[t.Tuple[str, models.
                                                   LinterComment]]],
                        ]


class FeedbackBase(TypedDict, total=True):
    """The base JSON representation for feedback.

    This representation is never sent, see the two models below.

    :ivar general: The general feedback given on this submission.
    :ivar linter: A mapping that is almost the same the user feedback mapping
        for feedback without replies, only the final key is not a string but a
        list of tuples where the first item is the linter code and the second
        item is a :class:`.models.LinterComment`.
    """
    general: t.Optional[str]
    linter: LinterComments


class FeedbackWithReplies(FeedbackBase, total=True):
    """The JSON representation for feedback with replies.

    .. note:: Both lists should be considered unsorted.

    :ivar authors: A list of all authors you have permission to see that placed
        comments. This list is unique, i.e. each author occurs at most once.
    :ivar user: A list of user given inline feedback.
    """
    user: t.List[models.CommentBase]
    authors: t.List[models.User]


class FeedbackWithoutReplies(FeedbackBase, total=True):
    """The JSON representation for feedback without replies.

    .. note::

        This representation is considered deprecated, as it doesn't include
        important information (i.e. replies)

    :ivar user: A mapping between file id and a mapping that is between line
        and feedback. So for example: ``{5: {0: 'Nice job!'}}`` means that file
        with ``id`` 5 has feedback on line 0.
    :ivar authors: The authors of the user feedback. In the example above the
        author of the feedback 'Nice job!' would be at ``{5: {0: $USER}}``.
    """
    user: t.Dict[int, t.Dict[int, str]]
    authors: t.Dict[int, t.Dict[int, models.User]]


@api.route("/submissions/<int:submission_id>", methods=['GET'])
@auth.login_required
def get_submission(submission_id: int
                   ) -> t.Union[ExtendedJSONResponse[models.Work],
                                JSONResponse[t.Mapping[str, str]],
                                ]:
    """Get the given submission (:class:`.models.Work`).

    .. :quickref: Submission; Get a single submission.

    This API has some options based on the 'type' argument in the request

    - If ``type == 'zip'`` see :py:func:`.get_zip`
    - If ``type == 'feedback'`` see :py:func:`.submissions.get_feedback`

    :param int submission_id: The id of the submission
    :returns: A response with the JSON serialized submission as content unless
              specified otherwise
    :rtype: flask.Response

    :query str owner: The type of files to list, if set to `teacher` only
        teacher files will be listed, otherwise only student files will be
        listed.

    :raises APIException: If the submission with given id does not exist.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the submission does not belong to the
                                 current user and the user can not see others
                                 work in the attached course.
                                 (INCORRECT_PERMISSION)
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    auth.WorkPermissions(work).ensure_may_see()

    if request.args.get('type') == 'zip':
        exclude_owner = models.File.get_exclude_owner(
            request.args.get('owner'),
            work.assignment.course_id,
        )
        return jsonify(get_zip(work, exclude_owner))
    elif request.args.get('type') == 'feedback':
        return jsonify(get_feedback(work))
    return extended_jsonify(work, use_extended=models.Work)


def get_feedback(work: models.Work) -> t.Mapping[str, str]:
    """Get the feedback of :class:`.models.Work` as a plain text file.

    :param work: The submission with the required feedback.
    :returns: A object with two keys: ``name`` where the value is the name
        which can be given to ``GET - /api/v1/files/<name>`` and
        ``output_name`` which is the resulting file should be named.
    """
    perms = auth.WorkPermissions(work)
    comments: t.Iterable[str]
    linter_comments: t.Iterable[str]

    if perms.ensure_may_see_grade.as_bool():
        grade = str(work.grade or '')
    else:
        grade = ''

    if perms.ensure_may_see_general_feedback.as_bool():
        general_comment = work.comment or ''
    else:
        general_comment = ''

    comments = work.get_user_feedback()

    if perms.ensure_may_see_linter_feedback.as_bool():
        linter_comments = work.get_linter_feedback()
    else:
        linter_comments = []

    filename = f'{work.assignment.name}-{work.user.name}-feedback.txt'.replace(
        '/', '_'
    )

    output_string = []
    output_string.append(
        f'Assignment: {work.assignment.name}\n'
        f'Grade: {grade}\n'
        f'General feedback:\n{general_comment}\n\n'
        f'Comments:\n'
    )
    for comment in comments:
        output_string.append(f'{comment}\n')

    output_string.append('\nLinter comments:\n')
    for lcomment in linter_comments:
        output_string.append(f'{lcomment}\n')

    with app.mirror_file_storage.putter() as putter:
        result = putter.from_string(''.join(output_string))
    return {'name': result.name, 'output_name': filename}


def get_zip(work: models.Work,
            exclude_owner: FileOwner) -> t.Mapping[str, str]:
    """Return a :class:`.models.Work` as a zip file.

    :param work: The submission which should be returns as zip file.
    :param exclude_owner: The owner to exclude from the files in the zip. So if
        this is `teacher` only files owned by `student` and `both` will be in
        the zip.
    :returns: A object with two keys: ``name`` where the value is the name
        which can be given to ``GET - /api/v1/files/<name>`` and
        ``output_name`` which is the resulting file should be named.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If submission does not belong to the current
                                 user and the user can not view files in the
                                 attached course. (INCORRECT_PERMISSION)
    """
    auth.ensure_can_view_files(work, exclude_owner == FileOwner.student)
    with work.create_zip(exclude_owner) as zip_file:
        max_size = app.max_large_file_size
        with app.mirror_file_storage.putter() as putter:
            result = putter.from_stream(stream=zip_file, max_size=max_size)

    name = result.try_extract(
        lambda: helpers.make_file_too_big_exception(max_size, True)
    ).name

    return {
        'name': name,
        'output_name':
            f'{work.assignment.name}-{work.user.name}-archive.zip'.replace(
                '/', '_'
            )
    }


@api.route('/submissions/<int:submission_id>', methods=['DELETE'])
def delete_submission(submission_id: int) -> EmptyResponse:
    """Delete a submission and all its files.

    .. :quickref: Submission; Delete a submission and all its files.

    :param submission_id: The submission to delete.
    :returns: Nothing
    """
    # TODO: This function doesn't really work for submissions by a user which
    # is also in a group. This is mainly caused by the fact that the
    # `get_from_latest_submissions` function doesn't really work when a user
    # has submissions in a group and individually.

    submission = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    # Make sure nobody does a submission while we are deleting.
    assignment = helpers.filter_single_or_404(
        models.Assignment,
        models.Assignment.id == submission.assignment_id,
        with_for_update=True
    )
    auth.WorkPermissions(submission).ensure_may_delete()

    user = submission.user
    was_latest = helpers.handle_none(
        db.session.query(
            assignment.get_from_latest_submissions(
                models.Work.id
            ).filter_by(id=submission.id).exists()
        ).scalar(),
        False,
    )

    logger.info(
        'Deleting submission',
        submission_id=submission.id,
        was_latest=was_latest
    )

    submission.deleted = True
    db.session.flush()

    WORK_DELETED.send(
        WorkDeletedData(
            deleted_work=submission,
            was_latest=was_latest,
            new_latest=(
                assignment.get_all_latest_submissions().filter_by(
                    user_id=user.id
                ).one_or_none() if was_latest else None
            ),
        )
    )

    db.session.commit()

    return make_empty_response()


class _WithFileId(Protocol):
    file_id: ColumnProxy[int]


TCom = t.TypeVar('TCom', bound=_WithFileId)


def _group_by_file_id(comms: t.List[TCom]
                      ) -> t.Iterator[t.Tuple[int, t.Iterator[TCom]]]:
    return itertools.groupby(comms, lambda c: c.file_id)


def _get_feedback_without_replies(
    comments: t.List[models.CommentBase],
    linter_comments: LinterComments,
    general: str,
) -> FeedbackWithoutReplies:
    user: t.Dict[int, t.Dict[int, str]] = defaultdict(dict)
    authors: t.Dict[int, t.Dict[int, models.User]] = defaultdict(dict)

    for file_id, comms in _group_by_file_id(comments):
        for com in comms:
            line = com.line
            reply = com.first_reply
            if reply is None:
                continue

            user[file_id][line] = reply.comment
            if reply.can_see_author:
                authors[file_id][line] = reply.author

    return {
        'general': general,
        'user': user,
        'authors': authors,
        'linter': linter_comments,
    }


def _get_feedback_with_replies(
    comments: t.List[models.CommentBase],
    linter_comments: LinterComments,
    general: str,
) -> FeedbackWithReplies:
    user_comments = [c for c in comments if c.user_visible_replies]
    authors = sorted(
        set(
            r.author for c in user_comments for r in c.replies
            if r.can_see_author
        )
    )

    return {
        'general': general,
        'user': user_comments,
        'authors': authors,
        'linter': linter_comments,
    }


@api.route('/submissions/<int:submission_id>/feedbacks/', methods=['GET'])
@auth.login_required
def get_feedback_from_submission(
    submission_id: int
) -> JSONResponse[t.Union[FeedbackWithoutReplies, FeedbackWithReplies]]:
    """Get all feedback for a submission

    .. :quickref: Submission; Get all (linter, user and general) feedback.

    :query boolean with_replies: If considered true (see
        :func:`.helpers.request_arg_true`) feedback is send including
        replies. Please note that passing this as false is deprecated.
    :returns: The feedback of this submission.
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    perms = auth.WorkPermissions(work)
    perms.ensure_may_see()

    if not perms.ensure_may_see_linter_feedback.as_bool():
        linter_comments = {}
    else:
        all_linter_comments = models.LinterComment.query.filter(
            models.LinterComment.file.has(work=work)
        ).order_by(
            models.LinterComment.file_id.asc(),
            models.LinterComment.line.asc(),
        ).all()

        def group_by_line(
            comms: t.Iterator[models.LinterComment]
        ) -> t.Iterator[t.Tuple[int, t.Iterator[models.LinterComment]]]:
            return itertools.groupby(comms, lambda lc: lc.line)

        linter_comments = {
            file_id: {
                line: [(com.linter_code, com) for com in comms]
                for line, comms in group_by_line(lcomms)
            }
            for file_id, lcomms in _group_by_file_id(all_linter_comments)
        }

    comments = models.CommentBase.get_base_comments_query().filter(
        models.File.work == work
    ).all()

    fun: t.Callable[[t.List[models.CommentBase], LinterComments, str], t.
                    Union[FeedbackWithoutReplies, FeedbackWithReplies]]
    if helpers.request_arg_true('with_replies'):
        fun = _get_feedback_with_replies
    else:
        fun = _get_feedback_without_replies

    if perms.ensure_may_see_general_feedback.as_bool():
        general = helpers.handle_none(work.comment, '')
    else:
        general = ''

    return jsonify(fun(comments, linter_comments, general))


@api.route("/submissions/<int:submission_id>/rubrics/", methods=['GET'])
@features.feature_required(features.Feature.RUBRICS)
def get_rubric(submission_id: int) -> JSONResponse[t.Mapping[str, t.Any]]:
    """Return full rubric of the :class:`.models.Assignment` of the given
    submission (:class:`.models.Work`).

    .. :quickref: Submission; Get a rubric and its selected items.

    :param int submission_id: The id of the submission
    :returns: A response containing the JSON serialized rubric as described in
        :py:meth:`.Work.__rubric_to_json__`.

    :raises APIException: If the submission with the given id does not exist.
                          (OBJECT_ID_NOT_FOUND)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not see the assignment of the
                                 given submission. (INCORRECT_PERMISSION)
    """
    work = helpers.filter_single_or_404(
        models.Work,
        models.Work.id == submission_id,
        ~models.Work.deleted,
        options=[
            selectinload(
                models.Work.assignment,
            ).selectinload(
                models.Assignment.rubric_rows,
            ).selectinload(
                models.RubricRow.items,
            ),
            selectinload(models.Work.selected_items),
        ]
    )
    auth.WorkPermissions(work).ensure_may_see()
    return jsonify(work.__rubric_to_json__())


@api.route('/submissions/<int:submission_id>/rubricitems/', methods=['PATCH'])
@features.feature_required(features.Feature.RUBRICS)
def select_rubric_items(submission_id: int
                        ) -> ExtendedJSONResponse[models.Work]:
    """Select the given rubric items for the given submission.

    .. :quickref: Submission; Select multiple rubric items.

    :param submission_id: The submission to unselect the item for.

    :>json array items: An array of objects, each object representing the item
        you want to select.
    :>jsonarr int row_id: The id of the row the item is in.
    :>jsonarr int item_id: The id of the item you want to select.
    :>jsonarr float mutiplier: The multiplier you want to use for this rubric
        item. This value defaults to 1.0, and can only be something other than
        1.0 for rubric rows with ``type`` 'continuous'.

    :returns: Nothing.

    :raises APIException: If the assignment of a given item does not belong to
        the assignment of the given submission. of the submission
        (INVALID_PARAM).
    :raises PermissionException: If the current user cannot grace work
        (INCORRECT_PERMISSION).
    """
    submission = helpers.filter_single_or_404(
        models.Work,
        models.Work.id == submission_id,
        ~models.Work.deleted,
        with_for_update=True,
        with_for_update_of=models.Work,
    )
    assig = submission.assignment

    auth.WorkPermissions(submission).ensure_may_edit_grade()

    content = ensure_json_dict(request.get_json())
    ensure_keys_in_dict(content, [('items', list)])
    json_input = t.cast(t.List[helpers.JSONType], content['items'])

    RowType = t.NamedTuple(
        'RowType', [('row_id', int), ('item_id', int), ('multiplier', float)]
    )
    sanitized_input: t.List[RowType] = []
    copy_locked_items = helpers.request_arg_true('copy_locked_items')

    if json_input and isinstance(json_input[0], dict):
        for json_row in json_input:
            with helpers.get_from_map_transaction(
                ensure_json_dict(json_row),
            ) as [get, opt_get]:
                row_id = get('row_id', int)
                item_id = get('item_id', int)
                multiplier = opt_get('multiplier', (float, int), 1.0)

            if multiplier > 1.0 or multiplier < 0.0:
                raise APIException(
                    'A multiplier has to be between 0.0 and 1.0.',
                    f'The given multiplier of {multiplier} is illegal',
                    APICodes.INVALID_PARAM, 400
                )

            sanitized_input.append(
                RowType(row_id=row_id, item_id=item_id, multiplier=multiplier)
            )
    else:
        sanitized_input = [
            RowType(row_id=item.rubricrow_id, item_id=item.id, multiplier=1.0)
            for item in helpers.get_in_or_error(
                models.RubricItem,
                models.RubricItem.id,
                t.cast(t.List[int], json_input),
            )
        ]

    if helpers.contains_duplicate(item.row_id for item in sanitized_input):
        duplicates = [
            k for k, v in Counter(item.row_id
                                  for item in sanitized_input).items() if v > 1
        ]
        raise APIException(
            'Duplicate rows in selected items',
            'The rows "{}" had duplicate items'.format(
                ','.join(map(str, duplicates))
            ), APICodes.INVALID_PARAM, 400
        )

    rows = helpers.get_in_or_error(
        models.RubricRow,
        models.RubricRow.id,
        [item.row_id for item in sanitized_input],
        options=[selectinload(models.RubricRow.items)],
        as_map=True,
    )

    if any(row.assignment_id != assig.id for row in rows.values()):
        raise APIException(
            'Selected rubric item is not coupled to the given submission', (
                f'A given item'
                f' of "{", ".join(str(i.item_id) for i in sanitized_input)}"'
                f' does not belong to assignment "{assig.id}"'
            ), APICodes.INVALID_PARAM, 400
        )

    items = [
        rows[item.row_id].make_work_rubric_item(
            work=submission, item_id=item.item_id, multiplier=item.multiplier
        ) for item in sanitized_input
    ]

    if copy_locked_items:
        for locked_item in db.session.query(models.WorkRubricItem).join(
            models.RubricItem,
            sql.expression.and_(
                models.RubricItem.id == models.WorkRubricItem.rubricitem_id,
                t.cast(DbColumn[int], models.RubricItem.rubricrow_id).in_(
                    list(assig.locked_rubric_rows.keys())
                ),
            )
        ).filter(models.WorkRubricItem.work == submission).options(
            contains_eager(models.WorkRubricItem.rubric_item)
        ).all():
            items.append(locked_item)

            row_id = locked_item.rubric_item.rubricrow_id
            if row_id in rows:
                raise APIException(
                    (
                        'You cannot specify locked rows when the option'
                        " 'copy_locked_items' is given."
                    ),
                    f'The row {row_id} was given twice',
                    APICodes.INVALID_PARAM,
                    400,
                )
    elif assig.auto_test is not None:
        changed_items = set(items) ^ set(submission.selected_items)
        locked_row_ids = set(assig.locked_rubric_rows)
        if any(
            item.rubric_item.rubricrow_id in locked_row_ids
            for item in changed_items
        ):
            raise APIException(
                (
                    'This rubric row is connected to an AutoTest category, so'
                    ' you cannot change it.'
                ), 'An item is connected to one of these rows: "{}"'.format(
                    ', '.join(map(str, assig.locked_rubric_rows))
                ), APICodes.INVALID_PARAM, 400
            )

    submission.select_rubric_items(items, current_user, True)
    db.session.commit()

    return extended_jsonify(submission, use_extended=models.Work)


@api.route(
    '/submissions/<int:submission_id>/rubricitems/<int:rubric_item_id>',
    methods=['DELETE']
)
@features.feature_required(features.Feature.RUBRICS)
@features.feature_required(features.Feature.INCREMENTAL_RUBRIC_SUBMISSION)
def unselect_rubric_item(
    submission_id: int, rubric_item_id: int
) -> EmptyResponse:
    """Unselect the given rubric item for the given submission.

    .. :quickref: Submission; Unselect the given rubric item.

    :param submission_id: The submission to unselect the item for.
    :param rubric_item_id: The rubric items id to unselect.
    :returns: Nothing.
    """
    submission = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )

    auth.WorkPermissions(submission).ensure_may_edit_grade()

    new_items = [
        item for item in submission.selected_items
        if item.rubricitem_id != rubric_item_id
    ]
    if len(new_items) == len(submission.selected_items):
        raise APIException(
            'Selected rubric item was not selected for this submission',
            f'The item {rubric_item_id} is not selected for {submission_id}',
            APICodes.INVALID_PARAM, 400
        )

    submission.select_rubric_items(new_items, current_user, True)
    db.session.commit()

    return make_empty_response()


@api.route(
    "/submissions/<int:submission_id>/rubricitems/<int:rubricitem_id>",
    methods=['PATCH']
)
@features.feature_required(features.Feature.RUBRICS)
@features.feature_required(features.Feature.INCREMENTAL_RUBRIC_SUBMISSION)
def select_rubric_item(
    submission_id: int, rubricitem_id: int
) -> EmptyResponse:
    """Select a rubric item of the given submission (:class:`.models.Work`).

    .. :quickref: Submission; Select a rubric item.

    :>json float multiplier: The mutiplier that should be used for the rubric
        item.
    :param int submission_id: The id of the submission
    :param int rubricitem_id: The id of the rubric item
    :returns: Nothing.

    :raises APIException: If either the submission or rubric item with the
                          given ids does not exist. (OBJECT_ID_NOT_FOUND)
    :raises APIException: If the assignment of the rubric is not the assignment
                          of the submission. (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the user can not grade the given submission
                                 (INCORRECT_PERMISSION)
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    auth.WorkPermissions(work).ensure_may_edit_grade()
    item = helpers.get_or_404(models.RubricItem, rubricitem_id)
    row = item.rubricrow

    json_data = request.get_json()
    with helpers.get_from_map_transaction(ensure_json_dict(json_data or {})
                                          ) as [_, opt_get]:
        multiplier = opt_get('multiplier', (float, int), 1.0)

    if row.assignment_id != work.assignment_id:
        raise APIException(
            'Rubric item selected does not match assignment',
            f'The rubric item "{item.id}" does not match the assignment',
            APICodes.INVALID_PARAM, 400
        )

    work.remove_selected_rubric_item(row.id)
    work.select_rubric_items(
        [row.make_work_rubric_item(work, item, multiplier)], current_user,
        False
    )
    db.session.commit()

    return make_empty_response()


@api.route("/submissions/<int:submission_id>", methods=['PATCH'])
def patch_submission(submission_id: int) -> ExtendedJSONResponse[models.Work]:
    """Update the given submission (:class:`.models.Work`) if it already
    exists.

    .. :quickref: Submission; Update a submissions grade and feedback.

    :param int submission_id: The id of the submission
    :returns: Empty response with return code 204

    :>json float grade: The new grade, this can be null or float where null
        resets the grade or clears it. This field is optional
    :>json str feedback: The feedback for the student. This field is optional.

    :raise APIException: If the submission with the given id does not exist
        (OBJECT_ID_NOT_FOUND)
    :raise APIException: If the value of the "grade" parameter is not a float
        (INVALID_PARAM)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If user can not grade the submission with the
        given id (INCORRECT_PERMISSION)
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    content = ensure_json_dict(request.get_json())

    auth.WorkPermissions(work).ensure_may_edit_grade()

    if 'feedback' in content:
        ensure_keys_in_dict(content, [('feedback', str)])
        feedback = t.cast(str, content['feedback']).replace('\0', '')

        work.comment = feedback
        work.comment_author = current_user

    if 'grade' in content:
        ensure_keys_in_dict(content, [('grade', (numbers.Real, type(None)))])
        grade = t.cast(t.Optional[float], content['grade'])
        assig = work.assignment

        if not (
            grade is None or
            (assig.min_grade <= float(grade) <= assig.max_grade)
        ):
            raise APIException(
                (
                    f'Grade submitted not between {assig.min_grade} and'
                    f' {assig.max_grade}'
                ), (
                    f'Grade for work with id {submission_id} '
                    f'is {content["grade"]} which is not between '
                    f'{assig.min_grade} and {assig.max_grade}'
                ), APICodes.INVALID_PARAM, 400
            )

        work.set_grade(grade, current_user)

    db.session.commit()
    return extended_jsonify(work, use_extended=models.Work)


@api.route("/submissions/<int:submission_id>/grader", methods=['PATCH'])
def update_submission_grader(submission_id: int) -> EmptyResponse:
    """Change the assigned grader of the given submission.

    .. :quickref: Submission; Update grader for the submission.

    :returns: Empty response and a 204 status.

    :>json int user_id: Id of the new grader. This is a required parameter.

    :raises PermissionException: If the logged in user cannot manage the
        course of the submission. (INCORRECT_PERMISSION)
    :raises APIException: If the new grader does not have the correct
        permission to grade this submission. (INCORRECT_PERMISSION)
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    with helpers.get_from_request_transaction() as [get, _]:
        user_id = get('user_id', int)

    auth.AssignmentPermissions(work.assignment).ensure_may_assign_graders()

    if work.user.is_test_student:
        raise APIException(
            'You cannot assign test submissions to a grader',
            f'The submission {work.id} is from a test student',
            APICodes.INVALID_PARAM, 400
        )

    grader = helpers.get_or_404(models.User, user_id)
    if not grader.has_permission(
        CPerm.can_grade_work, work.assignment.course_id
    ):
        raise APIException(
            f'User "{grader.name}" doesn\'t have the required permission',
            f'User "{grader.name}" doesn\'t have permission "can_grade_work"',
            APICodes.INCORRECT_PERMISSION, 400
        )

    work.assignee = grader
    work.assignment.set_graders_to_not_done(
        [grader.id],
        send_mail=grader.id != current_user.id,
        ignore_errors=True,
    )
    db.session.commit()

    return make_empty_response()


@api.route("/submissions/<int:submission_id>/grader", methods=['DELETE'])
def delete_submission_grader(submission_id: int) -> EmptyResponse:
    """Change the assigned grader of the given submission.

    .. :quickref: Submission; Delete grader for the submission.

    :returns: Empty response and a 204 status.

    :raises PermissionException: If the logged in user cannot manage the
        course of the submission. (INCORRECT_PERMISSION)
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    auth.AssignmentPermissions(work.assignment).ensure_may_assign_graders()

    work.assignee = None
    db.session.commit()

    return make_empty_response()


@api.route('/submissions/<int:submission_id>/grade_history/', methods=['GET'])
def get_grade_history(submission_id: int
                      ) -> JSONResponse[t.Sequence[models.GradeHistory]]:
    """Get the grade history for the given submission.

    .. :quickref: Submission; Get the grade history for the given submission.

    :returns: A list of :class:`.models.GradeHistory` object serialized to
        json for the given assignment.
    :raises PermissionException: If the current user has no permission to see
        the grade history. (INCORRECT_PERMISSION)
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )

    auth.WorkPermissions(work).ensure_may_see_grade_history()

    hist = db.session.query(
        models.GradeHistory
    ).filter(models.GradeHistory.work == work).order_by(
        models.GradeHistory.changed_at.desc(),
    ).all()

    return jsonify(hist)


@api.route("/submissions/<int:submission_id>/files/", methods=['POST'])
def create_new_file(submission_id: int) -> JSONResponse[t.Mapping[str, t.Any]]:
    """Create a new file or directory for the given submission.

    .. :quickref: Submission; Create a new file or directory for a submission.

    :param str path: The path of the new file to create. If the path ends in
        a forward slash a new directory is created and the body of the request
        is ignored, otherwise a regular file is created.

    :returns: Stat information about the new file, see
        :py:func:`.files.get_stat_information`

    :raises APIException: If the request is bigger than the maximum upload
        size. (REQUEST_TOO_LARGE)
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    exclude_owner = models.File.get_exclude_owner(
        'auto', work.assignment.course_id
    )

    auth.WorkPermissions(work).ensure_may_edit()
    new_owner = FileOwner.teacher

    ensure_keys_in_dict(request.args, [('path', str)])

    pathname: str = request.args.get('path', '')
    # `create_dir` means that the last file should be a dir or not.
    patharr, create_dir = psef.files.split_path(pathname)

    if len(patharr) < 2:
        raise APIException(
            'Path should contain at least a two parts',
            f'"{pathname}" only contains {len(patharr)} parts',
            APICodes.INVALID_PARAM, 400
        )

    parent = helpers.filter_single_or_404(
        models.File,
        models.File.work_id == submission_id,
        models.File.fileowner != exclude_owner,
        models.File.name == patharr[0],
        models.File.parent_id.is_(None),
        ~models.File.self_deleted,
    )

    code = None
    end_idx = 0
    for idx, part in enumerate(patharr[1:]):
        code = models.File.query.filter(
            models.File.fileowner != exclude_owner,
            models.File.name == part,
            models.File.parent == parent,
            ~models.File.self_deleted,
        ).first()
        end_idx = idx + 1
        if code is None:
            break
        parent = code
    else:
        end_idx += 1

    def _is_last(idx: int) -> bool:
        return end_idx + idx + 1 == len(patharr)

    if _is_last(-1) or not parent.is_directory:
        raise APIException(
            'All part did already exist',
            f'The path "{pathname}" did already exist',
            APICodes.INVALID_STATE,
            400,
        )

    parts = patharr[end_idx:]

    if set(parts) & psef.files.SPECIAL_FILENAMES:
        logger.warning('Invalid filename uploaded using API', filenames=parts)

        raise APIException(
            'Invalid filenames',
            'Some requested names are reserved',
            APICodes.INVALID_PARAM,
            400,
        )

    with app.file_storage.putter() as putter:
        for idx, part in enumerate(parts):
            if _is_last(idx) and not create_dir:
                max_size = app.max_single_file_size
                backing_file = putter.from_stream(
                    request.stream, max_size=max_size
                )
                if backing_file.is_nothing:
                    raise helpers.make_file_too_big_exception(max_size, True)

                code = models.File(
                    work_id=submission_id,
                    name=part,
                    backing_file=backing_file.value,
                    is_directory=False,
                    parent=parent,
                    fileowner=new_owner,
                )
            else:
                code = models.File(
                    work_id=submission_id,
                    name=part,
                    backing_file=None,
                    is_directory=True,
                    parent=parent,
                    fileowner=new_owner,
                )

            db.session.add(code)
            parent = code

        db.session.flush()
    db.session.commit()

    assert code is not None
    return jsonify(psef.files.get_stat_information(code))


class RootFileTreesJSON(TypedDict, total=True):
    """A representation containing both the teacher file tree and student file
    tree for a submission.
    """
    #: The teacher file tree, this will be ``null`` if you do not have the
    #: permission to see teacher files. This might be exactly the same as the
    #: student tree.
    teacher: t.Optional[psef.files.FileTree[int]]
    #: The student file tree of the submission. This will never be ``null``.
    student: psef.files.FileTree[int]


@api.route(
    "/submissions/<int:submission_id>/root_file_trees/", methods=['GET']
)
@auth.login_required
def get_root_file_trees(submission_id: int) -> JSONResponse[RootFileTreesJSON]:
    """Get all the file trees of a submission.

    .. :quickref: Submission; Get all the file trees of a submission.

    :param submission_id: The id of the submission of which you want to get the
        file trees.

    :returns: The student and teacher file tree, from the base/root directory
              of the submission.
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )
    auth.ensure_can_view_files(work, teacher_files=False)
    student_files = work.get_root_file(FileOwner.teacher).list_contents(
        FileOwner.teacher
    )

    try:
        auth.ensure_can_view_files(work, teacher_files=True)
    except PermissionException:
        teacher_files = None
    else:
        teacher_files = work.get_root_file(FileOwner.student).list_contents(
            FileOwner.student
        )

    return jsonify({'teacher': teacher_files, 'student': student_files})


@api.route("/submissions/<int:submission_id>/files/", methods=['GET'])
@auth.login_required
def get_dir_contents(
    submission_id: int
) -> t.Union[JSONResponse[psef.files.
                          FileTree[int]], JSONResponse[t.Mapping[str, t.Any]]]:
    """Return the file directory info of a file of the given submission
    (:class:`.models.Work`).

    .. :quickref: Submission; Get the directory contents for a submission.

    The default file is the root of the submission, but a specific file can be
    specified with the file_id argument in the request.

    .. note::

        If you want the root file trees for the teacher and students, you can
        also use the :func:`.get_root_file_trees` route to get these both in a
        single request.

    :param int submission_id: The id of the submission

    :returns: A response with the JSON serialized directory structure as
              content and return code 200. For the exact structure see
              :py:meth:`.File.list_contents`. If path is given the return value
              will be stat datastructure, see
              :py:func:`.files.get_stat_information`.

    :query int file_id: The file id of the directory to get. If this is not
        given the parent directory for the specified submission is used.
    :query str path: The path that should be searched. The ``file_id`` query
        parameter is used if both ``file_id`` and ``path`` are present.
    :query str owner: The type of files to list, if set to `teacher` only
        teacher files will be listed, otherwise only student files will be
        listed.

    :raise APIException: If the submission with the given id does not exist or
        when a file id was specified no file with this id exists.
        (OBJECT_ID_NOT_FOUND)

    :raises APIException: wWhen a file id is specified and the submission id
        does not match the submission id of the file. (INVALID_URL)
    :raises APIException: When a file id is specified and the file with that id
        is not a directory. (OBJECT_WRONG_TYPE)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If submission does not belong to the current
        user and the user can not view files in the attached course.
        (INCORRECT_PERMISSION)
    """
    work = helpers.filter_single_or_404(
        models.Work, models.Work.id == submission_id, ~models.Work.deleted
    )

    file_id = request.args.get('file_id', None, type=int)
    path: str = request.args.get('path', '')

    exclude_owner = models.File.get_exclude_owner(
        request.args.get('owner', None),
        work.assignment.course_id,
    )

    auth.ensure_can_view_files(work, exclude_owner == FileOwner.student)

    if file_id is not None:
        file = helpers.filter_single_or_404(
            models.File,
            models.File.id == file_id,
            models.File.work_id == work.id,
            ~models.File.self_deleted,
        )
    elif path:
        found_file = work.search_file(path, exclude_owner)
        return jsonify(psef.files.get_stat_information(found_file))
    else:
        file = work.get_root_file(exclude_owner)

    if not file.is_directory:
        raise APIException(
            'File is not a directory',
            f'The file with code {file.id} is not a directory',
            APICodes.OBJECT_WRONG_TYPE, 400
        )

    return jsonify(file.list_contents(exclude_owner))


@api.route('/submissions/<int:submission_id>/proxy', methods=['POST'])
@features.feature_required(features.Feature.RENDER_HTML)
def create_proxy(submission_id: int) -> JSONResponse[models.Proxy]:
    """Create a proxy to view the files of the given submission through.

    .. :quickref: Submission; Create a proxy to view the files of a submission

    This allows you to view files of a submission without authentication for a
    limited time.

    :param submission_id: The submission for which the proxy should be created.
    :<json bool allow_remote_resources: Allow the proxy to load remote
        resources.
    :<json bool allow_remote_scripts: Allow the proxy to load remote scripts,
        and allow to usage of 'eval'.
    :<json teacher_revision: Create a proxy for the teacher revision of the
        submission.
    :returns: The created proxy.
    """
    submission = helpers.filter_single_or_404(
        models.Work,
        models.Work.id == submission_id,
        ~models.Work.deleted,
    )

    with helpers.get_from_map_transaction(
        helpers.get_json_dict_from_request()
    ) as [get, _]:
        allow_remote_resources = get('allow_remote_resources', bool)
        allow_remote_scripts = get('allow_remote_scripts', bool)
        teacher_revision = get('teacher_revision', bool)

    auth.ensure_can_view_files(submission, teacher_revision)

    exclude_owner = (
        models.FileOwner.student
        if teacher_revision else models.FileOwner.teacher
    )
    base_file = models.File.query.filter(
        models.File.work == submission,
        models.File.fileowner != exclude_owner,
        models.File.parent_id.is_(None),
        ~models.File.self_deleted,
    ).one()

    proxy = models.Proxy(
        base_work_file=base_file,
        excluding_fileowner=exclude_owner,
        allow_remote_resources=allow_remote_resources,
        allow_remote_scripts=allow_remote_scripts,
    )
    db.session.add(proxy)
    db.session.commit()
    return jsonify(proxy)
