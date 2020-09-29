"""This module contains the code used for all LTI functionality.

SPDX-License-Identifier: AGPL-3.0-only AND MIT

This entire file is licensed as AGPL-3.0-only, except for the code copied
from https://github.com/ucfopen/lti-template-flask-oauth-tokens which is
MIT licensed. This copied code is located between the ``# START OF MIT LICENSED
COPIED WORK #`` and the ``# END OF MIT LICENSED COPIED WORK #`` comment blocks.
"""
import abc
import enum
import typing as t
import datetime
import xml.etree.ElementTree
from dataclasses import dataclass
from urllib.parse import urlparse

import flask
import oauth2
import dateutil
import httplib2
import structlog
from mypy_extensions import TypedDict
from defusedxml.ElementTree import fromstring as defused_xml_fromstring

from cg_dt_utils import DatetimeWithTimezone

from .. import app, auth, models, helpers, features
from ..models import db
from ..helpers import register, try_for_every
from .abstract import AbstractLTIConnector
from ..registry import lti_1_1_providers
from ..exceptions import APICodes, APIWarnings, APIException

logger = structlog.get_logger()

_T_LTI = t.TypeVar('_T_LTI', bound='LTI')


def _register_provider(cls: t.Type[_T_LTI]) -> t.Type[_T_LTI]:
    lti_1_1_providers.register(cls.get_lms_name())(cls)
    return cls


def init_app(_: t.Any) -> None:
    pass


# We do this as defusedxml overrides some of these classes and doing an `import
# ... as ET` causes different definitions, which means that `ET.ParseError`
# cannot be excepted.
ET = xml.etree.ElementTree

LTI_NAMESPACES = {
    'xmlns': 'http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0'
}

T_LTI_ROLE = t.TypeVar('T_LTI_ROLE', bound='LTIRole')  # pylint: disable=invalid-name


@dataclass
class LTIProperty:
    """An LTI property.

    :ivar internal: The name the property should be names in the launch params.
    :ivar external: The external name of the property.
    :ivar error_on_missing: This is considered a essential property.
    """
    internal: str
    external: str
    error_on_missing: bool = False


class LTIRoleException(APIException):
    """Thrown when a role could not be parsed.
    """


class LTIRole(abc.ABC):
    """LTI role, parsed from a role urn. The urn must be of the form
    urn:lti:{kind}:ims/lis/{name}/{subname}.

    :ivar ~.LTIRole.name: Primary role name.
    :ivar subnames: Secondary role names.
    """
    _LOOKUP: t.ClassVar[t.Mapping[str, t.Tuple[str, int]]]

    @classmethod
    @abc.abstractmethod
    def parse(cls: t.Type[T_LTI_ROLE], urn: str) -> T_LTI_ROLE:
        """Parse the given ``urn`` to a role.

        :param urn: The urn to parse.
        :returns: The parsed role.
        :raises LTIRoleException: If the role is not valid.
        """
        raise NotImplementedError

    @property
    def codegrade_role_name(self) -> t.Optional[str]:
        """If not ``None`` this role should be mapped to a CodeGrade role with
        this name.
        """
        if self.name in self._LOOKUP:
            return self._LOOKUP[self.name][0]
        return None

    @classmethod
    def codegrade_role_name_used(cls, name: str) -> bool:
        """Is the given name used for any known LTI role as CodeGrade role
            name.

        This is true if there is any role ``l`` for which
        ``l.codegrade_role_name == name``.

        :param name: The CodeGrade role name to check.
        """
        return any(cg_name == name for cg_name, _ in cls._LOOKUP.values())

    def _get_sort_key(self) -> int:
        return self._LOOKUP.get(self.name, ('', -1))[-1]

    def __lt__(self, other: object) -> bool:
        """Check if this item is less than the other item.

        >>> a = LTICourseRole(name='Instructor', subnames=['c'])
        >>> b = LTICourseRole(name='Learner', subnames=['c'])
        >>> c = LTIGlobalRole(name='Instructor', subnames=['c'])
        >>> a < b
        False
        >>> a > b
        True
        >>> a.__lt__(c)
        NotImplemented
        """
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._get_sort_key() < other._get_sort_key()

    @classmethod
    def _parse(
        cls: t.Type[T_LTI_ROLE], urn: str, wanted_kind: t.Collection[str]
    ) -> T_LTI_ROLE:
        """Parse a LTI role from a IMS urn.

        :param urn: The string to parse.
        :returns: The parsed LTI role.
        :raises LTIRoleException: If the role is not valid.
        """

        def role_assert(should_not_raise: bool) -> None:
            if not should_not_raise:
                raise LTIRoleException(
                    'The given role could not be parsed as an LTI role.',
                    f'The role {urn} could not be parsed as an LTI role.',
                    APICodes.INVALID_PARAM, 400
                )

        role_assert(urn.startswith('urn:lti:'))
        _, __, *rest = urn.split(':')
        role_assert(len(rest) >= 2)
        role_assert(rest[0] in wanted_kind)

        path = rest[1]
        role_assert(path.startswith('ims/lis/'))
        _, __, *names = path.split('/')
        role_assert(len(names) > 0)
        name = names[0]
        subnames = names[1:]
        return cls(name=name, subnames=subnames)

    def __init__(self, *, name: str, subnames: t.Sequence[str]) -> None:
        self.name = name
        self.subnames = subnames

    def __repr__(self) -> str:
        kind = self.__class__.__name__.lower()
        name = '/'.join([self.name, *self.subnames])
        return f'{kind}:{name}'


class LTICourseRole(LTIRole):
    """A class representing a course LTI role.
    """
    _LOOKUP = {
        # LIS standard Context Roles
        'Learner': ('Student', 0),
        'Instructor': ('Teacher', 3),
        'ContentDeveloper': ('Designer', 1),
        'Member': ('Student', 0),
        'Administrator': ('Teacher', 3),
        'TeachingAssistant': ('TA', 2),
    }

    @classmethod
    def parse(cls, urn: str) -> 'LTICourseRole':
        return cls._parse(urn, {'role'})


