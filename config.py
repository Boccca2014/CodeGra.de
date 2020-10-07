import os
import re
import sys
import json
import typing as t
import datetime
import tempfile
import warnings
import subprocess
import urllib.parse
from configparser import ConfigParser

from typing_extensions import Literal, TypedDict

import cg_object_storage

cur_dir = os.path.dirname(os.path.abspath(__file__))
config_file = os.getenv(
    'CODEGRADE_CONFIG_FILE', os.path.join(cur_dir, 'config.ini')
)

CONFIG: t.Dict[str, t.Any] = dict()
CONFIG['BASE_DIR'] = cur_dir

os.environ['BASE_DIR'] = str(CONFIG['BASE_DIR'])

parser = ConfigParser({k: v for k, v in os.environ.items() if k.isupper()})
parser.read(config_file)

if 'Back-end' not in parser:
    parser['Back-end'] = {}
if 'Features' not in parser:
    parser['Features'] = {}
if 'AutoTest' not in parser:
    parser['AutoTest'] = {}
if 'Front-end' not in parser:
    parser['Front-end'] = {}

backend_ops = parser['Back-end']
frontend_ops = parser['Front-end']
feature_ops = parser['Features']
auto_test_ops = parser['AutoTest']


class CeleryConfig(TypedDict, total=True):
    pass


if t.TYPE_CHECKING and getattr(
    t, 'SPHINX', False
) is not True:  # pragma: no cover
    import psef.features
    import psef.auto_test

AutoTestConfig = TypedDict(
    'AutoTestConfig', {
        'password': str,
        'container_url': t.Optional[str],
    }
)
AutoTestHosts = t.Mapping[str, AutoTestConfig]

FlaskConfig = TypedDict(
    'FlaskConfig', {
        'FEATURES': t.Mapping['psef.features.Feature', bool],
        '__S_FEATURES': t.Mapping[str, bool],
        'IS_AUTO_TEST_RUNNER': bool,
        'AUTO_TEST_PASSWORD': str,
        'AUTO_TEST_DISABLE_ORIGIN_CHECK': bool,
        'AUTO_TEST_POLL_TIME': int,
        'AUTO_TEST_OUTPUT_LIMIT': int,
        'AUTO_TEST_MEMORY_LIMIT': str,
        'AUTO_TEST_BDEVTYPE': str,
        'AUTO_TEST_TEMPLATE_CONTAINER': t.Optional[str],
        'AUTO_TEST_BROKER_URL': str,
        'AUTO_TEST_BROKER_PASSWORD': str,
        'AUTO_TEST_CF_SLEEP_TIME': float,
        'AUTO_TEST_CF_EXTRA_AMOUNT': int,
        'AUTO_TEST_MAX_OUTPUT_TAIL': int,
        'AUTO_TEST_STARTUP_COMMAND': t.Optional[str],
        'AUTO_TEST_RUNNER_INSTANCE_PASS': str,
        'AUTO_TEST_RUNNER_CONTAINER_URL': t.Optional[str],
        'CUR_COMMIT': str,
        'VERSION': str,
        'TESTING': bool,
        'Celery': CeleryConfig,
        'LTI_CONSUMER_KEY_SECRETS': t.Mapping[str, t.Tuple[str, t.List[str]]],
        'LTI1.3_MIN_POLL_INTERVAL': int,
        'DEBUG': bool,
        'SQLALCHEMY_DATABASE_URI': str,
        'SECRET_KEY': str,
        'LTI_SECRET_KEY': str,
        'HEALTH_KEY': None,
        'UPLOAD_DIR': str,
        'MIRROR_UPLOAD_DIR': str,
        'DEFAULT_ROLE': str,
        '_DEFAULT_COURSE_ROLES': t.Mapping[str, t.Mapping],
        'DEFAULT_SSO_ROLE': str,
        'SSO_METADATA_EXTRA_LANGUAGES': t.List[str],
        'EXTERNAL_DOMAIN': str,
        'EXTERNAL_URL': str,
        'PROXY_BASE_DOMAIN': str,
        'JAVA_PATH': str,
        'JPLAG_JAR': str,
        'JPLAG_SUPPORTED_LANGUAGES': t.Mapping[str, str],
        'MAIL_SERVER': str,
        'MAIL_PORT': int,
        'MAIL_USE_TLS': bool,
        'MAIL_USE_SSL': bool,
        'MAIL_USERNAME': str,
        'MAIL_PASSWORD': str,
        'MAIL_DEFAULT_SENDER': t.Tuple[str, str],
        'MAIL_MAX_EMAILS': int,
        'EMAIL_TEMPLATE': str,
        'REMINDER_TEMPLATE': str,
        'GRADER_STATUS_TEMPLATE': str,
        'DONE_TEMPLATE': str,
        'DIRECT_NOTIFICATION_TEMPLATE_FILE': t.Optional[str],
        'DIRECT_NOTIFICATION_SUBJECT': str,
        'DIGEST_NOTIFICATION_SUBJECT': str,
        'DIGEST_NOTIFICATION_TEMPLATE_FILE': t.Optional[str],
        'EXAM_LOGIN_TEMPLATE_FILE': t.Optional[str],
        'EXAM_LOGIN_SUBJECT': str,
        'CHECKSTYLE_PROGRAM': t.List[str],
        'PMD_PROGRAM': t.List[str],
        'ESLINT_PROGRAM': t.List[str],
        'PYLINT_PROGRAM': t.List[str],
        'FLAKE8_PROGRAM': t.List[str],
        '_USING_SQLITE': str,
        'ADMIN_USER': t.Optional[str],
        'GIT_CLONE_PROGRAM': t.List[str],
        'SESSION_COOKIE_SAMESITE': Literal['None', 'Strict', 'Lax'],
        'SESSION_COOKIE_SECURE': bool,
        'SENTRY_DSN': t.Optional[str],
        'MIN_FREE_DISK_SPACE': cg_object_storage.FileSize,
        'REDIS_CACHE_URL': str,
        'RATELIMIT_STORAGE_URL': t.Optional[str],
    },
    total=True
)


