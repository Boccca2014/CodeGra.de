"""This module defines all models needed for groups.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
from sys import maxsize as _maxsize
from functools import wraps

import coolname
from sqlalchemy.sql.expression import or_ as sql_or
from sqlalchemy.sql.expression import func as sql_func

import psef
import cg_cache.intra_request
from cg_dt_utils import DatetimeWithTimezone
from cg_cache.intra_request import cached_property
from cg_sqlalchemy_helpers.types import MyQueryTuple, hybrid_property

from . import Base, DbColumn, db
from . import user as user_models
from . import work as work_models
from . import _MyQuery
from ..helpers import NotEqualMixin
from ..exceptions import APICodes, APIException
from .link_tables import users_groups

FUN = t.TypeVar('FUN', bound=t.Callable)


def _group_members_manipulator(fun: FUN) -> FUN:
    @wraps(fun)
    def __inner(*args: object, **kwargs: object) -> object:
        try:
            return fun(*args, **kwargs)
        finally:
            Group.has_as_member.clear_cache()  # type: ignore[attr-defined]

    return t.cast(FUN, __inner)


class Group(Base):
    """This class represents a single group.

    A group is a collection of real (non virtual) users that itself is
    connected to a virtual user. A group is connected to a :class:`.GroupSet`.
    """
    __tablename__ = 'Group'

    id = db.Column('id', db.Integer, primary_key=True)
    #: The name of the group. This has to be unique in a group set.
    name = db.Column('name', db.Unicode)
    #: The id of the :class:`.GroupSet` this group is connected to.
    group_set_id = db.Column(
        'group_set_id',
        db.Integer,
        db.ForeignKey('GroupSet.id'),
        nullable=False,
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False
    )
    #: The id of the virtual user this group is connected to. This user is used
    #: to submissions as the group.
    virtual_user_id = db.Column(
        'virtual_user_id',
        db.Integer,
        db.ForeignKey('User.id'),
        nullable=False,
    )
    _members = db.relationship(
        lambda: user_models.User,
        secondary=users_groups,
        lazy='selectin',
        order_by=lambda: user_models.User.name,
        uselist=True,
    )

    virtual_user = db.relationship(
        lambda: psef.models.User, foreign_keys=virtual_user_id, uselist=False
    )

    group_set = db.relationship(
        lambda: GroupSet,
        back_populates='groups',
        innerjoin=True,
        uselist=False,
    )

    __table_args__ = (db.UniqueConstraint('group_set_id', 'name'), )

    def __init__(
        self,
        *,
        name: str,
        group_set: 'GroupSet',
        virtual_user: 'user_models.User',
        members: t.List['user_models.User'],
    ) -> None:
        super().__init__(
            name=name,
            group_set=group_set,
            virtual_user=virtual_user,
            _members=members,
        )

    def __eq__(self, other: object) -> bool:
        """Check if two Groups are equal.

        >>> g1 = Group(name='', group_set=None, virtual_user=None, members=[])
        >>> g2 = Group(name='', group_set=None, virtual_user=None, members=[])
        >>> g3 = Group(name='', group_set=None, virtual_user=None, members=[])
        >>> g1.id = 1
        >>> g2.id = 1
        >>> g3.id = 2

        >>> g1 == object()
        False
        >>> g1 == g2
        True
        >>> g1 == g3
        False
        """
        if not isinstance(other, Group):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @cg_cache.intra_request.cache_within_request
    def has_as_member(self, user: 'user_models.User') -> bool:
        """Check if the given user is member of this group.

        :param user: The user to check for
        """
        return user in self._members or user == self.virtual_user

    @property
    def is_empty(self) -> bool:
        """Check if this group has no members.
        """
        return not self._members

    @hybrid_property
    def members(self) -> t.Sequence['user_models.User']:
        """The members of this group.
        """
        return self._members

    @_group_members_manipulator
    def add_member(self, new_member: 'user_models.User') -> None:
        """Add a member to this group.
        """
        self._members.append(new_member)

    @_group_members_manipulator
    def remove_member(self, member_to_remove: 'user_models.User') -> None:
        """Add a member from this group.

        This also checks if the member is already in a group.
        """
        if not self.has_as_member(member_to_remove):
            raise APIException(
                'The selected user is not in the group',
                f'The user {member_to_remove.id} i snot in group {self.id}',
                APICodes.INVALID_PARAM, 404
            )

        self._members = [u for u in self._members if u != member_to_remove]

    @cached_property
    def has_a_submission(self) -> bool:
        """Is a submission handed in by this group.

        .. note::

            This property is cached after the first access within a request.

        """
        return db.session.query(
            work_models.Work.query.filter_by(
                user_id=self.virtual_user_id,
                deleted=False,
            ).exists()
        ).scalar() or False

    @classmethod
    def create_group(
        cls: 't.Type[Group]',
        group_set: 'GroupSet',
        members: t.List['user_models.User'],
        name: t.Optional[str] = None,
    ) -> 'Group':
        """Create a group with the given members.

        .. warning::

           This function **does** check if the given members are not yet in a
           group. It however doesn't check if the current user has the
           permission to add these users to the group, nor if the members are
           enrolled in the course.

        :param group_set: In which group set should this group be placed.
        :param members: The initial members should this group have.
        :param name: The name of the group. If not given a random name is
            generated.
        :returns: The newly created group.
        """
        if members and db.session.query(
            cls.contains_users(members).filter_by(group_set=group_set).exists()
        ).scalar():
            raise APIException(
                'Member already in a group',
                'One of the members is already in a group for this group set',
                APICodes.INVALID_PARAM, 400
            )
        virt = user_models.User.create_virtual_user('GROUP_')
        name = name or ' '.join(coolname.generate(3))
        self = cls(
            group_set=group_set, members=members, virtual_user=virt, name=name
        )
        db.session.flush()
        virt.name += str(self.id)
        return self

    @classmethod
    def contains_users(
        cls: t.Type['Group'],
        users: t.Sequence['user_models.User'],
        *,
        include_empty: bool = False,
    ) -> _MyQuery['Group']:
        """Get a query that for all groups that include the given users.

        :param users: Filter groups so that at least one of their members is
            one of these users.
        :param include_empty: Also include empty groups, so without users, in
            the query.
        :returns: The query as described above.
        """
        res = db.session.query(Group)
        cond = Group.id.in_(
            db.session.query(users_groups.c.group_id).filter(
                t.cast(DbColumn[int],
                       users_groups.c.user_id).in_([m.id for m in users])
            )
        )
        if include_empty:
            cond = sql_or(cond, ~Group.members.any())

        return res.filter(cond)

    def get_member_lti_states(
        self,
        assignment: 'psef.models.Assignment',
    ) -> t.Mapping[int, bool]:
        """Get the lti state of all members in the group.

        Check if it is possible to passback the grade for all members in this
        group. This is done by checking if there is a row for each user,
        assignment combination in the `.psef.models.AssignmentResult`
        table.

        :param assignment: The assignment to get the states for.
        :returns: A mapping between user id and if we can passback the grade
            for this user for every member in this group.
        """
        assert any(a.id == assignment.id for a in self.group_set.assignments)

        if assignment.is_lti and self.members:
            assig_results: t.Set[int] = set(
                user_id
                for user_id, in db.session.query(psef.models.AssignmentResult).
                filter_by(assignment_id=assignment.id).filter(
                    t.cast(
                        DbColumn[int],
                        user_models.User.id,
                    ).in_([member.id for member in self._members])
                ).with_entities(
                    t.cast(
                        DbColumn[int],
                        psef.models.AssignmentResult.user_id,
                    )
                )
            )
            return {
                member.id: member.id in assig_results
                for member in self._members
            }
        else:
            return {member.id: True for member in self._members}

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        return {
            'id': self.id,
            'members': self.members,
            'name': self.name,
            'group_set_id': self.group_set_id,
            'created_at': self.created_at.isoformat(),
        }

    def __extended_to_json__(self) -> t.Mapping[str, t.Any]:
        virt_user = self.virtual_user.__to_json__()
        del virt_user['group']

        return {
            **self.__to_json__(),
            'virtual_user': virt_user,
        }


class GroupSet(NotEqualMixin, Base):
    """This class represents a group set.

    A group set is a single wrapper over all groups. Every group is part of a
    group set. The group set itself is connected to a single course and zero or
    more assignments in this course.

    :ivar minimum_size: The minimum size of that group should have before it
        can be used to submit a submission.
    :ivar maximum_size: The maximum amount of members a group can ever have.
    """
    __tablename__ = 'GroupSet'

    id = db.Column('id', db.Integer, primary_key=True)
    minimum_size = db.Column('minimum_size', db.Integer, nullable=False)
    maximum_size = db.Column('maximum_size', db.Integer, nullable=False)
    course_id = db.Column(
        'Course_id', db.Integer, db.ForeignKey('Course.id'), nullable=False
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False
    )

    course = db.relationship(
        lambda: psef.models.Course,
        foreign_keys=course_id,
        back_populates='group_sets',
        innerjoin=True,
    )

    assignments = db.relationship(
        lambda: psef.models.Assignment,
        back_populates='group_set',
        lazy='joined',
        uselist=True,
        order_by=lambda: psef.models.Assignment.created_at
    )

    groups = db.relationship(
        lambda: psef.models.Group,
        back_populates='group_set',
        lazy='select',
        cascade='all,delete',
        uselist=True,
        order_by=lambda: psef.models.Group.created_at,
    )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GroupSet):
            return NotImplemented
        return self.id == other.id

    def get_valid_group_for_user(self, user: 'user_models.User'
                                 ) -> t.Optional['Group']:
        """Get the group for the given user.

        :param user: The user to get the group for.
        :returns: A group if a valid group was found, or ``None`` if no group
            is needed to submit to an assignment connected to this group set.
        :raises APIException: If the amount of members of the found group is
            less than the minimum size of this group set.
        """
        assert (
            user.group is None and not user.is_test_student
        ), "Only use this method for normal users"

        group = db.session.query(Group).filter_by(group_set_id=self.id).filter(
            t.cast(
                DbColumn[t.List['user_models.User']],
                Group.members,
            ).any(user_models.User.id == user.id)
        ).first()

        if group is None:
            if self.minimum_size > 1:
                raise APIException(
                    'No group was found',
                    (
                        f'The user {user.id} is not in a group of at least'
                        f' {self.minimum_size} people'
                    ),
                    APICodes.INSUFFICIENT_GROUP_SIZE,
                    404,
                    group=None,
                )
            else:
                return None
        elif len(group.members) < self.minimum_size:
            raise APIException(
                "Group doesn't have enough members",
                (
                    f"The group {group.id} doesn't have at least"
                    f' {self.minimum_size} members'
                ),
                APICodes.INSUFFICIENT_GROUP_SIZE,
                400,
                group=group,
            )
        else:
            return group

    __table_args__ = (
        db.CheckConstraint('minimum_size <= maximum_size'),
        db.CheckConstraint('minimum_size > 0')
    )

    def __to_json__(self) -> t.Mapping[str, t.Union[int, t.List[int]]]:
        own_assignments = set(a.id for a in self.assignments)
        visible_assigs = [
            a.id for a in self.course.get_all_visible_assignments()
            if a.id in own_assignments
        ]
        return {
            'id': self.id,
            'minimum_size': self.minimum_size,
            'maximum_size': self.maximum_size,
            'assignment_ids': visible_assigs,
        }

    def __get_group_size_query(self, asc: bool,
                               has_subs: bool) -> MyQueryTuple[int]:
        count = sql_func.count(users_groups.c.user_id)
        res = db.session.query(count).group_by(users_groups.c.group_id).join(
            Group,
            Group.id == users_groups.c.group_id,
        ).filter(
            Group.group_set_id == self.id,
        ).order_by(count if asc else count.desc())
        if has_subs:
            res = res.filter(
                work_models.Work.query.filter_by(
                    user_id=Group.virtual_user_id
                ).exists()
            )
        return res

    @cached_property
    def largest_group_size(self) -> int:
        """Get the size of the largest group in this group set.

        This group doesn't have to have submission.

        .. note::

            This property is cached within a request, and won't update after
            adding groups.

        :returns: The size of the largest group in the group set. The value -1
            is returned if there are no groups in this group set.
        """
        return self.__get_group_size_query(
            asc=False, has_subs=False
        ).limit(1).scalar() or -1

    @cached_property
    def smallest_group_size(self) -> int:
        """Get the size of the smallest group in this group set.

        .. note:: Only groups with a submission are counted.

        .. note::

            This property is cached within a request, and won't update after
            adding groups.

        :returns: The size of the smallest group with a submission in the group
            set. The value :class:`.sys.maxsize` is returned if there are no
            groups with a submission in this group set.
        """
        return self.__get_group_size_query(
            asc=False, has_subs=True
        ).limit(1).scalar() or _maxsize
