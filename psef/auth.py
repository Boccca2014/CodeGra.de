"""This module implements all authorization functions used by :py:mod:`psef`.

SPDX-License-Identifier: AGPL-3.0-only
"""
import copy
import typing as t
import itertools
import contextlib
from functools import wraps, partial

import oauth2
import structlog
import sqlalchemy
import humanfriendly
import flask_jwt_extended as flask_jwt
from flask import _app_ctx_stack  # type: ignore
from sqlalchemy import sql
from werkzeug.local import LocalProxy
from mypy_extensions import NoReturn
from typing_extensions import Final, Literal

import psef
from cg_json import JSONResponse
from cg_helpers import maybe_wrap_in_list
from cg_dt_utils import DatetimeWithTimezone
from psef.helpers import readable_join
from psef.exceptions import APICodes, APIException, PermissionException
from cg_sqlalchemy_helpers import func as sql_func
from cg_sqlalchemy_helpers import expression as sql_expression
from cg_cache.intra_request import cache_within_request
from cg_sqlalchemy_helpers.types import DbColumn, FilterColumn

from . import helpers
from .permissions import CoursePermission as CPerm
from .permissions import GlobalPermission as GPerm

logger = structlog.get_logger()

jwt = flask_jwt.JWTManager()  # pylint: disable=invalid-name

T = t.TypeVar('T', bound=t.Callable)


def init_app(app: t.Any) -> None:
    """Initialize the app by initializing our jwt manager.

    :param app: The flask app to initialize.
    """
    jwt.init_app(app)


def _get_login_exception(
    desc: str = 'No user was logged in.'
) -> PermissionException:
    return PermissionException(
        'You need to be logged in to do this.', desc, APICodes.NOT_LOGGED_IN,
        401
    )


def _raise_login_exception(desc: str = 'No user was logged in.') -> NoReturn:
    raise _get_login_exception(desc)


@jwt.revoked_token_loader
@jwt.expired_token_loader
@jwt.invalid_token_loader
@jwt.needs_fresh_token_loader
def _handle_jwt_errors(reason: str = 'No user was logged in.'
                       ) -> JSONResponse[PermissionException]:
    return JSONResponse.make(
        PermissionException(
            'You need to be logged in to do this.',
            reason,
            APICodes.NOT_LOGGED_IN,
            401,
        ),
        status_code=401,
    )


jwt.user_loader_error_loader(
    lambda id: _handle_jwt_errors(f'No user with id "{id}" was found.')
)

_T_PERM_CHECKER = t.TypeVar('_T_PERM_CHECKER', bound='PermissionChecker')  # pylint: disable=invalid-name
_T_COURSE_PERM_CHECKER = t.TypeVar(  # pylint: disable=invalid-name
    '_T_COURSE_PERM_CHECKER', bound='CoursePermissionChecker'
)


class _PermissionCheckFunction(t.Generic[_T_PERM_CHECKER]):
    __slots__ = ('__fn', )

    class _Inner:
        __slots__ = ('__fn', )

        def __init__(self, bound_fn: t.Callable[[], None]):
            self.__fn = bound_fn

        def __call__(self) -> None:
            self.__fn()

        def check(self) -> None:
            """This is just another way to call the checker, but in some cases
            (combining checkers) explicitly calling ``check`` can be more
            clear.
            """
            self.__fn()

        def and_(
            self, *others: '_PermissionCheckFunction._Inner'
        ) -> '_PermissionCheckFunction._Inner':
            """Combine this checker with other checkers to produce a checker
            that checks if all of the underlying checkers is satisfied.

            :param others: Other permission checkers that this checker should
                be combined with.

            :returns: A new checker, make sure to call this checker (see
                      :meth:`._PermissionCheckFunction.check` or
                      :meth:`._PermissionCheckFunction.as_bool`), otherwise
                      this method will not do anything useful.
            """

            def _inner() -> None:
                for checker in itertools.chain([self], others):
                    checker()

            return type(self)(_inner)

        def or_(
            self, *others: '_PermissionCheckFunction._Inner'
        ) -> '_PermissionCheckFunction._Inner':
            """Combine this checker with other checkers to produce a checker
            that checks if any of the underlying checkers is satisfied.

            :param others: Other permission checkers that this checker should
                be combined with.

            :returns: A new checker, make sure to call this checker (see
                      :meth:`._PermissionCheckFunction.check` or
                      :meth:`._PermissionCheckFunction.as_bool`), otherwise
                      this method will not do anything useful.
            """

            def _inner() -> None:
                err: t.Optional[PermissionException] = None
                for checker in itertools.chain([self], others):
                    try:
                        checker()
                    except PermissionException as exc:
                        err = err or exc
                    else:
                        return

                # err can never be ``None`` here, but this is needed for mypy
                assert err is not None

                raise err

            return type(self)(_inner)

        def as_bool(self) -> bool:
            """Get the result permission checker as a bool.

            :returns: ``True`` if the function didn't raise a
                :exc:`.PermissionException` and ``False`` if it did. This can
                be used to check if somebody has this higher level permission.
            """
            try:
                self()
            except PermissionException:
                return False
            else:
                return True

    def __init__(self, fn: t.Callable[[_T_PERM_CHECKER], None]) -> None:
        self.__fn = fn

    def __get__(
        self, instance: _T_PERM_CHECKER, owner: t.Type[_T_PERM_CHECKER]
    ) -> '_PermissionCheckFunction._Inner':
        return self.__class__._Inner(partial(self.__fn, instance))


class PermissionChecker:
    """The base permission checker class.
    """

    @staticmethod
    def all(
        initial: '_PermissionCheckFunction._Inner',
        *rest: '_PermissionCheckFunction._Inner'
    ) -> '_PermissionCheckFunction._Inner':
        """Check that the current user passes the given permission checkers.

        :param initial: A permission checker.
        :param rest: Other permission checkers this user should also pass.
        """
        return initial.and_(*rest)

    @property
    def user(self) -> 'psef.models.User':
        """The current logged in user.

        Accessing this property raises a :exc:`.PermissionException` if no user
        is logged in.
        """
        return _get_cur_user()


