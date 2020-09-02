"""This file implements the main logic for handling LTI 1.3 launches.

LTI 1.3 depends on an OpenId Connect like authentication flow, I really
recommend that you read the actual docs for LTI 1.3 (see the IMS Global
website), but here is short recap.

First a user navigates to a page of the LMS (Platform in LTI 1.3 terms, tool
consumer in LTI 1.1 terms) which redirects the user to the OIDC login endpoint
of CodeGrade (Tool in LTI 1.3 terms, Tool Provider in LTI 1.1 terms). We verify
some things in this OIDC login request, and save state in the session of the
user (to prevent replay attacks), and redirect the user to a page specified in
the ODIC login request. The LMS now redirects the user again, but now to the
launch url.

We verify the request (by using the public key from the tool, which we will
probably download or get from our cache, see
:meth:`.FlaskMessageLaunch.fetch_public_key`), and verify that the state saved
in the OIDC login request is present and correct. This finalizes the LTI stage
of the protocol.

Now we will do an extra redirection step. This is partly done to be able to
reuse logic of our LTI 1.1 implementation (which does this for legacy reasons),
but also to get some state inside our Vue application.

We save the data in the launch request to our :class:`psef.models.BlobStorage`
table, and redirect the user to the CodeGrade LTI launch page. Javascript on
this page will post to the ``/api/v1/lti/launch/2`` endpoint with the id for
the blob storage object. We will now create a :class:`.FlaskMessageLaunch`
using this data, and execute the
:meth:`psef.lti.abstract.do_second_step_of_lti` method.

.. seealso::

    The main `LTI 1.3 documentation <http://www.imsglobal.org/spec/lti/v1p3>`_.

    `OIDC login flow <https://www.imsglobal.org/spec/security/v1p0/#fig_oidcflow>`_
    from the LMS documentation. This shows the redirection flow.

SPDX-License-Identifier: AGPL-3.0-only
"""
import copy
import time
import typing as t
import dataclasses

import werkzeug
import structlog
from pylti1p3 import grade
from typing_extensions import Final, Literal, TypedDict
from pylti1p3.oidc_login import OIDCLogin
from pylti1p3.tool_config import ToolConfAbstract
from pylti1p3.registration import Registration
from pylti1p3.message_launch import MessageLaunch
from pylti1p3.service_connector import ServiceConnector
from pylti1p3.assignments_grades import AssignmentsGradesService
from pylti1p3.deep_link_resource import DeepLinkResource

import cg_override
from cg_dt_utils import DatetimeWithTimezone

from . import claims
from ... import PsefFlask, models, helpers, current_app
from .flask import (
    FlaskRequest, FlaskRedirect, FlaskCookieService, FlaskSessionService
)
from .roles import SystemRole
from ...models import db
from ..abstract import AbstractLTIConnector
from ...exceptions import APICodes, APIException

logger = structlog.get_logger()

T = t.TypeVar('T')

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from .lms_capabilities import LMSCapabilities
    from pylti1p3.message_launch import _JwtData, _LaunchData, _KeySet, _DeepLinkData

NEEDED_AGS_SCOPES = [
    'https://purl.imsglobal.org/spec/lti-ags/scope/score',
]

NEEDED_SCOPES = [
    *NEEDED_AGS_SCOPES,
    'https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly',
]

MemberLike = TypedDict('MemberLike', {'name': str, 'email': str}, total=False)


class _TestCookie:
    """This class contains the functionality for a test cookie.

    This cookie tests if we are able to set at all in an LTI launch.

    Currently :mod:`pylti1p3` also implements some form of testing if cookies
    are enabled, however that is done quite a bit differently. It redirects
    users to a specific page after the OIDC login (effectively stopping the
    launch there for a while) which checks the cookies and if it is able to set
    cookies it resumes the LTI flow (by redirecting to the correct OIDC
    redirection point). The advantage of this flow is that it is easier to
    detect if cookies are not working, but it also has disadvantages. The first
    one is that does an extra redirect for every user, even those without any
    cookie issues, furthermore it doesn't finish the LTI launch, so we are not
    able to use the (Canvas specific) features of the LMS to try and set
    cookies. In other words: we now that this functionality can be achieved
    using the library we are using, but we think our solution better suits our
    needs.
    """
    _NAME = 'CG_TEST_COOKIE'
    _MAX_DIFF = 600

    @classmethod
    def set_value(cls, service: FlaskCookieService) -> None:
        """This method sets the test cookie in the given cookie ``service``.

        :param service: The service in which you want to set the cookie.
        """
        service.set_cookie(cls._NAME, str(int(time.time())))

    @classmethod
    def clear_cookie_in_request(cls, service: FlaskCookieService) -> None:
        """Clear the test cookie in the given ``service``.
        """
        service.clear_cookie(cls._NAME)

    @classmethod
    def validate_value_in_request(
        cls, service: FlaskCookieService, provider: 'models.LTI1p3Provider'
    ) -> None:
        """Validate the test cookie, for both existence and correctness.

        :param service: The cookie service in which we should look for the
            cookie.
        :param provider: The LTI provider of this launch. This parameter is
            used to see if we can try to do anything about the issue. See the
            :meth:`psef.lti.v1_3.LMSCapabilities.cookie_post_message`.
        """
        found = service.get_cookie(cls._NAME)
        # Make sure the next launch tests for existence of the cookie again.
        cls.clear_cookie_in_request(service)
        if found is None:
            logger.info('Test cookie was not set')
            raise MissingCookieError(provider)

        # We store the time in the cookie to make sure we are actually seeing a
        # recent test cookie. This is to make sure we were able to set cookies
        # in the last OIDC login request. The method is not really precise (it
        # simply checks that the cookie is not too old, not that it was really
        # set in the last OIDC login), but this class isn't used for security
        # purposes so it doesn't really matter.
        now = time.time()

        try:
            diff = abs(now - int(found))
        except ValueError:
            logger.info('Test cookie had invalid data')
            diff = cls._MAX_DIFF + 1

        if diff > cls._MAX_DIFF:
            logger.info('Test cookie was to old')
            raise MissingCookieError(provider)