class LTIGlobalRole(LTIRole):
    """A class representing a global LTI role.

    This class represents both roles of type ``sysrole`` and of type
    ``instrole``, as CodeGrade handles those both the same way.
    """
    _LOOKUP = {
        # LIS standard System Roles,
        'SysAdmin': ('Staff', 3),
        'SysSupport': ('Staff', 3),
        'Creator': ('Staff', 3),
        'AccountAdmin': ('Staff', 3),
        'User': ('Student', 2),
        'Administrator': ('Staff', 3),
        'None': ('Nobody', 1),
        # LIS standard Institution Roles,
        'Student': ('Student', 2),
        'Faculty': ('Staff', 3),
        'Member': ('Student', 2),
        'Learner': ('Student', 2),
        'Instructor': ('Staff', 3),
        'Staff': ('Staff', 3),
        'Alumni': ('Student', 2),
        'ProspectiveStudent': ('Student', 2),
        'Guest': ('Student', 2),
        'Other': ('Student', 2),
        'Observer': ('Student', 2),
    }

    @classmethod
    def parse(cls, urn: str) -> 'LTIGlobalRole':
        return cls._parse(urn, {'sysrole', 'instrole'})


T_LTI = t.TypeVar('T_LTI', bound='LTI')  # pylint: disable=invalid-name