def ensure_between(
    option: str,
    val: t.Union[int, float],
    min: t.Union[int, float, None],
    max: t.Union[int, float, None],
) -> None:
    if (min is not None and val < min) or (max is not None and val > max):
        raise ValueError(
            f'Value of setting {option} must be between {min} and {max} (inclusive)',
        )


def set_bool(
    out: t.MutableMapping[str, t.Any],
    parser: t.Any,
    item: str,
    default: bool,
) -> None:
    val = parser.getboolean(item)
    out[item] = bool(default if val is None else val)


def set_float(
    out: t.MutableMapping[str, t.Any],
    parser: t.Any,
    item: str,
    default: float,
    min: float = None,
    max: float = None,
) -> None:
    val = parser.getfloat(item)
    val = float(default if val is None else val)
    ensure_between(item, val, min, max)
    out[item] = val


def set_int(
    out: t.MutableMapping[str, t.Any],
    parser: t.Any,
    item: str,
    default: int,
    min: int = None,
    max: int = None,
) -> None:
    val = parser.getint(item)
    val = int(default if val is None else val)
    ensure_between(item, val, min, max)
    out[item] = val



def set_str(
    out: t.MutableMapping[str, t.Any],
    parser: t.Any,
    item: str,
    default: object,
    key_in_parser: str = None,
) -> None:
    if key_in_parser is None:
        key_in_parser = item

    val = parser.get(key_in_parser)
    out[item] = default if val is None else str(val)


def set_list(
    out: t.MutableMapping[str, t.Any],
    parser: t.Any,
    item: str,
    default: object,
) -> None:
    val = parser.get(item)
    if val is None:
        out[item] = default
    else:
        parsed_val = json.loads(val)
        assert isinstance(parsed_val, list), f'Value "{item}" should be a list'
        assert all(isinstance(v, str) for v in parsed_val)
        out[item] = parsed_val


def set_dict(
    out: t.MutableMapping[str, t.Any],
    parser: t.Any,
    item: str,
    default: object,
) -> None:
    val = parser.get(item)
    if val is None:
        out[item] = default
    else:
        parsed_val = json.loads(val)
        assert isinstance(parsed_val, dict), f'Value "{item}" should be a list'
        out[item] = parsed_val


set_bool(CONFIG, backend_ops, 'DEBUG', False)
CONFIG['TESTING'] = False