class MissingCookieError(APIException):
    """This is the error that gets raised when we detected that we are not
    allowed to set cookies.
    """

    def __init__(self, provider: 'models.LTI1p3Provider') -> None:
        super().__init__(
            "Couldn't set needed cookies",
            'We were not allowed to set the necessary cookies',
            APICodes.LTI1_3_COOKIE_ERROR,
            400,
            lms_capabilities=provider.lms_capabilities,
        )


def get_email_for_user(
    member: MemberLike,
    provider: 'models.LTI1p3Provider',
    *,
    test_student_email: str = 'test_student@codegra.de',
) -> str:
    """Get the email for something that looks like an LTI member.

    This method takes possible test students into account, for which it returns
    the given ``test_student_email`` if no email was found for the student.

    :param member: The received member from the LTI message.
    :param provider: The LTI provider that received the message. This is used
        to determine what the name of the test student would be, if anything.
    :param test_student_email: The email to return if no email was found for
        the given member, and we determined that the given member was indeed a
        test student.

    :raises KeyError: If the given user is not a test student and doesn't have
        an email (i.e. this function will always return an email in that case).
    """
    full_name = member['name']
    caps = provider.lms_capabilities
    test_stud_name = caps.test_student_name
    if test_stud_name is not None and test_stud_name == full_name:
        return member.get('email', test_student_email)
    return member['email']


class CGRegistration(Registration):
    """This class represents a registration, something used internally by the
    :mod:`pylti1p3` library.

    This class only adds a nice constructor, so you can easily create a
    registration using a :class:`.models.LTI1p3Provider`.
    """

    def __init__(self, provider: 'models.LTI1p3Provider') -> None:
        assert provider._auth_login_url is not None
        assert provider.auth_token_url is not None
        assert provider.key_set_url is not None
        assert provider.client_id is not None
        assert provider.iss is not None
        assert provider.auth_audience is not None

        self.provider = provider

        self.set_auth_login_url(provider._auth_login_url) \
            .set_auth_token_url(provider.auth_token_url) \
            .set_client_id(provider.client_id) \
            .set_key_set_url(provider.key_set_url) \
            .set_issuer(provider.iss) \
            .set_tool_public_key(provider.get_public_key()) \
            .set_auth_audience(provider.auth_audience) \
            .set_tool_private_key(provider._private_key)


class CGServiceConnector(ServiceConnector):
    """This class implements the authenticated back channel as defined by the
    LTI 1.3 spec.

    This is heavily used by the :mod:`pylti1p3`, and completely implemented by
    them. The only thing we add in our subclass is caching of the access tokens
    needed to make authenticated requests. Caching is done using our
    :mod:`cg_cache.inter_reqeust` caching functionality.
    """

    def __init__(self, provider: 'models.LTI1p3Provider') -> None:
        super().__init__(provider.get_registration())
        self._provider = provider

    @cg_override.override
    def get_access_token(self, scopes: t.Sequence[str]) -> str:
        """Get the access token for the given scopes.

        This method is simply a caching wrapper over the implementation of the
        base implementation.

        :param scopes: The scopes for which you want to get an access token.
        """
        scopes = sorted(scopes)
        scopes_str = '|'.join(scopes)
        cache = current_app.inter_request_cache.lti_access_tokens
        super_method = super().get_access_token
        cache_key = (
            f'{self._provider.id}-{self._provider.auth_token_url}-{scopes_str}'
        )

        return cache.get_or_set(cache_key, lambda: super_method(scopes))


class CGGrade(grade.Grade):
    """A class implementing a grade, as needed by the :mod:`pylti1p3` library
        for the grades service.
    """

    def __init__(
        self,
        assignment: 'models.Assignment',
        timestamp: DatetimeWithTimezone,
        provider: 'models.LTI1p3Provider',
    ) -> None:
        self.set_score_maximum(assignment.GRADE_SCALE)
        self._provider = provider
        self.set_timestamp(timestamp.isoformat())