class CoursePermissionChecker(PermissionChecker):
    """The base permission checker class for course related permissions.
    """
    __slots__ = ('course', 'course_id')

    def __init__(self, course: 'psef.models.Course') -> None:
        super().__init__()

        self.course: Final = course
        self.course_id: Final = course.id

    @staticmethod
    def as_ensure_function(
        fun: t.Callable[[_T_COURSE_PERM_CHECKER], None]
    ) -> _PermissionCheckFunction[_T_COURSE_PERM_CHECKER]:
        """Wrap a permission checker function as a
            :class:`._PermissionCheckFunction`.

        This adds helper methods to the method like
        :meth:`._PermissionCheckFunction.as_bool`.
        """

        @wraps(fun)
        def __inner(self: _T_COURSE_PERM_CHECKER) -> None:
            self._ensure_course_visible()  # pylint: disable=protected-access
            fun(self)

        return _PermissionCheckFunction(__inner)

    def _ensure_course_visible(self) -> None:
        _ensure_course_visible_for_current_user(self.course)

    def _global_ensure(self, perm: GPerm) -> None:
        ensure_permission(perm, user=self.user)

    def _ensure(self, perm: CPerm, *, extra_message: str = '') -> None:
        ensure_permission(
            perm, self.course_id, user=self.user, extra_message=extra_message
        )

    def _ensure_for_course(
        self, perm: CPerm, *, course: 'psef.models.Course'
    ) -> None:
        ensure_permission(perm, course_id=course.id, user=self.user)

    def _ensure_if_not(
        self, checker: t.Callable[[], bool],
        perms: t.Union[t.List[CPerm], CPerm]
    ) -> None:
        """Ensure the given permission if the checker returns ``False``.

        This method flips the permission check around: it first checks if a
        user has the given permission (which is fast), and if that is **not**
        the case it calls the given ``checker``.

        :param checker: A function that should check if the given permission is
            required.
        :param perm: The permission the user should have if ``checker`` returns
            ``True``. If a list is passed any of the permissions is sufficient
            for this check to pass.
        """
        has_perm = self.user.has_permission
        course_id = self.course_id
        if isinstance(perms, list):
            if any(has_perm(p, course_id=course_id) for p in perms):
                return
        elif has_perm(perms, course_id=course_id):
            return

        if checker():
            return

        raise PermissionException(
            'You do not have permission to do this.',
            'None of the permissions "{}" are enabled for user "{}"'.format(
                readable_join([p.name for p in maybe_wrap_in_list(perms)]),
                self.user,
            ), APICodes.INCORRECT_PERMISSION, 403
        )

    def _ensure_any(self, perms: t.List[CPerm]) -> None:
        ensure_any_of_permissions(perms, self.course_id, user=self.user)


class GlobalPermissionChecker(PermissionChecker):
    """The base permission checker class for permissions related to a users
        global role.
    """

    @staticmethod
    def as_ensure_function(fun: t.Callable[[_T_PERM_CHECKER], None]
                           ) -> _PermissionCheckFunction[_T_PERM_CHECKER]:
        """Wrap a permission checker function as a
            :class:`._PermissionCheckFunction`.

        This adds helper methods to the method like
        :meth:`._PermissionCheckFunction.as_bool`.
        """
        return _PermissionCheckFunction(fun)

    def _ensure(self, perm: GPerm) -> None:
        ensure_permission(perm, user=self.user)


@jwt.user_loader_callback_loader
def _load_user(user_id: int) -> t.Optional['psef.models.User']:
    return psef.models.User.query.options(
        sqlalchemy.orm.selectinload(psef.models.User.courses).joinedload(
            psef.models.CourseRole.course
        )
    ).get(int(user_id))


def _resolve_user(user: t.Union[None, LocalProxy, 'psef.models.User']
                  ) -> t.Optional['psef.models.User']:
    if isinstance(user, LocalProxy):
        # pylint: disable=protected-access
        return user._get_current_object()
    return user


@t.overload
def user_active(user: None) -> Literal[False]:  # pylint: disable=missing-docstring
    ...


@t.overload
def user_active(user: t.Union[LocalProxy, 'psef.models.User']) -> bool:  # pylint: disable=missing-docstring
    ...


def user_active(user: t.Union[None, LocalProxy, 'psef.models.User']) -> bool:
    """Check if the given user is active.

    :returns: True if the given user is not ``None`` and active.
    """
    user = _resolve_user(user)

    return user is not None and user.is_active


def login_required(fun: T) -> T:
    """Make sure a valid user is logged in at this moment.

    :raises PermissionException: If no user was logged in.
    """

    @wraps(fun)
    def __wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        ensure_logged_in()
        return fun(*args, **kwargs)

    return t.cast(T, __wrapper)


def _get_cur_user_nullable() -> t.Optional['psef.models.User']:
    return _resolve_user(psef.current_user)


def _get_cur_user() -> 'psef.models.User':
    user = _resolve_user(psef.current_user)
    ensure_logged_in(user)
    assert user is not None
    return user