# Define the database. If `CODEGRADE_DATABASE_URL` is found in the enviroment
# variables it is used. The string should be in this format for postgresql:
# `postgresql://dbusername:dbpassword@dbhost/dbname`
set_str(
    CONFIG, backend_ops, 'SQLALCHEMY_DATABASE_URI',
    os.getenv('SQLALCHEMY_DATABASE_URI', 'postgresql:///codegrade_dev')
)
CONFIG['_USING_SQLITE'] = CONFIG['SQLALCHEMY_DATABASE_URI'].startswith(
    'sqlite'
)
CONFIG['DATABASE_CONNECT_OPTIONS'] = {}

# Secret key for signing JWT tokens.
set_str(
    CONFIG,
    backend_ops,
    'SECRET_KEY',
    (
        'secret'
        if CONFIG['DEBUG'] else os.environ.get('CODEGRADE_JWT_SECRET_KEY')
    ),
)

# This should be a strong random key that is not public.
set_str(
    CONFIG,
    backend_ops,
    'LTI_SECRET_KEY',
    (
        'hunter123'
        if CONFIG['DEBUG'] else os.environ.get('CODEGRADE_LTI_SECRET_KEY')
    ),
)

set_str(CONFIG, backend_ops, 'HEALTH_KEY', None)
if CONFIG['HEALTH_KEY'] is None:
    warnings.warn('No "health_key" provided, disabling health route.')

CONFIG['JWT_ALGORITHM'] = 'HS512'

# Path for storage of uploaded files.
# WARNING: Make sure these directories exist.
set_str(
    CONFIG, backend_ops, 'UPLOAD_DIR',
    os.path.join(CONFIG['BASE_DIR'], 'uploads')
)
if not os.path.isdir(CONFIG['UPLOAD_DIR']):
    warnings.warn(
        f'The given uploads directory "{CONFIG["UPLOAD_DIR"]}" does not exist',
    )

set_str(
    CONFIG, backend_ops, 'MIRROR_UPLOAD_DIR',
    os.path.join(CONFIG['BASE_DIR'], 'mirror_uploads')
)
if not os.path.isdir(CONFIG['MIRROR_UPLOAD_DIR']):
    warnings.warn(
        f'The given uploads directory "{CONFIG["MIRROR_UPLOAD_DIR"]}"'
        ' does not exist',
    )

with open(
    os.path.join(CONFIG['BASE_DIR'], 'seed_data', 'course_roles.json'), 'r'
) as f:
    CONFIG['_DEFAULT_COURSE_ROLES'] = json.load(f)

# The default site role a user should get. The name of this role should be
# present as a key in `seed_data/roles.json`.
set_str(CONFIG, backend_ops, 'DEFAULT_ROLE', 'Student')
set_str(CONFIG, backend_ops, 'DEFAULT_SSO_ROLE', 'SSO User')

set_list(CONFIG, backend_ops, 'SSO_METADATA_EXTRA_LANGUAGES', ['nl'])

# The external URL the server runs on.
set_str(CONFIG, backend_ops, 'EXTERNAL_URL', '')
set_str(CONFIG, backend_ops, 'PROXY_BASE_DOMAIN', '')
CONFIG['EXTERNAL_DOMAIN'] = urllib.parse.urlparse(
    CONFIG['EXTERNAL_URL']
).hostname
CONFIG['PREFERRED_URL_SCHEME'] = 'https'

set_str(CONFIG, backend_ops, 'JAVA_PATH', 'java')

set_str(CONFIG, backend_ops, 'JPLAG_JAR', 'jplag.jar')

set_str(CONFIG, backend_ops, 'SENTRY_DSN', None)

GB = 1024 ** 3
min_free = backend_ops.getint('MIN_FREE_DISK_SPACE', fallback=10 * GB)
CONFIG['MIN_FREE_DISK_SPACE'] = cg_object_storage.FileSize(min_free)


def _set_version() -> None:
    CONFIG['CUR_COMMIT'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'],
        text=True,
    ).strip()
    CONFIG['VERSION'] = subprocess.check_output(
        ['git', 'describe', '--abbrev=0', '--tags'],
        text=True,
    ).strip()


try:
    _set_version()
except subprocess.CalledProcessError:
    print(
        (
            'An error occurred trying to get the version, this is probably'
            ' caused by not deep cloning the repository. We will try that'
            ' now.'
        ),
        file=sys.stderr,
    )
    subprocess.check_call(['git', 'fetch', '--unshallow'])
    _set_version()
del _set_version

