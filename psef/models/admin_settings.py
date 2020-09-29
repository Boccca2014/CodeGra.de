import typing as t
import datetime
import dataclasses

from typing_extensions import Literal, Protocol

from cg_sqlalchemy_helpers import JSONB
from cg_cache.intra_request import cache_within_request
from cg_sqlalchemy_helpers.types import ColumnProxy
from cg_sqlalchemy_helpers.mixins import IdMixin, TimestampMixin

from . import Base, db

_T = t.TypeVar('_T', bool, datetime.timedelta, int, str, covariant=True)
T = t.TypeVar(
    'T',
    bool,
    datetime.timedelta,
    int,
    t.Sequence[datetime.timedelta],
    str,
    covariant=True
)


@dataclasses.dataclass
class _OptionCategory:
    name: str


# Work around for https://github.com/python/mypy/issues/5485
class _Parser(Protocol[T]):
    def __call__(self, value: str) -> T:
        ...


@dataclasses.dataclass
class _Option(t.Generic[T]):
    name: str
    default: T
    doc: str
    parser: _Parser[T]
    security: bool
    stored_parsed: bool
    category: t.Optional[_OptionCategory] = None


def parse_integer(value: str) -> int:
    return int(value)


def parse_string(value: str) -> str:
    assert value, 'The value should not be empty'
    return value


def parse_timedelta(value: str) -> datetime.timedelta:
    number, opt = int(value[:-1]), value[-1]
    if opt == 's':
        return datetime.timedelta(seconds=number)
    elif opt == 'm':
        return datetime.timedelta(minutes=number)
    elif opt == 'h':
        return datetime.timedelta(hours=number)
    elif opt == 'd':
        return datetime.timedelta(days=number)
    raise AssertionError('Unknown prefix: {}'.format(opt))


_KB = 1 << 10
_MB = _KB << 10
_GB = _MB << 10


def parse_size(value: str) -> int:
    number, unit = int(value[:-2]), value[-2:]
    if unit == 'kb':
        return number * _KB
    elif unit == 'mb':
        return number * _MB
    elif unit == 'gb':
        return number * _GB
    else:
        raise AssertionError('Unknown limit encountered: {}'.format(unit))


def parse_array(parse_item: t.Callable[[str], '_T']) -> '_Parser[t.Any]':
    def __inner(value: str) -> t.Sequence['_T']:
        res = tuple(parse_item(item.strip()) for item in value.split(','))
        assert res, 'The list should at least have one item'
        return res

    return __inner


_ALL_OPTIONS: t.Sequence[_Option] = (
    _Option(
        name='AUTO_TEST_MAX_TIME_COMMAND',
        doc=(
            'The default amount of time a step/substep in AutoTest can run. This can be overridden by the teacher.'
        ),
        parser=parse_timedelta,
        security=False,
        default=datetime.timedelta(seconds=300),
        stored_parsed=False
    ),
    _Option(
        name='AUTO_TEST_HEARTBEAT_INTERVAL',
        doc=(
            'The amount of time there can be between two heartbeats of a runner. Changing this to a lower value might cause some runners to crash.'
        ),
        parser=parse_timedelta,
        security=False,
        default=datetime.timedelta(seconds=10),
        stored_parsed=False
    ),
    _Option(
        name='AUTO_TEST_HEARTBEAT_MAX_MISSED',
        doc=(
            'The max amount of heartbeats that we may miss from a runner before we kill it and start a new one.'
        ),
        parser=parse_integer,
        security=False,
        default=6,
        stored_parsed=True
    ),
    _Option(
        name='AUTO_TEST_MAX_JOBS_PER_RUNNER',
        doc=(
            'This value determines the amount of runners we request for a single assignment. The amount of runners requested is equal to the amount of students not yet started divided by this value.'
        ),
        parser=parse_integer,
        security=False,
        default=10,
        stored_parsed=True
    ),
    _Option(
        name='AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS',
        doc=(
            'The maximum amount of batch AutoTest runs we will do at a time. AutoTest batch runs are runs that are done after the deadline for configurations that have hidden tests. Increasing this variable might cause heavy server load.'
        ),
        parser=parse_integer,
        security=False,
        default=3,
        stored_parsed=True
    ),
    _Option(
        name='EXAM_LOGIN_MAX_LENGTH',
        doc=(
            'The maximum duration an exam may take. Increasing this value also increases the maximum amount of time the login tokens send via email are valid. Therefore, you should make this too long.'
        ),
        parser=parse_timedelta,
        security=True,
        default=datetime.timedelta(seconds=43200),
        stored_parsed=False
    ),
    _Option(
        name='LOGIN_TOKEN_BEFORE_TIME',
        doc=(
            'This determines how long before the exam we will send the login emails to the students (only when enabled of course).'
        ),
        parser=parse_array(parse_timedelta),
        security=False,
        default=(datetime.timedelta(days=2), datetime.timedelta(seconds=1800)),
        stored_parsed=False
    ),
    _Option(
        name='MIN_PASSWORD_SCORE',
        doc=(
            'The minimum strength passwords by users should have. The higher this value the stronger the password should be. When increasing the strength all users with too weak passwords will be shown a warning on the next login.'
        ),
        parser=parse_integer,
        security=False,
        default=3,
        stored_parsed=True
    ),
    _Option(
        name='RESET_TOKEN_TIME',
        doc=(
            'The amount of time a reset token is valid. You should not increase this value too much as users might be not be too careful with these tokens. Increasing this value will allow **all** existing tokens to live longer.'
        ),
        parser=parse_timedelta,
        security=True,
        default=datetime.timedelta(days=1),
        stored_parsed=False
    ),
    _Option(
        name='SETTING_TOKEN_TIME',
        doc=(
            'The amount of time the link send in notification emails to change the notification preferences works to actually change the notifications.'
        ),
        parser=parse_timedelta,
        security=False,
        default=datetime.timedelta(days=1),
        stored_parsed=False
    ),
    _Option(
        name='SITE_EMAIL',
        doc=('The email shown to users as the email of CodeGrade.'),
        parser=parse_string,
        security=False,
        default='info@codegrade.com',
        stored_parsed=True
    ),
    _Option(
        name='MAX_NUMBER_OF_FILES',
        doc=(
            'The maximum amount of files and directories allowed in a single archive.'
        ),
        parser=parse_integer,
        security=False,
        default=16384,
        stored_parsed=True
    ),
    _Option(
        name='MAX_LARGE_UPLOAD_SIZE',
        doc=(
            'The maximum size of uploaded files that are mostly uploaded by "trusted" users. Examples of these kind of files include AutoTest fixtures and plagiarism base code.'
        ),
        parser=parse_size,
        security=False,
        default=134217728,
        stored_parsed=True
    ),
    _Option(
        name='MAX_NORMAL_UPLOAD_SIZE',
        doc=(
            'The maximum total size of uploaded files that are uploaded by normal users. This is also the maximum total size of submissions. Increasing this size might cause a hosting costs to increase.'
        ),
        parser=parse_size,
        security=False,
        default=67108864,
        stored_parsed=True
    ),
    _Option(
        name='MAX_FILE_SIZE',
        doc=(
            "The maximum size of a single file uploaded by normal users. This limit is really here to prevent users from uploading extremely large files which can't really be downloaded/shown anyway."
        ),
        parser=parse_size,
        security=False,
        default=52428800,
        stored_parsed=True
    ),
    _Option(
        name='JWT_ACCESS_TOKEN_EXPIRES',
        doc=(
            'The time a login session is valid. After this amount of time a user will always need to re-authenticate.'
        ),
        parser=parse_timedelta,
        security=False,
        default=datetime.timedelta(days=30),
        stored_parsed=False
    ),
)