# TODO: This class has so many public methods as they are properties. A lot of
# them can be converted to private properties which should be done.
class LTI(AbstractLTIConnector):  # pylint: disable=too-many-public-methods
    """The base LTI class.
    """

    @classmethod
    @abc.abstractmethod
    def get_lms_name(cls) -> str:
        raise NotImplementedError

    @staticmethod
    def supports_lti_launch_as_result() -> bool:  # pragma: no cover
        """Does this LTI consumer support the ``ltiLaunchUrl`` as result field.
        """
        return False

    @staticmethod
    def supports_lti_common_cartridge() -> bool:
        """Does this LMS support configuration using a Common Cartridge
            [common_cartridge]_.

        .. [common_cartridge] See `here
            <http://www.imsglobal.org/cc/ccv1p3/imscc_Overview-v1p3.html>`_ for
            more information.
        """
        return False

    def __init__(
        self,
        params: t.Mapping[str, str],
        lti_provider: 'models.LTI1p1Provider' = None
    ) -> None:
        self.launch_params = params

        if lti_provider is not None:
            self.lti_provider = lti_provider
        else:
            lti_id = params['lti_provider_id']
            self.lti_provider = helpers.get_or_404(
                models.LTI1p1Provider,
                lti_id,
            )

        if self.lti_provider.upgraded_to_lti1p3:
            raise APIException(
                'This provider has been upgraded to LTI 1.3',
                (
                    'This provider has been upgraded to a LTI 1.3 provider,'
                    ' the old connection can no longer be used'
                ),
                APICodes.INVALID_STATE,
                400,
                upgraded_lti1p3_id=self.lti_provider.upgraded_to_lti1p3.id,
            )

        self.key = self.lti_provider.key
        self.secrets = self.lti_provider.secrets

    @staticmethod
    def create_from_request(req: flask.Request) -> 'LTI':
        """Create an instance from a flask request.

        The request should have a ``form`` variable that has all the right
        parameters. So this request should be from an LTI launch.

        :param req: The request to create the LTI instance from.
        :returns: A fresh LTI instance.
        """
        params = req.form.copy()

        lti_provider = helpers.filter_single_or_404(
            models.LTI1p1Provider,
            models.LTI1p1Provider.key == params['oauth_consumer_key'],
        )

        if not lti_provider.is_finalized:
            raise APIException(
                (
                    'This LTI connection is not yet finalized, please make'
                    ' sure you have completed all steps in the wizard.'
                ), f'The LTIProvider {lti_provider.id} is not finalized',
                APICodes.INVALID_STATE, 400
            )

        params['lti_provider_id'] = lti_provider.id

        # This is semi sensitive information so it should not end up in the JWT
        # token.
        launch_params = {}
        for key, value in params.items():
            if not key.startswith('oauth'):
                launch_params[key] = value

        cls = lti_provider.lti_class
        self = cls(launch_params, lti_provider)
        launch_params['custom_lms_name'] = lti_provider.lms_name

        try_for_every(
            reversed(self.secrets),
            lambda secret: auth.ensure_valid_oauth(self.key, secret, req),
        )

        return self

    @staticmethod
    def create_from_launch_params(params: t.Mapping[str, str]) -> 'LTI':
        """Create an instance from launch params.

        The params should have an ``lti_class`` key with the name of the class
        to be instantiated.

        :param params: The launch params to create the LTI instance from.
        :returns: A fresh LTI instance.
        """
        lms = params['custom_lms_name']
        cls = lti_1_1_providers[lms]
        res = cls(params)
        res.ensure_lti_data_correct()
        return res

    @staticmethod
    def get_lti_properties() -> t.List[LTIProperty]:
        """All extension properties used by this LMS.

        :returns: The extension properties needed.
        """
        return []

    @staticmethod
    def get_custom_extensions() -> str:
        """Get a string that will be used verbatim in the LTI xml.

        :returns: A string used as extension
        """
        return ''

    @staticmethod
    def supports_max_points() -> bool:
        """Determine whether this LMS supports changing the max points.

        :returns: A boolean indicating whether this LTI instance supports
            changing the max points.
        """
        return False

    @staticmethod
    def supports_state_management() -> bool:
        """Determines whether this LMS sends the assignment state to CodeGrade.
        If this is ``True`` you cannot change state info, e.g. the
        ``available_at``.

        :returns: A boolean indicating whether this LTI instance gives the
                  assignment state to CodeGrade.
        """
        return False

    @staticmethod
    def supports_deadline() -> bool:
        """Determines whether this LMS sends the deadline of an assignment
        along with the lti launch request. If it does, the deadline for
        that assignment cannot be changed from within CodeGrade.

        :returns: A boolean indicating whether this LTI instance gives the
            deadline to CodeGrade.
        """
        return False

    @property
    def assignment_points_possible(self) -> t.Optional[float]:
        """The amount of points possible for the launched assignment.

        :returns: The possible points or ``None`` if this option is not
            supported or if the data is not present.
        """
        raise NotImplementedError

    @property
    def user_id(self) -> str:
        """The unique id of the current LTI user.
        """
        return self.launch_params['user_id']

    @property
    def user_email(self) -> str:
        """The email of the current LTI user.
        """
        return self.launch_params['lis_person_contact_email_primary']

    @property
    def full_name(self) -> str:
        """The name of the current LTI user.
        """
        return self.launch_params['lis_person_name_full']

    @property
    def username(self) -> str:  # pragma: no cover
        """The username of the current LTI user.
        """
        return self.launch_params['user_id']

    @property
    def course_id(self) -> str:  # pragma: no cover
        """The course id of the current LTI course.
        """
        return self.launch_params['context_id']

    @property
    def course_name(self) -> str:  # pragma: no cover
        """The name of the current LTI course.
        """
        return self.launch_params['context_title']

    @property
    def assignment_id(self) -> str:
        """The id of the current LTI assignment.
        """
        raise NotImplementedError

    @property
    def assignment_name(self) -> str:
        """The name of the current LTI assignment.
        """
        raise NotImplementedError

    @property
    def outcome_service_url(self) -> str:
        """The url used to passback grades to the LMS.
        """
        raise NotImplementedError

    def has_outcome_service_url(self) -> bool:
        """Check if the current LTI request has ``outcome_service_url`` field.

        This is not the case when launch LTI occurs for viewing a result.

        :returns: A boolean indicating if a ``sourcedid`` field was found.
        """
        raise NotImplementedError

    @property
    def result_sourcedid(self) -> str:
        """The sourcedid of the current user for the current assignment.
        """
        raise NotImplementedError

    @property
    def assignment_state(self) -> 'models.AssignmentStateEnum':  # pylint: disable=protected-access
        """The state of the current LTI assignment.
        """
        raise NotImplementedError

    @property
    def course_roles(self) -> t.Sequence[LTICourseRole]:
        """The course roles of the user doing the launch."""
        raise NotImplementedError

    @property
    def global_roles(self) -> t.Sequence[LTIGlobalRole]:
        """The global roles of the user doing the launch."""
        raise NotImplementedError

    def ensure_lti_data_correct(self) -> None:  # pylint: disable=no-self-use
        """Make sure the lti data is correct.

        This is the place were you can do some sanity checks, and make sure the
        setup of the assignment was done correct.
        """
        return

    def _roles(self, key: str,
               role_type: t.Type[T_LTI_ROLE]) -> t.Sequence[T_LTI_ROLE]:
        roles = self._get_unsorted_roles(key, role_type)
        logger.info(
            'Getting roles for LTI 1.1',
            role_type=role_type.__name__,
            found_raw_roles=self.launch_params.get(key),
            parsed_roles=roles,
        )
        roles.sort(reverse=True)
        return roles

    def _get_unsorted_roles(self, key: str, role_type: t.Type[T_LTI_ROLE]
                            ) -> t.List[T_LTI_ROLE]:
        roles = []
        for role in self.launch_params[key].split(','):
            try:
                roles.append(role_type.parse(role))
            except LTIRoleException:
                pass

        return roles

    def get_assignment_deadline(self, default: DatetimeWithTimezone = None
                                ) -> t.Optional[DatetimeWithTimezone]:
        """Get the deadline of the current LTI assignment.

        :param default: The value to be returned of the assignment has no
            deadline. If ``default.__bool__`` is ``False`` the current date
            plus 365 days is used.
        :returns: The deadline of the assignment as a datetime.
        """
        raise NotImplementedError

    def ensure_lti_user(
        self
    ) -> t.Tuple['models.User', t.Optional[str], t.Optional[str]]:
        """Make sure the current LTI user is logged in as a psef user.

        This is done by first checking if we know a user with the current LTI
        user_id, if this is the case this is the user we log in and return.

        Otherwise we check if a user is logged in and this user has no LTI
        user_id, if this is the case we link the current LTI user_id to the
        current logged in user and return this user.

        Otherwise we create a new user and link this user to current LTI
        user_id.

        :returns: A tuple containing the items in order: the user found as
            described above, optionally a new token for the user to login with,
            optionally the updated email of the user as a string, this is
            ``None`` if the email was not updated.
        """
        user, token = models.UserLTIProvider.get_or_create_user(
            lti_user_id=self.user_id,
            lti_provider=self.lti_provider,
            wanted_username=self.username,
            full_name=self.full_name,
            email=self.user_email,
        )

        updated_email = None
        if user.reset_email_on_lti:
            user.email = self.user_email
            updated_email = self.user_email
            user.reset_email_on_lti = False

        return user, token, updated_email

    def get_course(self) -> 'models.Course':
        """Get the current LTI course as a psef course.
        """
        course_lti_provider = self.lti_provider.find_course(self.course_id)

        if course_lti_provider is None:
            course = models.Course.create_and_add(name=self.course_name)
            course_lti_provider = models.CourseLTIProvider.create_and_add(
                course=course,
                lti_provider=self.lti_provider,
                lti_context_id=self.course_id,
                deployment_id=self.course_id,
            )
        else:
            course = course_lti_provider.course

        if course.name != self.course_name:
            logger.info(
                'Course changed name',
                old_name=course.name,
                new_name=self.course_name
            )
            course.name = self.course_name

        db.session.flush()

        return course

    def create_and_add_assignment(
        self, course: 'models.Course'
    ) -> 'models.Assignment':
        """Create a new assignment in the database from the launch parameters.

        This function also adds the created assignment to the current session.
        """
        assignment = models.Assignment(
            name=self.assignment_name,
            state=self.assignment_state,
            course=course,
            deadline=self.get_assignment_deadline(),
            lti_assignment_id=self.assignment_id,
            description='',
            is_lti=True,
        )
        db.session.add(assignment)
        db.session.flush()
        return assignment

    def get_assignment(
        self, user: 'models.User', course: 'models.Course'
    ) -> 'models.Assignment':
        """Get the current LTI assignment as a psef assignment.
        """
        assignment = models.Assignment.query.filter(
            models.Assignment.lti_assignment_id == self.assignment_id,
            models.Assignment.course == course,
        ).first()
        if assignment is None:
            logger.info(
                'Creating new assignment',
                lti_assignment_id=self.assignment_id,
                course_id=course.id,
            )
            assignment = self.create_and_add_assignment(course=course)

        if self.has_result_sourcedid():
            if assignment.id in user.assignment_results:
                user.assignment_results[assignment.id
                                        ].sourcedid = self.result_sourcedid
            else:
                assig_res = models.AssignmentResult(
                    sourcedid=self.result_sourcedid,
                    user_id=user.id,
                    assignment_id=assignment.id
                )
                db.session.add(assig_res)

        if self.assignment_points_possible is not None:
            assignment.lti_points_possible = self.assignment_points_possible

        if self.has_outcome_service_url():
            assignment.lti_grade_service_data = self.outcome_service_url

        if not assignment.is_done:
            assignment.state = self.assignment_state

        if assignment.name != self.assignment_name:
            logger.info(
                'Assignment changed name',
                old_name=assignment.name,
                new_name=self.assignment_name
            )
            assignment.name = self.assignment_name

        assignment.deadline = self.get_assignment_deadline(
            default=assignment.deadline
        )

        db.session.flush()

        return assignment

    def set_user_role(self, user: 'models.User') -> None:
        """Set the role of the given user if the user has no role.

        The role is determined according to
        :py:data:`.LTI_SYSROLE_LOOKUPS`.

        .. note::
            If the role could not be matched the ``DEFAULT_ROLE`` configured
            in the config of the app is used.

        :param models.User user: The user to set the role for.
        """
        if user.role is None:
            global_roles = self.global_roles
            logger.info(
                'Checking global roles', given_global_roles=global_roles
            )

            for role in global_roles:
                if role.codegrade_role_name is None:
                    continue
                user.role = models.Role.query.filter_by(
                    name=role.codegrade_role_name
                ).one()
                return
            user.role = models.Role.query.filter_by(
                name=app.config['DEFAULT_ROLE']
            ).one()

    def set_user_course_role(
        self, user: 'models.User', course: 'models.Course'
    ) -> t.Optional[str]:
        """Set the course role for the given course and user if there is no
        such role just yet.

        The mapping is done using :py:data:`.LTI_COURSEROLE_LOOKUPS`. If no
        role could be found a new role is created with the default
        permissions.

        :param models.User user: The user to set the course role  for.
        :param models.Course course: The course to connect to user to.
        :returns: The name of the new role created, or ``None`` if no role was
            created.
        """
        if user.is_enrolled(course):
            return None

        unknown_roles: t.List[str] = []
        course_roles = self.course_roles
        logger.info(
            'Checking course roles',
            given_course_roles=course_roles,
        )
        for role in course_roles:
            if role.codegrade_role_name is None:
                # TODO: Do this check a bit cleaner, but for now this is fine.
                if role.name != 'Admin':
                    unknown_roles.append(role.name)
                continue
            crole = models.CourseRole.query.filter_by(
                course_id=course.id, name=role.codegrade_role_name
            ).one()
            user.enroll_in_course(course_role=crole)
            return None

        if not features.has_feature(features.Feature.AUTOMATIC_LTI_ROLE):
            raise APIException(
                'The given LTI role could not be found or was not valid. '
                'Please ask your instructor or site administrator.',
                f'No role in "{list(self.course_roles)}" is a known LTI role',
                APICodes.INVALID_STATE, 400
            )

        # Add a new course role
        new_created: t.Optional[str] = None

        new_role = (unknown_roles + ['New LTI Role'])[0]
        existing_role = models.CourseRole.query.filter_by(
            course_id=course.id, name=new_role
        ).first()
        if existing_role is None:
            existing_role = models.CourseRole(
                course=course, name=new_role, hidden=False
            )
            db.session.add(existing_role)
            new_created = new_role

        user.enroll_in_course(course_role=existing_role)
        return new_created

    def has_result_sourcedid(self) -> bool:
        """Check if the current LTI request has a ``sourcedid`` field.

        :returns: A boolean indicating if a ``sourcedid`` field was found.
        """
        raise NotImplementedError

    @classmethod
    def generate_xml(cls) -> str:
        """Generate a config XML for this LTI consumer.
        """
        return flask.render_template(
            'lti_common_cartridge.j2',
            external_url=app.config['EXTERNAL_URL'],
            properties=cls.get_lti_properties(),
            custom_extensions=cls.get_custom_extensions(),
        )

    @classmethod
    @abc.abstractmethod
    def passback_grade(
        cls: t.Type[T_LTI],
        *,
        key: str,
        secret: str,
        grade: t.Union[float, None, int],
        initial: bool,
        service_url: str,
        sourcedid: str,
        lti_points_possible: t.Optional[float],
        submission: 'models.Work',
        host: str,
    ) -> None:
        """Do a LTI grade passback.

        :param key: The oauth key to use.
        :param secret: The oauth secret to use.
        :param grade: The grade to pass back, between 0 and
            10. If it is `None` the grade will be deleted, if it is a ``bool``
            no grade information will be send.
        :param service_url: The url used for grade passback.
        :param sourcedid: The ``sourcedid`` used in the grade passback.
        :param lti_points_possible: The maximum amount of points possible for
            the assignment we are passing back as reported by the LMS during
            launch.
        :param host: The host of this CodeGrade instance.
        :returns: The response of the LTI consumer.
        """
        raise NotImplementedError

    @classmethod
    def _passback_grade(
        cls: t.Type[T_LTI],
        *,
        key: str,
        secret: str,
        grade: t.Union[float, int, None],
        initial: bool,
        service_url: str,
        sourcedid: str,
        lti_points_possible: t.Optional[float],
        submission: 'models.Work',
        use_submission_details: bool,
        url: str,
    ) -> None:
        logger.info(
            'Doing LTI grade passback',
            consumer_key=key,
            lti_outcome_service_url=service_url,
            url=url,
            grade=grade,
            initial=initial,
            use_submission_details=use_submission_details,
        )
        lti_operation: LTIOperation
        submission_details: SubmissionDetails = {}
        if use_submission_details:
            submission_details['submittedAt'
                               ] = submission.created_at.isoformat()

        data_type = (
            LTIResultDataType.lti_launch_url
            if cls.supports_lti_launch_as_result() else LTIResultDataType.url
        )

        if initial:
            lti_operation = LTIInitalReplaceResultOperation(
                data_type=data_type,
                data_value=url,
                submission_details=submission_details,
            )
        elif grade is None:
            lti_operation = LTIDeleteResultOperation()
        elif grade > 10:
            assert lti_points_possible is not None
            lti_operation = LTIRawReplaceResultOperation(
                data_type=data_type,
                data_value=url,
                grade=str((grade / 10) * lti_points_possible),
                submission_details=submission_details,
            )
        else:
            lti_operation = LTINormalReplaceResultOperation(
                data_type=data_type,
                data_value=url,
                grade=str((grade / 10)),
                submission_details=submission_details,
            )

        OutcomeRequest(
            consumer_key=key,
            consumer_secret=secret,
            lis_outcome_service_url=service_url,
            lis_result_sourcedid=sourcedid,
            lti_operation=lti_operation,
            message_identifier=str(submission.id),
        ).post_outcome_request()


