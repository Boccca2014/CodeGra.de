"""This module defines all models needed for an assignment.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import json
import math
import uuid
import typing as t
import datetime
import dataclasses
from random import shuffle
from itertools import chain, cycle
from collections import Counter, defaultdict

import structlog
import sqlalchemy
from furl import furl
from sqlalchemy.orm import validates
from mypy_extensions import DefaultArg
from sqlalchemy.types import JSON
from sqlalchemy_utils import PasswordType
from typing_extensions import TypedDict
from sqlalchemy.orm.collections import attribute_mapped_collection

import psef
import cg_enum
import cg_cache
import cg_sqlalchemy_helpers
from cg_helpers import (
    humanize, handle_none, on_not_none, zip_times_with_offset
)
from cg_dt_utils import DatetimeWithTimezone
from cg_flask_helpers import callback_after_this_request
from cg_sqlalchemy_helpers import UUIDType
from cg_sqlalchemy_helpers import expression as sql_expression
from cg_cache.intra_request import cached_property
from cg_sqlalchemy_helpers.types import (
    _T_BASE, MyQuery, DbColumn, ColumnProxy, MyNonOrderableQuery,
    hybrid_property
)
from cg_sqlalchemy_helpers.mixins import IdMixin, UUIDMixin, TimestampMixin

from . import UUID_LENGTH, Base, db
from . import user as user_models
from . import work as work_models
from . import course as course_models
from . import linter as linter_models
from . import rubric as rubric_models
from . import analytics as analytics_models
from . import auto_test as auto_test_models
from . import validator
from . import task_result as task_result_models
from .. import auth, ignore, helpers, signals, db_locks
from .role import CourseRole
from .permission import Permission, PermissionComp
from ..exceptions import (
    APICodes, APIWarnings, APIException, PermissionException,
    InvalidAssignmentState
)
from .link_tables import user_course, users_groups, course_permissions
from ..permissions import CoursePermission as CPerm

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from pylti1p3.assignments_grades import _AssignmentsGradersData
    from . import group as group_models

T = t.TypeVar('T')
Y = t.TypeVar('Y')
Z = t.TypeVar('Z')

logger = structlog.get_logger()


class PeerFeedbackSettingJSON(TypedDict, total=True):
    """The serialization of an :class:`.AssignmentPeerFeedbackSettings`.
    """
    #: The amount of student that a single user should peer review.
    amount: int

    #: The amount of time in seconds a user has after the deadline to do the
    #: peer review.
    time: t.Optional[float]

    #: Should new peer feedback comments be considered approved by default or
    #: not.
    auto_approved: bool


class AssignmentPeerFeedbackConnectionJSON(TypedDict, total=True):
    """The serialization of an :class:`.AssignmentPeerFeedbackConnection`.
    """
    #: The user that should do the peer review.
    peer: 'user_models.User'
    #: The user that should be reviewed by ``peer``.
    subject: 'user_models.User'


class AssignmentJSON(TypedDict, total=True):
    """The serialization of an assignment.

    See the comments in the source code for the meaning of each field.
    """

    id: int  #: The id of the assignment.
    state: str  #: Current state of the assignment.
    description: t.Optional[str]  #: Description of the assignment.
    created_at: DatetimeWithTimezone  #: ISO UTC date.
    deadline: t.Optional[DatetimeWithTimezone]  #: ISO UTC date.
    name: str  #: The name of the assignment.
    is_lti: bool  #: Is this an LTI assignment.
    course_id: int  #: Course of this assignment.
    cgignore: t.Optional['psef.helpers.JSONType']  #: The cginore.
    cgignore_version: t.Optional[str]
    #: Has the whitespace linter run on this assignment.
    whitespace_linter: bool

    #: The time the assignment will become available (i.e. the state will
    #: switch from 'hidden' to 'open'). If the state is not 'hidden' this value
    #: has no meaning. If this value is not ``None`` you cannot change to state
    #: to 'hidden' or 'open'.
    available_at: t.Optional[DatetimeWithTimezone]

    #: Should we send login links to all users before the available_at time.
    send_login_links: bool

    #: The fixed value for the maximum that can be achieved in a rubric. This
    #: can be higher and lower than the actual max. Will be `null` if unset.
    fixed_max_rubric_points: t.Optional[float]

    #: The maximum grade you can get for this assignment. This is based around
    #: the idea that a 10 is a 'perfect' score. So if this value is 12 a user
    #: can score 2 additional bonus points. If this value is `null` it is unset
    #: and regarded as a 10.
    max_grade: t.Optional[float]

    #: The group set of this assignment. This is ``null`` if this assignment is
    #: not a group assignment.
    group_set: t.Optional['psef.models.GroupSet']

    #: The id of the AutoTest configuration connected to this assignment. This
    #: will always be given if there is a configuration connected to this
    #: assignment, even if you do not have permission to see the configuration
    #: itself.

    auto_test_id: t.Optional[int]
    files_upload_enabled: bool  #: Can you upload files to this assignment.
    webhook_upload_enabled: bool  #: Can you connect git to this assignment.

    #: The maximum amount of submission a student may create, inclusive. The
    #: value ``null`` indicates that there is no limit.
    max_submissions: t.Optional[int]

    #: These two values determine the maximum submissions in an amount of time
    #: by a user. A user can submit at most `amount_in_cool_off_period`
    #: submissions in `cool_off_period` seconds. `amount_in_cool_off_period`
    #: is always >= 1, so this check is disabled if `cool_off_period == 0`.
    cool_off_period: datetime.timedelta
    amount_in_cool_off_period: int

    #: ISO UTC date. This will be `null` if you don't have the permission to
    #: see this or if it is unset.
    reminder_time: t.Optional[str]

    #: The LMS providing this LTI assignment.
    lms_name: t.Optional[str]

    #: The peer feedback settings for this assignment. If ``null`` this
    #: assignment is not a peer feedback assignment.
    peer_feedback_settings: t.Optional['AssignmentPeerFeedbackSettings']

    #: The kind of reminder that will be sent.  If you don't have the
    #: permission to see this it will always be ``null``. If this is not set it
    #: will also be ``null``.
    done_type: t.Optional[str]
    #: The email where the done email will be sent to. This will be ``null`` if
    #: you do not have permission to see this information.
    done_email: t.Optional[str]

    #: The assignment id of the assignment that determines the grader division
    #: of this assignment. This will be ``null`` if you do not have permissions
    #: to see this information, or if no such parent is set.
    division_parent_id: t.Optional[int]

    #: The ids of the analytics workspaces connected to this assignment.
    #: WARNING: This API is still in beta, and might change in the future.
    analytics_workspace_ids: t.List[int]

    #: What kind of assignment is this.
    kind: 'AssignmentKind'


class AssignmentAmbiguousSettingTag(enum.Enum):
    """All items that can contribute to a ambiguous assignment setting.
    """
    webhook = enum.auto()
    cgignore = enum.auto()
    max_submissions = enum.auto()
    cool_off = enum.auto()
    deadline = enum.auto()


@dataclasses.dataclass(frozen=True)
class _AssignmentAmbiguousSetting:
    """A class representing a ambiguous setting for an assignment.
    """
    __slots__ = ['message', 'tags']
    message: str
    tags: t.Set[AssignmentAmbiguousSettingTag]


@enum.unique
class AssignmentStateEnum(cg_enum.CGEnum):
    """Describes in what state an :class:`.Assignment` is.
    """
    hidden = 0
    open = 1
    done = 2


@enum.unique
class AssignmentKind(cg_enum.CGEnum):
    """Describes in what state an :class:`.Assignment` is.
    """
    normal = 0
    exam = 1


@enum.unique
class AssignmentVisibilityState(enum.IntEnum):
    """This enum determines what the visibility state is of this assignment.

    This state is more important than that of :class:`.AssignmentStateEnum`.

    .. todo::

        Investigate if we can combine this class with
        :class:`.AssignmentStateEnum`. We would really need to take care that
        performance isn't impacted when combining, and that it actually
        improves the clarity of the code.

    :ivar deep_linked: This assignment is not finished at the moment, but is
        being deep linked inside an LMS.
    :ivar visible: Assignment is visible and can be used as normal.
    :ivar ~AssignmentVisibilityState.deleted: Assignment has been deleted and
        should be hidden.
    """
    deep_linked = 0
    visible = 1
    deleted = 2

    @property
    def is_deleted(self) -> bool:
        """Should you see this assignment as a deleted assignment?
        """
        return self == self.deleted


class AssignmentAssignedGrader(Base):
    """The class creates the link between an :class:`.user_models.User` and an
    :class:`.Assignment`.

    The user linked to the assignment is an assigned grader. In this link the
    weight is the weight this user was given when assigning.
    """
    __tablename__ = 'AssignmentAssignedGrader'
    weight = db.Column('weight', db.Float, nullable=False)
    user_id = db.Column(
        'User_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
        nullable=False,
    )
    assignment_id = db.Column(
        'Assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id', ondelete='CASCADE'),
        nullable=False,
    )

    __table_args__ = (db.PrimaryKeyConstraint(assignment_id, user_id), )


class AssignmentGraderDone(Base):
    """This class creates the link between an :class:`.user_models.User` and an
    :class:`.Assignment` that exists only when the grader is done.

    If a user is linked to the assignment this indicates that this user is done
    with grading.

    :ivar ~.AssignmentGraderDone.user_id: The id of the user that is linked.
    :ivar ~.AssignmentGraderDone.assignment_id: The id of the assignment that
        is linked.
    """
    __tablename__ = 'AssignmentGraderDone'
    user_id = db.Column(
        'User_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
        nullable=False,
    )
    assignment_id = db.Column(
        'Assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id', ondelete='CASCADE'),
        nullable=False,
    )

    __table_args__ = (db.PrimaryKeyConstraint(assignment_id, user_id), )


class AssignmentDoneType(enum.IntEnum):
    """Describes what type of reminder should be sent.

    :param none: Nobody should be e-mailed.
    :param assigned_only: Only graders that are assigned will be notified.
    :param all_graders: All users that have the permission to grade.
    """
    assigned_only: int = 1
    all_graders: int = 2


class AssignmentLinter(Base):
    """The class is used when a linter (see :py:mod:`psef.linters`) is used on
    a :class:`.Assignment`.

    Every :class:`.work_models.Work` that is tested is attached by a
    :class:`.linter_models.LinterInstance`.

    The name identifies which :class:`.linter_models.Linter` is used.

    :ivar ~.AssignmentLinter.name: The name of the linter which is the
        `__name__` of a subclass of :py:class:`.linter_models.Linter`.
    :ivar tests: All the linter instances for this linter, this are the
        recordings of the running of the actual linter (so in the case of the
        :py:class:`.Flake8` metadata about the `flake8` program).
    :ivar config: The config that was passed to the linter.
    """
    __tablename__ = 'AssignmentLinter'  # type: str
    # This has to be a String object as the id has to be a non guessable uuid.
    id = db.Column(
        'id', db.String(UUID_LENGTH), nullable=False, primary_key=True
    )
    name = db.Column('name', db.Unicode, nullable=False)
    tests = db.relationship(
        lambda: linter_models.LinterInstance,
        back_populates="tester",
        cascade='all,delete',
        order_by=lambda: linter_models.LinterInstance.work_id,
        uselist=True,
    )
    config = db.Column(
        'config',
        db.Unicode,
        nullable=False,
    )
    assignment_id = db.Column(
        'Assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id'),
        nullable=False,
    )

    assignment = db.relationship(
        lambda: Assignment,
        foreign_keys=assignment_id,
        backref=db.backref('linters', uselist=True),
    )

    @classmethod
    def get_whitespace_linter_query(cls) -> MyQuery['AssignmentLinter']:
        return cls.query.filter(AssignmentLinter.name == 'MixedWhitespace')

    @property
    def linters_crashed(self) -> int:
        """The amount of linters that have crashed.
        """
        return self._amount_linters_in_state(linter_models.LinterState.crashed)

    @property
    def linters_done(self) -> int:
        """The amount of linters that are done.
        """
        return self._amount_linters_in_state(linter_models.LinterState.done)

    @property
    def linters_running(self) -> int:
        """The amount of linters that are running.
        """
        return self._amount_linters_in_state(linter_models.LinterState.running)

    def _amount_linters_in_state(
        self, state: 'linter_models.LinterState'
    ) -> int:
        return linter_models.LinterInstance.query.filter_by(
            tester_id=self.id, state=state
        ).count()

    def __extended_to_json__(self) -> t.Mapping[str, t.Any]:
        """Creates an extended JSON serializable representation of this
        assignment linter.

        This object will look like this:

        .. code:: python

            {
                'tests': t.List[LinterInstance], # The tests done by this
                                                 # assignment linter.
                'id': str, # The id of this assignment linter.
                'name': str, # The name.
            }

        :returns: An object as described above.
        """
        return {
            'tests': [t for t in self.tests if not t.work.deleted],
            'id': self.id,
            'name': self.name,
        }

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Returns the JSON serializable representation of this class.

        This representation also returns a count of the
        :class:`.linter_models.LinterState` of the attached
        :class:`.linter_models.LinterInstance` objects.

        :returns: A dict containing JSON serializable representations of the
            attributes and the test state counts of this AssignmentLinter.
        """
        return {
            'done': self.linters_done,
            'working': self.linters_running,
            'crashed': self.linters_crashed,
            'id': self.id,
            'name': self.name,
        }

    @classmethod
    def create_linter(
        cls: t.Type['AssignmentLinter'],
        assignment_id: int,
        name: str,
        config: str,
    ) -> 'AssignmentLinter':
        """Create a new instance of this class for a given :class:`.Assignment`
        with a given :py:class:`.linter_models.Linter`

        :param assignment_id: The id of the assignment
        :param name: Name of the linter
        :returns: The created AssignmentLinter
        """
        new_id = str(uuid.uuid4())

        # Find a unique id.
        while db.session.query(
            AssignmentLinter.query.filter(cls.id == new_id).exists()
        ).scalar():  # pragma: no cover
            new_id = str(uuid.uuid4())

        self = cls(id=new_id, assignment_id=assignment_id, name=name)
        self.config = config

        self.tests = []
        assig = Assignment.query.get(assignment_id)

        if assig is not None:
            for work in assig.get_all_latest_submissions():
                self.tests.append(linter_models.LinterInstance(work, self))

        return self


