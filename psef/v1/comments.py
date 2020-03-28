import typing as t

from cg_json import ExtendedJSONResponse
from cg_flask_helpers import EmptyResponse

from . import api
from .. import models, helpers, current_user
from ..auth import FeedbackBasePermissions, FeedbackReplyPermissions
from ..models import CommentBase, CommentReply, CommentReplyEdit, db
from ..permissions import CoursePermission as CPerm


@api.route('/comments/', methods=['POST'])
def add_comment() -> ExtendedJSONResponse[CommentBase]:
    with helpers.get_from_request_transaction() as [get, _]:
        file_id = get('file_id', int)
        line = get('line', int)

    file = helpers.filter_single_or_404(
        models.File,
        models.File.id == file_id,
        also_error=lambda f: f.work.deleted,
        with_for_update=True,
    )
    base = CommentBase.create_if_not_exists(file=file, line=line)
    FeedbackBasePermissions(base).ensure_may_add()
    if base.id is None:
        db.session.add(base)  # type: ignore[unreachable]
        db.session.commit()

    return ExtendedJSONResponse.make(
        base, use_extended=(CommentBase, CommentReply)
    )


@api.route('/comments/<int:comment_base_id>/replies/', methods=['POST'])
def add_reply(comment_base_id: int) -> ExtendedJSONResponse[CommentReply]:
    with helpers.get_from_request_transaction() as [get, opt_get]:
        reply_message = get('comment', str)
        in_reply_to_id = opt_get('in_reply_to', int, None)
        reply_type = get('reply_type', models.CommentReplyType)

    base = helpers.get_or_404(CommentBase, comment_base_id)

    in_reply_to = None
    if in_reply_to_id is not None:
        in_reply_to = helpers.get_or_404(
            CommentReply,
            in_reply_to_id,
            also_error=lambda r: r.comment_base != base or r.deleted
        )
    reply = base.add_reply(
        current_user, reply_message, reply_type, in_reply_to
    )

    FeedbackReplyPermissions(reply).ensure_may_add()

    db.session.commit()
    return ExtendedJSONResponse.make(
        reply, use_extended=(CommentBase, CommentReply)
    )


@api.route(
    '/comments/<int:comment_base_id>/replies/<int:reply_id>',
    methods=['PATCH']
)
def update_reply(comment_base_id: int,
                 reply_id: int) -> ExtendedJSONResponse[CommentReply]:
    with helpers.get_from_request_transaction() as [get, opt_get]:
        message = get('comment', str)

    reply = helpers.filter_single_or_404(
        CommentReply,
        CommentReply.id == reply_id,
        CommentReply.comment_base_id == comment_base_id,
        ~CommentReply.deleted,
    )
    FeedbackReplyPermissions(reply).ensure_may_edit()

    db.session.add(reply.update(message))
    db.session.commit()
    return ExtendedJSONResponse.make(reply, use_extended=CommentReply)


@api.route(
    '/comments/<int:comment_base_id>/replies/<int:reply_id>/edits/',
    methods=['GET']
)
def get_reply_edits(comment_base_id: int, reply_id: int
                    ) -> ExtendedJSONResponse[t.List[CommentReplyEdit]]:
    reply = helpers.filter_single_or_404(
        CommentReply,
        CommentReply.id == reply_id,
        CommentReply.comment_base_id == comment_base_id,
        ~CommentReply.deleted,
    )
    FeedbackReplyPermissions(reply).ensure_may_see_edits()

    return ExtendedJSONResponse.make(reply.edits.all())


@api.route(
    '/comments/<int:comment_base_id>/replies/<int:reply_id>',
    methods=['DELETE']
)
def delete_reply(comment_base_id: int, reply_id: int) -> EmptyResponse:
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