@_register_provider
class CanvasLTI(LTI):
    """The LTI class used for the Canvas LMS.
    """

    @classmethod
    def get_lms_name(cls) -> str:
        return 'Canvas'

    @staticmethod
    def get_custom_extensions() -> str:
        """Get a string that will be used verbatim in the LTI xml.

        :returns: A string used as extension
        """
        return """
    <blti:extensions platform="canvas.instructure.com">
      <lticm:property name="tool_id">codegrade</lticm:property>
      <lticm:property name="privacy_level">public</lticm:property>
      <lticm:property name="domain">{}</lticm:property>
    </blti:extensions>
        """.format(urlparse(app.config['EXTERNAL_URL']).netloc)

    @staticmethod
    def supports_lti_launch_as_result() -> bool:
        return True

    @staticmethod
    def supports_lti_common_cartridge() -> bool:
        """Canvas supports common cartridges"""
        return True

    def ensure_lti_data_correct(self) -> None:
        super().ensure_lti_data_correct()
        for lti_prop in self.get_lti_properties():
            if not lti_prop.error_on_missing:
                continue
            if self.launch_params[lti_prop.internal] == lti_prop.external:
                raise APIException(
                    (
                        'It seems that CodeGrade was not added correctly as an'
                        ' assignment to this module, are you sure you did not'
                        ' add CodeGrade directly as an external tool?'
                    ),
                    f"The property {lti_prop.external} didn't have a value.",
                    APICodes.MISSING_REQUIRED_PARAM, 400
                )

    @staticmethod
    def get_lti_properties() -> t.List[LTIProperty]:
        """All extension properties used by Canvas.

        :returns: The extension properties needed.
        """
        return [
            LTIProperty(
                internal='custom_canvas_course_name',
                external='$Canvas.course.name',
                error_on_missing=True,
            ),
            LTIProperty(
                internal='custom_canvas_course_id',
                external='$Canvas.course.id',
                error_on_missing=True,
            ),
            LTIProperty(
                internal='custom_canvas_assignment_id',
                external='$Canvas.assignment.id',
                error_on_missing=True,
            ),
            LTIProperty(
                internal='custom_canvas_assignment_title',
                external='$Canvas.assignment.title',
                error_on_missing=True,
            ),
            LTIProperty(
                internal='custom_canvas_assignment_due_at',
                external='$Canvas.assignment.dueAt.iso8601',
            ),
            LTIProperty(
                internal='custom_canvas_assignment_published',
                external='$Canvas.assignment.published',
            ),
            LTIProperty(
                internal='custom_canvas_points_possible',
                external='$Canvas.assignment.pointsPossible',
            ),
        ]

    @staticmethod
    def supports_max_points() -> bool:
        return True

    @staticmethod
    def supports_deadline() -> bool:
        return True

    @staticmethod
    def supports_state_management() -> bool:
        return True

    @property
    def assignment_points_possible(self) -> t.Optional[float]:
        """The amount of points possible for the launched assignment.
        """
        try:
            return float(self.launch_params['custom_canvas_points_possible'])
        except (ValueError, KeyError):
            return None

    @property
    def username(self) -> str:
        return self.launch_params['custom_canvas_user_login_id']

    @property
    def course_name(self) -> str:
        return self.launch_params['custom_canvas_course_name']

    @property
    def course_id(self) -> str:
        return self.launch_params['custom_canvas_course_id']

    @property
    def assignment_id(self) -> str:
        return self.launch_params['custom_canvas_assignment_id']

    @property
    def assignment_name(self) -> str:
        return self.launch_params['custom_canvas_assignment_title']

    @property
    def outcome_service_url(self) -> str:
        return self.launch_params['lis_outcome_service_url']

    def has_outcome_service_url(self) -> bool:
        return 'lis_outcome_service_url' in self.launch_params

    @property
    def result_sourcedid(self) -> str:
        return self.launch_params['lis_result_sourcedid']

    def has_result_sourcedid(self) -> bool:
        return 'lis_result_sourcedid' in self.launch_params

    def create_and_add_assignment(
        self, course: 'models.Course'
    ) -> 'models.Assignment':
        if not self.has_outcome_service_url():
            helpers.add_warning(
                (
                    'It seems that CodeGrade was added directly to this module'
                    ' as an external tool, rather than as a CodeGrade'
                    ' assignment. Because of this we do not have the'
                    ' possibility to pass back grades. Make sure to first'
                    ' create a CodeGrade assignment and then connect that'
                    ' assignment to the module.'
                ), APIWarnings.POSSIBLE_LTI_SETUP_ERROR
            )
        return super().create_and_add_assignment(course=course)

    @property
    def assignment_state(self) -> 'models.AssignmentStateEnum':
        if self.launch_params['custom_canvas_assignment_published'] == 'true':
            return models.AssignmentStateEnum.open
        else:
            return models.AssignmentStateEnum.hidden

    @property
    def course_roles(self) -> t.Sequence[LTICourseRole]:
        return self._roles('ext_roles', LTICourseRole)

    @property
    def global_roles(self) -> t.Sequence[LTIGlobalRole]:
        return self._roles('ext_roles', LTIGlobalRole)

    def get_assignment_deadline(
        self, default: t.Optional[DatetimeWithTimezone] = None
    ) -> t.Optional[DatetimeWithTimezone]:
        try:
            deadline = dateutil.parser.parse(
                self.launch_params['custom_canvas_assignment_due_at']
            )
            deadline = deadline.astimezone(datetime.timezone.utc)
            return DatetimeWithTimezone.utcfromtimestamp(deadline.timestamp())
        except (KeyError, ValueError, OverflowError):
            return default

    @classmethod
    def passback_grade(
        cls: t.Type[T_LTI],
        *,
        key: str,
        secret: str,
        grade: t.Union[float, None, int],
        initial: bool,
        service_url: str,
        sourcedid: str,
        lti_points_possible: t.Optional[float],
        submission: 'models.Work',
        host: str,
    ) -> None:
        redirect = (
            '/courses/{course_id}'
            '/assignments/{assig_id}'
            '/submissions/{sub_id}?inLTI=true'
        ).format(
            course_id=submission.assignment.course_id,
            assig_id=submission.assignment_id,
            sub_id=submission.id,
        )
        # Namespacing this get parameter is important as Canvas duplicates all
        # get parameters in the body. This makes sure we won't override actual
        # launch parameters. Also the url doesn't need to be quoted, as canvas
        # does this for us.
        url = f'{host}/api/v1/lti/launch/1?codegrade_redirect={redirect}'
        cls._passback_grade(
            key=key,
            secret=secret,
            grade=grade,
            initial=initial,
            service_url=service_url,
            sourcedid=sourcedid,
            lti_points_possible=lti_points_possible,
            submission=submission,
            use_submission_details=True,
            url=url,
        )


