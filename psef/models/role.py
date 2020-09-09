"""This module defines all roles.

SPDX-License-Identifier: AGPL-3.0-only
"""

import abc
import typing as t

from flask import current_app
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.collections import attribute_mapped_collection

from cg_sqlalchemy_helpers.types import MyQuery, ColumnProxy

from . import Base, MyQuery, db
from . import course as course_models
from .permission import Permission
from .link_tables import roles_permissions, course_permissions
from ..permissions import BasePermission, CoursePermission, GlobalPermission

_T = t.TypeVar('_T', bound=BasePermission)  # pylint: disable=invalid-name


class AbstractRole(t.Generic[_T]):
    """An abstract class that implements all functionality a role should have.
    """

    def __init__(
        self,
        name: str,
        _permissions: t.MutableMapping['_T', Permission['_T']] = None
    ) -> None:
        self.name = name
        if _permissions is not None:
            self._permissions = _permissions

    @property
    @abc.abstractmethod
    def id(self) -> ColumnProxy[int]:
        """The id of this role.
        """
        raise NotImplementedError

    # Unfortunately mypy doesn't really support abstract properties at this
    # time.
    @property
    def name(self) -> ColumnProxy[str]:
        """The name of this role.
        """
        raise NotImplementedError

    @name.setter
    def name(self, new_name: ColumnProxy[str]) -> None:
        """The name of this role.
        """
        raise NotImplementedError

    @property
    def _permissions(self) -> t.MutableMapping['_T', Permission['_T']]:
        """The permissions this role has a connection to.

        A connection means this role has the permission if, and only if, the
        ``default_value`` of this permission is ``False``.
        """
        raise NotImplementedError

    @_permissions.setter
    def _permissions(
        self, new_perms: t.MutableMapping['_T', Permission['_T']]
    ) -> None:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def uses_course_permissions(self) -> bool:
        """Does this role use course permissions or global permissions.
        """
        raise NotImplementedError

    def set_permission(self, perm: '_T', should_have: bool) -> None:
        """Set the given :class:`.Permission` to the given value.

        :param should_have: If this role should have this permission
        :param perm: The permission this role should (not) have
        """
        if self.uses_course_permissions:
            assert isinstance(perm, CoursePermission)
        else:
            assert isinstance(perm, GlobalPermission)

        permission = Permission.get_permission(perm)

        if permission.default_value ^ should_have:
            self._permissions[perm] = permission
        else:
            try:
                del self._permissions[perm]
            except KeyError:
                pass

    def has_permission(self, permission: '_T') -> bool:
        """Check whether this course role has the specified
        :class:`.Permission`.

        :param permission: The permission or permission name
        :returns: True if the course role has the permission
        """
        if self.uses_course_permissions:
            assert isinstance(permission, CoursePermission)
        else:
            assert isinstance(permission, GlobalPermission)

        revert = permission in self._permissions
        res = permission.value.default_value
        if revert:
            return not res
        return res

    def get_all_permissions(self) -> t.Mapping['_T', bool]:
        """Get all course :class:`.Permissions` for this course role.

        :returns: A name boolean mapping where the name is the name of the
                  permission and the value indicates if this user has this
                  permission.
        """
        perms: t.List[Permission['_T']]
        perms = db.session.query(Permission).filter_by(
            course_permission=self.uses_course_permissions,
        ).all()
        return {
            p.value: (p.value in self._permissions) ^ p.default_value
            for p in perms
        }

    def __to_json__(self) -> t.MutableMapping[str, t.Any]:
        """Creates a JSON serializable representation of a role.

        This object will look like this:

        .. code:: python

            {
                'id':    int, # The id of this role.
                'name':  str, # The name of this role.
            }

        :returns: An object as described above.
        """
        return {
            'name': self.name,
            'id': self.id,
        }


class Role(AbstractRole[GlobalPermission], Base):
    """A role defines the set of global permissions :class:`.Permission` of a
    :class:`.User`.

    :ivar ~.Role.name: The name of the global role.
    """
    __tablename__ = 'Role'
    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column('name', db.Unicode, unique=True, nullable=False)
    _permissions: t.MutableMapping[
        GlobalPermission, Permission[GlobalPermission]] = db.relationship(
            'Permission',
            collection_class=attribute_mapped_collection('value'),
            secondary=roles_permissions,
            backref=db.backref('roles', lazy='dynamic')
        )

    @property
    def uses_course_permissions(self) -> bool:
        return False