class AssignmentPeerFeedbackConnection(Base, TimestampMixin):
    """This table represents a link between a two users and assignment.

    If a connection from ``peer_user`` to ``user`` for assignment ``A1`` exists this
    means that ``peer_user`` should peer review ``user`` for assignment ``A1``.
    """

    @t.overload
    def __init__(
        self,
        peer_feedback_settings: 'AssignmentPeerFeedbackSettings',
        *,
        user: 'user_models.User',
        peer_user: 'user_models.User',
    ) -> None:
        ...

    @t.overload
    def __init__(
        self,
        peer_feedback_settings: 'AssignmentPeerFeedbackSettings',
        *,
        user_id: int,
        peer_user_id: int,
    ) -> None:
        ...

    def __init__(
        self,
        peer_feedback_settings: 'AssignmentPeerFeedbackSettings',
        *,
        user: 'user_models.User' = None,
        peer_user: 'user_models.User' = None,
        user_id: int = None,
        peer_user_id: int = None,
    ) -> None:
        if user is not None:
            assert peer_user is not None
            assert user_id is None
            assert peer_user_id is None

            super().__init__(
                peer_feedback_settings=peer_feedback_settings,
                user=user,
                peer_user=peer_user,
                peer_feedback_settings_id=peer_feedback_settings.id,
                user_id=user.id,
                peer_user_id=peer_user.id,
            )
        else:
            assert peer_user is None
            assert user_id is not None
            assert peer_user_id is not None
            super().__init__(
                peer_feedback_settings=peer_feedback_settings,
                peer_feedback_settings_id=peer_feedback_settings.id,
                user_id=user_id,
                peer_user_id=peer_user_id,
            )

    peer_feedback_settings_id = db.Column(
        'peer_feedback_settings_id',
        db.Integer,
        db.ForeignKey(
            'assignment_peer_feedback_settings.id', ondelete='CASCADE'
        ),
        nullable=False,
    )

    #: The user that should be peer reviewed
    user_id = db.Column(
        'user_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
        nullable=False,
    )

    #: The id of the user that should do this peer feedback.
    peer_user_id = db.Column(
        'peer_user_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
        nullable=False,
    )

    peer_feedback_settings = db.relationship(
        lambda: AssignmentPeerFeedbackSettings,
        foreign_keys=peer_feedback_settings_id,
        lazy='selectin',
        innerjoin=True,
        back_populates='connections',
    )

    user = db.relationship(
        lambda: user_models.User,
        foreign_keys=user_id,
        innerjoin=True,
        lazy='selectin',
    )

    peer_user = db.relationship(
        lambda: user_models.User,
        foreign_keys=peer_user_id,
        innerjoin=True,
        lazy='selectin',
    )

    __table_args__ = (
        db.PrimaryKeyConstraint(
            peer_feedback_settings_id, user_id, peer_user_id
        ),
        db.CheckConstraint(
            'peer_user_id != user_id',
            name='peer_feedback_reviewer_is_not_subject',
        ),
    )

    def __repr__(self) -> str:
        return 'AssignmentPeerFeedbackConnection<peer={}, subject={}>'.format(
            self.peer_user_id,
            self.user_id,
        )

    def __to_json__(self) -> t.Any:
        return {
            'subject': self.user,
            'peer': self.peer_user,
        }