class BareBonesLTIProvider(LTI):
    """The LTI class that implements LTI a for simple "bare bones" LMS.
    """

    @staticmethod
    def supports_lti_launch_as_result() -> bool:
        return False

    @property
    def assignment_points_possible(self) -> t.Optional[float]:
        return None

    @property
    def username(self) -> str:
        return self.launch_params['lis_person_sourcedid']

    @property
    def course_id(self) -> str:
        return self.launch_params['context_id']

    @property
    def course_name(self) -> str:
        return self.launch_params['context_title']

    @property
    def assignment_id(self) -> str:
        return self.launch_params['resource_link_id']

    @property
    def assignment_name(self) -> str:
        return self.launch_params['resource_link_title']

    @property
    def outcome_service_url(self) -> str:
        return self.launch_params['lis_outcome_service_url']

    def has_outcome_service_url(self) -> bool:
        return 'lis_outcome_service_url' in self.launch_params

    @property
    def result_sourcedid(self) -> str:
        return self.launch_params['lis_result_sourcedid']

    def has_result_sourcedid(self) -> bool:
        return 'lis_result_sourcedid' in self.launch_params

    @property
    def assignment_state(self) -> 'models.AssignmentStateEnum':
        return models.AssignmentStateEnum.open

    @property
    def course_roles(self) -> t.Sequence[LTICourseRole]:
        return self._roles('roles', LTICourseRole)

    @property
    def global_roles(self) -> t.Sequence[LTIGlobalRole]:
        return self._roles('roles', LTIGlobalRole)

    def get_assignment_deadline(
        self, default: t.Optional[DatetimeWithTimezone] = None
    ) -> t.Optional[DatetimeWithTimezone]:
        return default

    @classmethod
    def passback_grade(
        cls: t.Type[T_LTI],
        *,
        key: str,
        secret: str,
        grade: t.Union[float, None, int],
        initial: bool,
        service_url: str,
        sourcedid: str,
        lti_points_possible: t.Optional[float],
        submission: 'models.Work',
        host: str,
    ) -> None:
        if initial:
            # Bare bones lti providers (like Blackboard) don't support
            # passbacks without a grade (which happens for initial
            # passbacks). Users shouldn't set a due date on LTI assignments in
            # blackboard, as all submissions will be considered late.
            return

        url = (
            '{host}'
            '/courses/{course_id}'
            '/assignments/{assig_id}'
            '/submissions/{sub_id}?inLTI=true'
        ).format(
            host=host,
            course_id=submission.assignment.course_id,
            assig_id=submission.assignment_id,
            sub_id=submission.id,
        )
        cls._passback_grade(
            key=key,
            secret=secret,
            grade=grade,
            initial=False,
            service_url=service_url,
            sourcedid=sourcedid,
            lti_points_possible=lti_points_possible,
            submission=submission,
            use_submission_details=False,
            url=url,
        )


