"""This module defines all site settings used.

.. note:

    This module is automatically generated, don't edit manually.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import datetime
import functools
import dataclasses

import structlog
from typing_extensions import Final, TypedDict

import cg_request_args as rqa
from cg_object_storage.types import FileSize

from . import PsefFlask, models, exceptions

logger = structlog.get_logger()

_T = t.TypeVar('_T')
_CallableT = t.TypeVar('_CallableT', bound=t.Callable)


@dataclasses.dataclass
class _OptionCategory:
    name: str


@dataclasses.dataclass(frozen=True)
class Option(t.Generic[_T]):
    name: str = dataclasses.field(hash=True)
    default: _T = dataclasses.field(init=False, hash=False)
    default_obj: dataclasses.InitVar[object]
    parser: rqa._Parser[_T] = dataclasses.field(hash=False)

    def __post_init__(self, default_obj: object) -> None:
        default: _T = self.parser.try_parse(default_obj)
        object.__setattr__(self, 'default', default)

    @property
    def value(self) -> _T:
        return models.SiteSetting.get_option(self)

    class AsJSON(TypedDict):
        name: str
        default: t.Any
        value: t.Any

    def __to_json__(self) -> AsJSON:
        return {
            'name': self.name,
            'default': self.default,
            'value': self.value,
        }

    def ensure_enabled(self: 'Option[bool]') -> None:
        """Check if a certain option is enabled.

        :returns: Nothing.
        """
        if not self.value:
            logger.warning('Tried to use disabled feature', feature=self.name)
            raise exceptions.OptionException(self)

    def required(self: 'Option[bool]', f: _CallableT) -> _CallableT:
        """A decorator used to make sure the function decorated is only called
        with a certain feature enabled.

        :returns: The value of the decorated function if the given feature is
            enabled.
        """

        @functools.wraps(f)
        def __decorated_function(*args: t.Any, **kwargs: t.Any) -> t.Any:
            self.ensure_enabled()
            return f(*args, **kwargs)

        return t.cast(_CallableT, __decorated_function)


class Opt:
    AUTO_TEST_MAX_TIME_COMMAND: Final = Option(
        name='AUTO_TEST_MAX_TIME_COMMAND',
        parser=rqa.RichValue.TimeDelta,
        default_obj='PT5M',
    )
    AUTO_TEST_HEARTBEAT_INTERVAL: Final = Option(
        name='AUTO_TEST_HEARTBEAT_INTERVAL',
        parser=rqa.RichValue.TimeDelta,
        default_obj='PT10S',
    )
    AUTO_TEST_HEARTBEAT_MAX_MISSED: Final = Option(
        name='AUTO_TEST_HEARTBEAT_MAX_MISSED',
        parser=rqa.SimpleValue.int,
        default_obj=6,
    )
    AUTO_TEST_MAX_JOBS_PER_RUNNER: Final = Option(
        name='AUTO_TEST_MAX_JOBS_PER_RUNNER',
        parser=rqa.SimpleValue.int,
        default_obj=10,
    )
    AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS: Final = Option(
        name='AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS',
        parser=rqa.SimpleValue.int,
        default_obj=3,
    )
    EXAM_LOGIN_MAX_LENGTH: Final = Option(
        name='EXAM_LOGIN_MAX_LENGTH',
        parser=rqa.RichValue.TimeDelta,
        default_obj='PT12H',
    )
    LOGIN_TOKEN_BEFORE_TIME: Final = Option(
        name='LOGIN_TOKEN_BEFORE_TIME',
        parser=rqa.List(rqa.RichValue.TimeDelta),
        default_obj=['P2D', 'PT30M'],
    )
    MIN_PASSWORD_SCORE: Final = Option(
        name='MIN_PASSWORD_SCORE',
        parser=rqa.SimpleValue.int,
        default_obj=3,
    )
    RESET_TOKEN_TIME: Final = Option(
        name='RESET_TOKEN_TIME',
        parser=rqa.RichValue.TimeDelta,
        default_obj='P1D',
    )
    SETTING_TOKEN_TIME: Final = Option(
        name='SETTING_TOKEN_TIME',
        parser=rqa.RichValue.TimeDelta,
        default_obj='P1D',
    )
    SITE_EMAIL: Final = Option(
        name='SITE_EMAIL',
        parser=rqa.SimpleValue.str,
        default_obj='info@codegrade.com',
    )
    MAX_NUMBER_OF_FILES: Final = Option(
        name='MAX_NUMBER_OF_FILES',
        parser=rqa.SimpleValue.int,
        default_obj=16384,
    )
    MAX_LARGE_UPLOAD_SIZE: Final = Option(
        name='MAX_LARGE_UPLOAD_SIZE',
        parser=rqa.RichValue.FileSize,
        default_obj='128mb',
    )
    MAX_NORMAL_UPLOAD_SIZE: Final = Option(
        name='MAX_NORMAL_UPLOAD_SIZE',
        parser=rqa.RichValue.FileSize,
        default_obj='64mb',
    )
    MAX_FILE_SIZE: Final = Option(
        name='MAX_FILE_SIZE',
        parser=rqa.RichValue.FileSize,
        default_obj='50mb',
    )
    JWT_ACCESS_TOKEN_EXPIRES: Final = Option(
        name='JWT_ACCESS_TOKEN_EXPIRES',
        parser=rqa.RichValue.TimeDelta,
        default_obj='P30D',
    )
    MAX_LINES: Final = Option(
        name='MAX_LINES',
        parser=rqa.SimpleValue.int,
        default_obj=2500,
    )
    NOTIFICATION_POLL_TIME: Final = Option(
        name='NOTIFICATION_POLL_TIME',
        parser=rqa.RichValue.TimeDelta,
        default_obj='PT30S',
    )
    RELEASE_MESSAGE_MAX_TIME: Final = Option(
        name='RELEASE_MESSAGE_MAX_TIME',
        parser=rqa.RichValue.TimeDelta,
        default_obj='P30D',
    )
    BLACKBOARD_ZIP_UPLOAD_ENABLED: Final = Option(
        name='BLACKBOARD_ZIP_UPLOAD_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=True,
    )
    RUBRICS_ENABLED: Final = Option(
        name='RUBRICS_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=True,
    )
    AUTOMATIC_LTI_ROLE_ENABLED: Final = Option(
        name='AUTOMATIC_LTI_ROLE_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=True,
    )
    LTI_ENABLED: Final = Option(
        name='LTI_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=True,
    )
    LINTERS_ENABLED: Final = Option(
        name='LINTERS_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=True,
    )
    INCREMENTAL_RUBRIC_SUBMISSION_ENABLED: Final = Option(
        name='INCREMENTAL_RUBRIC_SUBMISSION_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=True,
    )
    REGISTER_ENABLED: Final = Option(
        name='REGISTER_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=False,
    )
    GROUPS_ENABLED: Final = Option(
        name='GROUPS_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=False,
    )
    AUTO_TEST_ENABLED: Final = Option(
        name='AUTO_TEST_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=False,
    )
    COURSE_REGISTER_ENABLED: Final = Option(
        name='COURSE_REGISTER_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=False,
    )
    RENDER_HTML_ENABLED: Final = Option(
        name='RENDER_HTML_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=False,
    )
    EMAIL_STUDENTS_ENABLED: Final = Option(
        name='EMAIL_STUDENTS_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=False,
    )
    PEER_FEEDBACK_ENABLED: Final = Option(
        name='PEER_FEEDBACK_ENABLED',
        parser=rqa.SimpleValue.bool,
        default_obj=False,
    )
    _FRONTEND_OPTS: t.Sequence[Option] = [
        AUTO_TEST_MAX_TIME_COMMAND,
        EXAM_LOGIN_MAX_LENGTH,
        LOGIN_TOKEN_BEFORE_TIME,
        SITE_EMAIL,
        MAX_LINES,
        NOTIFICATION_POLL_TIME,
        RELEASE_MESSAGE_MAX_TIME,
        BLACKBOARD_ZIP_UPLOAD_ENABLED,
        RUBRICS_ENABLED,
        AUTOMATIC_LTI_ROLE_ENABLED,
        LTI_ENABLED,
        LINTERS_ENABLED,
        INCREMENTAL_RUBRIC_SUBMISSION_ENABLED,
        REGISTER_ENABLED,
        GROUPS_ENABLED,
        AUTO_TEST_ENABLED,
        COURSE_REGISTER_ENABLED,
        RENDER_HTML_ENABLED,
        EMAIL_STUDENTS_ENABLED,
        PEER_FEEDBACK_ENABLED,
    ]
    _ALL_OPTS: t.Sequence[Option] = [
        *_FRONTEND_OPTS,
        AUTO_TEST_HEARTBEAT_INTERVAL,
        AUTO_TEST_HEARTBEAT_MAX_MISSED,
        AUTO_TEST_MAX_JOBS_PER_RUNNER,
        AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS,
        MIN_PASSWORD_SCORE,
        RESET_TOKEN_TIME,
        SETTING_TOKEN_TIME,
        MAX_NUMBER_OF_FILES,
        MAX_LARGE_UPLOAD_SIZE,
        MAX_NORMAL_UPLOAD_SIZE,
        MAX_FILE_SIZE,
        JWT_ACCESS_TOKEN_EXPIRES,
    ]

    class FrontendOptsAsJSON(TypedDict):
        """The JSON representation of options visible to all users."""
        #: The default amount of time a step/substep in AutoTest can run. This
        #: can be overridden by the teacher.
        AUTO_TEST_MAX_TIME_COMMAND: datetime.timedelta
        #: The maximum time-delta an exam may take. Increasing this value also
        #: increases the maximum amount of time the login tokens send via email
        #: are valid. Therefore, you should make this too long.
        EXAM_LOGIN_MAX_LENGTH: datetime.timedelta
        #: This determines how long before the exam we will send the login
        #: emails to the students (only when enabled of course).
        LOGIN_TOKEN_BEFORE_TIME: t.Sequence[datetime.timedelta]
        #: The email shown to users as the email of CodeGrade.
        SITE_EMAIL: str
        #: The maximum amount of lines that we should in render in one go. If a
        #: file contains more lines than this we will show a warning asking the
        #: user what to do.
        MAX_LINES: int
        #: The amount of time to wait between two consecutive polls to see if a
        #: user has new notifications. Setting this value too low will cause
        #: unnecessary stres on the server.
        NOTIFICATION_POLL_TIME: datetime.timedelta
        #: What is the maximum amount of time after a release a message should
        #: be shown on the HomeGrid. **Note**: this is the amount of time after
        #: the release, not after this instance has been upgraded to this
        #: release.
        RELEASE_MESSAGE_MAX_TIME: datetime.timedelta
        #: If enabled teachers are allowed to bulk upload submissions (and
        #: create users) using a zip file in a format created by Blackboard.
        BLACKBOARD_ZIP_UPLOAD_ENABLED: bool
        #: If enabled teachers can use rubrics on CodeGrade. Disabling this
        #: feature will not delete existing rubrics.
        RUBRICS_ENABLED: bool
        #: Currently unused
        AUTOMATIC_LTI_ROLE_ENABLED: bool
        #: Should LTI be enabled.
        LTI_ENABLED: bool
        #: Should linters be enabled
        LINTERS_ENABLED: bool
        #: Should rubrics be submitted incrementally, so if a user selects a
        #: item should this be automatically be submitted to the server, or
        #: should it only be possible to submit a complete rubric at once. This
        #: feature is useless if `rubrics` is not set to `true`.
        INCREMENTAL_RUBRIC_SUBMISSION_ENABLED: bool
        #: Should it be possible to register on the website. This makes it
        #: possible for any body to register an account on the website.
        REGISTER_ENABLED: bool
        #: Should group assignments be enabled.
        GROUPS_ENABLED: bool
        #: Should auto test be enabled.
        AUTO_TEST_ENABLED: bool
        #: Should it be possible for teachers to create links that users can
        #: use to register in a course. Links to enroll can be created even if
        #: this feature is disabled.
        COURSE_REGISTER_ENABLED: bool
        #: Should it be possible to render html files within CodeGrade. This
        #: opens up more attack surfaces as it is now possible by design for
        #: students to run javascript. This is all done in a sandboxed iframe
        #: but still.
        RENDER_HTML_ENABLED: bool
        #: Should it be possible to email students.
        EMAIL_STUDENTS_ENABLED: bool
        #: Should peer feedback be enabled.
        PEER_FEEDBACK_ENABLED: bool

    @classmethod
    def get_frontend_opts(cls) -> FrontendOptsAsJSON:
        lookup: t.Any = models.SiteSetting.get_options(cls._FRONTEND_OPTS)
        return {
            'AUTO_TEST_MAX_TIME_COMMAND':
                lookup[cls.AUTO_TEST_MAX_TIME_COMMAND],
            'EXAM_LOGIN_MAX_LENGTH': lookup[cls.EXAM_LOGIN_MAX_LENGTH],
            'LOGIN_TOKEN_BEFORE_TIME': lookup[cls.LOGIN_TOKEN_BEFORE_TIME],
            'SITE_EMAIL': lookup[cls.SITE_EMAIL],
            'MAX_LINES': lookup[cls.MAX_LINES],
            'NOTIFICATION_POLL_TIME': lookup[cls.NOTIFICATION_POLL_TIME],
            'RELEASE_MESSAGE_MAX_TIME': lookup[cls.RELEASE_MESSAGE_MAX_TIME],
            'BLACKBOARD_ZIP_UPLOAD_ENABLED':
                lookup[cls.BLACKBOARD_ZIP_UPLOAD_ENABLED],
            'RUBRICS_ENABLED': lookup[cls.RUBRICS_ENABLED],
            'AUTOMATIC_LTI_ROLE_ENABLED':
                lookup[cls.AUTOMATIC_LTI_ROLE_ENABLED],
            'LTI_ENABLED': lookup[cls.LTI_ENABLED],
            'LINTERS_ENABLED': lookup[cls.LINTERS_ENABLED],
            'INCREMENTAL_RUBRIC_SUBMISSION_ENABLED':
                lookup[cls.INCREMENTAL_RUBRIC_SUBMISSION_ENABLED],
            'REGISTER_ENABLED': lookup[cls.REGISTER_ENABLED],
            'GROUPS_ENABLED': lookup[cls.GROUPS_ENABLED],
            'AUTO_TEST_ENABLED': lookup[cls.AUTO_TEST_ENABLED],
            'COURSE_REGISTER_ENABLED': lookup[cls.COURSE_REGISTER_ENABLED],
            'RENDER_HTML_ENABLED': lookup[cls.RENDER_HTML_ENABLED],
            'EMAIL_STUDENTS_ENABLED': lookup[cls.EMAIL_STUDENTS_ENABLED],
            'PEER_FEEDBACK_ENABLED': lookup[cls.PEER_FEEDBACK_ENABLED],
        }

    class AllOptsAsJSON(FrontendOptsAsJSON):
        """The JSON representation of all options."""
        #: The amount of time there can be between two heartbeats of a runner.
        #: Changing this to a lower value might cause some runners to crash.
        AUTO_TEST_HEARTBEAT_INTERVAL: datetime.timedelta
        #: The max amount of heartbeats that we may miss from a runner before
        #: we kill it and start a new one.
        AUTO_TEST_HEARTBEAT_MAX_MISSED: int
        #: This value determines the amount of runners we request for a single
        #: assignment. The amount of runners requested is equal to the amount
        #: of students not yet started divided by this value.
        AUTO_TEST_MAX_JOBS_PER_RUNNER: int
        #: The maximum amount of batch AutoTest runs we will do at a time.
        #: AutoTest batch runs are runs that are done after the deadline for
        #: configurations that have hidden tests. Increasing this variable
        #: might cause heavy server load.
        AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS: int
        #: The minimum strength passwords by users should have. The higher this
        #: value the stronger the password should be. When increasing the
        #: strength all users with too weak passwords will be shown a warning
        #: on the next login.
        MIN_PASSWORD_SCORE: int
        #: The amount of time a reset token is valid. You should not increase
        #: this value too much as users might be not be too careful with these
        #: tokens. Increasing this value will allow **all** existing tokens to
        #: live longer.
        RESET_TOKEN_TIME: datetime.timedelta
        #: The amount of time the link send in notification emails to change
        #: the notification preferences works to actually change the
        #: notifications.
        SETTING_TOKEN_TIME: datetime.timedelta
        #: The maximum amount of files and directories allowed in a single
        #: archive.
        MAX_NUMBER_OF_FILES: int
        #: The maximum size of uploaded files that are mostly uploaded by
        #: "trusted" users. Examples of these kind of files include AutoTest
        #: fixtures and plagiarism base code.
        MAX_LARGE_UPLOAD_SIZE: FileSize
        #: The maximum total size of uploaded files that are uploaded by normal
        #: users. This is also the maximum total size of submissions.
        #: Increasing this size might cause a hosting costs to increase.
        MAX_NORMAL_UPLOAD_SIZE: FileSize
        #: The maximum size of a single file uploaded by normal users. This
        #: limit is really here to prevent users from uploading extremely large
        #: files which can't really be downloaded/shown anyway.
        MAX_FILE_SIZE: FileSize
        #: The time a login session is valid. After this amount of time a user
        #: will always need to re-authenticate.
        JWT_ACCESS_TOKEN_EXPIRES: datetime.timedelta

    AllOptsAsJSON.__cg_extends__ = FrontendOptsAsJSON  # type: ignore

    @classmethod
    def get_all_opts(cls) -> AllOptsAsJSON:
        lookup: t.Any = models.SiteSetting.get_options(cls._ALL_OPTS)
        return {
            'AUTO_TEST_MAX_TIME_COMMAND':
                lookup[cls.AUTO_TEST_MAX_TIME_COMMAND],
            'AUTO_TEST_HEARTBEAT_INTERVAL':
                lookup[cls.AUTO_TEST_HEARTBEAT_INTERVAL],
            'AUTO_TEST_HEARTBEAT_MAX_MISSED':
                lookup[cls.AUTO_TEST_HEARTBEAT_MAX_MISSED],
            'AUTO_TEST_MAX_JOBS_PER_RUNNER':
                lookup[cls.AUTO_TEST_MAX_JOBS_PER_RUNNER],
            'AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS':
                lookup[cls.AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS],
            'EXAM_LOGIN_MAX_LENGTH': lookup[cls.EXAM_LOGIN_MAX_LENGTH],
            'LOGIN_TOKEN_BEFORE_TIME': lookup[cls.LOGIN_TOKEN_BEFORE_TIME],
            'MIN_PASSWORD_SCORE': lookup[cls.MIN_PASSWORD_SCORE],
            'RESET_TOKEN_TIME': lookup[cls.RESET_TOKEN_TIME],
            'SETTING_TOKEN_TIME': lookup[cls.SETTING_TOKEN_TIME],
            'SITE_EMAIL': lookup[cls.SITE_EMAIL],
            'MAX_NUMBER_OF_FILES': lookup[cls.MAX_NUMBER_OF_FILES],
            'MAX_LARGE_UPLOAD_SIZE': lookup[cls.MAX_LARGE_UPLOAD_SIZE],
            'MAX_NORMAL_UPLOAD_SIZE': lookup[cls.MAX_NORMAL_UPLOAD_SIZE],
            'MAX_FILE_SIZE': lookup[cls.MAX_FILE_SIZE],
            'JWT_ACCESS_TOKEN_EXPIRES': lookup[cls.JWT_ACCESS_TOKEN_EXPIRES],
            'MAX_LINES': lookup[cls.MAX_LINES],
            'NOTIFICATION_POLL_TIME': lookup[cls.NOTIFICATION_POLL_TIME],
            'RELEASE_MESSAGE_MAX_TIME': lookup[cls.RELEASE_MESSAGE_MAX_TIME],
            'BLACKBOARD_ZIP_UPLOAD_ENABLED':
                lookup[cls.BLACKBOARD_ZIP_UPLOAD_ENABLED],
            'RUBRICS_ENABLED': lookup[cls.RUBRICS_ENABLED],
            'AUTOMATIC_LTI_ROLE_ENABLED':
                lookup[cls.AUTOMATIC_LTI_ROLE_ENABLED],
            'LTI_ENABLED': lookup[cls.LTI_ENABLED],
            'LINTERS_ENABLED': lookup[cls.LINTERS_ENABLED],
            'INCREMENTAL_RUBRIC_SUBMISSION_ENABLED':
                lookup[cls.INCREMENTAL_RUBRIC_SUBMISSION_ENABLED],
            'REGISTER_ENABLED': lookup[cls.REGISTER_ENABLED],
            'GROUPS_ENABLED': lookup[cls.GROUPS_ENABLED],
            'AUTO_TEST_ENABLED': lookup[cls.AUTO_TEST_ENABLED],
            'COURSE_REGISTER_ENABLED': lookup[cls.COURSE_REGISTER_ENABLED],
            'RENDER_HTML_ENABLED': lookup[cls.RENDER_HTML_ENABLED],
            'EMAIL_STUDENTS_ENABLED': lookup[cls.EMAIL_STUDENTS_ENABLED],
            'PEER_FEEDBACK_ENABLED': lookup[cls.PEER_FEEDBACK_ENABLED],
        }


OPTIONS_INPUT_PARSER = rqa.Lazy(
    lambda: (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('AUTO_TEST_MAX_TIME_COMMAND'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.AUTO_TEST_MAX_TIME_COMMAND.parser),
                '',
            ),
        ).add_tag('opt', Opt.AUTO_TEST_MAX_TIME_COMMAND)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('AUTO_TEST_HEARTBEAT_INTERVAL'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.AUTO_TEST_HEARTBEAT_INTERVAL.parser),
                '',
            ),
        ).add_tag('opt', Opt.AUTO_TEST_HEARTBEAT_INTERVAL)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('AUTO_TEST_HEARTBEAT_MAX_MISSED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.AUTO_TEST_HEARTBEAT_MAX_MISSED.parser),
                '',
            ),
        ).add_tag('opt', Opt.AUTO_TEST_HEARTBEAT_MAX_MISSED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('AUTO_TEST_MAX_JOBS_PER_RUNNER'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.AUTO_TEST_MAX_JOBS_PER_RUNNER.parser),
                '',
            ),
        ).add_tag('opt', Opt.AUTO_TEST_MAX_JOBS_PER_RUNNER)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS.parser),
                '',
            ),
        ).add_tag('opt', Opt.AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('EXAM_LOGIN_MAX_LENGTH'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.EXAM_LOGIN_MAX_LENGTH.parser),
                '',
            ),
        ).add_tag('opt', Opt.EXAM_LOGIN_MAX_LENGTH)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('LOGIN_TOKEN_BEFORE_TIME'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.LOGIN_TOKEN_BEFORE_TIME.parser),
                '',
            ),
        ).add_tag('opt', Opt.LOGIN_TOKEN_BEFORE_TIME)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('MIN_PASSWORD_SCORE'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.MIN_PASSWORD_SCORE.parser),
                '',
            ),
        ).add_tag('opt', Opt.MIN_PASSWORD_SCORE)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('RESET_TOKEN_TIME'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.RESET_TOKEN_TIME.parser),
                '',
            ),
        ).add_tag('opt', Opt.RESET_TOKEN_TIME)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('SETTING_TOKEN_TIME'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.SETTING_TOKEN_TIME.parser),
                '',
            ),
        ).add_tag('opt', Opt.SETTING_TOKEN_TIME)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('SITE_EMAIL'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.SITE_EMAIL.parser),
                '',
            ),
        ).add_tag('opt', Opt.SITE_EMAIL)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('MAX_NUMBER_OF_FILES'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.MAX_NUMBER_OF_FILES.parser),
                '',
            ),
        ).add_tag('opt', Opt.MAX_NUMBER_OF_FILES)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('MAX_LARGE_UPLOAD_SIZE'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.MAX_LARGE_UPLOAD_SIZE.parser),
                '',
            ),
        ).add_tag('opt', Opt.MAX_LARGE_UPLOAD_SIZE)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('MAX_NORMAL_UPLOAD_SIZE'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.MAX_NORMAL_UPLOAD_SIZE.parser),
                '',
            ),
        ).add_tag('opt', Opt.MAX_NORMAL_UPLOAD_SIZE)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('MAX_FILE_SIZE'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.MAX_FILE_SIZE.parser),
                '',
            ),
        ).add_tag('opt', Opt.MAX_FILE_SIZE)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('JWT_ACCESS_TOKEN_EXPIRES'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.JWT_ACCESS_TOKEN_EXPIRES.parser),
                '',
            ),
        ).add_tag('opt', Opt.JWT_ACCESS_TOKEN_EXPIRES)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('MAX_LINES'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.MAX_LINES.parser),
                '',
            ),
        ).add_tag('opt', Opt.MAX_LINES)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('NOTIFICATION_POLL_TIME'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.NOTIFICATION_POLL_TIME.parser),
                '',
            ),
        ).add_tag('opt', Opt.NOTIFICATION_POLL_TIME)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('RELEASE_MESSAGE_MAX_TIME'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.RELEASE_MESSAGE_MAX_TIME.parser),
                '',
            ),
        ).add_tag('opt', Opt.RELEASE_MESSAGE_MAX_TIME)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('BLACKBOARD_ZIP_UPLOAD_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.BLACKBOARD_ZIP_UPLOAD_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.BLACKBOARD_ZIP_UPLOAD_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('RUBRICS_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.RUBRICS_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.RUBRICS_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('AUTOMATIC_LTI_ROLE_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.AUTOMATIC_LTI_ROLE_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.AUTOMATIC_LTI_ROLE_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('LTI_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.LTI_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.LTI_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('LINTERS_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.LINTERS_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.LINTERS_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('INCREMENTAL_RUBRIC_SUBMISSION_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.INCREMENTAL_RUBRIC_SUBMISSION_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.INCREMENTAL_RUBRIC_SUBMISSION_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('REGISTER_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.REGISTER_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.REGISTER_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('GROUPS_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.GROUPS_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.GROUPS_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('AUTO_TEST_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.AUTO_TEST_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.AUTO_TEST_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('COURSE_REGISTER_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.COURSE_REGISTER_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.COURSE_REGISTER_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('RENDER_HTML_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.RENDER_HTML_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.RENDER_HTML_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('EMAIL_STUDENTS_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.EMAIL_STUDENTS_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.EMAIL_STUDENTS_ENABLED)
    ) | (
        rqa.FixedMapping(
            rqa.RequiredArgument(
                'name',
                rqa.StringEnum('PEER_FEEDBACK_ENABLED'),
                '',
            ),
            rqa.RequiredArgument(
                'value',
                rqa.Nullable(Opt.PEER_FEEDBACK_ENABLED.parser),
                '',
            ),
        ).add_tag('opt', Opt.PEER_FEEDBACK_ENABLED)
    )
)
OPTIONS_INPUT_PARSER.as_schema('SiteSettingInputAsJSON')


def init_app(app: PsefFlask) -> None:
    pass