class AssignmentPeerFeedbackSettings(Base, IdMixin, TimestampMixin):
    """This table represents the peer feedback settings for an assignment.
    """
    #: The amount of students a single student should review. If this is 0 peer
    #: feedback is disabled.
    amount = db.Column('amount', db.Integer, default=0, nullable=False)

    #: The amount of time a user has after the deadline to do its peer
    #: feedback. If this is ``None`` the user has an infinite amount of time
    time = db.Column('time', db.Interval, nullable=True, default=None)

    auto_approved = db.Column(
        'auto_approved',
        db.Boolean,
        nullable=False,
        default=False,
        server_default='false'
    )

    assignment_id = db.Column(
        'assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )

    assignment = db.relationship(
        lambda: Assignment,
        foreign_keys=assignment_id,
        lazy='joined',
        innerjoin=True,
        back_populates="peer_feedback_settings",
    )

    connections = db.relationship(
        lambda: AssignmentPeerFeedbackConnection,
        back_populates='peer_feedback_settings',
        cascade='delete-orphan,delete,save-update',
        uselist=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "amount > 0",
            name='peer_feedback_amount_at_least_one',
        ),
    )

    def __init__(
        self,
        amount: int,
        time: t.Optional[datetime.timedelta],
        assignment: 'Assignment',
        auto_approved: bool,
    ) -> None:
        super().__init__(
            amount=amount,
            time=time,
            assignment=assignment,
            auto_approved=auto_approved,
        )

    def __to_json__(self) -> PeerFeedbackSettingJSON:
        return {
            'amount': self.amount,
            'time': on_not_none(self.time, lambda x: x.total_seconds()),
            'auto_approved': self.auto_approved,
        }

    @property
    def deadline_expired(self) -> bool:
        """Has the deadline for giving peer feedback expired.

        If the deadline for the assignment has not been set just yet we don't
        consider the deadline for the peer feedback expired. However, as the
        deadline for the assignment also hasn't expired in this case peer
        feedback is not yet open.
        """
        assig = self.assignment
        now = helpers.get_request_start_time()
        if self.time is None or assig.deadline is None:
            return False

        return (assig.deadline + self.time) < now

    @cg_cache.intra_request.cache_within_request
    def _get_subjects_for_user(self,
                               user: 'user_models.User') -> t.Container[int]:
        PFConn = AssignmentPeerFeedbackConnection
        result = set(
            user_id for user_id, in db.session.query(PFConn.user_id).filter(
                PFConn.peer_feedback_settings == self,
                PFConn.peer_user == user,
            )
        )
        return result

    def does_peer_review_of(
        self, *, reviewer: 'user_models.User', subject: 'user_models.User'
    ) -> bool:
        """Check if the given ``reviewer`` should peer review submissions by
        the given ``subject``.

        :param reviewer: The user that should do the review.
        :param subject: Submissions of this user should be peer reviewed by the
            ``reviewer`` if this function returns ``True``.

        :returns: ``True`` if the ``reviewer`` should do a peer review,
                  ``False`` otherwise. It also returns ``False`` if the
                  deadline of an assignment has not expired just yet.
        """
        # If the assignment is not yet done the ordering has not stabilized, so
        # we always return ``False`` for this check.
        if not self.assignment.deadline_expired:
            return False
        return subject.id in self._get_subjects_for_user(reviewer)

    def maybe_do_initial_division(self) -> bool:
        """Do the initial division of peer feedback if the amount of submissions is
        adequate.

        .. warning:: This will delete all old connections.

        :returns: A boolean indicating if the initial submission was done.
        """
        assig = self.assignment
        existing_submissions = assig.get_amount_not_deleted_submissions()
        if existing_submissions > self.amount:
            self.connections = []
            self._do_initial_division()
            return True
        return False

    def _make_connection(
        self, *, peer_user_id: int, user_id: int
    ) -> AssignmentPeerFeedbackConnection:
        return AssignmentPeerFeedbackConnection(
            peer_feedback_settings=self,
            peer_user_id=peer_user_id,
            user_id=user_id,
        )

    def _do_initial_division(self) -> None:
        """Do the initial division of peer feedback.

        This can only be done when the amount of submissions is equal to or
        larger than the amount of submissions that each user should review.
        """
        assig = self.assignment
        all_users = user_models.User.query.filter(
            user_models.User.id.in_(
                assig.get_from_latest_submissions(work_models.Work.user_id)
            )
        ).all()
        shuffle(all_users)

        self.connections = []
        can_do_better_division = len(all_users) > self.amount ** 2

        def get_offset_per_item(cur_depth: int) -> int:
            if can_do_better_division:
                return cur_depth ** 2
            return cur_depth

        logger.info(
            'Doing initial division',
            assignment=self.assignment,
            amount_of_users=len(all_users),
            division_amount=self.amount,
            can_do_better_division=can_do_better_division
        )
        for users in zip_times_with_offset(
            all_users, self.amount + 1, get_offset_per_item
        ):
            peer_user, *other_users = users
            for user in other_users:
                self._make_connection(
                    peer_user_id=peer_user.id, user_id=user.id
                )

    @classmethod
    def maybe_delete_division_among_peers(
        cls, deletion: signals.WorkDeletedData
    ) -> None:
        """Maybe delete the division for the student connected to the deleted
        work.

        This method might redivide all submissions again, so deleting work is
        quite dangerous. If this redivision happens a warning will be added to
        the response.

        :param deletion: The deleted work and extra data.

        :returns: Nothing.
        """
        assig = deletion.assignment
        self = assig.peer_feedback_settings
        if self is None:
            return
        self._maybe_delete_division_among_peers(deletion)  # pylint: disable=protected-access

    def _maybe_delete_division_among_peers(
        self, deletion: signals.WorkDeletedData
    ) -> None:
        author = deletion.deleted_work.user
        assig = deletion.assignment

        if (
            author.is_test_student or not deletion.was_latest or
            deletion.new_latest is not None
        ):
            return

        db_locks.acquire_lock(
            db_locks.LockNamespaces.peer_feedback_division, assig.id
        )

        PFConn = AssignmentPeerFeedbackConnection
        # First we get all connections that involve the author that now no
        # longer has a submission.
        all_conns = PFConn.query.filter(
            PFConn.peer_feedback_settings == self,
            sql_expression.or_(
                PFConn.user == author,
                PFConn.peer_user == author,
            )
        ).all()

        all_subjects = set(
            conn.user for conn in all_conns if conn.user != author
        )
        reviewers = set(
            conn.peer_user for conn in all_conns if conn.peer_user != author
        )
        assert len(reviewers) == len(all_subjects)
        assert len(reviewers) * 2 == len(all_conns)
        illegal_connections = set(
            db.session.query(PFConn.peer_user_id, PFConn.user_id).filter(
                PFConn.peer_feedback_settings == self,
                PFConn.user_id.in_([s.id for s in all_subjects]),
                PFConn.peer_user_id.in_([r.id for r in reviewers]),
            )
        )

        # We first want to divide the subjects that are also reviewers, as
        # these subjects might cause the redivision to fail.
        high_priority_subjects = all_subjects & reviewers
        low_priority_subjects = all_subjects - high_priority_subjects

        new_conns = []
        # Redivision might fail if a user should review the ``author`` and if
        # the ``author`` should review this user.
        redivide_failed = False

        for reviewer in reviewers:
            for subj in chain(high_priority_subjects, low_priority_subjects):
                # We don't know from which set we should remove the subject
                # (high or low priority) so we simply remove it from the all
                # set and check this set to see if the subject is still
                # available.
                if subj not in all_subjects:
                    continue
                if reviewer == subj:
                    continue
                if (reviewer.id, subj.id) in illegal_connections:
                    continue

                all_subjects.remove(subj)
                new_conns.append((reviewer, subj))
                break
            else:
                redivide_failed = True
                break

        if not redivide_failed:
            logger.info('Redividing succeeded', new_connections=new_conns)
            for conn in all_conns:
                db.session.delete(conn)
            for peer, subject in new_conns:
                PFConn(
                    peer_feedback_settings=self, user=subject, peer_user=peer
                )
            return

        self.connections = []
        db.session.flush()
        if self.maybe_do_initial_division():
            psef.helpers.add_warning(
                (
                    'All connections for peer feedback were redivided because'
                    ' of this deletion.'
                ), psef.errors.APIWarnings.ALL_PEER_FEEDBACK_REDIVIDED
            )

    @classmethod
    def maybe_divide_work_among_peers(cls, work: 'work_models.Work') -> None:
        """Maybe divide the given work among peers.

        The work will be divided if it is done by a real user (i.e. not a test
        student), and if peer feedback is enabled. All users with a submission
        for the assignment are considered peers.
        """
        self = work.assignment.peer_feedback_settings
        if self is None:
            return
        self._maybe_divide_work_among_peers(work)  # pylint: disable=protected-access

    def _maybe_divide_work_among_peers(self, work: 'work_models.Work') -> None:
        if work.user.is_test_student:
            # Test students cannot do peer feedback
            return

        assig = work.assignment

        def _has_no_submission() -> bool:
            return db.session.query(
                ~assig.get_not_deleted_submissions().filter(
                    work_models.Work.user == work.user,
                    work_models.Work.id != work.id,
                ).exists(),
            ).scalar()

        # We use the entire body of submissions to determine the peer reviewers
        # for this submission. So no submissions by new users (without any
        # submissions) should be created at this point to prevent race
        # conditions.
        if not db_locks.maybe_acquire_lock(
            _has_no_submission, db_locks.LockNamespaces.peer_feedback_division,
            assig.id
        ):
            logger.info(
                'No division necessary, user already has a submission',
                work_author=work.user,
            )
            return

        existing_submissions = assig.get_amount_not_deleted_submissions()
        if existing_submissions <= self.amount:
            # Not enough submissions to create a division
            logger.info(
                'Not enough submissions to do initial division',
                existing_submissions=existing_submissions,
                division_amount=self.amount
            )
            return
        elif existing_submissions == self.amount + 1:
            logger.info('Need to do initial division')
            self._do_initial_division()
            return

        PFConn = AssignmentPeerFeedbackConnection
        all_connections = PFConn.query.filter(
            PFConn.peer_feedback_settings == self,
        ).order_by(sql_expression.func.random())
        # XXX: It might be faster do a ``random.shuffle`` in Python instead of
        # ordering by a random value in the database. I have not tested this,
        # but this seems fast enough for now.

        illegal_connections: t.Set[t.Tuple[int, int]] = set()

        for connection in all_connections:
            new = (
                (connection.peer_user_id, work.user_id),
                (work.user_id, connection.user_id),
            )
            if any(new_conn in illegal_connections for new_conn in new):
                continue

            db.session.delete(connection)
            for peer_user, subject in new:
                self._make_connection(peer_user_id=peer_user, user_id=subject)

            illegal_connections.update(new)
            # We add two connections to `illegal_connections` every time, so
            # the amount of connections for our new author is the length of
            # that set divided by two.
            found = len(illegal_connections) / 2
            if found == self.amount:
                break
        else:  # pragma: no cover
            # This (``found < self.amount``) should never happen, but the exact
            # distribution of users (especially when ``self.amount > 1``) is
            # really hard to follow. We don't want uploading to fail, so in
            # production we simply redivide everybody and report this error to
            # sentry.
            if psef.current_app.do_sanity_checks:
                raise AssertionError(
                    (
                        'Could not upload new submission without redividing'
                        ' all existing users. Existing connections: {}'
                    ).format(self.connections)
                )
            logger.error(
                'All submissions needed a new division',
                report_to_sentry=True,
                old_connections=self.connections,
            )
            self.connections = []
            self._do_initial_division()


signals.WORK_DELETED.connect_immediate(
    AssignmentPeerFeedbackSettings.maybe_delete_division_among_peers
)
signals.WORK_CREATED.connect_immediate(
    AssignmentPeerFeedbackSettings.maybe_divide_work_among_peers
)


class AssignmentLoginLink(Base, UUIDMixin, TimestampMixin):
    """This class represents a link that a user can use to login for a specific
    assignment between the ``available_at`` and the ``deadline``.
    """
    user_id = db.Column(
        'user_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
        nullable=False,
    )
    user = db.relationship(
        lambda: user_models.User,
        foreign_keys=user_id,
        innerjoin=True,
        lazy='joined',
    )

    assignment_id = db.Column(
        'assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id', ondelete='CASCADE'),
        nullable=False,
    )
    assignment = db.relationship(
        lambda: Assignment,
        foreign_keys=assignment_id,
    )

    password = db.Column(
        'password',
        PasswordType(schemes=[
            'pbkdf2_sha512',
        ], deprecated=[]),
        nullable=True,
    )

    def get_url(self) -> str:
        return furl(
            psef.current_app.config['EXTERNAL_URL']
        ).add(path=['assignments', self.assignment_id, 'login', self.id]
              ).tostr()

    def get_message_id(self, idx: int) -> str:
        return '<{self_id}-{token_id}-{idx}@{domain}>'.format(
            self_id=self.id,
            token_id=self.assignment.send_login_links_token,
            idx=idx,
            domain=psef.current_app.config['EXTERNAL_DOMAIN'],
        )

    class AsJSON(TypedDict):
        """The way this class will be represented in JSON.
        """
        #: The id of this link.
        id: uuid.UUID
        #: The assignment connected to this login link.
        assignment: 'Assignment'
        #: The user that is link will login.
        user: 'user_models.User'

    def __to_json__(self) -> AsJSON:
        return {
            'id': self.id,
            'assignment': self.assignment,
            'user': self.user,
        }


class AssignmentResult(Base):
    """The class creates the link between an :class:`.user_models.User` and an
    :class:`.Assignment` in the database and the external users LIS sourcedid.

    :ivar sourcedid: The ``sourcedid`` for this user for this assignment.
    :ivar ~.AssignmentResult.user_id: The id of the user this belongs to.
    :ivar ~.AssignmentResult.assignment_id: The id of the assignment this
        belongs to.
    """
    __tablename__ = 'AssignmentResult'
    sourcedid = db.Column('sourcedid', db.Unicode)
    user_id = db.Column(
        'User_id', db.Integer, db.ForeignKey('User.id', ondelete='CASCADE')
    )
    assignment_id = db.Column(
        'Assignment_id', db.Integer,
        db.ForeignKey('Assignment.id', ondelete='CASCADE')
    )

    __table_args__ = (db.PrimaryKeyConstraint(assignment_id, user_id), )