@_register_provider
class BlackboardLTI(BareBonesLTIProvider):
    """The LTI class used for the Blackboard LMS.
    """

    @classmethod
    def get_lms_name(cls) -> str:
        return 'Blackboard'


class _BareRolesLTIProvider(BareBonesLTIProvider):
    """This mixin is for LMSes that give the "Instructor" and "Learner" without
    any namespace, but they should be considered course roles.
    """

    def _get_unsorted_roles(self, key: str, role_type: t.Type[T_LTI_ROLE]
                            ) -> t.List[T_LTI_ROLE]:
        roles: t.List[T_LTI_ROLE] = []

        for role in self.launch_params[key].split(','):
            if role in {
                'Instructor', 'Learner'
            } and role_type == LTICourseRole:
                roles.append(
                    t.cast(T_LTI_ROLE, LTICourseRole(name=role, subnames=[]))
                )
            try:
                roles.append(role_type.parse(role))
            except LTIRoleException:
                pass

        return roles


@_register_provider
class SakaiLTI(_BareRolesLTIProvider):
    """The LTI class used for the Sakai LMS.
    """

    @classmethod
    def get_lms_name(cls) -> str:
        return 'Sakai'


@_register_provider
class OpenEdX(_BareRolesLTIProvider):
    """The LTI class used for the Open edX LMS.
    """

    @classmethod
    def get_lms_name(cls) -> str:
        return 'Open edX'

    def __init__(
        self,
        params: t.Mapping[str, str],
        lti_provider: 'models.LTI1p1Provider' = None
    ) -> None:
        super().__init__(params, lti_provider)

        if 'custom_component_display_name' not in self.launch_params:
            raise APIException(
                (
                    "We couldn't find the assignment name. Please make sure"
                    " you set the 'Display Name' option."
                ), (
                    'The custom_component_display_name property was missing'
                    ' from launch_params'
                ), APICodes.INVALID_STATE, 400
            )
        elif not self.has_outcome_service_url():
            raise APIException(
                (
                    'We do not have the option to passback the grade. This is'
                    ' probably because you forgot to enable the "Scored"'
                    ' option when configuring the assignment.'
                ), 'The outcome service url is missing',
                APICodes.INVALID_PARAM, 400
            )
        elif not urlparse(self.outcome_service_url).netloc:
            raise APIException(
                (
                    'It seems like you launched CodeGrade from Studio, this'
                    ' is not supported. When you open this link outside studio'
                    ' it will work.'
                ), (
                    'The outcome service url was not a complete url, so this'
                    ' launch was probably done from within Studio'
                ), APICodes.INVALID_STATE, 400
            )

    @property
    def assignment_name(self) -> str:
        """The name of the current LTI assignment.
        """
        return self.launch_params['custom_component_display_name']


@_register_provider
class MoodleLTI(_BareRolesLTIProvider):
    """The LTI class used for the Moodle LMS.
    """

    @classmethod
    def get_lms_name(cls) -> str:
        return 'Moodle'

    @property
    def username(self) -> str:
        """The username of the current LTI user.
        """
        return self.launch_params['ext_user_username']

    @staticmethod
    def supports_lti_common_cartridge() -> bool:
        """Moodle supports common cartridges"""
        return True

    @classmethod
    def passback_grade(
        cls: t.Type[T_LTI],
        *,
        key: str,
        secret: str,
        grade: t.Union[float, None, int],
        initial: bool,
        service_url: str,
        sourcedid: str,
        lti_points_possible: t.Optional[float],
        submission: 'models.Work',
        host: str,
    ) -> None:
        if initial:
            # Moodle registers a grade delete as setting the grade to zero.
            initial = False
            grade = None

        url = (
            '{host}'
            '/courses/{course_id}'
            '/assignments/{assig_id}'
            '/submissions/{sub_id}?inLTI=true'
        ).format(
            host=host,
            course_id=submission.assignment.course_id,
            assig_id=submission.assignment_id,
            sub_id=submission.id,
        )
        cls._passback_grade(
            key=key,
            secret=secret,
            grade=grade,
            initial=False,
            service_url=service_url,
            sourcedid=sourcedid,
            lti_points_possible=lti_points_possible,
            submission=submission,
            use_submission_details=False,
            url=url,
        )