class CGAssignmentsGradesService(AssignmentsGradesService):
    """A class implementing the grades service for LTI 1.3.

    Implementation is done using the :mod:`pylti1p3` library, this class simply
    adds a nicer constructor.
    """

    def __init__(
        self, service_connector: ServiceConnector,
        assignment: 'models.Assignment'
    ):
        assert assignment.is_lti
        assert isinstance(assignment.lti_grade_service_data, dict)

        service_data = assignment.lti_grade_service_data
        super().__init__(service_connector, service_data)
        logger.info('Created assignments service', service_data=service_data)
        self._assignment = assignment


class CGCustomClaims:
    """This class represents the definition and parsing of custom claims.

    This actually also uses non custom claim data, in the case the custom claim
    wasn't present.

    The wanted variables are defined in the ``_WANTED_VARS`` array in this
    class. Each variable (wanted piece of information) has multiple options,
    these are the places we might find this piece of information. Each options
    can be a :class:`.CGCustomClaims.ReplacementVar`: something we might find
    in the custom claims, or a :class:`.CGCustomClaims.AbsoluteVar` something
    that we might find outside of the custom claims.

    The order of the options matters for two reasons: 1) it matters for how the
    user is instructed to add the variables to their LMS when configuring
    CodeGrade, and 2) it defines the order in which the variables are parsed.
    The options are iterated one by one if and we find the information using an
    option we stop parsing, i.e. earlier options take precedence.
    """

    @dataclasses.dataclass(frozen=True)
    class ClaimResult:
        """The result of parsing the custom claims.
        """
        username: t.Optional[str]
        deadline: t.Optional[DatetimeWithTimezone]
        is_available: t.Optional[bool]
        available_at: t.Optional[DatetimeWithTimezone]
        resource_id: t.Optional[str]

    class ReplacementVar:
        """This represents a replacement variable, i.e. a variable that we
        might find in the custom claims section of the LTI message.
        """

        def __init__(self, name: str) -> None:
            self.name = name
            assert self.name.startswith('$')
            self.exploded_name = self.name.split('.')

        def matches_group(self, group: t.Sequence[str]) -> bool:
            """Check if given group matches

            >>> var = CGCustomClaims.ReplacementVar('$a.b.cc.d')
            >>> var.matches_group(['$a'])
            True
            >>> var.matches_group('$a.b.cc'.split('.'))
            True
            >>> var.matches_group('$a.c.d'.split('.'))
            False
            >>> var.matches_group('$a.b.c'.split('.'))
            False
            """
            return all(
                found == wanted
                for found, wanted in zip(self.exploded_name, group)
            )

        def find_in_data(self, data: t.Mapping[str, str],
                         key: str) -> t.Optional[str]:
            """Find this variable in the given data.
            """
            found_val = data.get(key, None)
            if isinstance(found_val, str) and found_val != self.name:
                return found_val
            return None

    class AbsoluteVar:
        """This represents a absolute variable, i.e. any variable that is not
        present in the custom claims section of the LTI message.
        """

        def __init__(self, name: t.Union[str, t.List[str]]) -> None:
            self.names = helpers.maybe_wrap_in_list(name)

        def find_in_data(self,
                         data: t.Mapping[str, object]) -> t.Optional[str]:
            """Find this variable in the given data.
            """
            found_val = helpers.deep_get(data, self.names, None)
            if isinstance(found_val, str):
                return found_val
            return None

    @dataclasses.dataclass(frozen=True)
    class _Var:
        name: str
        opts: t.List[t.Union['CGCustomClaims.ReplacementVar',
                             'CGCustomClaims.AbsoluteVar']]

        def get_replacement_opts(
            self
        ) -> t.Iterable['CGCustomClaims.ReplacementVar']:
            """Get all options in this variable that are instances of
            :class:`.CGCustomClaims.ReplacementVar`.
            """
            for opt in self.opts:
                if isinstance(opt, CGCustomClaims.ReplacementVar):
                    yield opt

        def get_key(self, idx: int) -> str:
            return f'{self.name}_{idx}'

    _WANTED_VARS: Final = [
        _Var(
            'cg_username',
            [
                ReplacementVar('$User.username'),
                AbsoluteVar(['http://www.brightspace.com', 'username']),
                # Not used at this moment by Brightspace but they might switch.
                AbsoluteVar(['https://www.brightspace.com', 'username']),
                AbsoluteVar('lis_person_sourcedid'),
            ],
        ),
        _Var(
            'cg_deadline',
            [
                ReplacementVar('$ResourceLink.submission.endDateTime'),
                ReplacementVar('$Canvas.assignment.dueAt.iso8601')
            ],
        ),
        _Var(
            'cg_available_at',
            [ReplacementVar('$ResourceLink.submission.startDateTime')],
        ),
        _Var(
            'cg_is_published',
            [ReplacementVar('$Canvas.assignment.published')],
        ),
        _Var(
            'cg_resource_id',
            [
                ReplacementVar('$ResourceLink.id'),
                ReplacementVar('$com.instructure.Assignment.lti.id'),
                AbsoluteVar([claims.RESOURCE, 'id']),
            ],
        ),
        # We don't support a lock date just yet, but if we do in the future we
        # already get this info from the LTI 1.3 tools.
        _Var(
            'cg_lock_date',
            [
                ReplacementVar('$ResourceLink.available.endDateTime'),
                ReplacementVar('$Canvas.assignment.lockAt.iso8601'),
            ],
        )
    ]

    _VAR_LOOKUP: Final = {var.name: var for var in _WANTED_VARS}

    _DEFAULT_REPLACEMENT_GROUPS = [['$User'], ['$ResourceLink']]

    @classmethod
    def get_variable_claims_config(cls, lms_capabilities: 'LMSCapabilities'
                                   ) -> t.Mapping[str, str]:
        """Get the custom claims config for the given capabilities.

        :param lms_capabilities: This is used to determine which replacement
            groups are supported, see
            :meth:`psef.lti.v1_3.LMSCapabilities.supported_custom_replacement_groups`
            for how this is used.

        :returns: A mapping representing the wanted custom config. The key in
                  the mapping is how the variable should be named in the custom
                  claim, and the value is the replacement var that should be
                  used. The values are already prefixed with the necessary '$'.
        """
        res: t.Dict[str, str] = {}
        custom_groups = lms_capabilities.supported_custom_replacement_groups
        allowed_groups = [*cls._DEFAULT_REPLACEMENT_GROUPS, *custom_groups]

        for var in cls._WANTED_VARS:
            for idx, opt in enumerate(var.get_replacement_opts()):
                if any(opt.matches_group(group) for group in allowed_groups):
                    res[var.get_key(idx)] = opt.name

        return res

    @classmethod
    def _get_claim(
        cls,
        var_name: str,
        custom_data: t.Mapping[str, str],
        base_data: t.Mapping[str, object],
        converter: t.Callable[[str], t.Optional[T]],
    ) -> t.Optional[T]:
        var = cls._VAR_LOOKUP[var_name]

        for idx, opt in enumerate(var.opts):
            found_val: object

            if isinstance(opt, cls.ReplacementVar):
                found_val = opt.find_in_data(custom_data, var.get_key(idx))
            else:
                found_val = opt.find_in_data(base_data)

            if found_val is not None:
                res = converter(found_val)
                if res is not None:
                    return res

        return None

    @staticmethod
    def _str_not_empty(inp: str) -> t.Optional[str]:
        return inp or None

    @staticmethod
    def _parse_isoformat(inp: str) -> t.Optional[DatetimeWithTimezone]:
        if inp:
            return DatetimeWithTimezone.parse_isoformat(inp)
        return None

    @classmethod
    def get_custom_claim_data(
        cls,
        custom_claims: t.Mapping[str, str],
        base_data: t.Mapping[str, object],
    ) -> 'CGCustomClaims.ClaimResult':
        """Parse the custom claims for the given custom claim and base data.

        :param custom_claims: The custom claims to be parsed.
        :param base_data: The base data, this should be the location where we
            can find the :class:`.CGCustomClaims.AbsoluteVar` data.

        :returns: The parsed data, please note that ``None`` will be used for
                  data that either was not present, or could not be parsed.
        """
        username = cls._get_claim(
            'cg_username', custom_claims, base_data, cls._str_not_empty
        )

        resource_id = cls._get_claim(
            'cg_resource_id', custom_claims, base_data, cls._str_not_empty
        )

        deadline = cls._get_claim(
            'cg_deadline', custom_claims, base_data, cls._parse_isoformat
        )

        available_at = cls._get_claim(
            'cg_available_at', custom_claims, base_data, cls._parse_isoformat
        )
        is_available = cls._get_claim(
            'cg_is_published',
            custom_claims,
            base_data,
            lambda x: x.lower() == 'true',
        )

        return CGCustomClaims.ClaimResult(
            username=username,
            deadline=deadline,
            is_available=is_available,
            available_at=available_at,
            resource_id=resource_id,
        )


