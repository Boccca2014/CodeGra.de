"""This module defines all signals used by psef.

This file does not contain the implementation of the signals.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import dataclasses

from cg_signals import Signal

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    # pylint: disable=unused-import
    from . import PsefFlask, models

T = t.TypeVar('T')


@dataclasses.dataclass(frozen=True)
class WorkDeletedData:
    """Data emitted when a work is deleted in an assignment.

    .. TODO::

        The property ``new_latest`` is set for ``None`` if the latest group
        submission is deleted, however each user in the group might have
        personal submissions which are now the latest submission. We should
        handle this in some way.

    :ivar ~deleted_work: The :class:`.models.Work` that was deleted.
    :ivar ~was_latest: Was the deleted work the latest submission by the user.
    :ivar ~new_latest: The new latest work after this one is deleted
    """
    __slots__ = ('deleted_work', 'was_latest', 'new_latest')

    deleted_work: 'models.Work'
    was_latest: bool
    new_latest: t.Optional['models.Work']

    def __post_init__(self) -> None:
        if not self.was_latest:
            assert self.new_latest is None
        if self.new_latest is not None:
            assert self.new_latest.user_id == self.deleted_work.user_id
            assert self.new_latest.assignment_id == self.assignment_id

    @property
    def assignment(self) -> 'models.Assignment':
        """The assignment in which the work was deleted.
        """
        return self.deleted_work.assignment

    @property
    def assignment_id(self) -> int:
        """The id of assignment in which the work was deleted.
        """
        return self.deleted_work.assignment_id


@dataclasses.dataclass(frozen=True)
class UserToCourseData:
    """Data emitted when a user is added to a course.

    :ivar ~user: The :class:`.models.User` added to the course.
    :ivar ~course_role: The new :class:`.models.CourseRole` of the user in the
        course.
    """
    __slots__ = ('user', 'course_role')

    user: 'models.User'
    course_role: 'models.CourseRole'


WORK_CREATED = Signal['models.Work']('WORK_CREATED')
GRADE_UPDATED = Signal['models.Work']('GRADE_UPDATED')
ASSIGNMENT_STATE_CHANGED = Signal['models.Assignment'](
    'ASSIGNMENT_STATE_CHANGED'
)
FINALIZE_APP = Signal['PsefFlask']('FINALIZE_APP')
WORK_DELETED = Signal[WorkDeletedData]('WORK_DELETED')
USER_ADDED_TO_COURSE = Signal['UserToCourseData']('USER_ADDED_TO_COURSE')
ASSIGNMENT_CREATED = Signal['models.Assignment']('ASSIGNMENT_CREATED')
ASSIGNMENT_DEADLINE_CHANGED = Signal['models.Assignment'](
    'ASSIGNMENT_DEADLINE_CHANGED'
)


# We use this function to make sure the list has a type of Signal[object]
# and not Signal[Any]
def _make_all_signals_list(*s: Signal) -> t.Sequence[Signal[object]]:
    return list(s)


_ALL_SIGNALS = _make_all_signals_list(
    WORK_CREATED,
    GRADE_UPDATED,
    ASSIGNMENT_STATE_CHANGED,
    FINALIZE_APP,
    WORK_DELETED,
    USER_ADDED_TO_COURSE,
    ASSIGNMENT_CREATED,
    ASSIGNMENT_DEADLINE_CHANGED,
)


def init_app(app: 'PsefFlask') -> None:
    """Initialize the signals for this app.

    You should initialize the signals last.
    """
    for signal in _ALL_SIGNALS:
        signal.finalize_celery(app.celery)

    FINALIZE_APP.send(app)

    # Loop again to make it possible to setup celery tasks on the
    # `FINALIZE_APP` signal.
    for signal in _ALL_SIGNALS:
        signal.finalize_celery(app.celery)