@_register_provider
class BrightSpaceLTI(BareBonesLTIProvider):
    """The LTI class used for the BrightSpace LMS.
    """

    @classmethod
    def get_lms_name(cls) -> str:
        return 'BrightSpace'

    @property
    def username(self) -> str:
        return self.launch_params['ext_d2l_username']

    def _get_unsorted_roles(self, key: str, role_kind: t.Type[T_LTI_ROLE]
                            ) -> t.List[T_LTI_ROLE]:
        roles: t.List[T_LTI_ROLE] = []
        for role in self.launch_params[key].split(','):
            try:
                roles.append(role_kind.parse(role))
            except LTIRoleException:
                continue

        if role_kind != LTIGlobalRole and not roles:
            # Some Brightspace instances pass all roles as instrole (global
            # role). In those cases we yield each global role also as a course
            # role, because we cannot determine whether a role was meant to be
            # a global or a course role.
            for global_role in self._roles(key, LTIGlobalRole):
                roles.append(
                    role_kind(
                        name=global_role.name,
                        subnames=global_role.subnames,
                    )
                )

        return roles


#####################################
# START OF MIT LICENSED COPIED WORK #
#####################################

# This part is largely copied from https://github.com/tophatmonocle/ims_lti_py
# and MIT licensed, see below for the entire license.

# The MIT License (MIT)
#
# Copyright (c) 2017 University of Central Florida - Center for Distributed
# Learning
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


@enum.unique
class LTIResultDataType(enum.Enum):
    """All possible result data options for an LTI replaceResult request.
    """
    text = 'text'
    url = 'url'
    lti_launch_url = 'ltiLaunchUrl'


class LTIOperation(abc.ABC):
    """Base class representing a LTI operation.
    """

    @property
    @abc.abstractmethod
    def request_type(self) -> str:
        """Get the name of this operation as required in the LTI xml.
        """
        raise NotImplementedError


class LTIDeleteResultOperation(LTIOperation):
    """A delete result LTI operation.

    This operation deletes the result at canvas.
    """

    @property
    def request_type(self) -> str:
        return 'deleteResultRequest'


SubmissionDetails = TypedDict(  # pylint: disable=invalid-name
    'SubmissionDetails', {'submittedAt': str}, total=False
)


@dataclass
class LTIReplaceResultBaseOperation(LTIOperation, abc.ABC):
    """The base replaceResult LTI operation.
    """

    @property
    def request_type(self) -> str:
        return 'replaceResultRequest'

    data_type: LTIResultDataType
    data_value: str

    submission_details: SubmissionDetails


@dataclass
class LTINormalReplaceResultOperation(LTIReplaceResultBaseOperation):
    """A normal replaceResult with a grade that is in [0, 1]
    """
    grade: str


@dataclass
class LTIRawReplaceResultOperation(LTIReplaceResultBaseOperation):
    """A raw replaceResult with a grade that represents the amount of points a
    user got for the assignment.

    .. note:: This is currently only supported by Canvas.
    """
    grade: str


@dataclass
class LTIInitalReplaceResultOperation(LTIReplaceResultBaseOperation):
    """An initial replaceResult operation, which doens't provide a grade.
    """


class OutcomeRequest:
    """Class for generating LTI Outcome Requests.

    Outcome Request documentation:
        http://www.imsglobal.org/LTI/v1p1/ltiIMGv1p1.html#_Toc319560472
    """

    def __init__(
        self,
        *,
        lis_outcome_service_url: str,
        lis_result_sourcedid: str,
        consumer_key: str,
        consumer_secret: str,
        lti_operation: LTIOperation,
        message_identifier: str,
    ) -> None:
        self.lis_outcome_service_url = lis_outcome_service_url
        self.lis_result_sourcedid = lis_result_sourcedid
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.lti_operation = lti_operation
        self.message_identifier = message_identifier

    def post_outcome_request(self) -> 'OutcomeResponse':
        """Send this ``OutcomeRequest`` to the LTI provider.

        :returns: The parsed response from the provider.
        """
        log = logger.bind(
            operation=self.lti_operation,
            lti_request_message_identifier=self.message_identifier
        )
        log.info('Posting outcome request')

        consumer = oauth2.Consumer(
            key=self.consumer_key, secret=self.consumer_secret
        )

        client = oauth2.Client(consumer)

        # monkeypatch the _normalize function to ensures that the
        # ``Authorization`` header is NOT lower cased
        normalize = httplib2.Http._normalize_headers  # pylint: disable=protected-access

        def __my_normalize(
            self: t.Any, headers: t.Sequence
        ) -> t.Sequence:  # pragma: no cover
            ret = normalize(self, headers)
            if 'authorization' in ret:
                ret['Authorization'] = ret.pop('authorization')
            return ret

        httplib2.Http._normalize_headers = __my_normalize  # pylint: disable=protected-access
        monkey_patch_function = normalize

        response: httplib2.Response
        content: str
        passback_body = self.__generate_request_xml()
        log.info('Doing passback request', body=passback_body)
        response, content = client.request(
            uri=self.lis_outcome_service_url,
            method='POST',
            body=passback_body,
            headers={'Content-Type': 'application/xml'},
        )

        # Restore original function
        httplib2.Http._normalize_headers = monkey_patch_function  # pylint: disable=protected-access

        log = log.bind(
            response=response,
            response_body=content,
        )
        log.info('Posted outcome request')

        outcome = OutcomeResponse(content)

        log.bind(
            lti_response_message_identifier=outcome.message_identifier,
            lti_response_ref_message_identifier=outcome.message_ref_identifier,
            lti_code_major=outcome.code_major,
            lti_severity=outcome.severity,
            lti_description=outcome.description,
        )

        if outcome.message_ref_identifier != self.message_identifier:
            log.error('Received wrong "message_ref_identifier" in request')

        if outcome.is_failure:  # pragma: no cover
            log.error('Posting outcome failed')
        elif outcome.has_warning:  # pragma: no cover
            log.warning('Posting outcome had a warning')
        else:
            log.info('Posting outcome was successful')

        log.try_unbind(
            'response', 'response_body', 'operation', 'lti_code_major',
            'lti_severity', 'lti_description', 'lti_request_message_identifier'
            'lti_request_message_identifier',
            'lti_response_ref_message_identifier'
        )

        return outcome

    def __generate_request_xml(self) -> bytes:
        """Generate an xml that can be used to perform an outcome request.

        :returns: The xml as a bytestring.
        """
        root = ET.Element(
            'imsx_POXEnvelopeRequest', xmlns=LTI_NAMESPACES['xmlns']
        )

        header = ET.SubElement(root, 'imsx_POXHeader')
        header_info = ET.SubElement(header, 'imsx_POXRequestHeaderInfo')
        version = ET.SubElement(header_info, 'imsx_version')
        version.text = 'V1.0'
        message_identifier = ET.SubElement(
            header_info, 'imsx_messageIdentifier'
        )
        message_identifier.text = self.message_identifier
        body = ET.SubElement(root, 'imsx_POXBody')
        request = ET.SubElement(body, self.lti_operation.request_type)
        record = ET.SubElement(request, 'resultRecord')

        guid = ET.SubElement(record, 'sourcedGUID')

        sourcedid = ET.SubElement(guid, 'sourcedId')
        sourcedid.text = self.lis_result_sourcedid

        if isinstance(self.lti_operation, LTIReplaceResultBaseOperation):
            result = ET.SubElement(record, 'result')

            if isinstance(
                self.lti_operation, (
                    LTINormalReplaceResultOperation,
                    LTIRawReplaceResultOperation
                )
            ):
                grade = self.lti_operation.grade

                if isinstance(
                    self.lti_operation, LTIRawReplaceResultOperation
                ):
                    result_score = ET.SubElement(result, 'resultTotalScore')
                else:
                    result_score = ET.SubElement(result, 'resultScore')

                language = ET.SubElement(result_score, 'language')
                language.text = 'en'
                text_string = ET.SubElement(result_score, 'textString')
                text_string.text = grade

            result_data = ET.SubElement(result, 'resultData')
            result_data_el = ET.SubElement(
                result_data, self.lti_operation.data_type.value
            )
            result_data_el.text = self.lti_operation.data_value

            if self.lti_operation.submission_details:
                details_el = ET.SubElement(request, 'submissionDetails')
                for key, value in self.lti_operation.submission_details.items(
                ):
                    sub_details_el = ET.SubElement(details_el, key)
                    sub_details_el.text = str(value)

        return ET.tostring(root, encoding='utf-8')