class CGDeepLinkResource(DeepLinkResource):
    """The class representing a deep link.

    Deep links are not used by CodeGrade for their intended purpose (finding
    content in a tool and using that in the LMS), however we still use them.
    The UI for creating tools that support deep linking is much better in some
    cases (Brightspace), and sometimes even required (Canvas). So CodeGrade
    uses deeplinking in the following way: if we get a deeplinking request we
    do not prompt anything from the user, but simply directly return a resource
    the LMS. This resource is practically empty, and does not exist in our
    database, but this allows us to benefit from the UI of deep linking.
    """
    _deadline: t.Optional[DatetimeWithTimezone] = None

    @t.overload
    @classmethod
    def make(
        cls, message_launch: 'FlaskMessageLaunch'
    ) -> 'CGDeepLinkResource':
        ...

    @t.overload
    @classmethod
    def make(
        cls,
        *,
        lti_provider: 'models.LTI1p3Provider',
        deadline: DatetimeWithTimezone,
    ) -> 'CGDeepLinkResource':
        ...

    @classmethod
    @cg_override.no_override
    def make(
        cls,
        message_launch: 'FlaskMessageLaunch' = None,
        *,
        lti_provider: 'models.LTI1p3Provider' = None,
        deadline: t.Optional[DatetimeWithTimezone] = None,
    ) -> 'CGDeepLinkResource':
        """Make a practically empty deep link resource.

        :param message_launch: The launch deep link launch in which we should
            create the result. We use this launch to set the correct launch url
            on the resource.

        :returns: The created resource.
        """
        if lti_provider is None:
            assert message_launch is not None
            assert message_launch.is_deep_link_launch()
            lti_provider = message_launch.get_lti_provider()

        self = cls()
        self._deadline = deadline  # pylint: disable=protected-access

        url = lti_provider.get_launch_url(goto_latest_sub=False)
        return self.set_url(str(url)).set_custom_params(
            CGCustomClaims.get_variable_claims_config(
                lti_provider.lms_capabilities
            )
        )

    @cg_override.override
    def to_dict(self) -> t.Dict[str, object]:
        res = super().to_dict()
        if self._deadline is not None:
            res['submission'] = {
                'endDateTime': self._deadline.isoformat(),
            }
        return res