_OPTIONS_LOOKUP = {o.name: o for o in _ALL_OPTIONS}


class AdminSetting(Base, TimestampMixin):
    _name = db.Column('name', db.Unicode, nullable=False, primary_key=True)
    _value: ColumnProxy[t.Any] = db.Column('value', JSONB, nullable=False)

    @t.overload
    @classmethod
    def get_option(
        cls, name: Literal['AUTO_TEST_MAX_TIME_COMMAND']
    ) -> datetime.timedelta:
        ...

    @t.overload
    @classmethod
    def get_option(
        cls, name: Literal['AUTO_TEST_HEARTBEAT_INTERVAL']
    ) -> datetime.timedelta:
        ...

    @t.overload
    @classmethod
    def get_option(
        cls, name: Literal['AUTO_TEST_HEARTBEAT_MAX_MISSED']
    ) -> int:
        ...

    @t.overload
    @classmethod
    def get_option(cls, name: Literal['AUTO_TEST_MAX_JOBS_PER_RUNNER']) -> int:
        ...

    @t.overload
    @classmethod
    def get_option(
        cls, name: Literal['AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS']
    ) -> int:
        ...

    @t.overload
    @classmethod
    def get_option(
        cls, name: Literal['EXAM_LOGIN_MAX_LENGTH']
    ) -> datetime.timedelta:
        ...

    @t.overload
    @classmethod
    def get_option(cls, name: Literal['LOGIN_TOKEN_BEFORE_TIME']
                   ) -> t.Sequence[datetime.timedelta]:
        ...

    @t.overload
    @classmethod
    def get_option(cls, name: Literal['MIN_PASSWORD_SCORE']) -> int:
        ...

    @t.overload
    @classmethod
    def get_option(
        cls, name: Literal['RESET_TOKEN_TIME']
    ) -> datetime.timedelta:
        ...

    @t.overload
    @classmethod
    def get_option(
        cls, name: Literal['SETTING_TOKEN_TIME']
    ) -> datetime.timedelta:
        ...

    @t.overload
    @classmethod
    def get_option(cls, name: Literal['SITE_EMAIL']) -> str:
        ...

    @t.overload
    @classmethod
    def get_option(cls, name: Literal['MAX_NUMBER_OF_FILES']) -> int:
        ...

    @t.overload
    @classmethod
    def get_option(cls, name: Literal['MAX_LARGE_UPLOAD_SIZE']) -> int:
        ...

    @t.overload
    @classmethod
    def get_option(cls, name: Literal['MAX_NORMAL_UPLOAD_SIZE']) -> int:
        ...

    @t.overload
    @classmethod
    def get_option(cls, name: Literal['MAX_FILE_SIZE']) -> int:
        ...

    @t.overload
    @classmethod
    def get_option(
        cls, name: Literal['JWT_ACCESS_TOKEN_EXPIRES']
    ) -> datetime.timedelta:
        ...

    @classmethod
    @cache_within_request
    def get_option(cls, name: str) -> t.Any:
        opt = _OPTIONS_LOOKUP[name]
        self = cls.query.get(name)
        if self is None:
            return opt.default
        elif opt.stored_parsed:
            return self._value
        return opt.parser(self._value)


class AdminSettingHistory(Base, TimestampMixin, IdMixin):
    setting_name = db.Column(
        'name',
        db.Unicode,
        db.ForeignKey('admin_setting.name'),
        nullable=False,
    )
    old_value = db.Column('old_value', JSONB, nullable=True)
    new_value = db.Column('new_value', JSONB, nullable=False)
