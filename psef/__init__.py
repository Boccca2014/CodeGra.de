"""
This package implements the backend for codegrade. Because of historic reasons
this backend is named ``psef``.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import typing as t
import dataclasses
from datetime import timedelta

import redis
import jinja2
import structlog
import flask_jwt_extended as flask_jwt
from flask import Flask
from werkzeug.local import LocalProxy
from werkzeug.utils import cached_property

import cg_logger
import cg_object_storage
import cg_cache.inter_request
from cg_json import jsonify

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from pylti1p3.registration import _KeySet

    from config import FlaskConfig

    current_app: 'PsefFlask'
else:
    from flask import current_app


@dataclasses.dataclass(frozen=True)
class _PsefInterProcessCache:
    """All inter process cache stores used in psef.

    There really only should be one instance of this class.
    """
    # Pylint bug: https://github.com/PyCQA/pylint/issues/2822
    # pylint: disable=unsubscriptable-object
    lti_access_tokens: cg_cache.inter_request.Backend[str]
    lti_public_keys: cg_cache.inter_request.Backend['_KeySet']

    saml2_ipds: cg_cache.inter_request.Backend[
        t.Mapping[str, t.Union['psef.models.saml_provider.SamlUiInfo', object]]
    ]


class PsefFlask(Flask):
    """Our subclass of flask.

    This contains the extra property :meth:`.PsefFlask.do_sanity_checks`.
    """
    config: 'FlaskConfig'  # type: ignore

    def __init__(self, name: str, config: dict) -> None:
        super().__init__(name)
        self.config.update(t.cast(t.Any, config))

        dict_to_load = {}
        for key, t_name in [
            ('DIRECT_NOTIFICATION_TEMPLATE_FILE', 'notification.j2'),
            ('DIGEST_NOTIFICATION_TEMPLATE_FILE', 'digest.j2'),
            ('EXAM_LOGIN_TEMPLATE_FILE', 'exam_login.j2'),
        ]:
            template = self.config.get(key)
            if template:  # pragma: no cover
                with open(str(template), 'r') as f:
                    dict_to_load[t_name] = f.read()

        self.jinja_mail_env = jinja2.Environment(
            autoescape=True,
            undefined=jinja2.StrictUndefined,
            loader=jinja2.loaders.ChoiceLoader(
                [
                    jinja2.loaders.DictLoader(dict_to_load),
                    jinja2.loaders.FileSystemLoader(
                        os.path.join(
                            os.path.dirname(__file__),
                            'mail_templates',
                        )
                    ),
                ]
            )
        )

        self.file_storage: cg_object_storage.Storage
        self.file_storage = cg_object_storage.LocalStorage(
            self.config['UPLOAD_DIR'],
        )
        self.mirror_file_storage: cg_object_storage.Storage
        self.mirror_file_storage = cg_object_storage.LocalStorage(
            self.config['MIRROR_UPLOAD_DIR'],
        )

    @property
    def max_single_file_size(self) -> cg_object_storage.FileSize:
        """The maximum allowed size for a single file.
        """
        from . import site_settings  # pylint: disable=import-outside-toplevel
        return site_settings.Opt.MAX_FILE_SIZE.value

    @property
    def max_file_size(self) -> cg_object_storage.FileSize:
        """The maximum allowed size for normal files.

        .. note:: An individual file has a different limit!
        """
        from . import site_settings  # pylint: disable=import-outside-toplevel
        return site_settings.Opt.MAX_NORMAL_UPLOAD_SIZE.value

    @property
    def max_large_file_size(self) -> cg_object_storage.FileSize:
        """The maximum allowed size for large files (such as blackboard zips).

        .. note:: An individual file has a different limit!
        """
        from . import site_settings  # pylint: disable=import-outside-toplevel
        return site_settings.Opt.MAX_LARGE_UPLOAD_SIZE.value

    @property
    def do_sanity_checks(self) -> bool:
        """Should we do sanity checks for this app.

        :returns: ``True`` if ``debug`` or ``testing`` is enabled.
        """
        return getattr(self, 'debug', False) or getattr(self, 'testing', False)

    # Lazy initialization of the app. The `cached_property` from werkzeug
    # caches across requests which is something we want here.
    @cached_property
    def inter_request_cache(self) -> '_PsefInterProcessCache':
        """Get all inter process cache stores.
        """
        redis_conn = redis.from_url(self.config['REDIS_CACHE_URL'])
        return _PsefInterProcessCache(
            lti_access_tokens=cg_cache.inter_request.RedisBackend(
                'lti_access_tokens',
                timedelta(seconds=600),
                redis_conn,
            ),
            lti_public_keys=cg_cache.inter_request.RedisBackend(
                'lti_public_keys', timedelta(hours=1), redis_conn
            ),
            saml2_ipds=cg_cache.inter_request.RedisBackend(
                'saml2_ipds', timedelta(days=1), redis_conn
            )
        )


logger = structlog.get_logger()

app: PsefFlask = current_app  # pylint: disable=invalid-name

_current_tester = None  # pylint: disable=invalid-name
current_tester = LocalProxy(lambda: _current_tester)  # pylint: disable=invalid-name


def enable_testing() -> None:
    """Set this instance to be an AutoTest runner.
    """
    # pylint: disable=global-statement,invalid-name
    global _current_tester
    _current_tester = True


if t.TYPE_CHECKING:  # pragma: no cover
    import psef.models
    current_user: 'psef.models.User' = t.cast('psef.models.User', None)
else:
    current_user = flask_jwt.current_user  # pylint: disable=invalid-name


def create_app(  # pylint: disable=too-many-statements
    config: t.Mapping = None,
    skip_celery: bool = False,
    skip_perm_check: bool = True,
    skip_secret_key_check: bool = False,
    *,
    skip_all: bool = False,
) -> 'PsefFlask':
    """Create a new psef app.

    :param config: The config mapping that can be used to override config.
    :param skip_celery: Set to true to disable sanity checks for celery.
    :returns: A new psef app object.
    """
    # pylint: disable=import-outside-toplevel
    import config as global_config

    if skip_all:  # pragma: no cover
        skip_celery = skip_perm_check = skip_secret_key_check = True

    resulting_app = PsefFlask(
        __name__,
        {
            **global_config.CONFIG,
            **(config or {}),
        },
    )

    resulting_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'  # type: ignore
                         ] = False
    resulting_app.config['SESSION_COOKIE_SECURE'] = True
    resulting_app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    # We don't cache responses from the API so it makes no sense to sort the
    # keys.
    resulting_app.config['JSON_SORT_KEYS'] = False

    if not resulting_app.debug:
        assert not resulting_app.config['AUTO_TEST_DISABLE_ORIGIN_CHECK']

    if (
        not skip_secret_key_check and not (
            resulting_app.config['SECRET_KEY'] and
            resulting_app.config['LTI_SECRET_KEY']
        )
    ):  # pragma: no cover
        raise ValueError('The option to generate keys has been removed')

    from . import limiter
    limiter.init_app(resulting_app)

    cg_logger.init_app(resulting_app)

    from . import permissions
    permissions.init_app(resulting_app, skip_perm_check)

    from . import auth
    auth.init_app(resulting_app)

    from . import tasks
    tasks.init_app(resulting_app)

    from . import models
    models.init_app(resulting_app)

    from . import mail
    mail.init_app(resulting_app)

    from . import errors
    errors.init_app(resulting_app)

    from . import files
    files.init_app(resulting_app)

    from . import lti
    lti.init_app(resulting_app)

    from . import auto_test
    auto_test.init_app(resulting_app)

    from . import helpers
    helpers.init_app(resulting_app)

    from . import linters
    linters.init_app(resulting_app)

    from . import plagiarism
    plagiarism.init_app(resulting_app)

    # Register blueprint(s)
    from . import v1 as api_v1
    api_v1.init_app(resulting_app)

    from . import v_internal as api_v_internal
    api_v_internal.init_app(resulting_app)

    from . import signals
    signals.init_app(resulting_app)

    from . import saml2
    saml2.init_app(resulting_app)

    from . import site_settings
    site_settings.init_app(resulting_app)

    # Make sure celery is working
    if not skip_celery:  # pragma: no cover
        try:
            tasks.add(2, 3)
        except Exception:  # pragma: no cover
            logger.error('Celery is not responding! Please check your config')
            raise

    import cg_timers
    cg_timers.init_app(resulting_app)

    cg_cache.init_app(resulting_app)

    return resulting_app