# Set email settings
set_str(CONFIG, backend_ops, 'MAIL_SERVER', 'localhost')
set_int(CONFIG, backend_ops, 'MAIL_PORT', 25)
set_bool(CONFIG, backend_ops, 'MAIL_USE_TLS', False)
set_bool(CONFIG, backend_ops, 'MAIL_USE_SSL', False)
set_str(CONFIG, backend_ops, 'MAIL_USERNAME', 'noreply')
set_str(CONFIG, backend_ops, 'MAIL_PASSWORD', 'nopasswd')
sender = (
    backend_ops.get('MAIL_DEFAULT_SENDER_NAME', 'CodeGrade'),
    backend_ops.get('MAIL_DEFAULT_SENDER', 'noreply')
)
CONFIG['MAIL_DEFAULT_SENDER'] = sender
set_int(CONFIG, backend_ops, 'MAIL_MAX_EMAILS', 100)

set_str(
    CONFIG,
    backend_ops,
    'EMAIL_TEMPLATE',
    """
<p>Dear {user_name},

This email lets you reset your password on <a
href="{site_url}">{site_url}</a>. If you go to <a href="{url}">this page</a>
you can reset your password there. Please do not reply to this email.

If you have not triggered this action please ignore this email.</p>
    """.strip(),
)
set_str(
    CONFIG,
    backend_ops,
    'REMINDER_TEMPLATE',
    """
<p>Dear {user_name},

This email is a reminder that you have work left to grade on the assignment
"{assig_name}" on <a href="{site_url}">{site_url}</a>. If you go to <a
href="{site_url}/courses/{course_id}/assignments/{assig_id}/submissions">this
page</a> you can directly continue grading, which of course is joyful business
on CodeGrade! Good luck with grading.

This email was automatically sent because of reminder that was set for this
assignment and you have not yet indicated you were done grading. You can
indicate this <a href="{site_url}/courses/{course_id}">here</a>.</p>
    """.strip(),
)
set_str(
    CONFIG,
    backend_ops,
    'GRADER_STATUS_TEMPLATE',
    """
<p>Dear {user_name},

This email is a reminder that your grade status has been reset to 'not done'
for "{assig_name}" on <a href="{site_url}">{site_url}</a>. If you go to <a
href="{site_url}/courses/{course_id}/assignments/{assig_id}/submissions">this
page</a> you can directly continue grading, which of course is joyful business
on CodeGrade! Good luck with grading.

This email was automatically sent. The reason for this can be that a course
admin has reset your status or that you have been assigned new
submission(s).</p>
    """.strip(),
)
set_str(
    CONFIG, backend_ops, 'DONE_TEMPLATE', """
<p>Dear,

This email has been sent to let you know that all work has been graded on the
assignment "{assig_name}" on <a href="{site_url}">{site_url}</a>. If you go to
<a href="{site_url}/courses/{course_id}">this page</a> you can set the state of
the assignment to 'done' so that the students can see their grade!

This email was automatically sent because of reminder that was set for this
assignment. You can change these settings <a
href="{site_url}/courses/{course_id}">here</a>.</p>
        """.strip()
)

set_str(
    CONFIG,
    backend_ops,
    'DIGEST_NOTIFICATION_SUBJECT',
    "Your {{ send_type.name }} digest on CodeGrade",
)
CONFIG['DIGEST_NOTIFICATION_TEMPLATE_FILE'] = backend_ops.get(
    'DIGEST_NOTIFICATION_TEMPLATE_FILE'
)

set_str(
    CONFIG,
    backend_ops,
    'DIRECT_NOTIFICATION_SUBJECT',
    """{% set comment = notification.comment_reply -%}
{{ comment.author.get_readable_name() if comment.can_see_author else 'A grader' }} commented on a thread you are following
""".strip(),
)

CONFIG['DIRECT_NOTIFICATION_TEMPLATE_FILE'] = backend_ops.get(
    'DIRECT_NOTIFICATION_TEMPLATE_FILE'
)

set_str(
    CONFIG, backend_ops, 'EXAM_LOGIN_SUBJECT', """
{% set assignment = link.assignment -%}
Your CodeGrade login link for the {{ assignment.name }} in the {{ assignment.course.name }} course
""".strip()
)

set_str(CONFIG, backend_ops, 'EXAM_LOGIN_TEMPLATE_FILE', None)

