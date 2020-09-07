"""This module defines a User.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t
import functools
from datetime import timedelta
from collections import defaultdict

import structlog
import flask_jwt_extended
from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.local import LocalProxy
from sqlalchemy_utils import PasswordType
from typing_extensions import Literal, TypedDict
from sqlalchemy.sql.expression import false
from sqlalchemy.orm.collections import attribute_mapped_collection

import psef
from cg_dt_utils import DatetimeWithTimezone
from cg_sqlalchemy_helpers import CIText, hybrid_property

from . import UUID_LENGTH, Base, DbColumn, db
from . import course as course_models
from .. import auth, signals, db_locks
from .role import Role, CourseRole
from ..helpers import (
    NotEqualMixin, validate, handle_none, jsonify_options, maybe_unwrap_proxy,
    get_request_start_time
)
from .permission import Permission
from ..exceptions import APICodes, APIException, PermissionException
from .link_tables import user_course, course_permissions
from ..permissions import CoursePermission, GlobalPermission

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    # pylint: disable=unused-import,invalid-name
    from .assignment import AssignmentResult, AssignmentAssignedGrader

logger = structlog.get_logger()


@functools.total_ordering
class User(NotEqualMixin, Base):
    """This class describes a user of the system.

    >>> u1 = User('', '', '', '')
    >>> u1.id = 5
    >>> u1.id
    5
    >>> u1.id = 6
    Traceback (most recent call last):
    ...
    AssertionError

    :ivar ~.User.lti_user_id: The id of this user in a LTI consumer.
    :ivar ~.User.name: The name of this user.
    :ivar ~.User.role_id: The id of the role this user has.
    :ivar ~.User.courses: A mapping between course_id and course-role for all
        courses this user is currently enrolled.
    :ivar ~.User.email: The e-mail of this user.
    :ivar ~.User.virtual: Is this user an actual user of the site, or is it a
        virtual user.
    :ivar ~.User.password: The password of this user, it is automatically
        hashed.
    :ivar ~.User.assignment_results: The way this user can do LTI grade
        passback.
    :ivar ~.User.assignments_assigned: A mapping between assignment_ids and
        :py:class:`.AssignmentAssignedGrader` objects.
    :ivar reset_email_on_lti: Determines if the email should be reset on the
        next LTI launch.
    """

    class LoginResponse(TypedDict):
        """When logging in this object will be given.
        """
        #: The user that was logged in.
        user: 'User'
        #: A JWT token that can be used to do authenticated requests.
        access_token: str

    @t.overload
    def make_access_token(
        self,
        *,
        expires_in: t.Optional[timedelta] = None,
    ) -> str:
        ...

    @t.overload
    def make_access_token(
        self,
        *,
        expires_at: DatetimeWithTimezone,
        for_course: 'course_models.Course',
    ) -> str:
        ...

    def make_access_token(
        self,
        *,
        expires_at: t.Optional[DatetimeWithTimezone] = None,
        expires_in: t.Optional[timedelta] = None,
        for_course: t.Optional['course_models.Course'] = None
    ) -> str:
        """Make an access token for this user.

        :param expires_at: The date when this token expires. Cannot be given
            when ``expires_in`` is not ``None``.
        :param expires_in: The amount of time after which the token should
            expire. Cannot be given when ``expires_at`` is not ``None``.
        :param for_course: If given the token can only be used for requests in
            this course.

        :returns: A JWT token encoded as a string.
        """
        assert self.id is not None
        if expires_at is not None:
            assert expires_in is None, (
                'Cannot provide expires_in and expires_at'
            )
            now = get_request_start_time()
            expires_in = expires_at - now

        return flask_jwt_extended.create_access_token(
            identity=self.id,
            fresh=True,
            expires_delta=expires_in,
            user_claims={
                'for_course': None if for_course is None else for_course.id,
            }
        )

    @classmethod
    def resolve(
        cls: t.Type['User'], possible_user: t.Union['User', LocalProxy]
    ) -> 'User':
        """Unwrap the possible local proxy to a user.

        :param possible_user: The user we should unwrap.
        :returns: If the given argument was a LocalProxy
            `_get_current_object()` is called and the return value is returned,
            otherwise the given argument is returned.
        :raises AssertionError: If the given argument was not a user after
            unwrapping.
        """
        return maybe_unwrap_proxy(possible_user, cls, check=True)

    __tablename__ = "User"

    _id = db.Column('id', db.Integer, primary_key=True)

    def __init__(
        self,
        name: str,
        email: str,
        password: t.Optional[str],
        username: str,
        active: Literal[True] = True,
        virtual: bool = False,
        role: t.Optional[Role] = None,
        is_test_student: bool = False,
        courses: t.Mapping[int, CourseRole] = None,
    ) -> None:
        super().__init__(
            name=name,
            email=email,
            password=password,
            username=username,
            active=active,
            role=role,
            is_test_student=is_test_student,
            virtual=virtual,
            courses=handle_none(courses, {}),
        )

    @classmethod
    def find_possible_username(cls, wanted_username: str) -> str:
        """Find a possible username for a new user starting with
        ``wanted_username``.

        :param wanted_username: The username the new user should have in the
            ideal case. If not available we will try to find a username looking
            like ``$wanted_username ($number)``.

        :returns: A username that looks like ``wanted_username`` that is still
                  available.
        """
        i = 0

        def _get_username() -> str:
            return f'{wanted_username} ({i})' if i > 0 else wanted_username

        # Make sure we cannot have collisions, so simply lock this username for
        # the users while searching.
        db_locks.acquire_lock(db_locks.LockNamespaces.user, wanted_username)

        while db.session.query(
            cls.query.filter_by(username=_get_username()).exists()
        ).scalar():  # pragma: no cover
            i += 1

        return _get_username()

    def _get_id(self) -> int:
        """The id of the user
        """
        return self._id

    def _set_id(self, n_id: int) -> None:
        assert not hasattr(self, '_id') or self._id is None
        self._id = n_id

    id = hybrid_property(_get_id, _set_id)

    name = db.Column('name', db.Unicode, nullable=False)
    active = db.Column('active', db.Boolean, default=True, nullable=False)
    virtual = db.Column(
        'virtual', db.Boolean, default=False, nullable=False, index=True
    )
    is_test_student = db.Column(
        'is_test_student',
        db.Boolean,
        default=False,
        nullable=False,
        index=True
    )

    role_id = db.Column('Role_id', db.Integer, db.ForeignKey('Role.id'))
    courses: t.MutableMapping[int, CourseRole] = db.relationship(
        'CourseRole',
        collection_class=attribute_mapped_collection('course_id'),
        secondary=user_course,
        backref=db.backref('users', lazy='dynamic')
    )
    _username = db.Column(
        'username',
        CIText,
        unique=True,
        nullable=False,
        index=True,
    )

    def load_all_permissions(self) -> None:
        """Eagerly load all the permissions of this user object.

        :returns: Nothing
        """
        # This query seems to do nothing, but it updates the existing
        # ``CourseRole`` objects in memory with all permissions.
        db.session.query(CourseRole).filter(
            CourseRole.id.in_([cr.id for cr in self.courses.values()])
        ).options(CourseRole.eager_load_permissions()).all()

    def get_readable_name(self) -> str:
        """Get the readable name of this user.

        :returns: If this is a normal user this method simply returns the name
            of the user. If this user is the virtual user of a group a nicely
            formatted group name is returned.
        """
        if self.group:
            return f'group "{self.group.name}"'
        else:
            return self.name

    def _get_username(self) -> str:
        """The username of the user
        """
        return self._username

    def _set_username(self, username: str) -> None:
        assert not hasattr(self, '_username') or self._username is None
        self._username = username

    username = hybrid_property(_get_username, _set_username)

    reset_token = db.Column(
        'reset_token', db.String(UUID_LENGTH), nullable=True
    )
    reset_email_on_lti = db.Column(
        'reset_email_on_lti',
        db.Boolean,
        server_default=false(),
        default=False,
        nullable=False,
    )

    email = db.Column('email', db.Unicode, unique=False, nullable=False)
    password = db.Column(
        'password',
        PasswordType(schemes=[
            'pbkdf2_sha512',
        ], deprecated=[]),
        nullable=True,
    )

    assignments_assigned: t.MutableMapping[
        int, 'AssignmentAssignedGrader'] = db.relationship(
            'AssignmentAssignedGrader',
            collection_class=attribute_mapped_collection('assignment_id'),
            backref=db.backref('user', lazy='select')
        )

    assignment_results: t.MutableMapping[
        int, 'AssignmentResult'] = db.relationship(
            'AssignmentResult',
            collection_class=attribute_mapped_collection('assignment_id'),
            backref=db.backref('user', lazy='select')
        )

    group = db.relationship(
        lambda: psef.models.Group,
        back_populates='virtual_user',
        lazy='selectin',
        uselist=False,
    )

    role = db.relationship(lambda: Role, foreign_keys=role_id, lazy='select')

    def __structlog__(self) -> t.Mapping[str, t.Union[str, int]]:
        return {
            'type': self.__class__.__name__,
            'id': self.id,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self.id == other.id

    def __lt__(self, other: 'User') -> bool:
        return self.username < other.username

    def __hash__(self) -> int:
        return hash(self.id)

    def is_enrolled(
        self, course: t.Union[int, 'course_models.Course']
    ) -> bool:
        """Check if a user is enrolled in the given course.

        :param course: The course to in which the user might be enrolled. This
            can also be a course id for efficiency purposes (so you don't have
            to load the entire course object).

        :returns: If the user is enrolled in the given course. This is always
                  ``False`` if this user is virtual.
        """
        if self.virtual:
            return False
        course_id = (
            course.id if isinstance(course, course_models.Course) else course
        )
        return course_id in self.courses

    def enroll_in_course(self, *, course_role: CourseRole) -> None:
        """Enroll this user in a course with the given ``course_role``.

        :param course_role: The role the user should get in the new course.
            This object already contains the information about the course, so
            the user will be enrolled in the course connected to this role.

        :returns: Nothing.
        :raises AssertionError: If the user is already enrolled in the course.
        """
        assert not self.is_enrolled(
            course_role.course_id,
        ), 'User is already enrolled in the given course'

        self.courses[course_role.course_id] = course_role
        signals.USER_ADDED_TO_COURSE.send(
            signals.UserToCourseData(user=self, course_role=course_role)
        )

    def contains_user(self, possible_member: 'User') -> bool:
        """Check if given user is part of this user.

        A user ``A`` is part of a user ``B`` if either ``A == B`` or
        ``B.is_group and B.group.has_as_member(A)``

        :param possible_member: The user to check for if it is part of
            ``self``.
        :return: A bool indicating if ``self`` contains ``possible_member``.
        """
        if self.group is None:
            return self == possible_member
        else:
            return self.group.has_as_member(possible_member)

    def get_contained_users(self) -> t.Sequence['User']:
        """Get all contained users of this user.

        :returns: If this user is the virtual user of this group a list of
            members of the group, otherwise the user itself is wrapped in a
            list and returned.
        """
        if self.group is None:
            return [self]
        return self.group.members

    @classmethod
    def create_new_test_student(cls) -> 'User':
        """Create a new test student.

        :return: A newly created test student user named
            'TEST_STUDENT' followed by a random string.
        """

        return cls(
            name='Test Student',
            username=f'TEST_STUDENT__{uuid.uuid4()}',
            is_test_student=True,
            email='',
            password=None,
        )

    @classmethod
    def create_virtual_user(cls: t.Type['User'], name: str) -> 'User':
        """Create a virtual user with the given name.

        :return: A newly created virtual user with the given name prepended
            with 'Virtual - ' and a random username.
        """
        return cls(
            name=f'Virtual - {name}',
            username=f'VIRTUAL_USER__{uuid.uuid4()}',
            virtual=True,
            email='',
            password=None,
        )

    @t.overload
    def has_permission(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self, permission: CoursePermission, course_id: t.Union[int, 'course_models.Course']
    ) -> bool:
        ...  # pylint: disable=pointless-statement

    @t.overload
    def has_permission(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self,
        permission: GlobalPermission,
    ) -> bool:
        ...  # pylint: disable=pointless-statement

    def has_permission(  # pylint: disable=function-redefined
        self,
        permission: t.Union[GlobalPermission, CoursePermission],
        course_id: t.Union['course_models.Course', int, None] = None
    ) -> bool:
        """Check whether this user has the specified global or course
            :class:`.Permission`.

        To check a course permission the course_id has to be set.

        :param permission: The permission or permission name
        :param course_id: The course or course id

        :returns: Whether the role has the permission or not

        :raises KeyError: If the permission parameter is a string and no
            permission with this name exists.
        """
        if not self.active or self.virtual or self.is_test_student:
            return False

        if course_id is None:
            assert isinstance(permission, GlobalPermission)
            if self.role is None:
                return False
            return self.role.has_permission(permission)
        else:
            assert isinstance(permission, CoursePermission)

            if isinstance(course_id, course_models.Course):
                course_id = course_id.id

            if course_id in self.courses:
                return self.courses[course_id].has_permission(permission)
            return False

    def get_all_permissions_in_courses(
        self,
    ) -> t.Mapping[int, t.Mapping[CoursePermission, bool]]:
        """Get all permissions for all courses the current user is enrolled in

        :returns: A mapping from course id to a mapping from
            :py:class:`.CoursePermission` to a boolean indicating if the
            current user has this permission.
        """
        permission_links = db.session.query(
            user_course.c.course_id, Permission.get_name_column()
        ).join(User, User.id == user_course.c.user_id).filter(
            user_course.c.user_id == self.id
        ).join(
            course_permissions,
            course_permissions.c.course_role_id == user_course.c.course_id
        ).join(
            Permission,
            course_permissions.c.permission_id == Permission.id,
            isouter=True
        )
        lookup: t.Mapping[int, t.Set[str]] = defaultdict(set)
        for course_role_id, perm_name in permission_links:
            lookup[course_role_id].add(perm_name)

        out: t.MutableMapping[int, t.Mapping[CoursePermission, bool]] = {}
        for course_id, course_role in self.courses.items():
            perms = lookup[course_role.id]
            out[course_id] = {
                p: (p.name in perms) ^ p.value.default_value
                for p in CoursePermission
            }
        return out

    def get_permissions_in_courses(
        self,
        wanted_perms: t.Sequence[CoursePermission],
    ) -> t.Mapping[int, t.Mapping[CoursePermission, bool]]:
        """Check for specific :class:`.Permission`s in all courses
        (:class:`.course_models.Course`) the user is enrolled in.

        Please note that passing an empty ``perms`` object is
        supported. However the resulting mapping will be empty.

        >>> User('', '', '', '').get_permissions_in_courses([])
        {}

        :param wanted_perms: The permissions names to check for.
        :returns: A mapping where the first keys indicate the course id,
            the values at this are a mapping between the given permission names
            and a boolean indicating if the current user has this permission
            for the course with this course id.
        """
        assert not self.virtual

        if not wanted_perms:
            return {}

        perms: t.Sequence[Permission[CoursePermission]]
        perms = Permission.get_all_permissions_from_list(wanted_perms)

        course_roles = db.session.query(
            user_course.c.course_id
        ).join(User, User.id == user_course.c.user_id).filter(
            User.id == self.id
        ).subquery('course_roles')

        crp = db.session.query(
            course_permissions.c.course_role_id,
            t.cast(DbColumn[int], Permission.id),
        ).join(
            Permission,
            course_permissions.c.permission_id == Permission.id,
        ).filter(
            t.cast(DbColumn[int], Permission.id).in_([p.id for p in perms])
        ).subquery('crp')

        res: t.Sequence[t.Tuple[int, int]]
        res = db.session.query(course_roles.c.course_id, crp.c.id).join(
            crp,
            course_roles.c.course_id == crp.c.course_role_id,
            isouter=False,
        ).all()

        lookup: t.Mapping[int, t.Set[int]] = defaultdict(set)
        for course_role_id, permission_id in res:
            lookup[permission_id].add(course_role_id)

        out: t.MutableMapping[int, t.Mapping[CoursePermission, bool]] = {}
        for course_id, course_role in self.courses.items():
            out[course_id] = {
                p.value: (course_role.id in lookup[p.id]) != p.default_value
                for p in perms
            }

        return out

    @property
    def can_see_hidden(self) -> bool:
        """Can the user see hidden assignments.
        """
        return self.has_course_permission_once(
            CoursePermission.can_see_hidden_assignments
        )

    def __to_json__(self) -> t.Dict[str, t.Any]:
        """Creates a JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'id':    int, # The id of this user.
                'name':  str, # The full name of this user.
                'username': str, # The username of this user.
                'group': t.Optional[Group], # The group that this user
                                            # represents.
            }

        :returns: An object as described above.
        """
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'group': self.group,
            'is_test_student': self.is_test_student,
        }

    def __extended_to_json__(self) -> t.MutableMapping[str, t.Any]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'email': str, # The email of this user.
                'hidden': bool, # indicating if this user can once
                                # see hidden assignments.
                **self.__to_json__()
            }

        :returns: A object as described above.
        """
        is_self = psef.current_user and psef.current_user.id == self.id
        res = {
            'email': self.email if is_self else '<REDACTED>',
            "hidden": self.can_see_hidden,
            **self.__to_json__(),
        }
        if jsonify_options.get_options().add_permissions_to_user == self:
            res['permissions'] = GlobalPermission.create_map(
                self.get_all_permissions()
            )
        return res

    def has_course_permission_once(self, perm: CoursePermission) -> bool:
        """Check whether this user has the specified course
            :class:`.Permission` in at least one enrolled
            :class:`.course_models.Course`.

        :param perm: The permission or permission name

        :returns: True if the user has the permission once
        """
        assert not self.virtual
        return any(
            crole.has_permission(perm) for crole in self.courses.values()
        )

    @t.overload
    def get_all_permissions(self) -> t.Mapping[GlobalPermission, bool]:  # pylint: disable=function-redefined,missing-docstring,no-self-use
        ...  # pylint: disable=pointless-statement

    @t.overload
    def get_all_permissions(  # pylint: disable=function-redefined,missing-docstring,no-self-use,unused-argument
        self,
        course: 'course_models.Course',
    ) -> t.Mapping[CoursePermission, bool]:
        ...  # pylint: disable=pointless-statement

    def get_all_permissions(  # pylint: disable=function-redefined
        self, course: t.Union['course_models.Course', None] = None
    ) -> t.Union[t.Mapping[CoursePermission, bool], t.
                 Mapping[GlobalPermission, bool]]:
        """Get all global permissions (:class:`.Permission`) of this user or
            all course permissions of the user in a specific
            :class:`.course_models.Course`.

        :param course: The course or course id

        :returns: A name boolean mapping where the name is the name of the
                  permission and the value indicates if this user has this
                  permission.
        """
        assert not self.virtual

        if course is None:
            if self.role is None:
                return {perm: False for perm in GlobalPermission}
            else:
                return self.role.get_all_permissions()
        else:
            if auth.CoursePermissions(course).ensure_may_see.as_bool():
                return self.courses[course.id].get_all_permissions()
            else:
                return {perm: False for perm in CoursePermission}

    def get_reset_token(self) -> str:
        """Get a token which a user can use to reset his password.

        :returns: A token that can be used in :py:meth:`User.reset_password` to
            reset the password of a user.
        """
        timed_serializer = URLSafeTimedSerializer(
            current_app.config['SECRET_KEY']
        )
        self.reset_token = str(uuid.uuid4())
        return str(
            timed_serializer.dumps(self.username, salt=self.reset_token)
        )

    def reset_password(self, token: str, new_password: str) -> None:
        """Reset a users password by using a token.

        .. note:: Don't forget to commit the database.

        :param token: A token as generated by :py:meth:`User.get_reset_token`.
        :param new_password: The new password to set.
        :returns: Nothing.

        :raises PermissionException: If something was wrong with the
            given token.
        """
        assert not self.virtual

        timed_serializer = URLSafeTimedSerializer(
            current_app.config['SECRET_KEY']
        )
        try:
            username = timed_serializer.loads(
                token,
                max_age=current_app.config['RESET_TOKEN_TIME'],
                salt=self.reset_token
            )
        except BadSignature as exc:
            logger.warning(
                'Invalid password reset token encountered',
                token=token,
                exc_info=True,
            )
            raise PermissionException(
                'The given token is not valid',
                f'The given token {token} is not valid.',
                APICodes.INVALID_CREDENTIALS, 403
            ) from exc

        # This should never happen but better safe than sorry.
        if (
            username != self.username or self.reset_token is None
        ):  # pragma: no cover
            raise PermissionException(
                'The given token is not valid for this user',
                f'The given token {token} is not valid for user "{self.id}".',
                APICodes.INVALID_CREDENTIALS, 403
            )

        self.password = new_password
        self.reset_token = None

    @property
    def is_global_admin_user(self) -> bool:
        """Is this the global administrator of the site.

        This can only ever be ``True`` for users flushed to the database.
        """
        if self.id is None:
            return False  # type: ignore[unreachable]
        global_admin_username = psef.app.config['ADMIN_USER']
        return (
            bool(global_admin_username) and
            (self.username == global_admin_username)
        )

    @property
    def is_active(self) -> bool:
        """Is the current user an active user.

        .. todo::

            Remove this property

        :returns: If the user is active.
        """
        return self.active

    @classmethod
    def register_new_user(
        cls, *, username: str, password: str, email: str, name: str
    ) -> 'User':
        """Register a new user with the given data.

        :param username: The username of the new user, if a user already exists
            with this username an :class:`.APIException` is raised.
        :param password: The password of the new user, if the password is not
            strong enough an :class:`.APIException` is raised.
        :param email: The email of the new user, if not valid an
            :class:`.APIException` is raised.
        :name: The name of the new user.
        :returns: The created user, already added (but not committed) to the
            database.
        """
        if not all([username, email, name]):
            raise APIException(
                'All fields should contain at least one character',
                (
                    'The lengths of the given password, username and '
                    'email were not all larger than 1'
                ),
                APICodes.INVALID_PARAM,
                400,
            )
        validate.ensure_valid_password(
            password, username=username, email=email, name=name
        )
        validate.ensure_valid_email(email)

        db_locks.acquire_lock(db_locks.LockNamespaces.user, username)
        if db.session.query(
            cls.query.filter(cls.username == username).exists()
        ).scalar():
            raise APIException(
                'The given username is already in use',
                f'The username "{username}" is taken',
                APICodes.OBJECT_ALREADY_EXISTS,
                400,
            )

        role = Role.query.filter_by(name=current_app.config['DEFAULT_ROLE']
                                    ).one()
        self = cls(
            username=username,
            password=password,
            email=email,
            name=name,
            role=role,
            active=True,
        )

        db.session.add(self)
        db.session.flush()

        return self
