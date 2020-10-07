"""
This module defines all API routes for comments. With these routes you can
create, edit and delete comments. Retrieving comments should be done using the
route ``/api/v1/submissions/<submission_id>/feedbacks/``.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

import flask

from cg_json import ExtendedJSONResponse, MultipleExtendedJSONResponse
from cg_flask_helpers import EmptyResponse

from . import api
from .. import models, helpers, current_user
from ..auth import (
    FeedbackBasePermissions, FeedbackReplyPermissions, as_current_user
)
from ..models import CommentBase, CommentReply, CommentReplyEdit, db
from ..exceptions import APIWarnings


@api.route('/comments/', methods=['PUT'])
def add_comment(
) -> MultipleExtendedJSONResponse[CommentBase, t.
                                  Union[CommentBase, CommentReply]]:
    """Create a new comment base, or retrieve an existing one.

    .. :quickref: Comment; Create a new comment base.

    :>json int file_id: The id of the file in which this comment should be
        placed.
    :>json int line: The line on which this comment should be placed.
    :returns: The just created comment base.
    """
    with helpers.get_from_request_transaction() as [get, _]:
        file_id = get('file_id', int)
        line = get('line', int)

    file = helpers.filter_single_or_404(
        models.File,
        models.File.id == file_id,
        also_error=lambda f: f.deleted,
        with_for_update=True,
    )
    base = CommentBase.create_if_not_exists(file=file, line=line)
    FeedbackBasePermissions(base).ensure_may_add()
    if base.id is None:
        db.session.add(base)  # type: ignore[unreachable]
        db.session.commit()

    return MultipleExtendedJSONResponse.make(
        base, use_extended=(CommentBase, CommentReply)
    )


@api.route('/comments/<int:comment_base_id>/replies/', methods=['POST'])
def add_reply(
    comment_base_id: int
) -> MultipleExtendedJSONResponse[CommentReply, t.
                                  Union[CommentBase, CommentReply]]:
    """Add a reply to a comment base.

    .. :quickref: Comment; Add a reply to a comment base.

    :>json string comment: The content of the new reply.
    :>json string reply_type: The type of formatting used for the contents of
        the new reply. Should be a member of :class:`.models.CommentReplyType`.
    :>json t.Optional[int] in_reply_to: The id of the reply this new reply
        should be considered a reply to. (OPTIONAL).
    :param comment_base_id: The id of the base to which you want to add a
        reply.
    :returns: The just created reply.
    """
    with helpers.get_from_request_transaction() as [get, opt_get]:
        message = get('comment', str, transform=lambda x: x.replace('\0', ''))
        in_reply_to_id = opt_get('in_reply_to', (int, type(None)), None)
        reply_type = get('reply_type', models.CommentReplyType)

    base = helpers.get_or_404(
        CommentBase,
        comment_base_id,
        also_error=lambda b: b.file.deleted,
    )

    in_reply_to = None
    if in_reply_to_id is not None:
        in_reply_to = helpers.get_or_404(
            CommentReply,
            in_reply_to_id,
            also_error=lambda r: r.comment_base != base or r.deleted
        )
    reply = base.add_reply(current_user, message, reply_type, in_reply_to)

    checker = reply.perm_checker
    checker.ensure_may_add.or_(checker.ensure_may_add_as_peer).check()

    db.session.flush()

    warning_authors = set()
    for author in set(
        r.author for r in base.user_visible_replies if r.can_see_author
    ):
        with as_current_user(author):
            if not FeedbackReplyPermissions(reply).ensure_may_see.as_bool():
                warning_authors.add(author)

    if warning_authors:
        multiple = len(warning_authors) > 1
        helpers.add_warning(
            (
                'The author{s} {authors} {do_not} have sufficient permissions'
                ' to see this reply, the reply will probably only be visible'
                ' when the assignment state is set to "done".'
            ).format(
                s='s' if multiple else '',
                do_not="don't" if multiple else "doesn't",
                authors=helpers.readable_join(
                    [u.get_readable_name() for u in sorted(warning_authors)]
                ),
            ), APIWarnings.POSSIBLE_INVISIBLE_REPLY
        )

    db.session.commit()

    return MultipleExtendedJSONResponse.make(
        reply, use_extended=(CommentBase, CommentReply)
    )


@api.route(
    '/comments/<int:comment_base_id>/replies/<int:reply_id>',
    methods=['PATCH']
)
def update_reply(comment_base_id: int,
                 reply_id: int) -> ExtendedJSONResponse[CommentReply]:
    """Update the content of reply.

    .. :quickref: Comment; Update the content of an inline feedback reply.

    :>json string comment: The new content of the reply.
    :param comment_base_id: The base of the given reply.
    :param reply_id: The id of the reply for which you want to update.
    :returns: The just updated reply.
    """
    with helpers.get_from_request_transaction() as [get, _]:
        message = get('comment', str, transform=lambda x: x.replace('\0', ''))

    reply = helpers.filter_single_or_404(
        CommentReply,
        CommentReply.id == reply_id,
        CommentReply.comment_base_id == comment_base_id,
        ~CommentReply.deleted,
        with_for_update=True,
        with_for_update_of=CommentReply,
    )
    FeedbackReplyPermissions(reply).ensure_may_edit()

    edit = reply.update(message)
    if edit is not None:
        db.session.add(edit)

    db.session.commit()
    return ExtendedJSONResponse.make(reply, use_extended=CommentReply)


@api.route(
    '/comments/<int:comment_base_id>/replies/<int:reply_id>/edits/',
    methods=['GET']
)
def get_reply_edits(comment_base_id: int, reply_id: int
                    ) -> ExtendedJSONResponse[t.Sequence[CommentReplyEdit]]:
    """Get the edits of a reply.

    .. :quickref: Comment; Get the edits of an inline feedback reply.

    :param comment_base_id: The base of the given reply.
    :param reply_id: The id of the reply for which you want to get the replies.
    :returns: A list of edits, sorted from newest to oldest.
    """
    reply = helpers.filter_single_or_404(
        CommentReply,
        CommentReply.id == reply_id,
        CommentReply.comment_base_id == comment_base_id,
        ~CommentReply.deleted,
    )
    FeedbackReplyPermissions(reply).ensure_may_see_edits()

    return ExtendedJSONResponse.make_list(
        reply.edits.all(), use_extended=CommentReplyEdit
    )


@api.route(
    '/comments/<int:comment_base_id>/replies/<int:reply_id>',
    methods=['DELETE']
)
def delete_reply(comment_base_id: int, reply_id: int) -> EmptyResponse:
    """Delete the given reply.

    .. :quickref: Comment; Delete an inline feedback reply.

    :param comment_base_id: The base of the given reply.
    :param reply_id: The id of the reply to delete.
    :returns: Nothing.
    """
    reply = helpers.filter_single_or_404(
        CommentReply,
        CommentReply.id == reply_id,
        CommentReply.comment_base_id == comment_base_id,
        ~CommentReply.deleted,
    )
    FeedbackReplyPermissions(reply).ensure_may_delete()

    db.session.add(reply.delete())
    db.session.commit()

    return EmptyResponse.make()


@api.route(
    '/comments/<int:comment_base_id>/replies/<int:reply_id>/approval',
    methods=['POST', 'DELETE']
)
def update_reply_approval(comment_base_id: int,
                          reply_id: int) -> ExtendedJSONResponse[CommentReply]:
    """Update the content of reply.

    .. :quickref: Comment; Update the content of an inline feedback reply.

    :>json string comment: The new content of the reply.
    :param comment_base_id: The base of the given reply.
    :param reply_id: The id of the reply for which you want to update.
    :returns: The just updated reply.
    """
    reply = helpers.filter_single_or_404(
        CommentReply,
        CommentReply.id == reply_id,
        CommentReply.comment_base_id == comment_base_id,
        ~CommentReply.deleted,
        with_for_update=True,
        with_for_update_of=CommentReply,
    )
    FeedbackReplyPermissions(reply).ensure_may_change_approval()
    reply.is_approved = flask.request.method == 'POST'
    db.session.commit()

    return ExtendedJSONResponse.make(reply, use_extended=CommentReply)