class CourseRole(AbstractRole[CoursePermission], Base):
    """
    A course role is used to describe the abilities of a :class:`.User` in a
    :class:`.course_models.Course`.

    :ivar ~.CourseRole.name: The name of this role in the course.
    :ivar ~.CourseRole.course_id: The :py:class:`.course_models.Course` this
        role belongs to.
    """
    __tablename__ = 'Course_Role'
    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column('name', db.Unicode, unique=False, nullable=False)
    course_id = db.Column(
        'Course_id',
        db.Integer,
        db.ForeignKey('Course.id'),
        nullable=False,
    )
    _permissions: t.MutableMapping[
        CoursePermission, Permission[CoursePermission]] = db.relationship(
            'Permission',
            collection_class=attribute_mapped_collection('value'),
            secondary=course_permissions
        )

    course = db.relationship(
        lambda: course_models.Course,
        foreign_keys=course_id,
        backref="roles",
        innerjoin=True,
    )

    hidden = db.Column(
        'hidden',
        db.Boolean,
        default=False,
        server_default='false',
        nullable=False
    )

    @classmethod
    def eager_load_permissions(cls) -> object:
        """Get the selectinload option to eagerly load all permissions of this
        ``CourseRole`` by using a ``selectinload``.
        """
        return selectinload(cls._permissions)

    @property
    def uses_course_permissions(self) -> bool:
        return True

    def __init__(
        self,
        name: str,
        course: 'course_models.Course',
        _permissions: t.Optional[t.MutableMapping[CoursePermission, Permission]
                                 ] = None,
        *,
        hidden: bool,
    ) -> None:
        if _permissions:
            assert all(
                isinstance(p, CoursePermission) for p in _permissions.keys()
            )
        super().__init__(name=name, _permissions=_permissions)

        # Mypy doesn't get the sqlalchemy magic
        self.course = course
        if course.id:
            self.course_id = course.id
        self.hidden = hidden

    def __to_json__(self) -> t.MutableMapping[str, t.Any]:
        """Creates a JSON serializable representation of this object.
        """
        res = super().__to_json__()
        res['course'] = self.course
        res['hidden'] = self.hidden
        return res

    @classmethod
    def get_initial_course_role(
        cls: t.Type['CourseRole'], course: 'course_models.Course'
    ) -> 'CourseRole':
        """Get the initial course role for a given course.

        :param course: The course to get the initial role for.
        :returns: A course role that should be the role for the user creating
            the course.
        """
        for name, value in current_app.config['_DEFAULT_COURSE_ROLES'].items():
            if value['initial_role']:
                return cls.query.filter_by(name=name, course=course).one()
        raise ValueError('No initial course role found')

    @classmethod
    def get_admin_role(cls, course: 'course_models.Course'
                       ) -> t.Optional['CourseRole']:
        """Get the role that the admin user in a course should have.

        :param course: The course in which we should search for the role.
        :returns: The role the admin user should have in a course, or ``None``
            if no such role could be found.
        """
        for name, value in current_app.config['_DEFAULT_COURSE_ROLES'].items():
            if value.get('admin_role'):
                return cls.query.filter_by(
                    name=name, course=course
                ).one_or_none()
        return None

    @staticmethod
    def get_default_course_roles() -> t.Mapping[
        str, t.MutableMapping[CoursePermission, Permission[CoursePermission]]]:
        """Get all default course roles as specified in the config and their
        permissions (:class:`.Permission`).


        .. code:: python

            {
                'student': {
                    'can_edit_assignment_info': <Permission-object>,
                    'can_submit_own_work': <Permission-object>
                }
            }

        :returns: A name dict mapping where the name is the name of the
            course-role and the dict is name permission mapping between the
            name of a permission and the permission object. See above for an
            example.
        """
        res = {}
        for name, value in current_app.config['_DEFAULT_COURSE_ROLES'].items():
            perms = Permission.get_all_permissions(CoursePermission)
            r_perms = {}
            perms_set = set(value['permissions'])
            for perm in perms:
                if bool(perm.default_value
                        ) ^ bool(perm.value.name in perms_set):
                    r_perms[perm.value] = perm

            res[name] = r_perms
        return res

    @classmethod
    def get_by_name(
        cls,
        course: 'course_models.Course',
        name: str,
        *,
        include_hidden: bool = False,
    ) -> MyQuery['CourseRole']:
        """Get a course role within the given course.

        :param course: The course to get the role in.
        :param name: The name of the role.
        """
        res = cls.query.filter(
            cls.name == name,
            cls.course == course,
        )
        if not include_hidden:
            res = res.filter(~cls.hidden)
        return res

    @classmethod
    def get_roles_with_permission(
        cls,
        permission: CoursePermission,
    ) -> MyQuery['CourseRole']:
        """Get a DB filter that does a :py:func:`CourseRole.has_permission`
        check in the database.

        :param permission: The permission you want to check for.

        :returns: A database filter column that checks if a course role has the
                  given permission.
        """
        # Make extra sure this permission is not a global permission, as this
        # would not error during runtime otherwise.
        assert isinstance(permission, CoursePermission)

        perm_id = Permission.query_permission(permission).with_entities(
            Permission.id
        )

        has_link = db.session.query(course_permissions).filter(
            course_permissions.c.course_role_id == cls.id,
            course_permissions.c.permission_id == perm_id
        ).exists()

        # XOR is not available in postgres (or SQLAlchemy), so we solve it with
        # a simple if.
        if permission.value.default_value:
            link_cond = ~has_link
        else:
            link_cond = has_link

        return db.session.query(cls).filter(link_cond)