set_list(
    CONFIG, backend_ops, 'CHECKSTYLE_PROGRAM', [
        'java',
        '-Dbasedir={files}',
        '-jar',
        'checkstyle.jar',
        '-f',
        'xml',
        '-c',
        '{config}',
        '{files}',
    ]
)
set_list(
    CONFIG, backend_ops, 'PMD_PROGRAM', [
        './pmd/bin/run.sh',
        'pmd',
        '-dir',
        '{files}',
        '-failOnViolation',
        'false',
        '-format',
        'csv',
        '-shortnames',
        '-rulesets',
        '{config}',
    ]
)
set_list(
    CONFIG, backend_ops, 'PYLINT_PROGRAM', [
        'pylint',
        '--rcfile',
        '{config}',
        '--output-format',
        'json',
        '{files}',
    ]
)
set_list(
    CONFIG, backend_ops, 'FLAKE8_PROGRAM', [
        'flake8',
        '--disable-noqa',
        '--config={config}',
        '--format',
        '{line_fmt}',
        '--exit-zero',
        '{files}',
    ]
)
set_list(
    CONFIG, backend_ops, 'ESLINT_PROGRAM', [
        os.path.join(os.path.dirname(__file__), '.scripts', 'run_eslint.bash'),
        '{files}',
        '{config}',
    ]
)

set_list(
    CONFIG, backend_ops, 'GIT_CLONE_PROGRAM', [
        f'{os.path.dirname(os.path.abspath(__file__))}/.scripts/clone.sh',
        '{ssh_key}',
        '{clone_url}',
        '{commit}',
        '{out_dir}',
        '{git_branch}',
    ]
)

set_str(CONFIG, backend_ops, 'ADMIN_USER', default=None)

set_str(CONFIG, backend_ops, 'REDIS_CACHE_URL', None)

set_str(CONFIG, backend_ops, 'RATELIMIT_STORAGE_URL', 'memory://')

############
# FEATURES #
############
CONFIG['__S_FEATURES'] = {}
# This section contains all features, please do not add, remove or edit any
# keys, the values however can and should be edited. A truth value enables the
# given feature. Please do not add or remove any keys.

# Should any user be able to upload blackboard zips. If this is enabled
# sometimes the username can collide with another user, meaning work is
# uploaded for the wrong user. This option is UNSAFE to enable when working
# on a multiple school instance.
set_bool(CONFIG['__S_FEATURES'], feature_ops, 'BLACKBOARD_ZIP_UPLOAD', True)

# Should rubrics be enabled. This means rubrics can be created by teachers
# and used for grading purposes.
set_bool(CONFIG['__S_FEATURES'], feature_ops, 'RUBRICS', True)

# Should we automatically create a default role for LTI launches with roles
# that are not known.
set_bool(CONFIG['__S_FEATURES'], feature_ops, 'AUTOMATIC_LTI_ROLE', True)

# Should LTI be enabled.
set_bool(CONFIG['__S_FEATURES'], feature_ops, 'LTI', True)

# Should linters be enabled.
set_bool(CONFIG['__S_FEATURES'], feature_ops, 'LINTERS', True)

# Should incremental rubric submission be enabled.
set_bool(
    CONFIG['__S_FEATURES'], feature_ops, 'INCREMENTAL_RUBRIC_SUBMISSION', True
)

set_bool(CONFIG['__S_FEATURES'], feature_ops, 'COURSE_REGISTER', False)

# Should it be possible to register
set_bool(CONFIG['__S_FEATURES'], feature_ops, 'REGISTER', False)

set_bool(CONFIG['__S_FEATURES'], feature_ops, 'GROUPS', False)

set_bool(CONFIG['__S_FEATURES'], feature_ops, 'AUTO_TEST', False)

set_bool(CONFIG['__S_FEATURES'], feature_ops, 'RENDER_HTML', False)

set_bool(CONFIG['__S_FEATURES'], feature_ops, 'EMAIL_STUDENTS', True)

set_bool(CONFIG['__S_FEATURES'], feature_ops, 'PEER_FEEDBACK', False)

############
# LTI keys #
############

lti_parser = ConfigParser()
lti_parser.optionxform = str  # type: ignore
CONFIG['LTI_CONSUMER_KEY_SECRETS'] = {}


def parse_lti_value(
    keys_and_secs: t.Dict[str, t.Tuple[str, t.List[str]]], key: str, value: str
) -> None:
    match = re.match(r'^(.*)\[[0-9]+\]$', key)
    if match is not None:
        key = match.group(1)

    lms, sec = value.split(':', 1)
    assert lms
    assert sec

    if key in keys_and_secs:
        assert keys_and_secs[key][0] == lms
    else:
        keys_and_secs[key] = (lms, [])

    keys_and_secs[key][1].append(sec)


