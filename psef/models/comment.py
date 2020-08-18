"""
This module defines all database models needed for inline feedback comments.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import typing as t
from collections import defaultdict

import sqlalchemy
from sqlalchemy.orm import contains_eager, column_property
from typing_extensions import Literal, TypedDict

import psef
from cg_enum import CGEnum
from cg_dt_utils import DatetimeWithTimezone
from cg_flask_helpers import callback_after_this_request
from cg_typing_extensions import make_typed_dict_extender
from cg_cache.intra_request import cached_property
from cg_sqlalchemy_helpers.types import MyQuery, ImmutableColumnProxy
from cg_sqlalchemy_helpers.mixins import IdMixin, TimestampMixin

from . import Base, db
from . import file as file_models
from . import user as user_models
from . import notification as n_models
from .. import auth, db_locks, current_app, current_user


@enum.unique
class CommentType(CGEnum):
    """The kind of a reply."""
    #: This is a piece of normal feedback.
    normal = enum.auto()
    #: This is peer feedback given by another student.
    peer_feedback = enum.auto()


@enum.unique
class CommentReplyType(CGEnum):
    """The type of formatting used for the contents of the reply.
    """
    #: The reply is plain text.
    plain_text = enum.auto()
    #: The reply should be interpreted as markdown.
    markdown = enum.auto()


class CommentReplyJSON(TypedDict, total=True):
    """The serialization of an :class:`.CommentReply`.
    """
    #: The id of the reply
    id: int
    #: The content of the reply, see ``reply_type`` to check in what kind of
    #: formatting this reply is.
    comment: str
    #: The id of the author of this reply, this will be ``null`` if no author
    #: is known (for legacy replies), or if you do not have the permission to
    #: see the author.
    author_id: t.Optional[int]
    #: If this reply was a reply to a specific :class:`.CommentReply`, this
    #: field will be the id of this :class:`.CommentReply`. Otherwise this will
    #: be ``null``.
    in_reply_to_id: t.Optional[int]
    #: The date the last edit was made to this reply, this will be ``null`` if
    #: you do not have the permission to see this information.
    last_edit: t.Optional[DatetimeWithTimezone]
    #: The date this reply was created.
    created_at: DatetimeWithTimezone
    #: The formatting that the content of this reply is in.
    reply_type: CommentReplyType
    #: The type of comment this is.
    comment_type: CommentType
    #: Is this comment approved (i.e. visible for the author of the submission
    #: in most cases) or not.
    approved: bool
    #: The id of the :class:`.CommentBase` this reply is in.
    comment_base_id: int


class CommentReplyExtendedJSON(CommentReplyJSON, total=True):
    """The extended serialization of an :class:`.CommentReply`.

    This serialization contains all data from :class:`.CommentReplyJSON` plus
    some additional fields.
    """
    #: The author of this reply. This will be ``null`` if you do not have the
    #: permission to see this information.
    author: t.Optional['user_models.User']


class CommentBaseJSON(TypedDict, total=True):
    """The serialization of an :class:`.CommentBase`.
    """
    #: The id of the comment base.
    id: int

    #: The line on which the comment was placed.
    line: int

    #: The id of the file on which this comment was placed.
    file_id: str

    #: The id of the work that this comment was placed on. This work will
    #: always contain the file with ``file_id``.
    work_id: int

    #: The replies, that you are allowed to see, in this comment base.
    replies: t.Sequence['CommentReply']


class CommentReply(IdMixin, TimestampMixin, Base):
    """The class representing a reply.

    If a reply doesn't have a ``reply_to_id`` set you should see this as a
    reply to the comment base.
    """
    comment_base_id = db.Column(
        'comment_base_id',
        db.Integer,
        db.ForeignKey("Comment.id"),
        nullable=False
    )

    comment_base = db.relationship(
        lambda: CommentBase,
        foreign_keys=comment_base_id,
        innerjoin=True,
        back_populates='replies',
        lazy='selectin',
    )

    deleted = db.Column(
        'deleted',
        db.Boolean,
        nullable=False,
        default=False,
        server_default='f'
    )

    comment_type = db.Column(
        'comment_type',
        db.Enum(CommentType, name='commentreplycommenttype'),
        nullable=False,
        default=CommentType.normal,
        server_default='normal',
    )

    is_approved = db.Column(
        'is_approved',
        db.Boolean,
        nullable=False,
        default=True,
        server_default='true'
    )

    in_reply_to_id = db.Column(
        'in_reply_to_id',
        db.Integer,
        db.ForeignKey('comment_reply.id', ondelete='SET NULL'),
        nullable=True,
    )

    author_id = db.Column(
        'author_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
        nullable=False,
    )
    author = db.relationship(
        lambda: user_models.User,
        foreign_keys=author_id,
        innerjoin=True,
    )

    in_reply_to = db.relationship(
        lambda: CommentReply,
        foreign_keys=in_reply_to_id,
        innerjoin=False,
        uselist=False,
    )
    comment = db.Column('comment', db.Unicode, nullable=False)

    edits = db.relationship(
        lambda: CommentReplyEdit,
        back_populates='comment_reply',
        uselist=True,
        lazy='dynamic',
        # pylint: disable=unnecessary-lambda
        order_by=lambda: CommentReplyEdit.created_at.desc(),
    )

    reply_type = db.Column(
        'reply_type',
        db.Enum(CommentReplyType),
        nullable=False,
        server_default=CommentReplyType.plain_text.name,
    )

    notifications = db.relationship(
        lambda: n_models.Notification,
        back_populates='comment_reply',
        uselist=True,
    )

    # We set this property later on
    last_edit: ImmutableColumnProxy[t.Optional[DatetimeWithTimezone]]

    @property
    def can_see_author(self) -> bool:
        """Is the current user allowed to see this replies author.

        .. note::

            You are only allowed to see the author when you are also allowed to
            see the reply itself.
        """
        return self.perm_checker.ensure_may_see_author.as_bool()

    @property
    def message_id(self) -> str:
        """The message id of this reply when you send it as an e-mail.
        """
        return '<message_reply_{id_hash}@{domain}>'.format(
            id_hash=self.id, domain=current_app.config['EXTERNAL_DOMAIN']
        )

    @property
    def references(self) -> t.List['CommentReply']:
        """Get a list of all comment replies this reply references.
        """
        if self.in_reply_to is None:
            return []
        else:  # pragma: no cover
            base = self.in_reply_to.references
            base.append(self.in_reply_to)
            return base

    @property
    def perm_checker(self) -> 'auth.FeedbackReplyPermissions':
        """Get the permission checker for this class.
        """
        return auth.FeedbackReplyPermissions(self)

    def __init__(
        self,
        author: 'user_models.User',
        comment: str,
        reply_type: CommentReplyType,
        in_reply_to: t.Optional['CommentReply'],
        comment_base: 'CommentBase',
    ) -> None:
        assert author.group is None, 'Only normal users can place comments'

        super().__init__(
            deleted=False,
            author=user_models.User.resolve(author),
            comment=comment,
            reply_type=reply_type,
            in_reply_to_id=None if in_reply_to is None else in_reply_to.id,
            comment_base=comment_base,
        )

        self.is_approved = self.perm_checker.ensure_may_add_approved.as_bool()
        if not self.perm_checker.ensure_may_add.as_bool():
            self.comment_type = CommentType.peer_feedback

        work = self.comment_base.work
        user_reasons: t.Dict[user_models.User, t.Set[n_models.
                                                     NotificationReasons]]
        user_reasons = defaultdict(set)

        for reply in self.comment_base.replies:
            for user in reply.author.get_contained_users():
                user_reasons[user].add(n_models.NotificationReasons.replied)

        for work_author in work.user.get_contained_users():
            user_reasons[work_author].add(n_models.NotificationReasons.author)

        if work.assignee:
            for assignee in work.assignee.get_contained_users():
                user_reasons[assignee].add(
                    n_models.NotificationReasons.assignee
                )

        for receiver, reasons in user_reasons.items():
            if receiver != author:
                n_models.Notification(
                    receiver=receiver,
                    comment_reply=self,
                    reasons=sorted(reasons),
                )

        @callback_after_this_request
        def __after() -> None:
            psef.tasks.send_direct_notification_emails(
                [n.id for n in self.notifications]
            )

    def update(self, new_comment_text: str) -> t.Optional['CommentReplyEdit']:
        """Update the contents this reply and create a
            :class:`.CommentReplyEdit` object for this mutation.

        :param new_comment_text: The new content of the reply.
        :returns: The created :class:`.CommentReplyEdit` if the given
            ``new_comment_text`` is different than the existing text, otherwise
            ``None`` is returned.
        """
        if new_comment_text == self.comment:
            return None

        edit = CommentReplyEdit(
            self, current_user, new_comment_text=new_comment_text
        )
        self.comment = new_comment_text
        if not self.perm_checker.ensure_may_add_approved.as_bool():
            self.is_approved = False
        return edit

    def delete(self) -> 'CommentReplyEdit':
        """Delete this reply and create a :class:`.CommentReplyEdit` object for
            this mutation.

        :returns: The created :class:`.CommentReplyEdit`.
        """
        edit = CommentReplyEdit(self, current_user, is_deletion=True)
        self.deleted = True
        return edit

    def get_outdated_json(self) -> t.Mapping[str, object]:
        """Get the old JSON representation for this reply.

        This representation was used for the old comments api, the one before
        we supported replies. Don't use it for new apis.
        """
        res = {
            'line': self.comment_base.line,
            'msg': self.comment,
        }
        if self.can_see_author:
            res['author'] = self.author
        return res

    def __to_json__(self) -> CommentReplyJSON:
        last_edit = self.last_edit
        res: CommentReplyJSON = {
            'id': self.id,
            'comment': self.comment,
            'author_id': None,
            'in_reply_to_id': self.in_reply_to_id,
            'last_edit': last_edit,
            'created_at': self.created_at,
            'reply_type': self.reply_type,
            'comment_type': self.comment_type,
            'approved': self.is_approved,
            'comment_base_id': self.comment_base_id,
        }

        if self.can_see_author:
            res['author_id'] = self.author_id

        return res

    def __extended_to_json__(self) -> CommentReplyExtendedJSON:
        author = self.author if self.can_see_author else None
        # Tracking mypy issue: https://github.com/python/mypy/issues/4122
        return make_typed_dict_extender(
            self.__to_json__(), CommentReplyExtendedJSON
        )(author=author)


class CommentReplyEdit(IdMixin, TimestampMixin, Base):
    """A class representing an edit of a comment reply.
    """

    @t.overload
    def __init__(
        self, comment_reply: CommentReply, editor: 'user_models.User', *,
        is_deletion: Literal[True]
    ) -> None:
        ...

    @t.overload
    def __init__(
        self,
        comment_reply: CommentReply,
        editor: 'user_models.User',
        *,
        new_comment_text: str,
    ) -> None:
        ...

    def __init__(
        self,
        comment_reply: CommentReply,
        editor: 'user_models.User',
        *,
        new_comment_text: str = None,
        is_deletion: bool = False,
    ) -> None:
        ...
        assert comment_reply.id is not None, 'CommentReply should be in db'
        super().__init__(
            comment_reply_id=comment_reply.id,
            new_comment=new_comment_text,
            is_deletion=is_deletion,
            old_comment=comment_reply.comment,
            editor=user_models.User.resolve(editor),
        )

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'editor': self.editor,
            'old_text': self.old_comment,
            'new_text': self.new_comment,
        }

    comment_reply_id = db.Column(
        'comment_reply_id',
        db.Integer,
        db.ForeignKey(CommentReply.id),
        nullable=False,
    )

    comment_reply = db.relationship(
        lambda: CommentReply,
        foreign_keys=comment_reply_id,
        innerjoin=True,
        back_populates='edits',
    )

    editor_id = db.Column(
        'editor_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
        nullable=False,
    )
    editor = db.relationship(
        lambda: user_models.User,
        foreign_keys=editor_id,
        innerjoin=True,
    )

    new_comment = db.Column('new_comment', db.Unicode, nullable=True)
    is_deletion = db.Column('was_deleted', db.Boolean, nullable=False)
    old_comment = db.Column('old_comment', db.Unicode, nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            'new_comment IS NOT NULL OR was_deleted',
            name='either_new_comment_or_deletion'
        ),
    )


CommentReply.last_edit = column_property(
    sqlalchemy.sql.select(
        [sqlalchemy.sql.func.max(CommentReplyEdit.created_at)]
    ).where(CommentReplyEdit.comment_reply_id == CommentReply.id
            ).correlate_except(CommentReplyEdit).label('last_edit')
)


class CommentBase(IdMixin, Base):
    """Describes a comment placed in a :class:`.file_models.File` by a
    :class:`.user_models.User` with the ability to grade.

    A comment is always linked to a specific line in a file.
    """
    __tablename__ = "Comment"
    file_id = db.Column(
        'File_id',
        db.Integer,
        db.ForeignKey('File.id', ondelete='CASCADE'),
        nullable=False,
    )
    line = db.Column('line', db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint(file_id, line), )

    file = db.relationship(
        lambda: file_models.File,
        foreign_keys=file_id,
        innerjoin=True,
        lazy='selectin',
    )

    replies = db.relationship(
        lambda: CommentReply,
        back_populates='comment_base',
        uselist=True,
        lazy='selectin',
        order_by=CommentReply.created_at.asc,
        primaryjoin=lambda: sqlalchemy.and_(
            CommentBase.id == CommentReply.comment_base_id,
            ~CommentReply.deleted,
        )
    )

    def __eq__(self, other: object) -> bool:
        """Check if the given object is considered equal to this comment base.
        """
        return (
            other.id == self.id
            if isinstance(other, CommentBase) else NotImplemented
        )

    @property
    def work(self) -> 'psef.models.Work':
        """The :class:`psef.models.Work` associated with this comment base.
        """
        return self.file.work

    def add_reply(
        self,
        user: 'user_models.User',
        comment: str,
        reply_type: CommentReplyType,
        in_reply_to: t.Optional[CommentReply],
    ) -> CommentReply:
        """Add a reply to this comment base.

        :param user: The author of the reply.
        :param comment: The text of the reply.
        :param reply_type: The format of the reply text.
        :param in_reply_to: An optional reply, in this case the new reply will
            be considered a reply on this given reply.
        :returns: The created reply.
        """
        reply = CommentReply(
            comment=comment,
            author=user,
            reply_type=reply_type,
            in_reply_to=in_reply_to,
            comment_base=self,
        )
        self.__class__.user_visible_replies.clear_cache(self)
        return reply

    @classmethod
    def create_if_not_exists(
        cls, file: 'file_models.File', line: int
    ) -> 'CommentBase':
        """Find, or create if it doesn't exist, a comment base for the given
            ``file`` and ``line``.

        This function makes sure that no duplicates will be created in the
        database, at the cost of possibly multiple queries.

        :returns: A found or created (in which case it will not have been added
            to the session) comment base.
        """
        # Do an optimistic try to find it
        self = cls.query.filter(
            cls.file_id == file.id,
            cls.line == line,
        ).one_or_none()

        if self is None:
            # If we cannot find it lock this file for comments, search again,
            # and if we can still not find it we can safely create it.
            db_locks.acquire_lock(
                db_locks.LockNamespaces.comment_base, file.id
            )
            self = cls.query.filter(
                cls.file_id == file.id,
                cls.line == line,
            ).one_or_none()
            if self is None:
                self = cls(file=file, file_id=file.id, line=line, replies=[])
        return self

    @property
    def first_reply(self) -> t.Optional['CommentReply']:
        """Get the first reply that the currently logged in user may see.
        """
        reps = self.user_visible_replies
        return reps[0] if reps else None

    @cached_property
    def user_visible_replies(self) -> t.Sequence[CommentReply]:
        """Get the replies of this comment base that the currently logged in
            user may see.
        """
        return tuple(
            r for r in self.replies if r.perm_checker.ensure_may_see.as_bool()
        )

    @classmethod
    def get_base_comments_query(cls) -> MyQuery['CommentBase']:
        """Get a base query to get all comments and replies in a correct order.
        """
        return cls.query.filter(
            ~file_models.File.self_deleted,
            # We join the replies using an innerload to make sure we only get
            # ``CommentBase``s that have at least one reply.
        ).join(
            cls.replies, isouter=False
        ).join(
            cls.file, isouter=False
        ).order_by(
            cls.file_id.asc(),
            cls.line.asc(),
            CommentReply.created_at.asc(),
        ).options(
            contains_eager(cls.replies).selectinload(CommentReply.author),
            contains_eager(cls.file).selectinload(file_models.File.work),
        )

    def __to_json__(self) -> CommentBaseJSON:
        """Creates a JSON serializable representation of this object.


        This object will look like this:

        .. code:: python

            {
                'line': int, # The line of this comment.
                'file_id': str, # The file this feedback was given on.
                'replies': t.List[CommentReply] # All the replies on this
                                                # comment base.
            }

        :returns: A object as described above.
        """
        return {
            'id': self.id,
            'line': self.line,
            'file_id': str(self.file_id),
            'work_id': self.file.work_id,
            'replies': self.user_visible_replies,
        }