def ensure_logged_in(
    user: t.Union[None,
                  'psef.models.User',
                  Literal[helpers.MissingType.token],
                  ] = helpers.MISSING
) -> None:
    """Make sure a user is currently logged in.

    :returns: Nothing.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    user = psef.current_user if user is helpers.MISSING else user
    if not user_active(user):
        _raise_login_exception()


@cache_within_request
def _ensure_course_visible_for_current_user(
    course: 'psef.models.Course'
) -> None:
    """Ensure that the current user is enrolled in the given course.

    This function also checks if the scope of the logged in user is correct for
    the given token. So in other words, this is more than simply checking if
    the current user is enrolled.

    :param course_id: The id of the course to check for.

    :returns: Nothing.
    """
    err_msg = None
    user = _get_cur_user()

    if user.is_enrolled(course):
        for_course = flask_jwt.get_jwt_claims().get('for_course')
        state = course.state
        if for_course is not None and for_course != course.id:
            err_msg = (
                'You are not allowed to see this course with the provided'
                ' token'
            )
        elif state.is_deleted:
            err_msg = 'This course is deleted, so you may not see it'
        elif state.is_archived and not user.has_permission(
            CPerm.can_see_archived_courses, course_id=course
        ):
            err_msg = (
                'This course has been archived, and you do not have permission'
                ' to view archived courses'
            )
    else:
        err_msg = 'You are not enrolled in this course'

    if err_msg is not None:
        raise PermissionException(
            err_msg,
            f'The user "{user.id}" is not enrolled in course "{course.id}"',
            APICodes.INCORRECT_PERMISSION, 403
        )


@contextlib.contextmanager
def as_current_user(
    user: t.Union['psef.models.User', LocalProxy],
    *,
    jwt_claims: t.Mapping[str, t.Any] = None,
) -> t.Generator[None, None, None]:
    """Execute a block of code while pretending the given user is logged in.

    After the contextmanager exists the original logged in user is restored.
    """
    old_user = _get_cur_user_nullable()
    old_claims = copy.copy(flask_jwt.get_jwt_claims())
    try:
        _ensure_course_visible_for_current_user.clear_cache()  # type: ignore
        set_current_user(user, jwt_claims=jwt_claims)
        yield
    finally:
        set_current_user(old_user, jwt_claims=old_claims)


def set_current_user(
    user: t.Union['psef.models.User', LocalProxy, None],
    *,
    jwt_claims: t.Mapping[str, t.Any] = None
) -> None:
    """Set the current user for this request.

    You probably never should use this method, it is only useful after logging
    in a user.

    :param user: The user that should become the current user.
    :returns: Nothing
    """
    # This prevents infinite recursion if the `user` is a `LocalProxy` by
    # making sure we always assign an actual User object.
    if isinstance(user, LocalProxy):
        # pylint: disable=protected-access
        user = user._get_current_object()

    # This sets the current user for flask jwt. See
    # https://github.com/vimalloc/flask-jwt-extended/issues/206 to make this
    # easier.
    _app_ctx_stack.top.jwt_user = user
    if jwt_claims is None:
        jwt_claims = {}

    old_claims = flask_jwt.get_raw_jwt().setdefault(
        flask_jwt.config.config.user_claims_key, {}
    )
    old_claims.clear()
    old_claims.update(jwt_claims)


def _ensure_submission_limits_not_exceeded(
    assig: 'psef.models.Assignment', author: 'psef.models.User',
    current_user: 'psef.models.User'
) -> None:
    if current_user.has_permission(
        CPerm.can_override_submission_limiting, assig.course_id
    ) or author.is_test_student:
        return
    elif (
        assig.max_submissions is None and
        assig.cool_off_period.total_seconds() == 0
    ):
        return

    # Create a lock for the current assignment and author combination so we
    # make sure that you cannot exceed the limits, even when submitting
    # concurrently.
    psef.models.db.session.execute(
        sqlalchemy.select(
            [sql.func.pg_advisory_xact_lock(assig.id, author.id)]
        )
    )

    Work = psef.models.Work
    base_sql = assig.get_not_deleted_submissions().filter(
        Work.user_id == author.id,
    )
    now = helpers.get_request_start_time()
    cool_off_cutoff = now - assig.cool_off_period

    if assig.max_submissions is None:
        query_amount = sql_expression.literal(0).label('amount')
    else:
        query_amount = sql.func.count()

    query_oldest_in_period: t.Union[DbColumn[t.Optional[DatetimeWithTimezone]],
                                    DbColumn[DatetimeWithTimezone],
                                    ]
    if assig.cool_off_period.total_seconds() > 0:
        query_since_cool_off = sql_func.count(
            sql_expression.case(
                [(Work.created_at >= cool_off_cutoff, 1)],
                else_=None,
            )
        )
        query_oldest_in_period = base_sql.filter(
            Work.created_at >= cool_off_cutoff
        ).with_entities(sql_func.min(Work.created_at)).label('oldest')
    else:
        query_since_cool_off = sql_expression.literal(0).label(
            'since_cool_off'
        )
        query_oldest_in_period = sql_expression.literal(now).label('oldest')

    query = base_sql.with_entities(
        query_amount,
        query_since_cool_off,
        query_oldest_in_period,
    )
    amount_subs, since_cool_off, oldest_since_cool_off = query.one()

    logger.info(
        'Checking submission limits',
        cool_off_period=assig.cool_off_period.total_seconds(),
        amount_since_cool_off=since_cool_off,
        total_amount_submissions=amount_subs,
        oldest_since_cool_off=oldest_since_cool_off,
    )

    if (
        assig.max_submissions is not None and
        assig.max_submissions <= amount_subs
    ):
        if author.contains_user(current_user):
            you_text = 'Your group has' if author.group else 'You have'
        else:
            you_text = (
                f'The group "{author.group.name}"'
                if author.group else author.name
            ) + ' has'

        submissions_text = (
            'submissions' if assig.max_submissions > 1 else 'submission'
        )

        raise PermissionException(
            (
                f'{you_text} reached the maximum amount of'
                f' {assig.max_submissions} {submissions_text} for this'
                ' assignment.'
            ),
            (
                f'The user {author.id} has {amount_subs} which is too'
                f' much, as the limit is {assig.max_submissions}.'
            ),
            APICodes.TOO_MANY_SUBMISSIONS,
            403,
        )
    elif since_cool_off >= assig.amount_in_cool_off_period:
        # The name `oldest_since_cool_off` is `None` when there are no
        # submissions. However, in that case `since_cool_off` should also
        # always be 0. However, we limit `amount_in_cool_off_period` to be >=
        # 1, so the check never passes.
        if oldest_since_cool_off is None:  # pragma: no cover
            oldest_since_cool_off = now
        wait_time = assig.cool_off_period - (now - oldest_since_cool_off)
        raise PermissionException(
            (
                'You cannot submit again yet, you have to wait at least {}'
                ' before you can upload again'
            ).format(humanfriendly.format_timespan(wait_time)),
            f'The user {author.id} submitted too early to try again',
            APICodes.COOL_OFF_PERIOD_ACTIVE,
            403,
        )


def ensure_can_submit_work(
    assig: 'psef.models.Assignment',
    author: 'psef.models.User',
    *,
    for_user: 'psef.models.User',
) -> None:
    """Check if the current user can submit for the given assignment as the given
    author.

    .. note::

        This function also checks if the assignment is a LTI assignment. If
        this is the case it makes sure the ``author`` can do grade passback.

    :param assig: The assignment that should be submitted to.
    :param author: The author of the submission.
    :param for_user: The user that is submitting, this should be equal to
        ``author``, except when ``author`` is a group, in that case it should
        be one of the members of that group. This should be a user of an actual
        person, it can for example not be a group.

    :raises PermissionException: If the current user cannot submit for the
        given author.
    :raises APIException: If the LTI state if wrong.
    """
    assert author.contains_user(for_user)

    # The for_user argument should be the actual real-life user.
    assert for_user.group is None
    assert for_user.active
    assert not for_user.virtual

    current_user = _get_cur_user()

    AssignmentPermissions(assig).ensure_may_see()

    submit_self = author.contains_user(current_user)
    if not for_user.is_enrolled(assig.course):
        raise PermissionException(
            'The author is not enrolled in this course',
            f'The user {for_user.id} is not enrolled in {assig.course_id}',
            APICodes.INCORRECT_PERMISSION, 403
        )

    if submit_self:
        ensure_permission(
            CPerm.can_submit_own_work, assig.course_id, user=current_user
        )
    else:
        ensure_permission(
            CPerm.can_submit_others_work, assig.course_id, user=current_user
        )

    if assig.deadline_expired:
        ensure_permission(
            CPerm.can_upload_after_deadline,
            assig.course_id,
            user=current_user
        )

    _ensure_submission_limits_not_exceeded(assig, author, current_user)

    # We do not passback test student grades, so we do not need them to
    # be present in the assignment_results
    if author.is_test_student:
        pass
    elif (not assig.is_lti) or assig.course.lti_provider is None:
        pass
    elif assig.course.lti_provider.member_sourcedid_required:
        if author.group is not None:
            members = author.group.members
        else:
            members = [author]

        if any(
            assig.id not in member.assignment_results for member in members
        ):
            # An assignment can never be an LTI assignment when the course is
            # not an LTI course.
            assert assig.course.lti_provider is not None
            lms = assig.course.lti_provider.lms_name

            if author.group:
                raise APIException(
                    f"Some authors haven't opened the assignment in {lms} yet",
                    (
                        'No assignment_results found for some authors in the'
                        ' group'
                    ),
                    APICodes.ASSIGNMENT_RESULT_GROUP_NOT_READY,
                    400,
                    group=author.group,
                    author=for_user,
                )

            raise APIException(
                (
                    f'This is a {lms} assignment and it seems we do not have'
                    ' the possibility to pass back the grade. Please {}visit'
                    f' the assignment again on {lms}. If this issue persists,'
                    ' please contact your system administrator.'
                ).format('ask the given author to ' if submit_self else ''),
                (
                    f'The assignment {assig.id} is not present in the '
                    f'user {author.id} `assignment_results`'
                ),
                APICodes.INVALID_STATE,
                400,
            )


@login_required
def ensure_can_view_autotest_step_details(
    step: 'psef.models.AutoTestStepBase'
) -> None:
    """Check if the current user can see the detail of the given step.

    :param step: The step for which we have to check the permission.
    :returns: Nothing.
    """
    course = step.suite.auto_test_set.auto_test.assignment.course
    _ensure_course_visible_for_current_user(course)

    ensure_permission(CPerm.can_view_autotest_step_details, course.id)
    if step.hidden:
        ensure_permission(CPerm.can_view_hidden_autotest_steps, course.id)


@login_required
def ensure_can_view_files(
    work: 'psef.models.Work', teacher_files: bool
) -> None:
    """Make sure the current user can see files in the given work.

    :param work: The work the given user should be able to see files in.
    :param teacher_files: Should the user be able to see teacher files.
    :returns: Nothing.
    :raises PermissionException: If the user should not be able te see these
        files.
    """
    cur_user = _get_cur_user()
    course = work.assignment.course

    if teacher_files:
        if work.has_as_author(cur_user) and work.assignment.is_done:
            ensure_permission(CPerm.can_view_own_teacher_files, course.id)
        else:
            # If the assignment is not done you can only view teacher files
            # if you can edit somebodies work.
            ensure_permission(CPerm.can_edit_others_work, course.id)

    try:
        _ensure_course_visible_for_current_user(course)
        if not work.has_as_author(cur_user):
            try:
                ensure_any_of_permissions(
                    [CPerm.can_see_others_work, CPerm.can_view_plagiarism],
                    course.id,
                )
            except PermissionException:
                if not work.is_peer_reviewed_by(cur_user):
                    raise
    except PermissionException:
        # A user can also view a file if there is a plagiarism case between
        # submission {A, B} where submission A is from a virtual course and the
        # user has the `can_view_plagiarism` permission on the course of
        # submission B.
        if not work.assignment.course.virtual:
            raise

        for case in psef.models.PlagiarismCase.query.filter(
            (psef.models.PlagiarismCase.work1_id == work.id)
            | (psef.models.PlagiarismCase.work2_id == work.id)
        ):
            other_work = case.work1 if case.work2_id == work.id else case.work2
            if cur_user.has_permission(
                CPerm.can_view_plagiarism,
                course_id=other_work.assignment.course_id,
            ):
                return
        raise


@login_required
def ensure_can_edit_members_of_group(
    group: 'psef.models.Group', members: t.List['psef.models.User']
) -> None:
    """Make sure that the current user can edit the given group.

    :param group: The group to check for.
    :param members: The members you want to add to the group.
    :returns: Nothing.
    :raises PermissionException: If the current user cannot edit the given
        group.
    """
    course = group.group_set.course
    _ensure_course_visible_for_current_user(course)

    perms = [CPerm.can_edit_others_groups]
    if all(member.id == _get_cur_user().id for member in members):
        perms.append(CPerm.can_edit_own_groups)

    ensure_any_of_permissions(
        perms,
        course.id,
    )

    if not all(member.is_enrolled(course) for member in members):
        raise APIException(
            'The given user is not enrolled in this course',
            f'Some members are not enrolled in course {course.id}',
            APICodes.INVALID_PARAM, 400
        )
    elif any(member.is_test_student for member in members):
        raise APIException(
            'You cannot add test students to groups',
            'Some users are test students', APICodes.INVALID_PARAM, 400
        )

    if group.has_a_submission:
        ensure_permission(
            CPerm.can_edit_groups_after_submission,
            group.group_set.course_id,
            extra_message=(
                "This is because you don't have the permission to"
                " change the users of a group after the group handed in a"
                " submission."
            )
        )


class WorksByUserPermissions(CoursePermissionChecker):
    """The permission checker used to check if a user may see submissions by
    the given ``author`` in the given ``assignment``.
    """
    __slots__ = ('assignment', 'author')

    def __init__(
        self, assignment: 'psef.models.Assignment', author: 'psef.models.User'
    ):
        super().__init__(assignment.course)
        self.assignment = assignment
        self.author = author

    def _can_always_see(self) -> bool:
        # Is own submission
        if self.author.contains_user(self.user):
            return True

        # If peer sub
        pf_settings = self.assignment.peer_feedback_settings
        if pf_settings is None:
            return False
        return pf_settings.does_peer_review_of(
            reviewer=self.user, subject=self.author
        )

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see the submissions by the author
        connected to this permission checker.
        """
        self._ensure_if_not(self._can_always_see, CPerm.can_see_others_work)


class WorkPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.Work`.
    """
    __slots__ = ('work', )

    def __init__(self, work: 'psef.models.Work'):
        super().__init__(work.assignment.course)
        self.work = work

    def _is_my_work(self) -> bool:
        return self.work.user.contains_user(self.user)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_grade_history(self) -> None:
        """Ensure the current user may see this work.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_see_grade_history)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Make sure the current user may edit the content of files in this
        work.
        """
        self._ensure(CPerm.can_edit_others_work)
        if self.work.assignment.is_open:
            raise PermissionException(
                (
                    'You cannot edit work as teacher'
                    ' if the assignment is stil open!'
                ),
                (
                    f'The assignment "{self.work.assignment.id}" is still'
                    ' open.'
                ),
                APICodes.INCORRECT_PERMISSION,
                403,
            )

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Ensure the current user may see this work.
        """
        if self.work.deleted:
            raise PermissionException(
                'The given work is deleted, so you may not see it',
                f'The work "{self.work.id}" was deleted',
                APICodes.INCORRECT_PERMISSION,
                403,
            )
        WorksByUserPermissions(self.work.assignment,
                               self.work.user).ensure_may_see()

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_assignee(self) -> None:
        """Make sure the current user may see the assignee of this work.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_see_assignee)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_delete(self) -> None:
        """Ensure that the current user may delete this feedback reply.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_delete_submission)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_grade(self) -> None:
        """Make sure the current user may edit the grade of this work.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_grade_work)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_grade(self) -> None:
        """Ensure the current user can see the grade of the work.
        """
        if not self.work.assignment.is_done:
            self._ensure(CPerm.can_see_grade_before_open)

        # Don't check for ``ensure_can_see`` here as peer reviewers can see the
        # submission but should not see the grade.
        self._ensure_if_not(self._is_my_work, CPerm.can_see_others_work)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_general_feedback(self) -> None:
        """Ensure the given user can see the general feedback of the work.
        """
        if not self.work.assignment.is_done:
            self._ensure(CPerm.can_see_user_feedback_before_done)

        # Don't check for ``ensure_can_see`` here as peer reviewers can see the
        # submission but should not see the general feedback.
        self._ensure_if_not(self._is_my_work, CPerm.can_see_others_work)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_linter_feedback(self) -> None:
        """Ensure the current user can see the linter feedback of the work.
        """
        if not self.work.assignment.is_done:
            self._ensure(CPerm.can_see_linter_feedback_before_done)

        # Don't check for ``ensure_can_see`` here as peer reviewers can see the
        # submission but should not see the general feedback.
        self._ensure_if_not(self._is_my_work, CPerm.can_see_others_work)


class CodePermisisons(CoursePermissionChecker):
    """This is the permission checker for :class:`psef.models.File`
    """
    __slots__ = ('code', )

    def __init__(self, code: 'psef.models.File') -> None:
        super().__init__(code.work.assignment.course)
        self.code: Final = code

    def ensure_may_see(self) -> None:
        """Ensure the current user may see the contents of this file.
        """
        # The ``as_ensure_function`` decorator always checks if we enrolled in
        # the course, which is something we do not want for this method. So
        # don't decorate it.
        ensure_can_view_files(
            self.code.work, teacher_files=self.code.fileowner.is_teacher
        )

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Make sure the current user may edit this code.
        """
        WorkPermissions(self.code.work).ensure_may_edit()


class FeedbackBasePermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.CommentBase`.
    """
    __slots__ = ('base', )

    def __init__(self, base: 'psef.models.CommentBase'):
        super().__init__(base.work.assignment.course)
        self.base: Final = base

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_add(self) -> None:
        """Make sure the current user may add a comment base.
        """
        perms = [CPerm.can_grade_work]
        if self.base.work.has_as_author(self.user):
            perms.append(CPerm.can_add_own_inline_comments)

        self._ensure_if_not(
            lambda: self.base.work.is_peer_reviewed_by(self.user), perms
        )


class FeedbackReplyPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.CommentReply`.
    """
    __slots__ = ('reply', )

    def __init__(self, reply: 'psef.models.CommentReply'):
        super().__init__(reply.comment_base.work.assignment.course)
        self.reply: Final = reply

    @property
    def _is_own_reply(self) -> bool:
        return self.reply.author.contains_user(self.user)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Ensure that the current user may edit this reply.
        """
        if self._is_own_reply and self.reply.comment_type.is_peer_feedback:
            self.ensure_may_add_as_peer()
        elif not self._is_own_reply:
            self._ensure(CPerm.can_edit_others_comments)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_edits(self) -> None:
        """Ensure that the current user may see the edits of this reply.

        .. note::

            A user may always see if a reply is edited, this checks if the user
            may see the contents of these edits.

        .. note::

            If a user may see the edit, the author may also always be
            displayed.
        """
        self.ensure_may_see()

        if not self._is_own_reply:
            self._ensure(CPerm.can_view_others_comment_edits)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_add(self) -> None:
        """Ensure that the current user may add this feedback reply.
        """
        perms = [CPerm.can_grade_work]
        if self.reply.comment_base.work.has_as_author(self.user):
            perms.append(CPerm.can_add_own_inline_comments)
        self._ensure_any(perms)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_add_approved(self) -> None:
        """Ensure that the current user may add already approved comments.
        """
        assignment = self.reply.comment_base.work.assignment
        pf_settings = assignment.peer_feedback_settings
        if pf_settings is None or not pf_settings.auto_approved:
            self.ensure_may_add()
        else:
            self.ensure_may_add_as_peer()

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_add_as_peer(self) -> None:
        """Make sure the current user may add this reply as peer feedback.

        This might be the case while the user may not add normal feedback
        (:py:meth:`.FeedbackReplyPermissions.ensure_may_add`).
        """
        work = self.reply.comment_base.work
        assig = work.assignment
        pf_setting = assig.peer_feedback_settings

        if pf_setting is None or not work.is_peer_reviewed_by(self.user):
            raise PermissionException(
                (
                    'You are not the peer reviewer of this submission so you'
                    ' may not add a peer review comment'
                ),
                'The user is not a peer reviewer of this submission',
                APICodes.INCORRECT_PERMISSION,
                403,
            )
        elif pf_setting.deadline_expired:
            raise PermissionException(
                (
                    'You cannot place peer feedback as the deadline for this'
                    ' has expired.'
                ), 'The assignment is after the peer review window',
                APICodes.INCORRECT_PERMISSION, 403
            )

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_change_approval(self) -> None:
        """Ensure that the current user may change the approval status of this
        reply.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_approve_inline_comments)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_delete(self) -> None:
        """Ensure that the current user may delete this feedback reply.
        """
        self.ensure_may_edit()

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_author(self) -> None:
        """Ensure that the current user may see the author of this reply.

        .. note::

            You are only allowed to see the author when you are also allowed to
            see the reply itself.
        """
        self.ensure_may_see()
        if not self.reply.author.contains_user(self.user):
            self._ensure(CPerm.can_view_feedback_author)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this feedback reply.
        """
        work = self.reply.comment_base.work
        WorkPermissions(work).ensure_may_see()

        if self._is_own_reply:
            return

        # This check is faster than the other one, and more common to fail, so
        # lets check this one first.
        assignment = work.assignment
        if not assignment.is_done:
            self._ensure(CPerm.can_see_user_feedback_before_done)

        if self.reply.in_reply_to is not None:
            # You can only see the reply if you can see the base
            type(self)(self.reply.in_reply_to).ensure_may_see()

        if not self.reply.is_approved:
            self._ensure(CPerm.can_view_inline_feedback_before_approved)


class NotificationPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.Notification`.
    """
    __slots__ = ('notification', 'work')

    def __init__(self, notification: 'psef.models.Notification'):
        work = notification.comment_reply.comment_base.work
        super().__init__(work.assignment.course)

        self.work: Final = work
        self.notification: Final = notification

    def _ensure_my_notification(self) -> None:
        if self.notification.receiver != self.user:
            raise PermissionException(
                'The given notification does not belong to the current user', (
                    f'The notification {self.notification.id} does not belong'
                    f' to {self.user.id}'
                ), APICodes.UNSUPPORTED, 403
            )

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this notification.
        """
        FeedbackReplyPermissions(
            self.notification.comment_reply,
        ).ensure_may_see()

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Make sure the current user may edit this notification.
        """
        self.ensure_may_see()
        self._ensure_my_notification()


class AnalyticsWorkspacePermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.AnalyticsWorkspace`.
    """
    __slots__ = ('workspace', )

    def __init__(
        self, analytics_workspace: 'psef.models.AnalyticsWorkspace'
    ) -> None:
        super().__init__(analytics_workspace.assignment.course)
        self.workspace = analytics_workspace

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Check if the current user has the permission to see analytics data.
        """
        AssignmentPermissions(self.workspace.assignment).ensure_may_see()
        self._ensure(CPerm.can_view_analytics)


class CoursePermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.Course`.
    """

    @staticmethod
    def ensure_may_see_filter() -> FilterColumn:
        """Get a database filter that filters out all courses the current user
        may not see.
        """
        user = _get_cur_user_nullable()
        if user is None:
            return sql_expression.false()

        course_ids = list(user.courses.keys())
        course_role_ids = [cr.id for cr in user.courses.values()]

        allowed_archived = psef.models.CourseRole.get_roles_with_permission(
            CPerm.can_see_archived_courses,
        ).filter(psef.models.CourseRole.id.in_(course_role_ids)).with_entities(
            psef.models.CourseRole.course_id
        )

        correct_state_filter: DbColumn[bool] = sql_expression.case(
            [
                (psef.models.Course.state.is_visible, True),
                (
                    psef.models.Course.state.is_archived,
                    psef.models.Course.id.in_(allowed_archived)
                )
            ],
            else_=False,
        )
        conditions: t.List[FilterColumn] = [
            psef.models.Course.id.in_(course_ids), correct_state_filter
        ]

        for_course = flask_jwt.get_jwt_claims().get('for_course')
        if for_course is not None:
            conditions.append(psef.models.Course.id == for_course)

        return sql_expression.and_(*conditions)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current see this course.
        """
        # This function is designed to be empty as the decorator already checks
        # this permission.

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_info(self) -> None:
        """Make sure the current user may edit this course's general info.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_edit_course_info)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_state(self) -> None:
        """Make sure the current user may edit this course's visibility state.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_archive_courses)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_roles(self) -> None:
        """Ensure the current user may see the roles in this course.
        """
        self._ensure(CPerm.can_edit_course_roles)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_roles(self) -> None:
        """Ensure the current user may edit the roles in this course.
        """
        self._ensure(CPerm.can_edit_course_roles)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_users(self) -> None:
        """Make sure the current user may see the participants in this course.
        """
        self._ensure(CPerm.can_list_course_users)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_users(self) -> None:
        """Make sure the current user may edit participants and their roles in
        this course.
        """
        self._ensure(CPerm.can_edit_course_users)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_snippets(self) -> None:
        """Make sure the current user may see course snippets.
        """
        self._global_ensure(GPerm.can_use_snippets)
        self._ensure_any(
            [CPerm.can_view_course_snippets, CPerm.can_manage_course_snippets]
        )

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_snippets(self) -> None:
        """Make sure the current user may edit snippets in this course.
        """
        self._global_ensure(GPerm.can_use_snippets)
        self._ensure(CPerm.can_manage_course_snippets)


class AssignmentPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.Assignment`.
    """
    __slots__ = ('assignment', )

    def __init__(self, assignment: 'psef.models.Assignment') -> None:
        super().__init__(assignment.course)
        self.assignment: Final = assignment

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_add(self) -> None:
        """Make sure the current user may add this assignment.
        """
        self._ensure(CPerm.can_create_assignment)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this assignment.
        """
        if not self.assignment.is_visible:
            raise PermissionException(
                'This assignment is not visible for any user',
                (f'The assignment {self.assignment.id} is not visible'),
                APICodes.INCORRECT_PERMISSION, 403
            )

        self._ensure(
            CPerm.can_see_assignments,
            extra_message=(
                'The permission to see assignments has not been enabled for'
                ' your account.'
            ),
        )

        if self.assignment.is_hidden:
            self._ensure(
                CPerm.can_see_hidden_assignments,
                extra_message=(
                    'This assignment is still hidden, and you do not have the'
                    ' permission to see hidden assignments.'
                ),
            )

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_plagiarism(self) -> None:
        """Make sure the current user may edit the this assignments
        plagiarism runs, and their result.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_view_plagiarism)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_plagiarism(self) -> None:
        """Make sure the current user may edit the this assignments
        plagiarism runs.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_manage_plagiarism)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_graders(self) -> None:
        """Ensure the current user may see the graders of work.
        """
        self.ensure_may_see()
        # TODO: This should probably be on the work checker, however we also
        # want to check this for assignments sometimes.
        self._ensure(CPerm.can_see_assignee)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_assign_graders(self) -> None:
        """Ensure the current user may assign graders to this work.
        """
        self.ensure_may_see()
        # TODO: This should probably be on the work checker, however we also
        # want to check this for assignments sometimes.
        self._ensure(CPerm.can_assign_graders)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_info(self) -> None:
        """Make sure the current user may edit this assignment's
        general info.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_edit_assignment_info)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_cgignore(self) -> None:
        """Make sure the current user may edit this assignment's
        ``cgignore``.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_edit_cgignore)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_notifications(self) -> None:
        """Make sure the current user may edit the assignment notification
        settings.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_update_course_notifications)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_group_status(self) -> None:
        """Make sure the current user may see the (LTI) group status of groups
        connected to this assignment.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_edit_group_assignment)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit_peer_feedback(self) -> None:
        """Make sure the current user may edit the peer feedback settings of
        this assignment.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_edit_peer_feedback_settings)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_delete(self) -> None:
        """Make sure the current user may delete this assignment
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_delete_assignments)


class LinterPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.LinterPermissions`.
    """
    __slots__ = ('linter', )

    def __init__(self, linter: 'psef.models.AssignmentLinter') -> None:
        super().__init__(linter.assignment.course)
        self.linter: Final = linter

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_delete(self) -> None:
        """Make sure the current user may delete this linter (and its results).
        """
        self._ensure(CPerm.can_use_linter)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this linter.
        """
        self._ensure(CPerm.can_use_linter)


class GroupSetPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.GroupSet`
    """
    __slots__ = ('group_set', )

    def __init__(self, group_set: 'psef.models.GroupSet') -> None:
        super().__init__(group_set.course)
        self.group_set: Final = group_set

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this group set.
        """
        # This does check for something, this is done by the decorator.

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_add(self) -> None:
        """Make sure the current user may add this group set.
        """
        self._ensure(CPerm.can_edit_group_set)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_delete(self) -> None:
        """Make sure the current user may delete this group set.
        """
        self._ensure(CPerm.can_edit_group_set)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Make sure the current user may edit this group set.
        """
        self._ensure(CPerm.can_edit_group_set)


class GroupPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.Group`
    """
    __slots__ = ('group', )

    def __init__(self, group: 'psef.models.Group') -> None:
        super().__init__(group.group_set.course)
        self.group: Final = group

    @property
    def _is_my_group(self) -> bool:
        return self.group.has_as_member(self.user)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this group.
        """
        self._ensure_if_not(
            lambda: self.group.is_empty or self._is_my_group,
            CPerm.can_view_others_groups,
        )

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Make sure the current user may edit this group.
        """
        perms = [CPerm.can_edit_others_groups]
        if self.group.is_empty or self._is_my_group:
            perms.append(CPerm.can_edit_own_groups)

        self._ensure_any(perms)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_delete(self) -> None:
        """Make sure the current user may delete this group.
        """
        self.ensure_may_edit()


class AutoTestPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.AutoTest`.
    """
    __slots__ = ('auto_test', )

    def __init__(self, auto_test: 'psef.models.AutoTest') -> None:
        super().__init__(auto_test.assignment.course)
        self.auto_test: Final = auto_test

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this auto test configuration.
        """
        AssignmentPermissions(self.auto_test.assignment)

        if self.auto_test.run and self.auto_test.results_always_visible:
            return
        elif not self.auto_test.assignment.is_done:
            self._ensure(CPerm.can_view_autotest_before_done)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Make sure the current user may edit this AutoTest.
        """
        self.ensure_may_see()
        self._ensure(CPerm.can_edit_autotest)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_add(self) -> None:
        """Make sure the current user may add this AutoTest.
        """
        self.ensure_may_edit()


class AutoTestFixturePermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.AutoTestFixture`
    """
    __slots__ = ('fixture', '_auto_test_checker')

    def __init__(self, fixture: 'psef.models.AutoTestFixture') -> None:
        auto_test = fixture.auto_test
        super().__init__(auto_test.assignment.course)
        self.fixture: Final = fixture
        self._auto_test_checker: Final = AutoTestPermissions(auto_test)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Make sure the current user may edit this fixture.
        """
        self.ensure_may_see()
        self._auto_test_checker.ensure_may_edit()

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user can see the contents of this fixture.

        :returns: Nothing.
        """
        self._auto_test_checker.ensure_may_see()

        self._ensure(CPerm.can_view_autotest_fixture)
        if self.fixture.hidden:
            self._ensure(CPerm.can_view_hidden_fixtures)


class AutoTestRunPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.AutoTestRun`.
    """
    __slots__ = ('run', )

    def __init__(self, run: 'psef.models.AutoTestRun') -> None:
        super().__init__(run.auto_test.assignment.course)
        self.run: Final = run

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this AutoTest run.
        """
        AutoTestPermissions(self.run.auto_test).ensure_may_see()

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_start(self) -> None:
        """Make sure the current user may start this AutoTest run.
        """
        self._ensure(CPerm.can_run_autotest)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_stop(self) -> None:
        """Make sure the current user may stop this AutoTest run.
        """
        self._ensure(CPerm.can_delete_autotest_run)


class AutoTestResultPermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.AutoTestResult`.
    """
    __slots__ = ('result', )

    def __init__(self, result: 'psef.models.AutoTestResult') -> None:
        super().__init__(result.run.auto_test.assignment.course)
        self.result: Final = result

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this AutoTest result.
        """
        AutoTestPermissions(self.result.run.auto_test).ensure_may_see()
        run = self.result.run
        work = self.result.work

        if run.auto_test.results_always_visible:
            # We cannot simply check if the user may see this work as peer
            # reviewers are not allowed to see the AutoTest results.
            if work.has_as_author(self.user):
                return
            self._ensure(CPerm.can_see_others_work)
        else:
            WorkPermissions(work).ensure_may_see_grade()

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_output_files(self) -> None:
        """Make sure the current user may see the output files connected to
        this AutoTest result.
        """
        self.ensure_may_see()
        if not self.result.run.auto_test.assignment.is_done:
            self._ensure(CPerm.can_view_autotest_output_files_before_done)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_restart(self) -> None:
        """Make sure the current user may restart this AutoTest result.
        """
        self.ensure_may_see()
        run_perms = AutoTestRunPermissions(self.result.run)
        run_perms.ensure_may_start()
        run_perms.ensure_may_stop()


class PlagiarismCasePermissions(CoursePermissionChecker):
    """The permission checker for :class:`psef.models.PlagiarismCase`.
    """
    __slots__ = ('case', '_assignment_id')

    def __init__(self, case: 'psef.models.PlagiarismCase') -> None:
        super().__init__(case.plagiarism_run.assignment.course)
        self._assignment_id: Final = case.plagiarism_run.assignment_id
        self.case: Final = case

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Make sure the current user may see this plagiarism case.
        """
        AssignmentPermissions(self.case.works.own_work.assignment
                              ).ensure_may_see()
        self._ensure(CPerm.can_view_plagiarism)

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_other_assignment(self) -> None:
        """Make sure the current user may see the other submission in this
        plagiarism case.

        The other assignment is seen as the assignment that might not be the
        same as the assignment connected to the plagiarism run.
        """
        self.ensure_may_see()

        other_assig = self.case.works.other_work.assignment
        other_course = other_assig.course

        # You can see virtual data of virtual assignments
        if other_course.virtual:
            return

        try:
            self._ensure_for_course(
                CPerm.can_view_plagiarism, course=other_course
            )
        except PermissionException:
            AssignmentPermissions(other_assig).ensure_may_see()

    @CoursePermissionChecker.as_ensure_function
    def ensure_may_see_other_submission(self) -> None:
        """Make sure the current user may see the other submission in this
        plagiarism case.
        """
        self.ensure_may_see()

        other_sub = self.case.works.other_work
        other_course = other_sub.assignment.course

        # You can see virtual data of virtual assignments
        if other_course.virtual:
            return

        try:
            self._ensure_for_course(
                CPerm.can_view_plagiarism, course=other_course
            )
        except PermissionException:
            WorkPermissions(other_sub).ensure_may_see()


class TaskResultPermissions(GlobalPermissionChecker):
    """The permission checker for :class:`psef.models.TaskResult`
    """

    def __init__(self, task_result: 'psef.models.TaskResult') -> None:
        self.task_result: Final = task_result

    @GlobalPermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Check if the current user may see this task result.
        """
        task_user = self.task_result.user

        if task_user is None or task_user != self.user:
            raise PermissionException(
                'This task result does not belong to you', (
                    f'The task result {self.task_result.id} does not belong to'
                    f' {self.user}.'
                ), APICodes.INCORRECT_PERMISSION, 403
            )


class LTI1p3ProviderPermissions(GlobalPermissionChecker):
    """The permission checker for :class:`psef.models.LTI1p3Provider`.
    """
    __slots__ = ('lti_provider', 'secret_is_correct')

    def __init__(
        self,
        lti_provider: 'psef.models.LTI1p3Provider',
        *,
        secret: str = None
    ) -> None:
        self.lti_provider: Final = lti_provider
        self.secret_is_correct: Final = (
            secret == str(lti_provider.edit_secret)
        )

    def _ensure_can_manage(self) -> None:
        if self.secret_is_correct:
            return
        self._ensure(GPerm.can_manage_lti_providers)

    @GlobalPermissionChecker.as_ensure_function
    def ensure_may_add(self) -> None:
        """Check if the current user may add this lti provider.
        """
        # You don' thave the permission to add based on a passed secret.
        self._ensure(GPerm.can_manage_lti_providers)

    @GlobalPermissionChecker.as_ensure_function
    def ensure_may_see(self) -> None:
        """Check if the current user may see this lti provider.
        """
        self._ensure_can_manage()

    @GlobalPermissionChecker.as_ensure_function
    def ensure_may_edit(self) -> None:
        """Check if the current user may edit this lti provider.
        """
        self._ensure_can_manage()
        if self.lti_provider.is_finalized:
            raise PermissionException(
                (
                    'You do not have the permission to edit this lti provider,'
                    ' as it has already been finalized.'
                ), (
                    f'The LTI provider {self.lti_provider.id} has already been'
                    ' finalized.'
                ), APICodes.INCORRECT_PERMISSION, 403
            )


@login_required
def ensure_any_of_permissions(
    permissions: t.List[CPerm],
    course_id: int,
    user: t.Optional['psef.models.User'] = None,
) -> None:
    """Make sure that the current user has at least one of the given
        permissions.

    :param permissions: The permissions to check for.
    :param course_id: The course id of the course that should be used to check
        for the given permissions.
    :param user: The user param that will be passed to
        :func:`ensure_permission`.
    :returns: Nothing.
    :raises PermissionException: If the current user has none of the given
        permissions. This will always happen if the list of given permissions
        is empty.
    """
    for perm in permissions:
        try:
            ensure_permission(perm, course_id, user=user)
        except PermissionException:
            continue
        else:
            return
    # All checks raised a PermissionException.
    raise PermissionException(
        'You do not have permission to do this.',
        'None of the permissions "{}" are enabled for user "{}"'.format(
            readable_join([p.name for p in permissions]),
            _get_cur_user().id,
        ),
        APICodes.INCORRECT_PERMISSION,
        403,
        missing_permissions=[permissions],
    )


@t.overload
# pylint: disable=function-redefined,missing-docstring,unused-argument
def ensure_permission(
    permission: CPerm,
    course_id: int,
    *,
    user: t.Optional['psef.models.User'] = None,
    extra_message: str = '',
) -> None:
    ...  # pylint: disable=pointless-statement


@t.overload
# pylint: disable=function-redefined,missing-docstring,unused-argument
def ensure_permission(
    permission: GPerm,
    *,
    user: t.Optional['psef.models.User'] = None,
    extra_message: str = ''
) -> None:
    ...  # pylint: disable=pointless-statement


def ensure_permission(  # pylint: disable=function-redefined
    permission: t.Union[CPerm, GPerm], course_id: t.Optional[int] = None
        , *, user: t.Optional['psef.models.User'] = None,
        extra_message: str = '',
) -> None:
    """Ensure that the current user is logged and has the given permission.

    :param permission_name: The name of the permission to check for.
    :param course_id: The course id of the course that should be used for the
        course permission, if it is None a role permission is implied. If a
        course_id is supplied but the given permission is not a course
        permission (but a role permission) this function will **NEVER** grant
        the permission.
    :param user: The user to check for, defaults to current user when not
        provided.
    :param extra_message: Text that should be appended to the message provided
        in the raised :class:`.PermissionException` when the permission check
        fails.

    :returns: Nothing

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    :raises PermissionException: If the permission is not enabled for the
                                 current user. (INCORRECT_PERMISSION)
    """
    user = _get_cur_user_nullable() if user is None else user

    if user is not None and user_active(user):
        if (
            isinstance(permission, CPerm) and course_id is not None and
            user.has_permission(permission, course_id=course_id)
        ):
            return
        elif isinstance(
            permission, GPerm
        ) and course_id is None and user.has_permission(permission):
            return
        else:
            if _get_cur_user_nullable() == user:
                you_do = 'You do'
            else:
                you_do = f'{user.name} does'

            maybe_space = ' ' if extra_message else ''
            msg = (
                f'{you_do} not have the permission to do this.'
                f'{maybe_space}{extra_message}'
            )

            raise PermissionException(
                msg,
                'The permission "{}" is not enabled for user "{}"'.format(
                    permission.name,
                    user.id,
                ),
                APICodes.INCORRECT_PERMISSION,
                403,
                missing_permissions=[permission],
            )
    else:
        _raise_login_exception(
            (
                'The user was not logged in, ' +
                'so it did not have the permission "{}"'
            ).format(permission.name)
        )


def permission_required(permission: GPerm) -> t.Callable[[T], T]:
    """A decorator used to make sure the function decorated is only called with
    certain permissions.

    :param permission: The global permission to check for.

    :returns: The value of the decorated function if the current user has the
        required permission.

    :raises PermissionException: If the current user does not have the required
        permission, this is done in the same way as
        :py:func:`ensure_permission` does this.
    """

    def __decorator(f: T) -> T:
        @wraps(f)
        def __decorated_function(*args: t.Any, **kwargs: t.Any) -> t.Any:
            assert isinstance(permission, GPerm)
            ensure_permission(permission)
            return f(*args, **kwargs)

        return t.cast(T, __decorated_function)

    return __decorator


class RequestValidatorMixin:
    '''
    A 'mixin' for OAuth request validation.
    '''

    def __init__(self, key: str, secret: str) -> None:
        super().__init__()
        self.consumer_key = key
        self.consumer_secret = secret

        self.oauth_server = oauth2.Server()
        signature_method = oauth2.SignatureMethod_HMAC_SHA1()
        self.oauth_server.add_signature_method(signature_method)
        self.oauth_consumer = oauth2.Consumer(
            self.consumer_key, self.consumer_secret
        )

    def is_valid_request(
        self,
        request: t.Any,
        parameters: t.Optional[t.MutableMapping[str, str]] = None,
        fake_method: t.Any = None,
        handle_error: bool = True
    ) -> bool:
        '''
        Validates an OAuth request using the python-oauth2 library:
            https://github.com/simplegeo/python-oauth2
        '''

        def __handle(err: oauth2.Error) -> bool:
            if handle_error:
                return False
            else:
                raise err
            # This is needed to please pylint
            raise RuntimeError()

        try:
            method, url, headers, parameters = self.parse_request(
                request, parameters, fake_method
            )

            oauth_request = oauth2.Request.from_request(
                method,
                url,
                headers=headers,
                parameters=parameters,
            )

            self.oauth_server.verify_request(
                oauth_request, self.oauth_consumer, {}
            )

        except (oauth2.Error, ValueError) as err:
            logger.error(
                'Got invalid oauth request',
                exc_info=True,
                report_to_sentry=True
            )
            return __handle(err)
        # Signature was valid
        return True

    def parse_request(
        self,
        req: t.Any,
        parameters: t.Optional[t.MutableMapping[str, str]] = None,
        fake_method: t.Optional[t.Any] = None,
    ) -> t.Tuple[str, str, t.MutableMapping[str, str], t.
                 MutableMapping[str, str]]:  # pragma: no cover
        '''
        This must be implemented for the framework you're using
        Returns a tuple: (method, url, headers, parameters)
        method is the HTTP method: (GET, POST)
        url is the full absolute URL of the request
        headers is a dictionary of any headers sent in the request
        parameters are the parameters sent from the LMS

        :param object request: The request to be parsed.
        :param dict parameters: Extra parameters for the given request.
        :param object fake_method: The fake method to be used.
        :rtype: tuple[str, str, dict[str, str], dict[str, str]]
        :returns: A tuple of, respectively, the requets method, url, headers
            and form, where the last two are a key value mapping.
        '''
        raise NotImplementedError()


class _FlaskOAuthValidator(RequestValidatorMixin):
    def parse_request(
        self,
        req: 'flask.Request',
        parameters: t.MutableMapping[str, str] = None,
        fake_method: t.Any = None,
    ) -> t.Tuple[str, str, t.MutableMapping[str, str], t.
                 MutableMapping[str, str]]:
        '''
        Parse Flask request
        '''
        # base_url is used because of:
        # https://github.com/instructure/canvas-lms/issues/600
        return (req.method, req.base_url, dict(req.headers), req.form.copy())


def ensure_valid_oauth(
    key: str,
    secret: str,
    request: t.Any,
    parser_cls: t.Type = _FlaskOAuthValidator
) -> None:
    """Make sure the given oauth key and secret is valid for the given request.

    :param str key: The oauth key to be used for validating.
    :param str secret: The oauth secret to be used for validating.
    :param object request: The request that should be validated.
    :param RequestValidatorMixin parser_cls: The class used to parse the given
        ``request`` it should subclass :py:class:`RequestValidatorMixin` and
        should at least override the
        :func:`RequestValidatorMixin.parse_request` method.
    :returns: Nothing
    """
    validator = parser_cls(key, secret)
    if not validator.is_valid_request(request):
        raise PermissionException(
            'No valid oauth request could be found.',
            'The given request is not a valid oauth request.',
            APICodes.INVALID_OAUTH_REQUEST, 400
        )


if t.TYPE_CHECKING:  # pragma: no cover
    import flask  # pylint: disable=unused-import