if lti_parser.read(config_file) and 'LTI Consumer keys' in lti_parser:
    for key, value in lti_parser['LTI Consumer keys'].items():
        parse_lti_value(CONFIG['LTI_CONSUMER_KEY_SECRETS'], key, value)

set_int(CONFIG, backend_ops, 'LTI1.3_MIN_POLL_INTERVAL', 60)

###################
# Jplag languages #
###################
lang_parser = ConfigParser()
lang_parser.optionxform = str  # type: ignore
if lang_parser.read(config_file) and 'Jplag Languages' in lang_parser:
    CONFIG['JPLAG_SUPPORTED_LANGUAGES'] = dict(lang_parser['Jplag Languages'])
else:
    CONFIG['JPLAG_SUPPORTED_LANGUAGES'] = {
        "Python 3": "python3",
        "C/C++": "c/c++",
        "Java 1": "java11",
        "Java 2": "java12",
        "Java 5": "java15dm",
        "Java 7": "java17",
        "Java 8": "java15",
        "C# 1.2": "c#-1.2",
        "Chars": "char",
        "Text": "text",
        "Scheme": "scheme",
        "Scala": "scala",
        "JSON": "json",
        "PHP": "php",
        "JavaScript": "javascript",
        "Jupyter": "jupyter",
    }

##########
# CELERY #
##########
celery_parser = ConfigParser()
celery_parser.optionxform = str  # type: ignore
if celery_parser.read(config_file) and 'Celery' in celery_parser:
    CONFIG['CELERY_CONFIG'] = dict(celery_parser['Celery'])
else:
    CONFIG['CELERY_CONFIG'] = {}

set_bool(CONFIG, auto_test_ops, 'IS_AUTO_TEST_RUNNER', False)

# These are all variables defined for the runner
set_int(CONFIG, auto_test_ops, 'AUTO_TEST_POLL_TIME', 30)
set_int(CONFIG, auto_test_ops, 'AUTO_TEST_OUTPUT_LIMIT', 32768)
set_int(CONFIG, auto_test_ops, 'AUTO_TEST_MAX_OUTPUT_TAIL', 2 ** 13)
set_str(CONFIG, auto_test_ops, 'AUTO_TEST_MEMORY_LIMIT', '512M')
set_str(CONFIG, auto_test_ops, 'AUTO_TEST_BDEVTYPE', 'best')
set_str(CONFIG, auto_test_ops, 'AUTO_TEST_TEMPLATE_CONTAINER', None)
set_str(CONFIG, auto_test_ops, 'AUTO_TEST_STARTUP_COMMAND', None)
set_float(CONFIG, auto_test_ops, 'AUTO_TEST_CF_SLEEP_TIME', 5.0)
set_str(CONFIG, auto_test_ops, 'AUTO_TEST_RUNNER_INSTANCE_PASS', '')
set_str(CONFIG, auto_test_ops, 'AUTO_TEST_RUNNER_CONTAINER_URL', None)
set_int(CONFIG, auto_test_ops, 'AUTO_TEST_CF_EXTRA_AMOUNT', 20)

set_str(CONFIG, auto_test_ops, 'AUTO_TEST_BROKER_URL', '')
set_str(CONFIG, auto_test_ops, 'AUTO_TEST_BROKER_PASSWORD', None)
set_str(CONFIG, auto_test_ops, 'AUTO_TEST_PASSWORD', None)
set_bool(CONFIG, auto_test_ops, 'AUTO_TEST_DISABLE_ORIGIN_CHECK', False)

if CONFIG['IS_AUTO_TEST_RUNNER']:
    assert CONFIG['SQLALCHEMY_DATABASE_URI'] == 'postgresql:///codegrade_dev'
    assert CONFIG['CELERY_CONFIG'] == {}
    assert CONFIG['LTI_CONSUMER_KEY_SECRETS'] == {}
    assert CONFIG['LTI_SECRET_KEY'] == ''
    assert CONFIG['SECRET_KEY'] == ''
    assert CONFIG['HEALTH_KEY'] == ''
    assert CONFIG['EXTERNAL_URL'] == ''
    assert CONFIG['AUTO_TEST_BROKER_PASSWORD'] is None