class LTIConfig(ToolConfAbstract[FlaskRequest]):
    """This class implements the connection between our database an the needed
    (by :mod:`pyltip13`) config store.

    It works by finding (or verifying if you passed on in the constructor) a
    :class:`.models.LTI1p3Provider` using the given data. This provider
    contains the necessary data to construct the wanted, by :mod:`pylti1p3`,
    classes.
    """

    def __init__(
        self, lti_provider: t.Optional['models.LTI1p3Provider']
    ) -> None:
        super().__init__()
        self.reg_extended_search = True
        self._lti_provider = lti_provider

    @cg_override.override
    def check_iss_has_one_client(self, iss: str) -> bool:
        """Our issuers have multiple clients.

        The issuer is not unique, some LMSes (Canvas, Blackboard) even use the
        same ``iss`` for every deployment.
        """
        return False

    @cg_override.override
    def find_registration_by_issuer(
        self, iss: str, *args: None,
        **kwargs: t.Union[Literal['message_launch', 'oidc_login'],
                          FlaskRequest, '_LaunchData']
    ) -> t.Optional[Registration]:
        """Find the registration in a legacy way.

        >>> LTIConfig(None).find_registration_by_issuer('anything')
        Traceback (most recent call last):
        ...
        AssertionError

        This is not supported and this method will always raise an
        :exc:`.AssertionError`.
        """
        raise AssertionError("We don't support registration by only issuer")

    def find_provider_by_params(
        self, iss: str, client_id: t.Optional[str]
    ) -> 'models.LTI1p3Provider':
        """Find the provider using the given ``iss`` and ``client_id``.

        If this config already has a reference to an
        :class:`.models.LTI1p3Provider` we simply check that the information
        passed to us is the same as the information in the provider

        :param iss: The ``iss`` of the wanted provider.
        :param client_id: The ``client_id``, pass ``None`` if not available,
            however in this case there really already should be a provider
            connect to this instance.

        :returns: The found provider.
        """
        if self._lti_provider is None:
            filters = [models.LTI1p3Provider.iss == iss]
            if isinstance(client_id, str):
                filters.append(models.LTI1p3Provider.client_id == client_id)
            else:  # pragma: no cover
                logger.warning(
                    'Have to search for an LTI tool without client_id',
                    tool_iss=iss,
                    tool_client_id=client_id,
                    report_to_sentry=True,
                )

            self._lti_provider = helpers.filter_single_or_404(
                models.LTI1p3Provider, *filters
            )
        else:
            correct = self._lti_provider.iss == iss
            if correct and isinstance(client_id, str):
                correct = self._lti_provider.client_id == client_id

            if not correct:
                logger.error(
                    'Found incorrect LTI provider',
                    found_iss=iss,
                    provider_iss=self._lti_provider.iss,
                    found_client_id=client_id,
                    provider_client_id=self._lti_provider.client_id,
                    report_to_sentry=True,
                )
                raise APIException(
                    (
                        'The provided LTI provider does not match the data in'
                        ' the request'
                    ), (
                        'The found LTI provider info does not match the given'
                        ' provider'
                    ), APICodes.OBJECT_NOT_FOUND, 404
                )

        if not self._lti_provider.is_finalized:
            raise APIException(
                (
                    'This LTI connection is not yet finalized, please make'
                    ' sure you have completed all steps in the wizard.'
                ), f'The LTIProvider {self._lti_provider.id} is not finalized',
                APICodes.INVALID_STATE, 400
            )

        return self._lti_provider

    @cg_override.override
    def find_registration_by_params(
        self,
        iss: str,
        client_id: t.Optional[str],
        *args: None,
        **kwargs: t.Union[Literal['message_launch', 'oidc_login'],
                          FlaskRequest, '_LaunchData'],
    ) -> t.Optional[Registration]:
        """Find a registration by params.

        This simply uses :meth:`.LTIConfig.find_provider_by_params`, see its
        docstring for how it works.
        """
        return self.find_provider_by_params(
            iss=iss, client_id=client_id
        ).get_registration()

    @cg_override.override
    def find_deployment(
        self,
        iss: str,
        deployment_id: str,
    ) -> None:
        """We don't use deployments, this always returns ``None``.

        >>> LTIConfig(None).find_deployment('anything', 'anything') is None
        True
        """
        return None

    @cg_override.override
    def find_deployment_by_params(
        self, iss: str, deployment_id: str, client_id: str, *args: None,
        **kwargs: None
    ) -> None:
        """We don't use deployments, this always returns ``None``.

        >>> LTIConfig(None).find_deployment_by_params('any', '', '') is None
        True
        """
        return None