class Assignment(helpers.NotEqualMixin, Base):  # pylint: disable=too-many-public-methods
    """This class describes a :class:`.course_models.Course` specific assignment.

    :ivar ~.Assignment.name: The name of the assignment.
    :ivar ~.Assignment.cgignore: The .cgignore file of this assignment.
    :ivar ~.Assignment.state: The current state the assignment is in.
    :ivar ~.Assignment.description: UNUSED
    :ivar ~.Assignment.course: The course this assignment belongs to.
    :ivar ~.Assignment.created_at: The date this assignment was added.
    :ivar ~.Assignment.deadline: The deadline of this assignment.
    :ivar ~.Assignment._mail_task_id: This is the id of the current task that
        will email all the TA's to hurry up with grading.
    :ivar reminder_email_time: The time the reminder email should be sent. To
        see if we should actually send these reminders look at `done_type`
    :ivar done_email: The email address we should sent a email if the grading
        is done. The function :py:func:`email.utils.getaddresses` should be
        able to parse this string.
    :ivar done_type: The type of reminder that should be sent.
    :ivar assigned_graders: All graders that are assigned to grade mapped by
        user_id to `AssignmentAssignedGrader` object.
    :ivar rubric_rows: The rubric rows that make up the rubric for this
        assignment.
    """
    __tablename__ = "Assignment"
    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column('name', db.Unicode, nullable=False)
    _cgignore = db.Column('cgignore', db.Unicode)
    _cgignore_version = db.Column('cgignore_version', db.Unicode)

    visibility_state = db.Column(
        'visibility_state',
        db.Enum(AssignmentVisibilityState),
        default=AssignmentVisibilityState.visible,
        nullable=False,
    )
    _state = db.Column(
        'state',
        db.Enum(AssignmentStateEnum, name='_assignmentstateenum'),
        default=AssignmentStateEnum.hidden,
        nullable=False,
    )

    kind = db.Column(
        'kind',
        db.Enum(AssignmentKind),
        default=AssignmentKind.normal,
        nullable=False,
        server_default='normal'
    )

    description = db.Column('description', db.Unicode, default='')
    course_id = db.Column(
        'Course_id', db.Integer, db.ForeignKey('Course.id'), nullable=False
    )
    created_at: ColumnProxy[DatetimeWithTimezone] = db.Column(
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False
    )
    _deadline = db.Column('deadline', db.TIMESTAMP(timezone=True))

    _mail_task_id = db.Column(
        'mail_task_id',
        db.Unicode,
        nullable=True,
        default=None,
    )
    reminder_email_time = db.Column(
        'reminder_email_time',
        db.TIMESTAMP(timezone=True),
        default=None,
        nullable=True,
    )
    done_email = db.Column(
        'done_email',
        db.Unicode,
        default=None,
        nullable=True,
    )
    done_type = db.Column(
        'done_type',
        db.Enum(AssignmentDoneType),
        nullable=True,
        default=None,
    )
    _max_grade = db.Column('max_grade', db.Float, nullable=True, default=None)

    # This is always `None` for LTI 1.3. As LTI 1.3 supports sending more than
    # the set maximum amount of points.
    lti_points_possible = db.Column(
        'lti_points_possible',
        db.Float,
        nullable=True,
        default=None,
    )

    # All stuff for LTI
    lti_assignment_id = db.Column(
        'lti_assignment_id', db.Unicode, nullable=True
    )
    is_lti = db.Column('is_lti', db.Boolean, nullable=False, default=False)

    # This is the lti outcome service url for LTI 1.1 and for LTI 1.3 this is
    # the data passed under the
    # "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint" claim.
    lti_grade_service_data: ColumnProxy[
        t.Union[None, '_AssignmentsGradersData', str]]
    lti_grade_service_data = db.Column(
        'lti_grade_service_data', JSON, nullable=True
    )

    assigned_graders: t.MutableMapping[
        int, AssignmentAssignedGrader] = db.relationship(
            'AssignmentAssignedGrader',
            cascade='delete-orphan, delete, save-update',
            collection_class=attribute_mapped_collection('user_id'),
            backref=db.backref('assignment', lazy='select')
        )
    division_parent_id = db.Column(
        'division_parent_id',
        db.Integer,
        db.ForeignKey('Assignment.id'),
        nullable=True,
    )
    division_parent = db.relationship(
        lambda: Assignment,
        back_populates='division_children',
        foreign_keys=division_parent_id,
        remote_side=[id],
        lazy='select',
    )
    division_children = db.relationship(
        lambda: Assignment,
        back_populates="division_parent",
        uselist=True,
        lazy='select',
    )

    finished_graders = db.relationship(
        lambda: AssignmentGraderDone,
        backref=db.backref('assignment'),
        cascade='delete-orphan, delete',
        uselist=True,
    )

    assignment_results: t.MutableMapping[
        int, AssignmentResult] = db.relationship(
            'AssignmentResult',
            collection_class=attribute_mapped_collection('user_id'),
            backref=db.backref('assignment', lazy='select')
        )

    course = db.relationship(
        lambda: course_models.Course,
        foreign_keys=course_id,
        back_populates='assignments',
        lazy='joined',
        innerjoin=True,
    )

    fixed_max_rubric_points = db.Column(
        'fixed_max_rubric_points',
        db.Float,
        nullable=True,
    )
    rubric_rows = db.relationship(
        lambda: rubric_models.RubricRowBase,
        back_populates='assignment',
        cascade='delete-orphan, delete, save-update',
        order_by=lambda: rubric_models.RubricRowBase.created_at,
        uselist=True,
    )

    analytics_workspaces = db.relationship(
        lambda: analytics_models.AnalyticsWorkspace,
        back_populates='assignment',
        cascade='delete-orphan, delete, save-update',
        uselist=True,
    )

    group_set_id = db.Column(
        'group_set_id',
        db.Integer,
        db.ForeignKey('GroupSet.id'),
        nullable=True,
    )

    group_set = db.relationship(
        lambda: psef.models.GroupSet,
        back_populates='assignments',
        cascade='all',
        uselist=False,
    )

    # This variable is available through a backref
    linters: ColumnProxy[t.Iterable['AssignmentLinter']]

    # This variable is available through a backref
    submissions: ColumnProxy[t.Iterable['work_models.Work']]

    auto_test_id = db.Column(
        'auto_test_id',
        db.Integer,
        db.ForeignKey('AutoTest.id'),
        nullable=True,
    )

    auto_test = db.relationship(
        lambda: auto_test_models.AutoTest,
        foreign_keys=auto_test_id,
        back_populates="assignment",
        cascade='all',
    )

    files_upload_enabled = db.Column(
        'files_upload_enabled',
        db.Boolean,
        default=True,
        server_default='true',
        nullable=False,
    )
    webhook_upload_enabled = db.Column(
        'webhook_upload_enabled',
        db.Boolean,
        default=False,
        server_default='false',
        nullable=False,
    )

    _cool_off_period = db.Column(
        'cool_off_period', db.Interval, default=None, nullable=True
    )

    _amount_in_cool_off_period = db.Column(
        'amount_in_cool_off_period',
        db.Integer,
        default=1,
        nullable=False,
        server_default='1',
    )

    _max_submissions = db.Column(
        'max_amount_of_submissions', db.Integer, default=None, nullable=True
    )

    peer_feedback_settings = db.relationship(
        AssignmentPeerFeedbackSettings,
        back_populates="assignment",
        uselist=False,
        cascade='delete-orphan,delete,save-update',
    )

    _available_at = db.Column(
        'available_at',
        db.TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )

    _send_login_links_token = db.Column(
        'send_login_links_token',
        UUIDType,
        nullable=True,
        default=None,
    )

    __table_args__ = (
        db.CheckConstraint(
            "files_upload_enabled or webhook_upload_enabled",
            name='upload_methods_check',
        ),
        db.CheckConstraint(
            'amount_in_cool_off_period >= 1',
            name='amount_in_cool_off_period_check'
        ),
        db.CheckConstraint(
            (
                'available_at IS NULL OR deadline IS NULL OR available_at <'
                ' deadline'
            ),
            name='available_at_before_deadline',
        ),
        db.CheckConstraint(
            'send_login_links_token IS NULL OR available_at IS NOT NULL',
            name='send_login_links_only_valid_with_available_at',
        ),
        db.UniqueConstraint(
            lti_assignment_id,
            course_id,
            name='ltiassignmentid_courseid_unique',
        ),
    )

    @validator.validates(
        lambda: (
            Assignment._available_at,
            Assignment._deadline,
            Assignment._send_login_links_token,
        )
    )
    def _check_available_at_and_login_links(self) -> None:
        if not self.send_login_links:
            return

        if self.available_at is None or self.deadline is None:
            raise APIException(
                (
                    'Login links can only be enabled when an available at and'
                    ' deadline is set'
                ), f'Some required data was missing for assignment {self.id}',
                APICodes.INVALID_STATE, 409
            )

        max_time = psef.current_app.config['EXAM_LOGIN_MAX_LENGTH']
        if (self.deadline - self.available_at) > max_time:
            raise APIException(
                (
                    'Login links can only be enabled if the deadline is at'
                    ' most {} after the available at date'
                ).format(humanize.timedelta(max_time, no_prefix=True)),
                (
                    f'The assignment {self.id} has too long between deadline'
                    f' and available at'
                ),
                APICodes.INVALID_STATE,
                409,
            )

    @validator.validates(
        lambda: (Assignment._available_at, Assignment._deadline)
    )
    def _check_available_at_and_deadline(self) -> None:
        if self.available_at is None or self.deadline is None:
            return
        if self.available_at >= self.deadline:
            raise APIException(
                'The assignment should become available before the deadline.',
                'The available_at is at or after the deadline',
                APICodes.INVALID_STATE, 409
            )

    @validator.validates(
        lambda: (Assignment.kind, Assignment._send_login_links_token)
    )
    def _check_normal_assignment_login_links(self) -> None:
        if self.kind.is_normal and self.send_login_links:
            raise APIException(
                'Login links are only available for exam mode assignments',
                f'The assignment {self.id} is not an exam assignment',
                APICodes.INVALID_STATE, 409
            )

    @validator.validates(
        lambda: (
            Assignment.kind,
            Assignment._available_at,
            Assignment._deadline,
        )
    )
    def _check_kind_and_required_data(self) -> None:
        if self.kind.is_exam and (
            self.available_at is None or self.deadline is None
        ):
            raise APIException(
                (
                    'Exam mode assignments are required to set an available at'
                    ' and deadline'
                ), f'Some required data was missing for assignment {self.id}',
                APICodes.INVALID_STATE, 409
            )

    @validator.validates(lambda: (Assignment.is_lti, Assignment.kind))
    def _exam_mode_not_for_lti(self) -> None:
        if self.is_lti and self.kind.is_exam:
            raise APIException(
                'Exam mode is not available for LTI assignments',
                'You cannot combine LTI assignments and exam mode',
                APICodes.INVALID_STATE, 409
            )

    def __init__(
        self,
        course: 'course_models.Course',
        is_lti: bool,
        name: str = None,
        visibility_state: AssignmentVisibilityState = (
            AssignmentVisibilityState.visible
        ),
        state: AssignmentStateEnum = None,
        deadline: DatetimeWithTimezone = None,
        lti_assignment_id: str = None,
        description: str = ''
    ) -> None:
        super().__init__(
            course=course,
            course_id=course.id,
            name=name,
            visibility_state=visibility_state,
            state=state,
            _deadline=deadline,
            lti_assignment_id=lti_assignment_id,
            description=description,
            is_lti=is_lti,
            analytics_workspaces=[
                analytics_models.AnalyticsWorkspace(assignment=self)
            ],
            kind=AssignmentKind.normal,
        )
        self._changed_ambiguous_settings: t.Set[AssignmentAmbiguousSettingTag]
        self._on_orm_load()

        signals.ASSIGNMENT_CREATED.send(self)

    @sqlalchemy.orm.reconstructor
    def _on_orm_load(self) -> None:
        self._changed_ambiguous_settings = set()

    def __structlog__(self) -> t.Mapping[str, t.Union[str, int]]:
        return {
            'type': self.__class__.__name__,
            'id': self.id,
            'visibility_state': self.visibility_state.name,
            'course_id': self.course_id,
        }

    def __eq__(self, other: object) -> bool:
        """Check if two Assignments are equal."""
        if isinstance(other, Assignment):
            return self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.id, ))

    def _get_deadline(self) -> t.Optional[DatetimeWithTimezone]:
        return self._deadline

    def _set_deadline(
        self, new_deadline: t.Optional[DatetimeWithTimezone]
    ) -> None:
        if self._deadline != new_deadline:
            self._deadline = new_deadline
            self._changed_ambiguous_settings.add(
                AssignmentAmbiguousSettingTag.deadline
            )
            signals.ASSIGNMENT_DEADLINE_CHANGED.send(self)

    deadline = hybrid_property(_get_deadline, _set_deadline)

    @property
    def send_login_links_token(self) -> t.Optional[uuid.UUID]:
        """The login links token.

        This parameter is updated every time we reschedule the tasks to send
        the login links, and the token is also passed to the task. This makes
        it possible for the task to see if it should actually execute or not.
        Do not use a ``is None`` check to see if login tokens are enabled, but
        use ``send_login_links``.
        """
        return self._send_login_links_token

    @validates('group_set')
    def validate_group_set(
        self, _: str, group_set: t.Optional['psef.models.GroupSet']
    ) -> t.Optional['psef.models.GroupSet']:
        """Make sure the course id of the group set is the same as the course
        id of the assignment.
        """
        if group_set is not None:
            assert self.course_id == group_set.course_id
        return group_set

    @hybrid_property
    def is_visible(self) -> bool:
        """Is this assignment visible to users.

        The value of this property does not depend on the current user at this
        moment.
        """
        return self.visibility_state == AssignmentVisibilityState.visible

    def mark_as_deleted(self) -> None:
        self.visibility_state = AssignmentVisibilityState.deleted

    GRADE_SCALE = 10

    @property
    def max_grade(self) -> float:
        """Get the maximum grade possible for this assignment.

        :returns: The maximum a grade for a submission.
        """
        return self.GRADE_SCALE if self._max_grade is None else self._max_grade

    @property
    def cgignore(self) -> t.Optional[ignore.SubmissionFilter]:
        """The submission filter of this assignment.
        """
        if self._cgignore is None:
            return None
        elif self._cgignore_version is None:  # pragma: no cover
            # This branch is needed for backwards compatibility, but it is not
            # possible to test as it is not possible to insert this old data
            # using the api.
            return ignore.IgnoreFilterManager.parse(self._cgignore)
        else:
            filter_type = ignore.filter_handlers[self._cgignore_version]
            return filter_type.parse(json.loads(self._cgignore))

    @cgignore.setter
    def cgignore(self, val: ignore.SubmissionFilter) -> None:
        self._changed_ambiguous_settings.add(
            AssignmentAmbiguousSettingTag.cgignore
        )
        self._cgignore_version = ignore.filter_handlers.find(type(val), None)
        self._cgignore = json.dumps(val.export())

    def update_cgignore(self, version: str, data: 'helpers.JSONType') -> None:
        """Update the cgignore file of this assignment.

        :param version: The type of cgignore file to use. This should be
            registered with ``psef.ignore.filter_handlers``.
        :param data: The data to use for the cgignore, this should be
            compatible for the given ``version``.

        :raises APIException: If the ``version`` is unknown or if the ``data``
            is unsupported for the given ``version``.
        """
        filter_type = ignore.filter_handlers.get(version)
        if filter_type is None:
            raise APIException(
                'The given ignore version was not found.', (
                    'The known values are:'
                    f' {", ".join(ignore.filter_handlers.keys())}'
                ), APICodes.OBJECT_NOT_FOUND, 404
            )
        self.cgignore = filter_type.parse(data)

    @property
    def cool_off_period(self) -> datetime.timedelta:
        """The minimum amount of time there should be between two submissions
            from the same user.
        """
        if self._cool_off_period is None:
            return datetime.timedelta(seconds=0)
        return self._cool_off_period

    @cool_off_period.setter
    def cool_off_period(self, delta: datetime.timedelta) -> None:
        self._changed_ambiguous_settings.add(
            AssignmentAmbiguousSettingTag.cool_off
        )
        self._cool_off_period = delta

    @property
    def amount_in_cool_off_period(self) -> int:
        """The maximum amount of submissions that a user may create inside the
            cool off period.

        .. warning::

            Setting this property may raise an :exc:`.APIException` if the
            value is not valid.
        """
        return self._amount_in_cool_off_period

    @amount_in_cool_off_period.setter
    def amount_in_cool_off_period(self, new_amount: int) -> None:
        if new_amount < 1:
            raise APIException(
                (
                    'The minimum amount of submissions that can be done in a'
                    ' cool of period should be at least one'
                ), (
                    f'The given amount {new_amount} is too low for'
                    ' `amount_in_cool_off_period`'
                ), APICodes.INVALID_PARAM, 400
            )
        self._amount_in_cool_off_period = new_amount

    @property
    def max_submissions(self) -> t.Optional[int]:
        """The maximum amount of submissions a user is allowed to make.

        .. warning::

            Setting this property is not pure! It may raise an
            :exc:`.APIException` if the value is not valid, it may add a
            warning to the response, and it may change the
            ``_changed_ambiguous_settings`` attribute. Furthermore, it may also
            be slow as it will query the database.
        """
        return self._max_submissions

    @max_submissions.setter
    def max_submissions(self, max_submissions: t.Optional[int]) -> None:
        self._changed_ambiguous_settings.add(
            AssignmentAmbiguousSettingTag.max_submissions
        )
        if helpers.handle_none(max_submissions, 1) <= 0:
            raise APIException(
                'You have to allow at least one submission',
                'The set maximum amount of submissions is too low',
                APICodes.INVALID_PARAM, 400
            )

        if max_submissions is not None and db.session.query(
            self.get_not_deleted_submissions().group_by(
                work_models.Work.user_id
            ).having(sql_expression.func.count() > max_submissions).exists()
        ).scalar():
            helpers.add_warning(
                (
                    'There are already users with more submission than the'
                    ' set max submissions amount'
                ),
                APIWarnings.LIMIT_ALREADY_EXCEEDED,
            )

        self._max_submissions = max_submissions

    def _state_getter(self) -> AssignmentStateEnum:
        return self._state

    def _state_setter(self, new_value: AssignmentStateEnum) -> None:
        if self.available_at is not None and not new_value.is_done:
            now = helpers.get_request_start_time()
            expired = now >= self.available_at
            new_value = (
                AssignmentStateEnum.open
                if expired else AssignmentStateEnum.hidden
            )

        if new_value == self._state:
            return

        self._state = new_value
        signals.ASSIGNMENT_STATE_CHANGED.send(self)

    state = hybrid_property(_state_getter, _state_setter)

    def _schedule_send_login_links(self) -> None:
        if self.deadline_expired:
            helpers.add_warning(
                (
                    'The deadline for this assignment already expired, so we'
                    ' will not send any login links.'
                ), APIWarnings.ALREADY_EXPIRED
            )
        token = uuid.uuid4()
        self._send_login_links_token = token
        assig_id = self.id

        tasks = []
        for offset in psef.current_app.config['LOGIN_TOKEN_BEFORE_TIME']:
            task = task_result_models.TaskResult(user=None)
            db.session.add(task)
            tasks.append((offset, task))

        def _after_req() -> None:
            assert self.available_at is not None
            now = helpers.get_request_start_time()
            for idx, (offset, task) in enumerate(tasks):
                eta = self.available_at - offset
                if eta < now and idx != len(tasks) - 1:
                    continue

                psef.tasks.send_login_links_to_users(
                    (assig_id, task.id.hex, eta.isoformat(), token.hex, idx),
                    eta=eta,
                )

        callback_after_this_request(_after_req)

    @property
    def send_login_links(self) -> bool:
        """Should we send login links to the users with permissions to receive
        one.
        """
        return self.send_login_links_token is not None

    @send_login_links.setter
    def send_login_links(self, new_value: bool) -> None:
        if new_value == self.send_login_links:
            return

        if new_value:
            self._schedule_send_login_links()
        else:
            self._send_login_links_token = None

    @property
    def available_at(self) -> t.Optional[DatetimeWithTimezone]:
        """At what time should this assignment become available.
        """
        return self._available_at

    @available_at.setter
    def available_at(
        self, new_value: t.Optional[DatetimeWithTimezone]
    ) -> None:
        old_value = self._available_at
        self._available_at = new_value

        if new_value is None:
            return

        # The state setter sets this to the correct value based on the
        # expiration state.
        if not self.state.is_done:
            self.state = AssignmentStateEnum.open

        if old_value == new_value:
            return

        now = helpers.get_request_start_time()
        expired = now >= new_value
        if not expired:
            callback_after_this_request(
                lambda: psef.tasks.maybe_open_assignment_at(
                    (self.id, ),
                    eta=new_value,
                )
            )
        if self.send_login_links:
            self._schedule_send_login_links()

    # We don't use property.setter because in that case `new_val` could only be
    # a `float` because of https://github.com/python/mypy/issues/3004
    def set_max_grade(self, new_val: t.Union[None, float, int]) -> None:
        """Set or unset the maximum grade for this assignment.

        :param new_val: The new value for ``_max_grade``.
        :return: Nothing.
        """
        self._max_grade = new_val

    #: The minimum grade for a submission in this assignment.
    min_grade = 0

    def change_notifications(
        self,
        done_type: t.Optional[AssignmentDoneType],
        grader_date: t.Optional[DatetimeWithTimezone],
        done_email: t.Optional[str],
    ) -> None:
        """Change the notifications for the current assignment.

        :param done_type: How to determine when the assignment is done. Set
            this value to ``None`` to disable the reminder for this assignment.
        :param grader_date: The datetime when to send graders that are causing
            the assignment to be not done a reminder email.
        :param done_email: The email to send a notification when grading for
            this assignment is done.
        """
        if self._mail_task_id is not None:
            psef.tasks.celery.control.revoke(self._mail_task_id)

        self.done_type = done_type

        # Make sure _reminder_email_time is ``None`` if ``done_type`` is
        # ``none``
        self.reminder_email_time = None if done_type is None else grader_date
        self.done_email = None if done_type is None else done_email

        if self.reminder_email_time is None:
            # Make sure id is reset so we don't revoke it multiple times
            self._mail_task_id = None
        else:
            res = psef.tasks.send_reminder_mails((self.id, ), eta=grader_date)
            self._mail_task_id = res.id

    def graders_are_done(self) -> bool:
        """Check if the graders of this assignment are done.

        :returns: A boolean indicating if the graders of this assignment are
            done.
        """
        if self.done_type is None:
            # We are never done as we have no condition to be done
            return False
        elif self.done_type == AssignmentDoneType.assigned_only:
            assigned = set(self.get_assigned_grader_ids())
            finished = set(fg.user_id for fg in self.finished_graders)
            # Check if every assigned grader is done.
            return assigned.issubset(finished)
        elif self.done_type == AssignmentDoneType.all_graders:
            # All graders should be done. As finished_graders all have unique
            # user ids we simply need to check if the lengths are the same
            return len(self.finished_graders) == self.get_all_graders().count()

        # This is needed because of https://github.com/python/mypy/issues/4223
        # and to please pylint
        raise ValueError(
            f'The assignment has a invalid `done_type`: {self.done_type}'
        )  # pragma: no cover

    def get_assigned_grader_ids(self) -> t.Iterable[int]:
        """Get the ids of all the graders that have submissions assigned.

        .. note::

            This only gets graders with latest submissions assigned to them.

        :returns: The ids of the all the graders that have work assigned within
            this assignnment.
        """
        query = self.get_from_latest_submissions(
            work_models.Work.assigned_to,
        ).distinct().filter(work_models.Work.assigned_to.isnot(None))

        # The last check (`user_id is not None`) is only needed for mypy to let
        # it know that this generator will never yield `None`.
        return (user_id for user_id, in query if user_id is not None)

    def set_graders_to_not_done(
        self,
        user_ids: t.Sequence[int],
        send_mail: bool = False,
        ignore_errors: bool = False,
    ) -> None:
        """Set the status of the given graders to 'not done'.

        :param user_ids: The ids of the users that should be set to 'not done'
        :param send_mail: If ``True`` the users who are reset to 'not done'
            will get an email notifying them of this.
        :param ignore_errors: Do not raise an error if a user in ``user_ids``
            was not yet done.
        :raise ValueError: If a user in ``user_ids`` was not yet done. This can
            happen because the user has not indicated this yet, because this
            user does not exist or because of any reason.
        """
        if not user_ids:
            return

        graders = AssignmentGraderDone.query.filter(
            AssignmentGraderDone.assignment_id == self.id,
            AssignmentGraderDone.user_id.in_(user_ids),
        ).all()

        if not ignore_errors and len(graders) != len(user_ids):
            raise ValueError('Not all graders were found')

        for grader in graders:
            if send_mail:
                psef.tasks.send_grader_status_mail(self.id, grader.user_id)
            db.session.delete(grader)

    def has_non_graded_submissions(self, user_id: int) -> bool:
        """Check if the user with the given ``user_id`` has submissions
        assigned without a grade.

        :param user_id: The id of the user to check for

        :returns: A boolean indicating if user has work assigned that does not
                  have grade or a selected rubric item
        """
        latest = self.get_from_latest_submissions(work_models.Work.id)
        sql = latest.filter(
            work_models.Work.assigned_to == user_id,
        ).join(
            rubric_models.WorkRubricItem,
            rubric_models.WorkRubricItem.work_id == work_models.Work.id,
            isouter=True
        ).having(
            sql_expression.and_(
                sql_expression.func.count(
                    rubric_models.WorkRubricItem.rubricitem_id
                ) == 0,
                # We access _grade here directly as we need it to do this query
                work_models.Work._grade.is_(None)  # pylint: disable=protected-access
            )
        ).group_by(work_models.Work.id)

        return db.session.query(sql.exists()).scalar() or False

    @property
    def max_rubric_points(self) -> t.Optional[float]:
        """Get the maximum amount of points possible for the rubric

        .. note::

          This is always higher than zero (so also not zero).


        :returns: The maximum amount of points.
        """
        if self.fixed_max_rubric_points is not None:
            return self.fixed_max_rubric_points
        else:
            return self._dynamic_max_points

    @cached_property
    def locked_rubric_rows(
        self
    ) -> t.Mapping[int, 'rubric_models.RubricLockReason']:
        """Get the locked rubric rows of this assignment.

        :returns: A mapping from rubric row id to the reason why they are
            locked. Ids not in this mapping are not locked.
        """
        if self.auto_test is None:
            return {}
        return {
            s.rubric_row_id: rubric_models.RubricLockReason.auto_test
            for s in self.auto_test.all_suites
        }

    @property
    def deadline_expired(self) -> bool:
        """Has the deadline of this assignment expired.
        """
        if self.deadline is None:
            return False
        return self.deadline < helpers.get_request_start_time()

    @cached_property
    def _dynamic_max_points(self) -> t.Optional[float]:
        sub = db.session.query(
            sql_expression.func.max(rubric_models.RubricItem.points
                                    ).label('max_val')
        ).join(
            rubric_models.RubricRowBase, rubric_models.RubricRowBase.id ==
            rubric_models.RubricItem.rubricrow_id
        ).filter(rubric_models.RubricRowBase.assignment_id == self.id
                 ).group_by(rubric_models.RubricRowBase.id).subquery('sub')
        return db.session.query(sql_expression.func.sum(sub.c.max_val)
                                ).scalar()

    @property
    def is_open(self) -> bool:
        """Is the current assignment open, which means the assignment is in the
        state students submit work.
        """
        if self.deadline is None:
            return False
        if not self.state.is_open:
            return False
        return not self.deadline_expired

    @property
    def is_hidden(self) -> bool:
        """Is the assignment hidden.
        """
        return self.state == AssignmentStateEnum.hidden

    @property
    def is_done(self) -> bool:
        """Is the assignment done, which means that grades are open.
        """
        return self.state.is_done

    @property
    def should_passback(self) -> bool:
        """Should we passback the current grade.
        """
        return self.is_done and self.is_lti

    @property
    def state_name(self) -> str:
        """The current name of the grade.

        .. warning:: This is not the same as ``str(self.state)``.

        :returns: The correct name of the current state.
        """
        if self.state.is_open:
            return 'submitting' if self.is_open else 'grading'
        return AssignmentStateEnum(self.state).name

    @property
    def whitespace_linter_exists(self) -> bool:
        """Does this assignment have a whitespace linter.
        """
        # pylint: disable=attribute-defined-outside-init
        # _whitespace_linter_exists is a cache property, so this is why it is
        # defined outside of the init.
        if not hasattr(self, '_whitespace_linter_exists'):
            self._whitespace_linter_exists = db.session.query(
                AssignmentLinter.get_whitespace_linter_query().filter(
                    AssignmentLinter.assignment_id == self.id,
                ).exists(),
            ).scalar()

        return self._whitespace_linter_exists

    @whitespace_linter_exists.setter
    def whitespace_linter_exists(self, exists: bool) -> None:
        """Preset the cache for ``whitespace_linter_exists`` reducing the
        amount of queries needed.
        """
        # pylint: disable=attribute-defined-outside-init
        # _whitespace_linter_exists is a cache property, so this is why it is
        # defined outside of the init.
        self._whitespace_linter_exists = exists

    @property
    def whitespace_linter(self) -> bool:
        """Check if this assignment has an associated MixedWhitespace linter.

        .. note::

            If the assignment is not yet done we check if the ``current_user``
            has the permission ``can_see_linter_feedback_before_done``.

        :returns: True if there is an :py:class:`.AssignmentLinter` with name
            ``MixedWhitespace`` and ``assignment_id``.
        """
        try:
            if not self.is_done:
                auth.ensure_permission(
                    CPerm.can_see_linter_feedback_before_done, self.course_id
                )
        except PermissionException:
            return False
        else:
            return self.whitespace_linter_exists

    def __to_json__(self) -> AssignmentJSON:
        """Creates a JSON serializable representation of this assignment.

        :returns: An :class:``.AssignmentJSON`` dictionary.

        .. todo:: Remove 'description' field from Assignment model.
        """
        # This property getter is quite expensive, and we evaluate it at most 3
        # times so caching it in a local variable is a good idea.
        cgignore = self.cgignore

        res: AssignmentJSON = {
            'id': self.id,
            'state': self.state_name,
            'description': self.description,
            'created_at': self.created_at,
            'deadline': self.deadline,
            'name': self.name,
            'is_lti': self.is_lti,
            'course_id': self.course_id,
            'cgignore': None if cgignore is None else cgignore.export(),
            'cgignore_version': self._cgignore_version,
            'whitespace_linter': self.whitespace_linter,
            'fixed_max_rubric_points': self.fixed_max_rubric_points,
            'max_grade': self._max_grade,
            'group_set': self.group_set,
            'auto_test_id': self.auto_test_id,
            'files_upload_enabled': self.files_upload_enabled,
            'webhook_upload_enabled': self.webhook_upload_enabled,
            'max_submissions': self.max_submissions,
            'cool_off_period': self.cool_off_period,
            'amount_in_cool_off_period': self.amount_in_cool_off_period,
            'peer_feedback_settings': self.peer_feedback_settings,
            'available_at': self.available_at,
            'send_login_links': self.send_login_links,
            'kind': self.kind,

            # These are all filled in based on permissions and data
            # availability.
            'reminder_time': None,
            'lms_name': None,
            'done_type': None,
            'done_email': None,
            'division_parent_id': None,
            'analytics_workspace_ids': [],
        }

        if not helpers.request_arg_true('no_course_in_assignment'):
            helpers.add_deprecate_warning(
                'The option to send a complete course with an assignment will'
                ' be removed in the next major release of CodeGrade'
            )
            res['course'] = self.course.__to_json__()  # type: ignore[misc]

        if self.course.lti_provider is not None:
            res['lms_name'] = self.course.lti_provider.lms_name

        if psef.current_user.has_permission(
            CPerm.can_grade_work,
            self.course_id,
        ):
            if self.done_email is not None:
                res['done_email'] = self.done_email
            if self.done_type is not None:
                res['done_type'] = self.done_type.name
            if self.reminder_email_time is not None:
                res['reminder_time'] = self.reminder_email_time.isoformat()
        if psef.current_user.has_permission(
            CPerm.can_see_assignee, self.course_id
        ):
            res['division_parent_id'] = self.division_parent_id

        for workspace in self.analytics_workspaces:
            if auth.AnalyticsWorkspacePermissions(workspace
                                                  ).ensure_may_see.as_bool():
                res['analytics_workspace_ids'].append(workspace.id)

        return res

    def set_state_with_string(self, state: str) -> None:
        """Update the current state (class:`AssignmentStateEnum`).

        You can update the state to hidden, done or open. A assignment can not
        be updated to 'submitting' or 'grading' as this is an assignment with
        state of 'open' and, respectively, a deadline before or after the
        current time.

        :param state: The new state, can be 'hidden', 'done' or 'open'
        :returns: Nothing
        """
        try:
            new_state = AssignmentStateEnum[state]
        except KeyError:
            raise InvalidAssignmentState(f'{state} is not a valid state')

        self.state = new_state

    def get_amount_not_deleted_submissions(self) -> int:
        return handle_none(
            self.get_not_deleted_submissions().with_entities(
                sql_expression.func.count(
                    cg_sqlalchemy_helpers.distinct(work_models.Work.user_id)
                )
            ).scalar(),
            0,
        )

    def get_not_deleted_submissions(self) -> MyQuery['work_models.Work']:
        """Get a query returning all not deleted submissions to this
            assignment.

        This method returns a faster query than just filtering submissions on
        not deleted and an assignment, as it checks the state of the assignment
        itself separately.
        """
        base_query = db.session.query(
            work_models.Work,
        ).filter(
            work_models.Work.assignment == self,
            # We don't need the intelligent `deleted` attribute here from the
            # Work models, which also checks if the assignment is deleted, as
            # we already check this at the start of the function.
            ~work_models.Work._deleted,  # pylint: disable=protected-access
        )

        if not self.is_visible:
            return base_query.filter(sqlalchemy.sql.false())

        return base_query

    def get_latest_submission_for_user(
        self,
        user: 'user_models.User',
        *,
        group_of_user: t.Optional['group_models.Group'] = None,
    ) -> MyNonOrderableQuery['work_models.Work']:
        """Get the latest non deleted submission for a given user.

        This function returns a query, but also executes a query, so be careful
        in calling this in a loop.

        .. note::

            Be very careful when changing this function, it is important that
            it always returns the same submission for a user as
            `get_from_latest_submission`.

        :param user: The user to get the latest non deleted submission for.
        :param group_of_user: The group that the user belongs to for this
            assignment. This parameter prevents that the database is queried to
            check if the user is in a group.
        :returns: A query that should not be reordered that contains the latest
            submission for the given user.
        """
        base_query = self.get_not_deleted_submissions()

        user_ids = [user.id]
        order_bys = [
            work_models.Work.created_at.desc(),
            # Sort by id too so that when the date is exactly the same we can
            # still have well defined behavior (i.e. always get the same
            # submissions for a user.)
            work_models.Work.id.desc()
        ]

        group_user_id = None
        if group_of_user is not None:
            group_user_id = group_of_user.virtual_user_id
        elif self.group_set_id is not None:
            group_user_id = db.session.query(
                psef.models.Group.virtual_user_id
            ).filter_by(group_set_id=self.group_set_id).filter(
                psef.models.Group.members.any(user_models.User.id == user.id)
            ).scalar()
            if group_user_id is not None:
                user_ids.append(group_user_id)
                # Make sure that group submissions are ordered before user
                # submissions. This makes sure group submissions are always
                # seen as the latest submission, even if their created_at is a
                # bit later. This is the same behavior as
                # `get_from_latest_submission`.
                order_bys.insert(
                    0, (work_models.Work.user_id == group_user_id).desc()
                )

        return base_query.filter(
            work_models.Work.user_id.in_(user_ids),
        ).order_by(*order_bys).limit(1)

    @t.overload
    def get_from_latest_submissions(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self,
        __to_query: t.Type[_T_BASE],
        *,
        include_deleted: bool = False,
        include_old_user_submissions: bool = False,
    ) -> MyQuery[_T_BASE]:
        ...

    @t.overload
    def get_from_latest_submissions(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self,
        __to_query: DbColumn[T],
        *,
        include_deleted: bool = False,
        include_old_user_submissions: bool = False,
    ) -> MyQuery[t.Tuple[T]]:
        ...

    @t.overload
    def get_from_latest_submissions(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self,
        __first: DbColumn[T],
        __second: DbColumn[Y],
        *,
        include_deleted: bool = False,
        include_old_user_submissions: bool = False,
    ) -> MyQuery[t.Tuple[T, Y]]:
        ...

    def get_from_latest_submissions(  # pylint: disable=function-redefined
        self,
        *to_query: t.Any,
        include_deleted: bool = False,
        include_old_user_submissions: bool = False,
    ) -> MyQuery[t.Any]:
        """Get the given fields from all last submitted submissions.

        .. note::

            Be very careful when changing this function, it is important that
            it always returns the same submission for a user as
            `get_latest_submission_for_user`.

        :param to_query: The field to get from the last submitted submissions.
        :returns: A query object with the given fields selected from the last
            submissions.
        """
        base_query = db.session.query(*to_query).select_from(work_models.Work)
        if not self.is_visible:
            return base_query.filter(sqlalchemy.sql.false())

        # TODO: Investigate this subquery here. We need to do that right now as
        # other functions might use this method and might want to order in a
        # different way or do other distincts. But I have no idea how slow this
        # subquery makes the query, as postgres could optimize it out.
        sql = db.session.query(
            work_models.Work.id,
        ).filter(
            work_models.Work.assignment_id == self.id,
        ).order_by(
            work_models.Work.user_id,
            work_models.Work.created_at.desc(),
            # Sort by id too so that when the date is exactly the same we can
            # still have well defined behavior (i.e. always get the same
            # submissions for a user.)
            work_models.Work.id.desc()
        )
        if not include_deleted:
            sql = sql.filter_by(_deleted=False)

        sub = sql.distinct(work_models.Work.user_id).subquery('ids')

        res = base_query.filter(work_models.Work.id.in_(sub), )
        if self.group_set_id is not None and not include_old_user_submissions:
            sub_query = db.session.query(work_models.Work).filter(
                work_models.Work.assignment_id == self.id,
                work_models.Work.user_id == psef.models.Group.virtual_user_id,
            )
            if not include_deleted:
                # We don't need the intelligent `deleted` attribute here from
                # the Work models, which also checks if the assignment is
                # deleted, as we already check this at the start of the
                # function.
                # pylint: disable=protected-access
                sub_query = sub_query.filter(~work_models.Work._deleted)
            groups_with_submission = db.session.query(
                psef.models.Group.id
            ).filter(
                psef.models.Group.group_set_id == self.group_set_id,
                sub_query.exists(),
            )
            res = res.filter(
                ~work_models.Work.user_id.in_(
                    db.session.query(users_groups.c.user_id).filter(
                        users_groups.c.group_id.in_(groups_with_submission)
                    )
                )
            )
        return res

    def get_all_latest_submissions(
        self,
        *,
        include_deleted: bool = False,
        include_old_user_submissions: bool = False,
    ) -> MyQuery['work_models.Work']:
        """Get a list of all the latest submissions
        (:class:`.work_models.Work`) by each :class:`.user_models.User` who has
        submitted at least one work for this assignment.

        :returns: The latest submissions.
        """
        # get_from_latest_submissions uses SQLAlchemy magic that MyPy cannot
        # encode.
        return self.get_from_latest_submissions(
            work_models.Work,
            include_deleted=include_deleted,
            include_old_user_submissions=include_old_user_submissions,
        )

    def get_divided_amount_missing(
        self
    ) -> t.Tuple[t.Mapping[int, float], t.Callable[[int, DefaultArg(bool)], t.
                                                   Mapping[int, float]]]:
        """Get a mapping between user and the amount of submissions that they
        should be assigned but are not.

        For example if we have two graders, John and Dorian that respectively
        have the weights 1 and 1 assigned. Lets say we have three submissions
        divided in such a way that John has to grade 2 and Dorian has to grade
        one, then our function we return that John is missing -0.5 submissions
        and Dorian is missing 0.5.

        .. note::

            If ``self.assigned_graders`` is empty this function and its
            recalculate will always return an empty directory.

        :returns: A mapping between user int and the amount missing as
            described above. Furthermore it returns a function that can be used
            to recalculate this mapping by given it the user id of the user
            that was assigned a submission.
        """
        if not self.assigned_graders:
            return {}, lambda _, __=False: {}

        total_weight = sum(w.weight for w in self.assigned_graders.values())

        amount_subs: int
        amount_subs = self.get_from_latest_submissions(  # type: ignore
            sql_expression.func.count(),
        ).scalar()

        divided_amount: t.MutableMapping[int, float] = defaultdict(float)
        for u_id, amount in self.get_from_latest_submissions(
            work_models.Work.assigned_to, sql_expression.func.count()
        ).group_by(work_models.Work.assigned_to):
            if u_id is not None:
                divided_amount[u_id] = amount

        missing = {}
        for user_id, assigned in self.assigned_graders.items():
            missing[user_id] = (assigned.weight / total_weight *
                                amount_subs) - divided_amount[user_id]

        def __recalculate(user_id: int, increment_sub_amount: bool = True
                          ) -> t.MutableMapping[int, float]:
            nonlocal amount_subs

            if increment_sub_amount:
                amount_subs += 1
            divided_amount[user_id] += 1
            missing = {}

            for assigned_user_id, assigned in self.assigned_graders.items():
                missing[assigned_user_id] = (
                    assigned.weight / total_weight * amount_subs
                ) - divided_amount[assigned_user_id]

            return missing

        return missing, __recalculate

    def _weights_changed(
        self, user_weights: t.Sequence[t.Tuple['user_models.User', float]]
    ) -> bool:
        """Check if the given users and their weights have changed since the
        last division.

        :param user_weights: A list of tuples that map users and the weights.
            The weights are used to determine how many submissions should be
            assigned to a single user.
        :returns: If the weights have changed.
        """
        if len(user_weights) == len(self.assigned_graders):
            for user, weight in user_weights:
                if (
                    user.id not in self.assigned_graders or
                    self.assigned_graders[user.id].weight != weight
                ):
                    break
            else:
                return False

        return True

    def divide_submissions(
        self, user_weights: t.Sequence[t.Tuple['user_models.User', float]]
    ) -> None:
        """Divide all newest submissions for this assignment between the given
        users.

        This methods prefers to keep submissions assigned to the same grader as
        much as possible. To get completely new and random assignments first
        clear all old assignments.

        :param user_weights: A list of tuples that map users and the weights.
            The weights are used to determine how many submissions should be
            assigned to a single user.
        :returns: Nothing.
        """
        # If the weights are not changed we should not divide anything as that
        # would mean that pressing the button again on accident might change
        # the (custom) division.
        if not self._weights_changed(user_weights):
            return

        submissions = self.get_all_latest_submissions().join(
            work_models.Work.user
        ).filter(~user_models.User.is_test_student).all()
        shuffle(submissions)

        counts: t.MutableMapping[int, int] = defaultdict(int)
        user_submissions: t.MutableMapping[t.Optional[int], t.List[work_models.
                                                                   Work]]
        user_submissions = defaultdict(list)

        # Remove all users not in user_weights
        new_users = set(u.id for u, _ in user_weights)
        for submission in submissions:
            if submission.assigned_to not in new_users:
                submission.assigned_to = None
            else:
                counts[submission.assigned_to] += 1
            user_submissions[submission.assigned_to].append(submission)

        new_total_weight = sum(weight for _, weight in user_weights)

        negative_weights, positive_weights = {}, {}
        for user, new_weight in user_weights:
            percentage = (new_weight / new_total_weight)
            new = percentage * len(submissions)

            if new < counts[user.id]:
                negative_weights[user.id] = counts[user.id] - new
            elif new > counts[user.id]:
                positive_weights[user.id] = new - counts[user.id]

        for user_id, delete_amount in negative_weights.items():
            for sub in user_submissions[user_id][:round(delete_amount)]:
                user_submissions[None].append(sub)

        to_assign: t.List[int] = []
        if positive_weights:
            ratio = math.ceil(1 / min(1, max(positive_weights.values())))
            for user_id, new_amount in positive_weights.items():
                to_assign += [user_id] * round(new_amount * ratio)

        shuffle(to_assign)
        newly_assigned: t.Set[int] = set()
        for sub, user_id in zip(user_submissions[None], cycle(to_assign)):
            sub.assigned_to = user_id
            newly_assigned.add(user_id)

        self.set_graders_to_not_done(
            list(newly_assigned),
            send_mail=True,
            ignore_errors=True,
        )

        self.assigned_graders = {}
        for user, weight in user_weights:
            db.session.add(
                AssignmentAssignedGrader(
                    weight=weight, user_id=user.id, assignment=self
                )
            )

    def get_assignee_from_division_children(self, student_id: int
                                            ) -> t.Optional[int]:
        """Get id of the most common grader for a student in the division
        children of this assignment.

        If this is tied a user is chosen arbitrarily from the most common
        graders. If the student is not present in the children ``None`` is
        returned.

        :param student_id: The id of the student you want to get the assignee
            for.
        :returns: The id of the assignee, or ``None`` if there is none.
        """
        assert self.division_children
        assert not self.division_parent_id

        shuffled_children = list(self.division_children)
        shuffle(shuffled_children)

        def get_other_assignees() -> t.Iterable[int]:
            for child in shuffled_children:
                assignee_id = child.get_from_latest_submissions(
                    work_models.Work.assigned_to
                ).filter(work_models.Work.user_id == student_id).first()
                if assignee_id is not None and assignee_id[0] is not None:
                    yield assignee_id[0]

        latest = Counter(get_other_assignees())
        if latest:
            return latest.most_common(1)[0][0]
        return None

    def get_assignee_for_submission(
        self, sub: 'work_models.Work', *, from_divided: bool = True
    ) -> t.Optional[int]:
        """Get the id of the default assignee for a given submission.

        This checks if a user has handed in a submission to this assignment
        before. In that is the case the same assignee is returned. Otherwise,
        if the assignment has a division parent it checks for an assignee
        there, and uses the value if it is not ``None``.

        If the assignment doesn't have a submission by the same user and is a
        parent it will search through the children. There the most common
        assignee for the submitting user is found. If such an assignee exists
        this value is returned.

        Finally if ``from_divided`` is enabled it finds a assignee among the
        divided graders. If no assignee is found ``None`` is returned.

        :param sub: The submission you want to get the assignee for.
        :param from_divided: Get a grader from the divided graders if all other
            methods fail.
        :returns: The id of the assignee or ``None`` if no assignee was found.
        """
        if sub.user.is_test_student:
            return None

        user_id = self.get_from_latest_submissions(
            work_models.Work.assigned_to
        ).filter(work_models.Work.user_id == sub.user_id).first()
        if user_id is not None:
            return user_id[0]

        if self.division_parent is not None:
            user = self.division_parent.get_assignee_for_submission(
                sub, from_divided=False
            )
            if user is not None:
                return user
        elif self.division_children:
            most_common = self.get_assignee_from_division_children(sub.user_id)
            if most_common is not None:
                return most_common

        if from_divided:
            missing, _ = self.get_divided_amount_missing()
            if missing:
                return max(missing.keys(), key=missing.get)
        return None

    def connect_division(self, parent: t.Optional['Assignment']
                         ) -> t.List['work_models.Work']:
        """Set the division parent of this assignment.

        :param parent: The assignment that should be the new division parent of
            this assignment. Set this to ``None`` to remove the division parent
            of this assignment.
        :returns: A list of submissions that couldn't be assigned and are left
            unassigned.
        """
        # If we unset the division parent we don't touch the divisions at all.
        if parent is None:
            self.division_parent = None
            return []

        assert parent.division_parent is None
        assert parent.course_id == self.course_id
        if self.division_parent_id == parent.id:
            return []

        # We first empty this value. This is needed as
        # `AssignmentAssignedGrader` objects have a primary key constraint on
        # the tuple `(assignment_id, user_id)`. If a assignee only changes
        # weight sqlalchemy gets confused as this tuple doesn't change. This is
        # a bit slower (as the flush does a db roundtrip) but fixes that issue.
        # TODO: Investigate if this is possible without the db.session.flush()
        self.assigned_graders = {}
        db.session.flush()
        self.assigned_graders = {
            key: AssignmentAssignedGrader(
                weight=value.weight,
                user_id=value.user_id,
                assignment_id=self.id
            )
            for key, value in parent.assigned_graders.items()
        }
        self.division_parent = parent
        user_sub = {s.user_id: s for s in self.get_all_latest_submissions()}
        todo = {}
        for sub in user_sub.values():
            sub.assigned_to = None
            todo[sub.id] = sub

        for user_id, assigned_to in parent.get_from_latest_submissions(
            work_models.Work.user_id,
            work_models.Work.assigned_to,
        ):
            if user_id in user_sub:
                user_sub[user_id].assigned_to = assigned_to
                if user_sub[user_id].assigned_to:
                    del todo[user_sub[user_id].id]

        db.session.flush()
        missing, recalc = self.get_divided_amount_missing()
        for sub in list(todo.values()):
            if sub.user.is_test_student:
                # Remove from todo as we simply do not want to assign these
                # submissions.
                del todo[sub.id]
                continue

            other = parent.get_assignee_from_division_children(sub.user_id)
            if other is None and missing:
                other = max(missing.keys(), key=missing.get)
            sub.assigned_to = other
            if sub.assigned_to is not None:
                recalc(sub.assigned_to, False)
                del todo[sub.id]
        return list(todo.values())

    def get_all_graders(
        self, sort: bool = True
    ) -> 'MyQuery[t.Tuple[str, int, bool]]':
        """Get all graders for this assignment.

        The graders are retrieved from the database using a single query. The
        return value is a query with three items selected: the first is the
        name of the grader, the second is the database id of the user object
        of grader and the third and last is a boolean indicating if this grader
        is done grading. You can use this query as an iterator.

        :param sort: Should the graders be sorted by name.
        :returns: A query with items selected as described above.
        """
        done_graders = db.session.query(
            user_models.User.name.label("name"),
            user_models.User.id.label("id"),
            # This now can be NULL as we do an outerjoin on assignments graders
            # done. It is `None` for every grader that is not yet done.
            ~AssignmentGraderDone.user_id.is_(
                t.cast(t.Any, None),
            ).label("done"),
            user_course.c.course_id.label("course_id"),
        ).join(
            AssignmentGraderDone,
            sql_expression.and_(
                user_models.User.id == AssignmentGraderDone.user_id,
                AssignmentGraderDone.assignment_id == self.id,
            ),
            isouter=True
        ).join(
            user_course,
            user_models.User.id == user_course.c.user_id,
        ).subquery('done_graders')

        graders = db.session.query(course_permissions.c.course_role_id).join(
            CourseRole,
            CourseRole.id == course_permissions.c.course_role_id,
        ).join(
            Permission,
            course_permissions.c.permission_id == Permission.id,
        ).filter(
            CourseRole.course_id == self.course_id,
            t.cast(
                PermissionComp[CPerm],
                Permission[CPerm].value,  # type: ignore[misc]
            ) == CPerm.can_grade_work,
        ).subquery('graders')

        res = db.session.query(
            # We cast here so that we get an accurately types query, as
            # `RawTable.c.{something}` is currently always typed as `Any`.
            t.cast(DbColumn[str], done_graders.c.name),
            t.cast(DbColumn[int], done_graders.c.id),
            t.cast(DbColumn[bool], done_graders.c.done),
        ).join(graders, done_graders.c.course_id == graders.c.course_role_id)

        if sort:
            res = res.order_by(sql_expression.func.lower(done_graders.c.name))

        return res

    def has_group_submissions(self) -> bool:
        """Check if the assignment has submissions by a group.

        :returns: ``True`` if the assignment has a submission by a group.
        """
        return db.session.query(
            db.session.query(
                work_models.Work
            ).filter_by(assignment_id=self.id, deleted=False).join(
                user_models.User,
                user_models.User.id == work_models.Work.user_id
            ).join(psef.models.Group).exists()
        ).scalar()

    def get_author_handing_in(
        self, request_args: t.Mapping[str, str]
    ) -> 'user_models.User':
        """Get the author handing in a submission from the request arguments.

        This function also validates that the current user is allowed to
        hand-in a submission as the given user.

        :param request_args: The GET request arguments of the request.
        :returns: The :class:`.user_models.User` that should be the author of
            the submission.
        """
        given_author = request_args.get('author', None)
        is_test_submission = helpers.request_arg_true(
            'is_test_submission', request_args
        )
        logger.info(
            'Uploading submission',
            is_test_submission=is_test_submission,
            given_author=given_author,
            assignment_id=self.id,
        )

        if given_author is not None and is_test_submission:
            raise APIException(
                'You cannot provide an author for a test submission', (
                    'The options `given_author` and `is_test_submission`'
                    ' cannot be combined'
                ), APICodes.INVALID_PARAM, 400
            )

        if self.deadline is None and not is_test_submission:
            msg = (
                'The deadline for this assignment has not yet been set. '
                'Please ask your teacher to set a deadline before you can '
                'submit your work.'
            )
            if psef.current_user.has_permission(
                CPerm.can_submit_others_work, self.course_id
            ):
                msg += ' You can still upload a test submission.'
            raise APIException(
                msg,
                f'The deadline for assignment {self.name} is unset.',
                APICodes.ASSIGNMENT_DEADLINE_UNSET,
                400,
            )

        if is_test_submission:
            author = self.course.get_test_student()
            db.session.flush()
        elif given_author is None:
            author = psef.current_user
        else:
            author = helpers.filter_single_or_404(
                user_models.User,
                user_models.User.username == given_author,
                also_error=lambda user: user.is_test_student,
            )

        if self.group_set and not author.is_test_student:
            group = self.group_set.get_valid_group_for_user(author)
            resulting_author = author if group is None else group.virtual_user
        else:
            resulting_author = author

        auth.ensure_can_submit_work(
            self, author=resulting_author, for_user=author
        )

        return resulting_author

    def has_webhooks(self) -> bool:
        """Does this assignment have any connected webhooks.

        :returns: The presence of any webhooks for this assignment after
                  querying the database.
        """
        return db.session.query(
            psef.models.WebhookBase.query.filter_by(assignment=self).exists()
        ).scalar()

    def get_changed_ambiguous_combinations(
        self
    ) -> t.Iterator[_AssignmentAmbiguousSetting]:
        """Get all new ambiguous setting combinations on this assignment.

        This simply gets all ambiguous settings on an assignment and checks
        which settings were changed since the assignment was loaded from the
        database/created.
        """
        for warning in self.get_all_ambiguous_combinations():
            if warning.tags & self._changed_ambiguous_settings:
                yield warning

    def get_all_ambiguous_combinations(
        self
    ) -> t.Sequence[_AssignmentAmbiguousSetting]:
        """Get all ambiguous settings for an assignment.

        :returns: A list of ambiguous settings.
        """
        res = []

        if not isinstance(
            self.cgignore, (ignore.EmptySubmissionFilter, type(None))
        ) and self.webhook_upload_enabled:
            res.append(
                _AssignmentAmbiguousSetting(
                    tags={
                        AssignmentAmbiguousSettingTag.webhook,
                        AssignmentAmbiguousSettingTag.cgignore
                    },
                    message=(
                        'Hand-in requirements are currently ignored when'
                        ' handing in using Git'
                    )
                )
            )

        if (
            self.cool_off_period.total_seconds() > 0 and
            self.webhook_upload_enabled
        ):
            res.append(
                _AssignmentAmbiguousSetting(
                    tags={
                        AssignmentAmbiguousSettingTag.webhook,
                        AssignmentAmbiguousSettingTag.cool_off,
                    },
                    message=(
                        'When combining a cool off period with webhooks '
                        ' submissions can be silently ignored when students'
                        ' push too quickly.'
                    )
                )
            )

        if self.max_submissions is not None and self.webhook_upload_enabled:
            res.append(
                _AssignmentAmbiguousSetting(
                    tags={
                        AssignmentAmbiguousSettingTag.webhook,
                        AssignmentAmbiguousSettingTag.max_submissions,
                    },
                    message=(
                        'When combining a limit on submissions and webhooks'
                        ' submissions can be silently dropped, as the student'
                        ' might not check if a push results in a new'
                        ' submission.'
                    )
                )
            )

        return res

    def update_submission_types(
        self, *, webhook: t.Optional[bool], files: t.Optional[bool]
    ) -> None:
        """Update the enabled submission types for this assignment.

        This method has the side effect of possibly adding items to the
        ``_changed_ambiguous_settings`` attribute. So if you're setting
        multiple properties on the assignment make sure you call
        :meth:`.Assignment.get_changed_ambiguous_combinations` at the end. This
        method might also add a warning to the response.

        :param webhook: Should users be allowed to upload using webhooks. Pass
            ``None`` to keep the current option.
        :param files: Should users be allowed to upload files for a submission.
            Pass ``None`` to keep the current option.

        :raises APIException: If both ``webhook`` and ``files`` uploading will
            be disabled at the end of this method.
        """
        if files is not None:
            self.files_upload_enabled = files

        if webhook is not None:
            self._changed_ambiguous_settings.add(
                AssignmentAmbiguousSettingTag.webhook
            )

            self.webhook_upload_enabled = webhook
            if not self.webhook_upload_enabled and self.has_webhooks():
                helpers.add_warning(
                    (
                        'This assignment already has existing webhooks, these '
                        'will continue to work'
                    ), APIWarnings.EXISTING_WEBHOOKS_EXIST
                )

        if not any([self.webhook_upload_enabled, self.files_upload_enabled]):
            raise APIException(
                'At least one way of uploading needs to be enabled',
                'It is not possible to disable both webhook and files uploads',
                APICodes.INVALID_STATE, 400
            )
