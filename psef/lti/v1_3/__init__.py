import copy
import typing as t
import dataclasses
import urllib.parse
from datetime import timedelta

import requests
import werkzeug
import structlog
import sqlalchemy.sql
from pylti1p3.actions import Action as PyLTI1p3Action
from pylti1p3.lineitem import LineItem
from typing_extensions import Final, Literal, TypedDict
from pylti1p3.deployment import Deployment
from pylti1p3.oidc_login import OIDCLogin
from pylti1p3.tool_config import ToolConfAbstract
from pylti1p3.registration import Registration
from pylti1p3.message_launch import MessageLaunch
from pylti1p3.service_connector import ServiceConnector
from pylti1p3.assignments_grades import AssignmentsGradesService
from pylti1p3.deep_link_resource import DeepLinkResource

import flask
import cg_override
from cg_dt_utils import DatetimeWithTimezone

from . import claims
from ... import PsefFlask, models, helpers, signals, current_app
from .flask import (
    FlaskRequest, FlaskRedirect, FlaskCookieService, FlaskSessionService
)
from .roles import SystemRole
from ...cache import cache_within_request_make_key
from ...models import db
from ..abstract import AbstractLTIConnector
from ...exceptions import APICodes, APIException

logger = structlog.get_logger()

T = t.TypeVar('T')

if t.TYPE_CHECKING:
    from pylti1p3.message_launch import _JwtData, _LaunchData, _KeySet

NEEDED_AGS_SCOPES = [
    'https://purl.imsglobal.org/spec/lti-ags/scope/score',
    'https://purl.imsglobal.org/spec/lti-ags/scope/lineitem',
]

NEEDED_SCOPES = [
    *NEEDED_AGS_SCOPES,
    'https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly',
]

MemberLike = TypedDict('MemberLike', {'name': str, 'email': str}, total=False)


def get_email_for_user(
    member: MemberLike, provider: 'models.LTI1p3Provider'
) -> str:
    full_name = member['name']
    caps = provider.lms_capabilities
    test_stud_name = caps.test_student_name
    if test_stud_name is not helpers.UNSET and test_stud_name == full_name:
        return member.get('email', 'test_student@codegra.de')
    return member['email']


class CGServiceConnector(ServiceConnector):
    def __init__(self, provider: 'models.LTI1p3Provider') -> None:
        super().__init__(provider.get_registration())
        self._provider = provider

    @cg_override.override
    def get_access_token(self, scopes: t.Sequence[str]) -> str:
        scopes = sorted(scopes)
        scopes_str = '|'.join(scopes)
        cache = current_app.inter_request_cache.lti_access_tokens
        super_method = super().get_access_token

        return cache.get_or_set(
            f'lti-provider-{self._provider.id}-{scopes_str}',
            lambda: super_method(scopes),
        )


class CGAssignmentsGradesService(AssignmentsGradesService):
    def __init__(
        self, service_connector: ServiceConnector,
        assignment: 'models.Assignment'
    ):
        assert assignment.is_lti
        assert isinstance(assignment.lti_grade_service_data, dict)

        super().__init__(service_connector, assignment.lti_grade_service_data)
        self._assignment = assignment