class FlaskMessageLaunch(
    AbstractLTIConnector,
    MessageLaunch[FlaskRequest, LTIConfig, FlaskSessionService,
                  FlaskCookieService]
):
    """This class handles the launch message, and the second step launch, of
    the LTI 1.3 protocol and our extension on it.

    .. seealso::

        The module documentation of :mod:`psef.lti.v1_3` for more information,
        this class handles everything **after** the OIDC login request. See
        :class:`.FlaskOIDCLogin` for how that is handled.
    """

    @staticmethod
    def _make_key_set_url_cache_key(key_set_url: str) -> str:
        return f'key-url-{key_set_url}'

    @cg_override.override
    def validate_jwt_signature(self) -> 'FlaskMessageLaunch':
        """Validate the jwt signature in the request.

        This method clears the key set url cache if the validation (implemented
        in the base class) failed.
        """
        try:
            return super().validate_jwt_signature()
        except:  # pylint: disable=bare-except
            # It might happen that our cache is outdated, in that case remove
            # the cache and try to validate the signature again.
            logger.info(
                'Validating signature key failed, clearing cache and trying'
                ' again'
            )
            key_set_url = self.get_lti_provider().key_set_url
            if key_set_url is not None:
                assert self._registration is not None
                self._registration.set_key_set(None)
                current_app.inter_request_cache.lti_public_keys.clear(
                    self._make_key_set_url_cache_key(key_set_url)
                )
            return super().validate_jwt_signature()

    @cg_override.override
    def fetch_public_key(self, key_set_url: str) -> '_KeySet':
        """Fetch the public key at the given url.

        This method uses a inter request cache for theses keys, so that keys
        are fetched less. The key for the cache is the url at which the key can
        be found, i.e. the cache can be shared between different LTI providers.

        There is no reason to call this method manually, but it is used by the
        :mod:`pylti1p3` library.

        :param key_set_url: The url where the key can be found.

        :returns: The found key, either from the cache or by querying the given
                  ``key_set_url``.
        """
        cache = current_app.inter_request_cache.lti_public_keys
        super_method = super().fetch_public_key

        return cache.get_or_set(
            self._make_key_set_url_cache_key(key_set_url),
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
        return custom_claim.resource_id

    def _find_assignment(
        self,
        course: 'models.Course',
    ) -> 't.Optional[models.Assignment]':
        """Find the assignment of this launch.

        :param course: The course of the launch, we will only search inside
            this course for assignments.
        """
        resource_id = self._get_resource_id()
        old_resource_id = self.get_launch_data().get(claims.MIGRATION, {}).get(
            'resource_link_id', resource_id
        )

        return self.get_lti_provider().find_assignment(
            course=course,
            resource_id=resource_id,
            old_resource_id=old_resource_id
        )

    # We don't use the @cg_override.override decorator here as this method
    # overrides one of our own classes, and I think it makes most sense if we
    # use the decorator to signal that we override a method from a class
    # outside of our control (external lib).
    def get_assignment(
        self, user: object, course: 'models.Course'
    ) -> 'models.Assignment':
        """Get or create the assignment in this LTI request.

        :param user: Unused but required as this method overrides a method that
            specifies it.
        :param course: The course in which the launch is done, this parameter
            is used. We assume that the resource (LTI speak for assignment in
            our case) identifier is unique within a course, so we will only
            search for assignments inside this course, and created assignments
            will be created inside this course.

        :returns: The found or created assignment, updated with the found
                  information in this launch.
        """
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

        if assignment.is_done:
            pass
        elif custom_claim.available_at is not None:
            assignment.available_at = custom_claim.available_at
        elif custom_claim.is_available is False:
            assignment.state = models.AssignmentStateEnum.hidden
        else:
            assignment.state = models.AssignmentStateEnum.open

        return assignment

    def set_user_course_role(
        self, user: 'models.User', course: 'models.Course'
    ) -> t.Optional[str]:
        assert course.course_lti_provider, (
            'The given course is not an LTI course'
        )
        return course.course_lti_provider.maybe_add_user_to_course(
            user,
            self.get_launch_data()[claims.ROLES],
        )

    @property
    def deployment_id(self) -> str:
        """The deployment id of this LTI launch.

        Accessing this property raises an :exc:`.LTIException` when the
        deployment id was not found the launch data.
        """
        return self._get_deployment_id()

    @cg_override.override
    def _get_request_param(self, key: str) -> object:
        return self._request.get_param(key)

    @classmethod
    def from_request(
        cls, lti_provider: t.Optional['models.LTI1p3Provider']
    ) -> 'FlaskMessageLaunch':
        """Create a :class:`.FlaskMessageLaunch` from **untrusted** data.

        :param lti_provider: If the launch request specified which lti provider
            to use it should be provided using this parameter. See
            :meth:`.LTIConfig.find_provider_by_params` for how this provider is
            used.

        :returns: The created message launch.
        """
        f_request = FlaskRequest(force_post=True)
        self = cls(
            f_request,
            LTIConfig(lti_provider=lti_provider),
            FlaskSessionService(f_request),
            FlaskCookieService(),
        )
        return self

    def get_lti_provider(self) -> 'models.LTI1p3Provider':
        """Get the LTI provider of this launch.

        .. note::

            You can only use this method on validated or restored launches.

        :returns: The found lti provider, see
                  :meth:`.LTIConfig.find_provider_by_params` for how this
                  provider is found.
        """
        assert self._validated or self._restored
        reg = self._registration
        assert reg is not None, 'Registration should be set at this point'
        client_id = reg.get_client_id()
        return self._tool_config.find_provider_by_params(
            iss=self._get_iss(),
            client_id=client_id,
        )

    @cg_override.override
    def save_launch_data(self) -> 'FlaskMessageLaunch':
        """Save the launch data.

        We never want to save the launch data in the session, as we have no
        use-case for it, and it slows down every request. So this method does
        nothing, however as the base class calls this method it should not
        raise.
        """
        return self

    @cg_override.override
    def validate_deployment(self) -> 'FlaskMessageLaunch':
        """Validate the found deployment in the launch.

        This only makes sense when for implementations that hard limit the
        valid deployments for an LTI connection. As we don't do this there is
        nothing to validate. The base class calls this method so it should not
        raise!
        """
        return self

    def validate_has_needed_data(self) -> 'FlaskMessageLaunch':
        """Check that all data required by CodeGrade is present in this launch.
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
            if mapping is None:
                mapping = {}
            missing = [key for key in keys if key not in mapping]

            if missing:
                raise get_exc(msg, mapping, missing)

        user_err_msg = (
            'We are missing required data about the user doing this LTI'
            ' launch, please check the privacy levels of the tool:'
            ' CodeGrade requires the {} of the user.'
        )
        check_and_raise(user_err_msg.format('name'), launch_data, 'name')
        try:
            get_email_for_user(launch_data, provider)
        except KeyError:
            raise get_exc(user_err_msg.format('email'), launch_data, ['email'])

        context = launch_data.get(claims.CONTEXT)
        check_and_raise(
            'The LTI launch did not contain a context', context, 'id', 'title'
        )

        if self.is_resource_launch():
            lti_provider = self.get_lti_provider()
            custom = launch_data.get(claims.CUSTOM)

            # We don't need this info for deep link launches.
            check_and_raise(
                (
                    'The LTI launch is missing required custom claims, the'
                    ' setup was probably done incorrectly'
                ),
                custom,
                *CGCustomClaims.get_variable_claims_config(
                    lti_provider.lms_capabilities
                ).keys(),
            )

            if not self.has_nrps():
                raise get_exc(
                    (
                        'It looks like the NamesRoles Provisioning service is'
                        ' not enabled for this LTI deployment, please check'
                        ' your configuration.'
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
                    ' grades and updating deadlines in the LMS, please check'
                    ' your configuration'
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
    def _get_jwt_body(self) -> '_LaunchData':
        assert self._validated or self._restored
        return super()._get_jwt_body()

    def get_deep_link_settings(self) -> '_DeepLinkData':
        return self._get_jwt_body()[claims.DEEP_LINK]

    @cg_override.override
    def validate(self) -> 'FlaskMessageLaunch':
        """Validate this request, both for security and data completeness.
        """
        try:
            # The parent method validates the security aspects of the request.
            super().validate()
        except:
            # If the validation failed this can happen because of a lot of
            # reasons.  However, if it happens because the user is not allowed
            # to set cookies (and thus incorrect values were found in the
            # session) we want to display a nicer error message to the user. To
            # do this we use our :class:`_TestCookie` class, however this needs
            # an LTI provider (see docs in the class for why), which we can
            # only get using the data in the request. So in this except block
            # we make a copy of the request (so it can never happen that this
            # request is seen as validated) and do as if it were validated, so
            # we can get the LTI provider.

            self_copy = copy.copy(self)
            try:
                # Make sure we can get the lti provider
                self_copy._validated = True  # pylint: disable=protected-access
                self_copy.validate_jwt_format()
                self_copy.validate_registration()

                _TestCookie.validate_value_in_request(
                    self_copy._cookie_service,  # pylint: disable=protected-access
                    self_copy.get_lti_provider(),
                )
            finally:
                # This copy never really should be leaked from this call,
                # however in the extraordinary case that it is we make sure
                # that it is longer seen as a validated request.
                self_copy._validated = False  # pylint: disable=protected-access
                self_copy._restored = False  # pylint: disable=protected-access

            # The error was not a cookie error in this case.
            raise
        else:
            # We don't need to validate this cookie (launching worked so we
            # were able to set the necessary cookies), however we do want to
            # clear it to reduce the size of future requests, and to make sure
            # the validation still works for future requests.
            _TestCookie.clear_cookie_in_request(self._cookie_service)

        try:
            return self.validate_has_needed_data()
        except:
            self._validated = False
            raise

    def get_custom_claims(self) -> CGCustomClaims.ClaimResult:
        """Get and parse the custom claim in this request.

        Parsing is not really done here, but in
        :meth:`.CGCustomClaims.get_custom_claim_data`.
        """
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

        old_lti_user_id = launch_data.get(claims.MIGRATION, {}).get('user_id')
        user, token = models.UserLTIProvider.get_or_create_user(
            lti_user_id=launch_data['sub'],
            lti_provider=self.get_lti_provider(),
            wanted_username=custom_claims.username,
            full_name=full_name,
            email=email,
            old_lti_user_id=old_lti_user_id,
        )

        updated_email = None
        if user.reset_email_on_lti:
            user.email = email
            updated_email = user.email
            user.reset_email_on_lti = False

        return user, token, updated_email

    def get_course(self) -> 'models.Course':
        """Get the course of this LTI launch, or create (and add it to the db
        session) if it does not yet exist.

        :returns: The found or created course.
        """
        launch_data = self.get_launch_data()
        deployment_id = self._get_deployment_id()
        context_claim = launch_data[claims.CONTEXT]
        course_name = context_claim['title']
        lti_course_id = context_claim['id']
        old_lti_course_id = launch_data.get(claims.MIGRATION, {}).get(
            'context_id', lti_course_id
        )

        course_lti_provider = self.get_lti_provider().find_course(
            lti_course_id=lti_course_id,
            deployment_id=deployment_id,
            old_lti_course_id=old_lti_course_id,
        )

        if course_lti_provider is None:
            course = models.Course.create_and_add(name=course_name)
            course_lti_provider = models.CourseLTIProvider.create_and_add(
                course=course,
                lti_provider=self.get_lti_provider(),
                lti_context_id=lti_course_id,
                deployment_id=deployment_id,
            )
            models.db.session.flush()
        else:
            course = course_lti_provider.course
            course.name = course_name

        if claims.NAMESROLES in launch_data:
            names_roles_claim = launch_data[claims.NAMESROLES]
            course_lti_provider.names_roles_claim = names_roles_claim

        return course

    @classmethod
    def from_message_data(
        cls,
        *,
        launch_data: t.Mapping[str, object],
        lti_provider: 'models.LTI1p3Provider',
    ) -> 'FlaskMessageLaunch':
        """Create a :class:`.FlaskMessageLaunch` from **trusted** input.

        .. warning::

            This method will skip all security checks! Do **not** use raw LTI
            launch data as input to this method, as this will not verify that
            the launch is valid and correct!

        :param launch_data: The launch data to use as jwt body.
        :param lti_provider: The provider of the original request.

        :returns: The create message launch.
        """
        f_request = FlaskRequest(force_post=False)
        obj = cls(
            f_request,
            LTIConfig(lti_provider),
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
    """This class handles the OIDC login requests of LTI.

    .. seealso::

        The module documentation of :mod:`psef.lti.v1_3` for more information
        about what part OIDC login requests play in the entire LTI 1.3 flow.
    """

    @cg_override.override
    def get_redirect(self, url: str) -> FlaskRedirect:
        """Get the redirect that you need to do after the OIDC login.

        This method sets a test cookie that will later be used to verify that
        cookies work in the browser of the user.

        :param url: The url to which you want to redirect. You can probably get
            this by searching the request for a ``target_link_uri``.
        """
        _TestCookie.set_value(self._cookie_service)
        return FlaskRedirect(url, self._cookie_service)

    @classmethod
    def from_request(
        cls, lti_provider: t.Optional['models.LTI1p3Provider']
    ) -> 'FlaskOIDCLogin':
        """Create a :class:`.FlaskOIDCLogin` from the current (global) flask
        request.

        The current request will not be copied or anything, so you cannot
        create this object in a request and then use it in another one.

        :param lti_provider: The lti provider that has initialized this OIDC
            login. This will be checked: we will verify (when you start using
            the returned object) that the information identifying the
            ``lti_provider`` in the login request matches the given provider.

        :returns: The created object.
        """
        f_request = FlaskRequest(force_post=False)
        return FlaskOIDCLogin(
            f_request,
            LTIConfig(lti_provider=lti_provider),
            FlaskSessionService(f_request),
            FlaskCookieService(),
        )


def init_app(_: PsefFlask) -> None:
    pass
