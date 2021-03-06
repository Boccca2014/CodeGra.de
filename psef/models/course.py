"""This module defines a Course.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import uuid
import typing as t

import structlog
from sqlalchemy.orm import selectinload
from typing_extensions import TypedDict

import psef
import cg_enum
from cg_dt_utils import DatetimeWithTimezone
from cg_typing_extensions import make_typed_dict_extender
from cg_sqlalchemy_helpers import mixins, expression

from . import Base, MyQuery, db
from . import role as role_models
from . import user as user_models
from . import work as work_models
from .. import auth
from ..helpers import NotEqualMixin, jsonify_options
from .assignment import Assignment
from .link_tables import user_course
from ..permissions import CoursePermission

logger = structlog.get_logger()


class CourseRegistrationLink(Base, mixins.UUIDMixin, mixins.TimestampMixin):
    """Class that represents links that register users within a course.

    :ivar ~.CourseRegistrationLink.course_id: The id of the course in which the
        user will be enrolled.
    :ivar ~.CourseRegistrationLink.course_role_id: The id of the role the user
        will get in the course.
    :ivar ~.CourseRegistrationLink.expiration_date: The date after which this
        link is no longer valid.
    """
    course_id = db.Column(
        'course_id', db.Integer, db.ForeignKey('Course.id'), nullable=False
    )
    course_role_id = db.Column(
        'course_role_id',
        db.Integer,
        db.ForeignKey('Course_Role.id'),
        nullable=False
    )
    expiration_date = db.Column(
        'expiration_date',
        db.TIMESTAMP(timezone=True),
        nullable=False,
    )

    course = db.relationship(
        lambda: Course,
        foreign_keys=course_id,
        back_populates='registration_links',
        innerjoin=True,
    )
    course_role = db.relationship(
        lambda: role_models.CourseRole,
        foreign_keys=course_role_id,
        innerjoin=True
    )

    allow_register = db.Column(
        'allow_register',
        db.Boolean,
        nullable=False,
        default=True,
        server_default='true'
    )

    class AsJSON(TypedDict):
        """The JSON representation of a course registration link.
        """
        #: The id of this link
        id: uuid.UUID
        #: The moment this link will stop working
        expiration_date: DatetimeWithTimezone
        #: The role new users will get
        role: 'psef.models.CourseRole'
        #: Can users register with this link
        allow_register: bool

    def __to_json__(self) -> AsJSON:
        return {
            'id': self.id,
            'expiration_date': self.expiration_date,
            'role': self.course_role,
            'allow_register': self.allow_register,
        }

    def __extended_to_json__(self) -> t.Mapping[str, object]:
        return {
            **self.__to_json__(),
            'course': self.course,
        }


class CourseSnippet(Base):
    """Describes a mapping from a keyword to a replacement text that is shared
    amongst the teachers and TAs of the course.
    """
    __tablename__ = 'CourseSnippet'
    id = db.Column('id', db.Integer, primary_key=True)
    key = db.Column('key', db.Unicode, nullable=False)
    value = db.Column('value', db.Unicode, nullable=False)
    course_id = db.Column(
        'course_id', db.Integer, db.ForeignKey('Course.id'), nullable=False
    )
    created_at = db.Column(
        'created_at',
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False,
    )

    course = db.relationship(
        lambda: Course,
        foreign_keys=course_id,
        back_populates='snippets',
        innerjoin=True,
    )

    __table_args__ = (db.UniqueConstraint(course_id, key), )

    class AsJSON(TypedDict):
        """The JSON representation of a course snippet.
        """
        id: int  #: The id of this snippet.
        key: str  #: The key of this snippet.
        #: The value of this snippet, i.e. what this snippet should expand to.
        value: str

    def __to_json__(self) -> AsJSON:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'key': self.key,
            'value': self.value,
            'id': self.id,
        }


@enum.unique
class CourseState(cg_enum.CGEnum):
    """Describes in what state a :class:`.Course` is.
    """
    visible = 'visible'
    archived = 'archived'
    deleted = 'deleted'


class Course(NotEqualMixin, Base, mixins.TimestampMixin, mixins.IdMixin):
    """This class describes a course.

    A course can hold a collection of :class:`.Assignment` objects.

    :param name: The name of the course
    :param lti_course_id: The id of the course in LTI
    :param lti_provider: The LTI provider
    """
    __tablename__ = "Course"
    name = db.Column('name', db.Unicode, nullable=False)

    state = db.Column(
        'state',
        cg_enum.CGDbEnum(CourseState),
        nullable=False,
        default=CourseState.visible,
        server_default=CourseState.visible.name,
    )

    course_lti_provider = db.relationship(
        lambda: psef.models.CourseLTIProvider,
        back_populates="course",
        uselist=False,
        primaryjoin=lambda: expression.and_(
            Course.id == psef.models.CourseLTIProvider.course_id,
            ~psef.models.CourseLTIProvider.old_connection,
        ),
    )

    @property
    def lti_provider(self) -> t.Optional['psef.models.LTIProviderBase']:
        """The LTI provider connected to this course.

        If this is ``None`` the course is not an LTI course.
        """
        if self.course_lti_provider is None:
            return None
        return self.course_lti_provider.lti_provider

    virtual = db.Column('virtual', db.Boolean, default=False, nullable=False)

    group_sets = db.relationship(
        lambda: psef.models.GroupSet,
        back_populates="course",
        cascade='all,delete',
        uselist=True,
        order_by=lambda: psef.models.GroupSet.created_at,
        lazy='select',
    )

    snippets = db.relationship(
        lambda: CourseSnippet,
        back_populates='course',
        cascade='all,delete',
        uselist=True,
        lazy='select',
        order_by=lambda: CourseSnippet.created_at,
    )

    registration_links = db.relationship(
        lambda: CourseRegistrationLink,
        back_populates='course',
        cascade='all,delete',
        uselist=True,
        order_by=lambda: CourseRegistrationLink.created_at,
        lazy='select',
    )

    assignments = db.relationship(
        lambda: Assignment,
        back_populates="course",
        cascade='all,delete',
        uselist=True,
        lazy='select',
    )

    class AsJSON(TypedDict, total=True):
        """The way this class will be represented in JSON.
        """
        #: The id of this course
        id: int
        #: The name of this course
        name: str
        #: The date this course was created
        created_at: DatetimeWithTimezone
        #: Is this an LTI course?
        #: Deprecated: Use the ``lti_provider`` attribute (and check for
        #: ``null``).
        is_lti: bool
        #: Is this a virtual course.
        virtual: bool
        #: The lti provider that manages this course, if ``null`` this is not a
        #: LTI course.
        lti_provider: t.Optional['psef.models.LTIProviderBase']
        #: The state this course is in.
        state: CourseState

    class AsExtendedJSON(AsJSON, total=True):
        """The way this class will be represented in extended JSON.
        """
        #: The assignments connected to this assignment.
        assignments: t.Sequence['psef.models.Assignment']
        #: The groups sets of this course.
        group_sets: t.Sequence['psef.models.GroupSet']
        #: The snippets of this course.
        snippets: t.Sequence[CourseSnippet]

    def __to_json__(self) -> AsJSON:
        """Creates a JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'name': str, # The name of the course,
                'id': int, # The id of this course.
                'created_at': str, # ISO UTC date.
                'is_lti': bool, # Is the this course a LTI course,
                'virtual': bool, # Is this a virtual course,
            }

        :returns: A object as described above.
        """
        res: 'Course.AsJSON' = {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at,
            'is_lti': self.is_lti,
            'virtual': self.virtual,
            'lti_provider': self.lti_provider,
            'state': self.state,
        }
        if jsonify_options.get_options().add_role_to_course:
            user = psef.current_user
            res['role'] = user.courses[self.id  # type: ignore
                                       ].name if user else None
        return res

    def __extended_to_json__(self) -> AsExtendedJSON:
        if auth.CoursePermissions(self).ensure_may_see_snippets.as_bool():
            snippets = self.snippets
        else:
            snippets = []

        return make_typed_dict_extender(
            self.__to_json__(),
            Course.AsExtendedJSON,
        )(
            assignments=self.get_all_visible_assignments(),
            group_sets=self.group_sets,
            snippets=snippets,
        )

    @classmethod
    def update_query_for_extended_jsonify(cls, query: MyQuery['Course']
                                          ) -> MyQuery['Course']:
        """Update the given query to load all attributes needed for an extended
            jsonify eagerly.

        :param query: The query to update.
        :returns: The updated query, which now loads all attributes needed for
            an extended jsonify eagerly.
        """
        load_assig = selectinload(Course.assignments)
        return query.options(
            selectinload(Course.assignments),
            selectinload(Course.snippets),
            selectinload(Course.group_sets),
            selectinload(Course.course_lti_provider),
            load_assig.selectinload(Assignment.analytics_workspaces),
            load_assig.selectinload(Assignment.rubric_rows),
            load_assig.selectinload(Assignment.group_set),
            load_assig.selectinload(Assignment.peer_feedback_settings),
        )

    @classmethod
    def create_and_add(
        cls,
        name: str = None,
        virtual: bool = False,
    ) -> 'Course':
        """Create a new course and add it to the current database session.

        :param name: The name of the new course.
        :param virtual: Is this a virtual course.
        """

        self = cls(
            name=name,
            virtual=virtual,
        )
        if virtual:
            return self

        for role_name, perms in role_models.CourseRole.get_default_course_roles(
        ).items():
            role_models.CourseRole(
                name=role_name, course=self, _permissions=perms, hidden=False
            )

        db.session.add(self)
        db.session.flush()
        admin_username = psef.current_app.config['ADMIN_USER']

        if admin_username is not None:
            admin_user = user_models.User.query.filter_by(
                username=admin_username,
            ).one_or_none()
            admin_role = role_models.CourseRole.get_admin_role(self)

            if admin_user is None:
                logger.error(
                    'Could not find admin user',
                    admin_username=admin_username,
                    admin_role_name=admin_role
                )
            elif admin_role is None:
                logger.error(
                    'Could not find admin role',
                    admin_username=admin_username,
                    admin_role_name=admin_role
                )
            else:
                logger.info(
                    'Adding admin to course',
                    course_id=self.id,
                    admin_role_id=admin_role.id,
                    admin_user_id=admin_user.id
                )
                admin_user.courses[self.id] = admin_role

        return self

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        """Check if two courses are equal.

        >>> role_models.CourseRole.get_default_course_roles = lambda: {}
        >>> c1 = Course()
        >>> c1.id = 5
        >>> c2 = Course()
        >>> c2.id = 5
        >>> c1 == c2
        True
        >>> c1 == c1
        True
        >>> c1 == object()
        False
        """
        if isinstance(other, Course):
            return self.id == other.id
        return NotImplemented

    @property
    def is_lti(self) -> bool:
        """Is this course a LTI course.

        :returns: A boolean indicating if this is the case.
        """
        return self.course_lti_provider is not None

    def __structlog__(self) -> t.Mapping[str, t.Union[str, int]]:
        return {'type': self.__class__.__name__, 'id': self.id}

    def get_all_visible_assignments(self) -> t.Sequence['Assignment']:
        """Get all visible assignments for the current user for this course.

        :returns: A list of assignments the currently logged in user may see.
        """
        assigs = (
            assig for assig in self.assignments
            if auth.AssignmentPermissions(assig).ensure_may_see.as_bool()
        )

        return sorted(
            assigs, key=lambda item: item.deadline or DatetimeWithTimezone.max
        )

    def get_assignments(self) -> MyQuery['Assignment']:
        return Assignment.query.filter(Assignment.course == self)

    def get_all_users_in_course(
        self,
        *,
        include_test_students: bool,
        with_permission: CoursePermission = None
    ) -> MyQuery['t.Tuple[user_models.User, role_models.CourseRole]']:
        """Get a query that returns all users in the current course and their
            role.

        :returns: A query that contains all users in the current course and
            their role.
        """
        CourseRole = role_models.CourseRole

        join_conds = [CourseRole.id == user_course.c.course_id]
        if with_permission is not None:
            join_conds.append(
                CourseRole.id.in_(
                    CourseRole.get_roles_with_permission(
                        with_permission,
                    ).filter(CourseRole.course_id == self.id).with_entities(
                        CourseRole.id
                    )
                )
            )

        res = db.session.query(user_models.User, CourseRole).join(
            user_course,
            user_course.c.user_id == user_models.User.id,
        ).join(
            CourseRole,
            expression.and_(*join_conds),
        ).filter(
            CourseRole.course_id == self.id,
            user_models.User.virtual.isnot(True),
        )

        if not include_test_students:
            res = res.filter(~user_models.User.is_test_student)

        return res

    @classmethod
    def create_virtual_course(
        cls: t.Type['Course'], tree: 'psef.files.ExtractFileTree'
    ) -> 'Course':
        """Create a virtual course.

        The course will contain a single assignment. The tree should be a
        single directory with multiple directories under it. For each directory
        a user will be created and a submission will be created using the files
        of this directory.

        :param tree: The tree to use to create the submissions.
        :returns: A virtual course with a random name.
        """
        self = cls.create_and_add(
            name=f'VIRTUAL_COURSE__{uuid.uuid4()}', virtual=True
        )
        assig = Assignment(
            name=f'Virtual assignment - {tree.name}',
            course=self,
            is_lti=False
        )
        self.assignments.append(assig)
        for child in list(tree.values):
            # This is done before we wrap single files to get better author
            # names.
            work = work_models.Work(
                assignment=assig,
                user=user_models.User.create_virtual_user(child.name)
            )

            subdir: psef.files.ExtractFileTreeBase
            if isinstance(child, psef.files.ExtractFileTreeFile):
                subdir = psef.files.ExtractFileTreeDirectory(name='top')
                tree.forget_child(child)
                subdir.add_child(child)
            else:
                assert isinstance(child, psef.files.ExtractFileTreeDirectory)
                subdir = child
            work.add_file_tree(subdir)
        return self

    def get_test_student(self) -> 'user_models.User':
        """Get the test student for this course. If no test student exists yet
        for this course, create a new one and return that.

        :returns: A test student user.
        """

        user = self.get_all_users_in_course(include_test_students=True).filter(
            user_models.User.is_test_student,
        ).from_self(user_models.User).first()

        if user is None:
            role = role_models.CourseRole(
                name=f'Test_Student_Role__{uuid.uuid4()}',
                course=self,
                hidden=True,
            )
            db.session.add(role)
            user = user_models.User.create_new_test_student()
            user.courses[self.id] = role
            db.session.add(user)

        return user