class CGCustomClaims:
    @dataclasses.dataclass(frozen=True)
    class ClaimResult:
        username: str
        deadline: t.Optional[DatetimeWithTimezone]
        is_available: t.Optional[bool]
        resource_id: t.Optional[str]

    class _ReplacementVar:
        def __init__(self, name: str) -> None:
            self.name = name

    class _AbsoluteVar:
        def __init__(self, name: str) -> None:
            self.name = name

    @dataclasses.dataclass(frozen=True)
    class _Var:
        name: str
        opts: t.List[t.Union['CGCustomClaims._ReplacementVar',
                             'CGCustomClaims._AbsoluteVar']]
        required: bool

        def get_replacement_opts(
            self
        ) -> t.Iterable['CGCustomClaims._ReplacementVar']:
            for opt in self.opts:
                if isinstance(opt, CGCustomClaims._ReplacementVar):
                    yield opt

        def get_key(self, idx: int) -> str:
            return f'{self.name}_{idx}'

    _WANTED_VARS: Final = [
        _Var(
            'cg_username', [
                _ReplacementVar('$User.username'),
                _AbsoluteVar('lis_person_sourcedid')
            ], True
        ),
        _Var(
            'cg_deadline',
            [
                _ReplacementVar('$ResourceLink.submission.endDateTime'),
                _ReplacementVar('$Canvas.assignment.dueAt.iso8601')
            ],
            False,
        ),
        _Var(
            'cg_available_at',
            [_ReplacementVar('$ResourceLink.submission.startDateTime')],
            False,
        ),
        _Var(
            'cg_is_published',
            [_ReplacementVar('$Canvas.assignment.published')],
            False,
        ),
        _Var(
            'cg_resource_id',
            [_ReplacementVar('$ResourceLink.id')],
            False,
        )
    ]

    _VAR_LOOKUP: Final = {var.name: var for var in _WANTED_VARS}

    @classmethod
    def get_variable_claims_config(cls) -> t.Mapping[str, str]:
        res: t.Dict[str, str] = {}
        for var in cls._WANTED_VARS:
            for idx, opt in enumerate(var.get_replacement_opts()):
                res[var.get_key(idx)] = opt.name

        return res

    @classmethod
    def get_claim_keys(cls) -> t.Iterable[str]:
        yield from cls.get_variable_claims_config().keys()

    @classmethod
    def _get_claim(
        cls,
        var_name: str,
        custom_data: t.Mapping[str, str],
        base_data: t.Mapping[str, object],
        converter: t.Callable[[str], T],
    ) -> t.Optional[T]:
        var = cls._VAR_LOOKUP[var_name]

        for idx, opt in enumerate(var.opts):
            found_val: object

            if isinstance(opt, cls._ReplacementVar):
                found_val = custom_data.get(var.get_key(idx), opt.name)
            else:
                found_val = base_data.get(opt.name, opt.name)

            if isinstance(found_val, str) and found_val != opt.name:
                logger.info(
                    'Trying to parse claim',
                    found_value=found_val,
                    current_variable=var
                )
                return converter(found_val)

        if var.required:
            raise AssertionError(
                'Required variable {} was not found in {}'.format(
                    var_name, base_data
                )
            )
        return None

    @classmethod
    def get_custom_claim_data(
        cls,
        custom_claims: t.Mapping[str, str],
        base_data: t.Mapping[str, object],
    ) -> 'CGCustomClaims.ClaimResult':
        username = cls._get_claim('cg_username', custom_claims, base_data, str)
        # Username is a required var, so this should never happen
        assert username is not None, 'Required data not found'

        resource_id = cls._get_claim(
            'cg_resource_id', custom_claims, base_data, str
        )

        deadline = cls._get_claim(
            'cg_deadline', custom_claims, base_data,
            DatetimeWithTimezone.parse_isoformat
        )

        available_at = cls._get_claim(
            'cg_available_at', custom_claims, base_data,
            DatetimeWithTimezone.parse_isoformat
        )
        if available_at is None:
            is_available = cls._get_claim(
                'cg_is_published',
                custom_claims,
                base_data,
                lambda x: x == 'true',
            )
        else:
            is_available = DatetimeWithTimezone.utcnow() >= available_at

        return CGCustomClaims.ClaimResult(
            username=username,
            deadline=deadline,
            is_available=is_available,
            resource_id=resource_id,
        )


class CGDeepLinkResource(DeepLinkResource):
    @classmethod
    def make(cls, app: PsefFlask) -> 'CGDeepLinkResource':
        return cls(
        ).set_url(f'{app.config["EXTERNAL_URL"]}/api/v1/lti1.3/launch')


def init_app(app: PsefFlask) -> None:
    pass


