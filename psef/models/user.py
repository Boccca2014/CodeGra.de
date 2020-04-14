"""This module defines a User.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t
import functools
from collections import defaultdict

import structlog
from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.local import LocalProxy
from sqlalchemy_utils import PasswordType
from sqlalchemy.sql.expression import false
from sqlalchemy.orm.collections import attribute_mapped_collection

import psef
from cg_sqlalchemy_helpers import CIText, hybrid_property

from . import UUID_LENGTH, Base, DbColumn, db, course, _MyQuery
from .role import Role, CourseRole
from ..helpers import NotEqualMixin, validate
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

    >>> u1 = User()
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
        if isinstance(possible_user, LocalProxy):
            # pylint: disable=protected-access
            possible_user = possible_user._get_current_object()
        assert isinstance(possible_user, cls), 'Give object is not a User'
        return possible_user

    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['User']] = Base.query

    __tablename__ = "User"

    _id = db.Column('id', db.Integer, primary_key=True)

    def _get_id(self) -> int:
        """The id of the user
        """
        return self._id

    def _set_id(self, n_id: int) -> None:
        assert not hasattr(self, '_id') or self._id is None
        self._id = n_id

    id = hybrid_property(_get_id, _set_id)

    # All stuff for LTI
    lti_user_id = db.Column(db.Unicode, unique=True)

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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self.id == other.id

    def __lt__(self, other: 'User') -> bool:
        return self.username < other.username

    def __hash__(self) -> int:
        return hash(self.id)

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

    def get_contained_users(self) -> t.Iterable['User']:
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
            email=''
        )

    @t.overload
    def has_permission(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self, permission: CoursePermission, course_id: t.Union[int, 'course.Course']
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
        course_id: t.Union['course.Course', int, None] = None
    ) -> bool:
        """Check whether this user has the specified global or course
        :class:`.Permission`.

        To check a course permission the course_id has to be set.

        >>> user_without_role = User(active=True)
        >>> user_without_role.has_permission(
        ...  GlobalPermission.can_edit_own_password
        ... )
        False
        >>> user_without_role.has_permission(
        ...  CoursePermission.can_submit_own_work, course_id=1
        ... )
        False

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

            if isinstance(course_id, course.Course):
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
        (:class:`.course.Course`) the user is enrolled in.

        Please note that passing an empty ``perms`` object is
        supported. However the resulting mapping will be empty.

        >>> User().get_permissions_in_courses([])
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
        return {
            'email': self.email if is_self else '<REDACTED>',
            "hidden": self.can_see_hidden,
            **self.__to_json__(),
        }

    def has_course_permission_once(self, perm: CoursePermission) -> bool:
        """Check whether this user has the specified course
        :class:`.Permission` in at least one enrolled :class:`.course.Course`.

        :param perm: The permission or permission name
        :returns: True if the user has the permission once
        """
        assert not self.virtual

        permission = Permission.get_permission(perm)
        assert permission.course_permission

        course_roles = db.session.query(
            user_course.c.course_id
        ).join(User, User.id == user_course.c.user_id).filter(
            User.id == self.id
        ).subquery('course_roles')
        crp = db.session.query(course_permissions.c.course_role_id).join(
            Permission, course_permissions.c.permission_id == Permission.id
        ).filter(Permission.id == permission.id).subquery('crp')
        res = db.session.query(
            course_roles.c.course_id
        ).join(crp, course_roles.c.course_id == crp.c.course_role_id)
        link = db.session.query(res.exists()).scalar()

        return link ^ permission.default_value

    @t.overload
    def get_all_permissions(self) -> t.Mapping[GlobalPermission, bool]:  # pylint: disable=function-redefined,missing-docstring,no-self-use
        ...  # pylint: disable=pointless-statement

    @t.overload
    def get_all_permissions(  # pylint: disable=function-redefined,missing-docstring,no-self-use,unused-argument
        self,
        course_id: t.Union['course.Course', int],
    ) -> t.Mapping[CoursePermission, bool]:
        ...  # pylint: disable=pointless-statement

    def get_all_permissions(  # pylint: disable=function-redefined
        self, course_id: t.Union['course.Course', int, None] = None
    ) -> t.Union[t.Mapping[CoursePermission, bool], t.
                 Mapping[GlobalPermission, bool]]:
        """Get all global permissions (:class:`.Permission`) of this user or
        all course permissions of the user in a specific
        :class:`.course.Course`.

        >>> user_without_role = User()
        >>> perms = user_without_role.get_all_permissions()
        >>> assert set(list(GlobalPermission)) == set(perms.keys())
        >>> assert not any(perms.values())
        >>> cperms = user_without_role.get_all_permissions(course_id=1)
        >>> assert not any(perms.values())

        :param course_id: The course or course id
        :returns: A name boolean mapping where the name is the name of the
                  permission and the value indicates if this user has this
                  permission.
        """
        assert not self.virtual

        if isinstance(course_id, course.Course):
            course_id = course_id.id

        if course_id is None:
            if self.role is None:
                return {perm: False for perm in GlobalPermission}
            else:
                return self.role.get_all_permissions()
        else:
            if course_id in self.courses:
                return self.courses[course_id].get_all_permissions()
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
        except BadSignature:
            logger.warning(
                'Invalid password reset token encountered',
                token=token,
                exc_info=True,
            )
            raise PermissionException(
                'The given token is not valid',
                f'The given token {token} is not valid.',
                APICodes.INVALID_CREDENTIALS, 403
            )

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

        if db.session.query(cls.query.filter_by(username=username).exists()
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
