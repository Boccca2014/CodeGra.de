"""
This module defines all API routes with the main directory "about". Thus
the APIs in this module are mostly used get information about the instance
running psef.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

import structlog
from flask import request
from requests import RequestException
from typing_extensions import TypedDict

import cg_dt_utils
import cg_request_args as rqa
import cg_typing_extensions
from cg_json import JSONResponse

from . import api
from .. import models, helpers, current_app, permissions, site_settings
from ..permissions import CoursePermission

logger = structlog.get_logger()


class LegacyFeaturesAsJSON(TypedDict):
    """The legacy features of CodeGrade.

    Please don't use this object, but instead check for enabled settings.
    """
    #: See settings.
    AUTOMATIC_LTI_ROLE: bool
    #: See settings.
    AUTO_TEST: bool
    #: See settings.
    BLACKBOARD_ZIP_UPLOAD: bool
    #: See settings.
    COURSE_REGISTER: bool
    #: See settings.
    EMAIL_STUDENTS: bool
    #: See settings.
    GROUPS: bool
    #: See settings.
    INCREMENTAL_RUBRIC_SUBMISSION: bool
    #: See settings.
    LINTERS: bool
    #: See settings.
    LTI: bool
    #: See settings.
    PEER_FEEDBACK: bool
    #: See settings.
    REGISTER: bool
    #: See settings.
    RENDER_HTML: bool
    #: See settings.
    RUBRICS: bool


class BaseReleaseInfo(TypedDict):
    """The part of the release info that will always be present.
    """
    #: The commit which is running on this server.
    commit: str


class ReleaseInfo(BaseReleaseInfo, total=False):
    """Information about the release running on the server.
    """
    #: What version is running, this key might not be present.
    version: str
    #: What date was the version released.
    date: cg_dt_utils.DatetimeWithTimezone
    #: A small message about the new features of this release.
    message: str
    #: What ``ui_preference`` controls if we should show the release message.
    ui_preference: models.UIPreferenceName


ReleaseInfo.__cg_extends__ = BaseReleaseInfo  # type: ignore[attr-defined]


class BaseAboutAsJSON(TypedDict):
    """The base information about this instance.
    """
    #: What version is running on this server. Deprecated, please use
    #: ``release.version`` instead.
    version: t.Optional[str]
    #: The commit this server is running. Deprecated, please use
    #: ``release.commit`` instead.
    commit: str
    #: The features enabled on this instance. Deprecated, please use
    #: ``settings``.
    features: LegacyFeaturesAsJSON
    #: The frontend settings and their values for this instance.
    settings: site_settings.Opt.FrontendOptsAsJSON
    #: Information about the release running on this server.
    release: ReleaseInfo


class HealthAsJSON(TypedDict):
    """Information about the health of this instance.
    """
    #: Always true.
    application: bool
    #: Is the database ok?
    database: bool
    #: Is the upload storage system ok?
    uploads: bool
    #: Can the broker be reached?
    broker: bool
    #: Is the mirror upload storage system ok?
    mirror_uploads: bool
    #: Is the temporary directory on this server ok?
    temp_dir: bool


class AboutAsJSON(BaseAboutAsJSON, total=False):
    """Information about this CodeGrade instance.
    """
    #: Health information, will only be present when the correct (secret)
    #: health key is provided.
    health: HealthAsJSON


AboutAsJSON.__cg_extends__ = BaseAboutAsJSON  # type: ignore[attr-defined]


@api.route('/about', methods=['GET'])
@rqa.swaggerize('get')
def about() -> JSONResponse[AboutAsJSON]:
    """Get information about this CodeGrade instance.

    .. :quickref: About; Get the version and features.
    """
    _no_val = object()
    status_code = 200

    settings = site_settings.Opt.get_frontend_opts()
    release_info = current_app.config['RELEASE_INFO']
    res: AboutAsJSON = {
        'version': release_info.get('version'),
        'commit': release_info['commit'],
        # We include the old features here to be backwards compatible.
        'features':
            {
                'AUTOMATIC_LTI_ROLE': settings['AUTOMATIC_LTI_ROLE_ENABLED'],
                'AUTO_TEST': settings['AUTO_TEST_ENABLED'],
                'BLACKBOARD_ZIP_UPLOAD':
                    settings['BLACKBOARD_ZIP_UPLOAD_ENABLED'],
                'COURSE_REGISTER': settings['COURSE_REGISTER_ENABLED'],
                'EMAIL_STUDENTS': settings['EMAIL_STUDENTS_ENABLED'],
                'GROUPS': settings['GROUPS_ENABLED'],
                'INCREMENTAL_RUBRIC_SUBMISSION':
                    settings['INCREMENTAL_RUBRIC_SUBMISSION_ENABLED'],
                'LINTERS': settings['LINTERS_ENABLED'],
                'LTI': settings['LTI_ENABLED'],
                'PEER_FEEDBACK': settings['PEER_FEEDBACK_ENABLED'],
                'REGISTER': settings['REGISTER_ENABLED'],
                'RENDER_HTML': settings['RENDER_HTML_ENABLED'],
                'RUBRICS': settings['RUBRICS_ENABLED'],
            },
        'settings': settings,
        'release': release_info,
    }

    if request.args.get('health', _no_val) == current_app.config['HEALTH_KEY']:
        try:
            database = len(
                models.Permission.get_all_permissions(
                    permissions.CoursePermission
                )
            ) == len(CoursePermission)
        except:  # pylint: disable=bare-except
            logger.error('Database not working', exc_info=True)
            database = False

        min_free = current_app.config['MIN_FREE_DISK_SPACE']
        uploads = current_app.file_storage.check_health(
            min_free_space=min_free
        )
        mirror_uploads = current_app.file_storage.check_health(
            min_free_space=min_free
        )

        with helpers.BrokerSession() as ses:
            try:
                # Set a short timeout as the broker really shouldn't take
                # longer than 2 seconds to answer.
                ses.get('/api/v1/ping', timeout=2).raise_for_status()
            except RequestException:
                logger.error('Broker unavailable', exc_info=True)
                broker_ok = False
            else:
                broker_ok = True

        health_value: HealthAsJSON = {
            'application': True,
            'database': database,
            'uploads': uploads,
            'broker': broker_ok,
            'mirror_uploads': mirror_uploads,
            'temp_dir': True,
        }

        res['health'] = health_value
        if not all(health_value.values()):
            status_code = 500

    return JSONResponse.make(res, status_code=status_code)