class LTIConfig(ToolConfAbstract[FlaskRequest]):
    def check_iss_has_one_client(self, iss: str) -> bool:
        return False

    def find_registration_by_issuer(
        self, iss: str, *args: None,
        **kwargs: t.Union[Literal['message_launch', 'oidc_login'],
                          FlaskRequest, '_LaunchData']
    ) -> t.Optional[Registration]:
        raise AssertionError("We don't support registration by only issuer")

    def find_registration_by_params(
        self,
        iss: str,
        client_id: t.Optional[str],
        *args: None,
        **kwargs: t.Union[Literal['message_launch', 'oidc_login'],
                          FlaskRequest, '_LaunchData'],
    ) -> t.Optional[Registration]:
        filters = [models.LTI1p3Provider.iss == iss]
        if isinstance(client_id, str):
            filters.append(models.LTI1p3Provider.client_id == client_id)

        return helpers.filter_single_or_404(
            models.LTI1p3Provider,
            *filters,
        ).get_registration()

    def find_deployment(
        self,
        iss: str,
        deployment_id: str,
    ) -> None:
        return None

    def find_deployment_by_params(
        self, iss: str, deployment_id: str, client_id: str, *args: None,
        **kwargs: None
    ) -> None:
        return None


class FlaskMessageLaunch(
    AbstractLTIConnector,
    MessageLaunch[FlaskRequest, LTIConfig, FlaskSessionService,
                  FlaskCookieService]
):
    _provider: t.Optional['models.LTI1p3Provider'] = None

    @cg_override.override
    def fetch_public_key(self, key_set_url: str) -> '_KeySet':
        provider = self.get_lti_provider()
        cache = current_app.inter_request_cache.lti_public_keys
        super_method = super().fetch_public_key

        return cache.get_or_set(
            f'lti-provider-{provider.id}-{key_set_url}',
            lambda: super_method(key_set_url),
        )

    def get_lms_name(self) -> str:
        return self.get_lti_provider().lms_name

    def set_user_role(self, user: 'models.User') -> None:
        """Set the role of the given user if the user has no role.

        If the role could not be matched the ``DEFAULT_ROLE`` configured in the
        config of the app is used.

        :param models.User user: The user to set the role for.
        """
        if user.role is not None:
            return

        roles_claim = self.get_launch_data()[claims.ROLES]
        global_roles = SystemRole.parse_roles(roles_claim)
        logger.info(
            'Checking global roles',
            given_global_roles=global_roles,
            roles_claim=roles_claim,
        )

        role_name = (
            global_roles[0].codegrade_role_name
            if global_roles else current_app.config['DEFAULT_ROLE']
        )
        user.role = models.Role.query.filter(
            models.Role.name == role_name,
        ).one()

    def _get_resource_id(self) -> t.Optional[str]:
        custom_claim = self.get_custom_claims()
        resource_id = custom_claim.resource_id

        if resource_id is None:
            launch_data = self.get_launch_data()
            resource_claim = launch_data.get(claims.RESOURCE, {})
            resource_id = resource_claim.get('id', None)

        return resource_id

    def _find_assignment(
        self,
        course: 'models.Course',
    ) -> 't.Optional[models.Assignment]':
        resource_id = self._get_resource_id()
        if resource_id is None:
            return None

        return course.get_assignments().filter(
            models.Assignment.is_visible,
            models.Assignment.lti_assignment_id == resource_id,
        ).one_or_none()

    def get_assignment(
        self, user: 'models.User', course: 'models.Course'
    ) -> 'models.Assignment':
        launch_data = self.get_launch_data()
        resource_claim = launch_data[claims.RESOURCE]
        custom_claim = self.get_custom_claims()

        assignment = self._find_assignment(course)
        logger.bind(assignment=assignment)

        if assignment is None:
            resource_id = self._get_resource_id()
            if resource_id is None:
                # This could easily happen with LTI 1.1, simply using CodeGrade
                # in another place than assignments. This shouldn't be the case
                # for LTI1.3, but better to be sure.
                raise APIException(
                    (
                        'No resource id was provided for this launch, please'
                        ' check that you are in fact creating an assignment'
                    ), (
                        'The launch was not done in a resource context, so we'
                        ' were not provided with the necessary information.'
                    ), APICodes.INVALID_PARAM, 400
                )

            assignment = models.Assignment(
                course=course,
                name=resource_claim['title'],
                visibility_state=models.AssignmentVisibilityState.visible,
                is_lti=True,
                lti_assignment_id=resource_id,
            )
            db.session.add(assignment)
            db.session.flush()

        assignment.lti_grade_service_data = launch_data[claims.GRADES]

        if custom_claim.deadline is not None:
            assignment.deadline = custom_claim.deadline

        # This claim is not required by the LTI spec, so we simply don't
        # override the assignment name if it is not given or if it is empty.
        if resource_claim.get('title'):
            assignment.name = resource_claim['title']

        if not assignment.is_done:
            if custom_claim.is_available is None or custom_claim.is_available:
                assignment.state = models._AssignmentStateEnum.open
            else:
                assignment.state = models._AssignmentStateEnum.hidden

        return assignment

    def set_user_course_role(
        self, user: 'models.User', course: 'models.Course'
    ) -> t.Optional[str]:
        assert course.course_lti_provider
        return course.course_lti_provider.maybe_add_user_to_course(
            user,
            self.get_launch_data()[claims.ROLES],
        )

    @cg_override.override
    def _get_request_param(self, key: str) -> object:
        return self._request.get_param(key)

    @classmethod
    def from_request(cls) -> 'FlaskMessageLaunch':
        f_request = FlaskRequest(force_post=True)
        self = cls(
            f_request,
            LTIConfig(),
            FlaskSessionService(f_request),
            FlaskCookieService(),
        )
        return self

    def get_lti_provider(self) -> 'models.LTI1p3Provider':
        if self._provider is None:
            assert self._registration is not None

            client_id = self._registration.get_client_id()
            self._provider = helpers.filter_single_or_404(
                models.LTI1p3Provider,
                models.LTI1p3Provider.iss == self._get_iss(),
                models.LTI1p3Provider.client_id == client_id,
            )
        return self._provider

    # We never want to save the launch data in the session, as we have no
    # use-case for it, and it slows down every request
    @cg_override.override
    def save_launch_data(self) -> 'FlaskMessageLaunch':
        return self

    @cg_override.override
    def validate_deployment(self) -> 'FlaskMessageLaunch':
        return self

    def validate_has_needed_data(self) -> 'FlaskMessageLaunch':
        """Check that all data required by CodeGrade is present.
        """
        launch_data = self.get_launch_data()
        provider = self.get_lti_provider()

        def get_exc(
            msg: str,
            claim: t.Union[None, t.Mapping, t.Sequence[str]],
            missing: t.Iterable[str],
        ) -> APIException:
            return APIException(
                msg,
                f'The claim "{claim}" was missing the following keys: {missing}',
                APICodes.MISSING_REQUIRED_PARAM, 400
            )

        def check_and_raise(
            msg: str,
            mapping: t.Optional[t.Mapping[str, object]],
            *keys: str,
        ) -> None:
            missing: t.Iterable[str]
            if mapping:
                missing = [key for key in keys if key not in mapping]
            else:
                missing = keys

            if missing:
                raise get_exc(msg, mapping, missing)

        user_err_msg = (
            'We are missing required data about the user doing this LTI'
            ' launch, please check the privacy levels of the tool:'
            ' CodeGrade requires the {} of the user.'
        )
        check_and_raise(user_err_msg.format('name'), launch_data, 'name')
        if provider.lms_capabilities.test_student_name != launch_data['name']:
            check_and_raise(user_err_msg.format('email'), launch_data, 'email')

        context = launch_data.get(claims.CONTEXT)
        check_and_raise(
            'The LTI launch did not contain a context', context, 'id', 'title'
        )

        custom = launch_data[claims.CUSTOM]
        check_and_raise(
            (
                'The LTI launch is missing required custom claims, the setup'
                ' was probably done incorrectly'
            ), custom, *CGCustomClaims.get_claim_keys()
        )

        if not self.is_deep_link_launch():
            if not self.has_nrps():
                raise get_exc(
                    (
                        'It looks like the NamesRoles Provisioning service is not'
                        ' enabled for this LTI deployment, please check your'
                        ' configuration.'
                    ),
                    launch_data,
                    claims.NAMESROLES,
                )

            ags = launch_data.get(claims.GRADES, {})
            check_and_raise(
                (
                    'It looks like the Assignments and Grades service is not'
                    ' enabled for this LTI deployment, please check your'
                    ' configuration'
                ),
                ags,
                'scope',
            )

            scopes = ags.get('scope', [])

            check_and_raise(
                (
                    'We do not have the required permissions for passing back'
                    ' grades and updating deadlines in the LMS, please check your'
                    ' configuration'
                ),
                {s: True
                 for s in scopes},
                *NEEDED_AGS_SCOPES,
            )

        # We don't need to check the roles claim, as that is required by spec
        # to always exist. The same for the resource claim, it is also
        # required.

        return self

    @cg_override.override
    def validate(self) -> 'FlaskMessageLaunch':
        super().validate()

        try:
            return self.validate_has_needed_data()
        except:
            self._validated = False
            raise

    def get_custom_claims(self) -> CGCustomClaims.ClaimResult:
        launch_data = self.get_launch_data()
        return CGCustomClaims.get_custom_claim_data(
            launch_data[claims.CUSTOM], launch_data
        )

    def ensure_lti_user(
        self
    ) -> t.Tuple['models.User', t.Optional[str], t.Optional[str]]:
        launch_data = self.get_launch_data()
        custom_claims = self.get_custom_claims()
        full_name = launch_data['name']
        email = get_email_for_user(launch_data, self.get_lti_provider())

        user, token = models.UserLTIProvider.get_or_create_user(
            lti_user_id=launch_data['sub'],
            lti_provider=self.get_lti_provider(),
            wanted_username=custom_claims.username,
            full_name=full_name,
            email=email,
        )

        updated_email = None
        if user.reset_email_on_lti:
            user.email = email
            updated_email = user.email
            user.reset_email_on_lti = False

        return user, token, updated_email

    def get_course(self) -> 'models.Course':
        launch_data = self.get_launch_data()
        deployment_id = self._get_deployment_id()
        context_claim = launch_data[claims.CONTEXT]
        course_lti_provider = db.session.query(
            models.CourseLTIProvider
        ).filter(
            models.CourseLTIProvider.deployment_id == deployment_id,
            models.CourseLTIProvider.lti_course_id == context_claim['id'],
            models.CourseLTIProvider.lti_provider == self.get_lti_provider(),
        ).one_or_none()

        if course_lti_provider is None:
            course = models.Course.create_and_add(name=context_claim['title'])
            course_lti_provider = models.CourseLTIProvider.create_and_add(
                course=course,
                lti_provider=self.get_lti_provider(),
                lti_context_id=context_claim['id'],
                deployment_id=deployment_id,
            )
            models.db.session.flush()
        else:
            course = course_lti_provider.course

        course.name = context_claim['title']
        if claims.NAMESROLES in launch_data:
            course_lti_provider.names_roles_claim = launch_data[
                claims.NAMESROLES]

        return course

    @classmethod
    def from_message_data(
        cls,
            *,
        launch_data: t.Mapping[str, object],
    ) -> 'FlaskMessageLaunch':
        f_request = FlaskRequest(force_post=False)
        obj = cls(
            f_request,
            LTIConfig(),
            session_service=FlaskSessionService(f_request),
            cookie_service=FlaskCookieService(),
        )

        return obj.set_auto_validation(enable=False) \
            .set_jwt(t.cast('_JwtData', {'body': launch_data})) \
            .set_restored() \
            .validate_registration()


class FlaskOIDCLogin(
    OIDCLogin[FlaskRequest, LTIConfig, FlaskSessionService, FlaskCookieService,
              werkzeug.wrappers.Response]
):
    @cg_override.override
    def get_redirect(self, url: str) -> FlaskRedirect:
        return FlaskRedirect(url, self._cookie_service)

    @classmethod
    def from_request(cls) -> 'FlaskOIDCLogin':
        f_request = FlaskRequest(force_post=False)
        return FlaskOIDCLogin(
            f_request,
            LTIConfig(),
            FlaskSessionService(f_request),
            FlaskCookieService(),
        )