class OutcomeResponse:
    """This class consumes LTI Outcome Responses.

    Response documentation:
        http://www.imsglobal.org/LTI/v1p1/ltiIMGv1p1.html#_Toc319560472

    Error code documentation:
        http://www.imsglobal.org/gws/gwsv1p0/imsgws_baseProfv1p0.html#1639667

    >>> import doctest
    >>> import os
    >>> doctest.ELLIPSIS_MARKER = '-etc-'
    >>> get_file = lambda name: open(
    ... os.path.join(
    ...   os.path.dirname(__file__),
    ...   '..',
    ...   '..',
    ...   'test_data',
    ...   'example_strings',
    ...   name,
    ... )).read()

    >>> res = OutcomeResponse(get_file('invalid_xml.xml'))
    -etc-
    >>> res.code_major, res.severity, res.description
    ('failure', 'error', 'unknown error')
    >>> res.is_success, res.is_failure, res.has_warning
    (False, True, False)

    >>> res = OutcomeResponse(get_file('invalid_replace_result.xml'))
    -etc-
    >>> res.code_major, res.severity, res.description
    ('failure', 'error', 'unknown error')
    >>> res.is_success, res.is_failure, res.has_warning
    (False, True, False)

    >>> res = OutcomeResponse(get_file('valid_replace_result.xml'))
    >>> (
    ...   res.code_major,
    ...   res.severity,
    ...   res.description,
    ...   res.message_identifier,
    ...   res.message_ref_identifier,
    ... )
    ('success', 'status', 'Score for 3124567 is now 0.92', '4560', '999999123')
    >>> res.is_success, res.is_failure, res.has_warning
    (True, False, False)
    """

    def __init__(
        self,
        input_xml: str,
    ) -> None:
        self.message_identifier: t.Optional[str] = None

        self.code_major: t.Optional[str] = None
        self.severity: t.Optional[str] = None
        self.description: t.Optional[str] = None
        self.operation: t.Optional[str] = None
        self.message_ref_identifier: t.Optional[str] = None

        self.__process_xml(input_xml)

    @property
    def is_success(self) -> bool:
        """Check if a response indicated a success.

        :returns: ``True`` if the response indicated a success.
        """
        return self.code_major == 'success'

    @property
    def is_failure(self) -> bool:
        """Check if a response indicated a failure.

        :returns: ``True`` if the response indicated a failure.
        """
        return self.code_major == 'failure'

    @property
    def has_warning(self) -> bool:
        """Check if a response had a warning

        :returns: ``True`` if the response had a warning
        """
        return self.severity == 'warning'

    def __process_xml(self, input_xml: str) -> None:
        """Parse OutcomeResponse data form XML.

        :param xml: The xml to parse.
        :returns: Nothing
        """

        class WrongValueException(ValueError):
            pass

        def get_node(root: ET.Element, path: str) -> ET.Element:
            node = root.find(path, namespaces=LTI_NAMESPACES)
            if node is None:
                raise WrongValueException(
                    'Could not find path', root, path.split('/')
                )
            return node

        def get_text(root: ET.Element, path: str) -> t.Optional[str]:
            return get_node(root, path).text

        try:
            root: ET.Element = defused_xml_fromstring(input_xml)

            # Get message idenifier from header info
            self.message_identifier = get_text(
                root,
                (
                    'xmlns:imsx_POXHeader/'
                    'xmlns:imsx_POXResponseHeaderInfo/'
                    'xmlns:imsx_messageIdentifier'
                ),
            )

            status_node = get_node(
                root,
                (
                    'xmlns:imsx_POXHeader/'
                    'xmlns:imsx_POXResponseHeaderInfo/'
                    'xmlns:imsx_statusInfo'
                ),
            )

            # Get status parameters from header info status
            self.code_major = get_text(status_node, 'xmlns:imsx_codeMajor')
            self.severity = get_text(status_node, 'xmlns:imsx_severity')
            self.description = get_text(status_node, 'xmlns:imsx_description')
            self.message_ref_identifier = get_text(
                status_node, 'xmlns:imsx_messageRefIdentifier'
            )
            self.operation = get_text(
                status_node, 'xmlns:imsx_operationRefIdentifier'
            )
        except (WrongValueException, ET.ParseError):
            logger.error(
                'Broken xml received',
                xml_received=xml,
                exc_info=True,
            )
            self.code_major = 'failure'
            self.severity = 'error'
            self.description = 'unknown error'


###################################
# END OF MIT LICENSED COPIED WORK #
###################################
