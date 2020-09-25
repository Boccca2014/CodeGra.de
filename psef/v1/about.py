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

from cg_json import JSONResponse

from . import api
from .. import models, helpers, current_app, permissions
from ..permissions import CoursePermission

logger = structlog.get_logger()


@api.route('/about', methods=['GET'])
def about(
) -> JSONResponse[t.Mapping[str, t.Union[str, object, t.Mapping[str, bool]]]]:
    """Get the version and features of the currently running instance.

    .. :quickref: About; Get the version and features.

    :>json string version: The version of the running instance.
    :>json object features: A mapping from string to a boolean for every
        feature indicating if the current instance has it enabled.

    :returns: The mapping as described above.
    """
    _no_val = object()
    status_code = 200

    features = {
        key.name: bool(value)
        for key, value in current_app.config['FEATURES'].items()
    }

    res = {
        'version': current_app.config['VERSION'],
        'commit': current_app.config['CUR_COMMIT'],
        'features': features,
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

        health_value = {
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
