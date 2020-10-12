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
    AUTOMATIC_LTI_ROLE: bool
    AUTO_TEST: bool
    BLACKBOARD_ZIP_UPLOAD: bool
    COURSE_REGISTER: bool
    EMAIL_STUDENTS: bool
    GROUPS: bool
    INCREMENTAL_RUBRIC_SUBMISSION: bool
    LINTERS: bool
    LTI: bool
    PEER_FEEDBACK: bool
    REGISTER: bool
    RENDER_HTML: bool
    RUBRICS: bool


class BaseReleaseInfo(TypedDict):
    commit: str


class ReleaseInfo(BaseReleaseInfo, total=False):
    version: str
    date: cg_dt_utils.DatetimeWithTimezone
    message: str
    ui_preference: models.UIPreferenceName


class BaseAboutAsJSON(TypedDict):
    version: t.Optional[str]
    commit: str
    features: LegacyFeaturesAsJSON
    settings: site_settings.Opt.FrontendOptsAsJSON
    release: ReleaseInfo


class HealthAsJSON(TypedDict):
    application: bool
    database: bool
    uploads: bool
    broker: bool
    mirror_uploads: bool
    temp_dir: bool


class AboutAsJSON(BaseAboutAsJSON, total=False):
    health: HealthAsJSON


@api.route('/about', methods=['GET'])
def about() -> JSONResponse[AboutAsJSON]:
    """Get the version and features of the currently running instance.

    .. :quickref: About; Get the version and features.

    :>json string version: The version of the running instance.
    :>json object features: A mapping from string to a boolean for every
        feature indicating if the current instance has it enabled.

    :returns: The mapping as described above.
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
