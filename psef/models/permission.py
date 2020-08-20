"""This module defines a Permission.

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

from cg_sqlalchemy_helpers import (
    Comparator, hybrid_property, hybrid_expression
)
from cg_sqlalchemy_helpers.types import MyQuery, DbColumn

from . import Base, db
from .. import helpers
from ..permissions import (
    BasePermission, CoursePermission, GlobalPermission, UnknownPermission
)

_T = t.TypeVar('_T', bound=BasePermission)  # pylint: disable=invalid-name
T = t.TypeVar('T')

if getattr(t, 'SPHINX', False):  # pragma: no cover:
    # Sphinx fails with this decorator for whatever reason.
    cache_within_request = lambda x: x  # pylint: disable=invalid-name
else:
    from cg_cache.intra_request import cache_within_request


class PermissionComp(t.Generic[_T], Comparator[str]):  # pylint: disable=missing-docstring,too-many-ancestors
    def __eq__(self, other: _T) -> DbColumn[bool]:  # type: ignore
        assert isinstance(other, BasePermission)
        return self.__clause_element__() == other.name


class Permission(Base, t.Generic[_T]):  # pylint: disable=unsubscriptable-object
    """This class defines **database** permissions.

    A permission can be a global- or a course- permission. Global permissions
    describe the ability to do something general, e.g. create a course or the
    usage of snippets. These permissions are connected to a :class:`.Role`
    which is hold be a :class:`.User`. Similarly course permissions are bound
    to a :class:`.CourseRole`. These roles are assigned to users only in the
    context of a single :class:`.Course`. Thus a user can hold different
    permissions in different courses.

    .. warning::

      Think twice about using this class directly! You probably want a non
      database permission (see ``permissions.py``) which are type checked and
      WAY faster. If you need to check if a user has a certain permission use
      the :meth:`.User.has_permission` of, even better,
      :func:`psef.auth.ensure_permission` functions.

    :ivar default_value: The default value for this permission.
    :ivar course_permission: Indicates if this permission is for course
        specific actions. If this is the case a user can have this permission
        for a subset of all the courses. If ``course_permission`` is ``False``
        this permission is global for the entire site.

    """
    __tablename__ = 'Permission'

    id = db.Column('id', db.Integer, primary_key=True)

    __name = db.Column(
        'name', db.Unicode, unique=True, index=True, nullable=False
    )

    default_value = db.Column(
        'default_value', db.Boolean, default=False, nullable=False
    )
    course_permission = db.Column(
        'course_permission', db.Boolean, index=True, nullable=False
    )

    @classmethod
    def get_name_column(cls: t.Type['Permission[_T]']) -> DbColumn[str]:
        """Get the name column in the database for the permissions.

        :returns: The name column of permissions.
        """
        return t.cast(DbColumn[str], cls.__name)

    @classmethod
    def get_all_permissions(
        cls: t.Type['Permission[_T]'], perm_type: t.Type[_T]
    ) -> 't.Sequence[Permission[_T]]':
        """Get all database permissions of a certain type.

        :param perm_type: The type of permission to get.
        :returns: A list of all database permissions of the given type.
        """
        assert perm_type in (GlobalPermission, CoursePermission)
        return db.session.query(cls).filter_by(  # type: ignore
            course_permission=perm_type == CoursePermission
        ).all()

    @classmethod
    def get_all_permissions_from_list(
        cls: t.Type['Permission[_T]'], perms: t.Sequence[_T]
    ) -> 't.Sequence[Permission[_T]]':
        """Get database permissions corresponding to a list of permissions.

        :param perms: The permissions to get the database permission of.
        :returns: A list of all requested database permission.
        """
        if not perms:  # pragma: no cover
            return []

        assert isinstance(perms[0], (GlobalPermission, CoursePermission))
        assert all(isinstance(perm, type(perms[0])) for perm in perms)

        return helpers.filter_all_or_404(
            cls,
            t.cast(DbColumn[str],
                   Permission.__name).in_([p.name for p in perms]),
            Permission.course_permission == isinstance(
                perms[0], CoursePermission
            ),
        )

    @classmethod
    def query_permission(cls: 't.Type[Permission[_T]]',
                         perm: '_T') -> MyQuery['Permission[_T]']:
        """Get a database permission from a permission.

        :param perm: The permission to get the database permission of.
        :returns: The correct database permission.
        """
        # Mypy wraps the Permission in another Permission, no idea why.
        return db.session.query(cls).filter(  # type: ignore[return-value]
            cls.value == perm,
            cls.course_permission == isinstance(perm, CoursePermission),
        )

    @classmethod
    @cache_within_request
    def get_permission(
        cls: 't.Type[Permission[_T]]', perm: '_T'
    ) -> 'Permission[_T]':
        """Get a database permission from a permission.

        :param perm: The permission to get the database permission of.
        :returns: The correct database permission.
        """
        return cls.query_permission(perm).one()

    def _get_value(self) -> '_T':
        """Get the permission value of the database permission.

        :returns: The permission of this database permission.
        """
        try:
            if self.course_permission:
                return t.cast('_T', CoursePermission[self.__name])
            else:
                return t.cast('_T', GlobalPermission[self.__name])
        except KeyError:  # pragma: no cover
            # We might have old permissions still in the database
            return t.cast('_T', UnknownPermission(self.__name))

    @hybrid_expression
    def _get_value_comp(cls: t.Type['Permission[_T]']) -> PermissionComp[_T]:  # pylint: disable=no-self-argument,missing-docstring
        return PermissionComp(cls.__name)

    value = hybrid_property(_get_value, custom_comparator=_get_value_comp)
