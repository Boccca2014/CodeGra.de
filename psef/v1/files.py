"""
This module defines all API routes with the main directory "files". These APIs
serve to upload and download temporary files which are not stored explicitly in
the database.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
from datetime import timedelta

import werkzeug
from flask import request, safe_join, send_file
from werkzeug.exceptions import NotFound

from cg_dt_utils import DatetimeWithTimezone

from . import api
from .. import app, auth, files, tasks
from ..auth import APICodes, APIException
from ..helpers import (
    JSONResponse, jsonify, get_request_start_time, callback_after_this_request,
    raise_file_too_big_exception
)

_MAX_AGE = timedelta(minutes=2)


@api.route("/files/", methods=['POST'])
@auth.login_required
def post_file() -> JSONResponse[str]:
    """Temporarily store some data on the server.

    .. :quickref: File; Safe a file temporarily on the server.

    .. note::
        The posted data will be removed after 60 seconds.

    :returns: A response with the JSON serialized name of the file as content
        and return code 201.

    :raises APIException: If the request is bigger than the maximum upload
                          size. (REQUEST_TOO_LARGE)
    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    max_size = app.max_single_file_size
    with app.mirror_file_storage.putter() as putter:
        result = putter.from_stream(request.stream, max_size=max_size)

    if result.is_nothing:
        raise_file_too_big_exception(max_size, True)

    tasks.delete_mirror_file_at_time(
        name=result.value.name,
        deletion_time=(get_request_start_time() + _MAX_AGE).isoformat(),
    )

    return jsonify(result.value.name, status_code=201)


@api.route('/files/<file_name>', methods=['GET'])
@api.route('/files/<file_name>/<path:name>')
def get_file(
    file_name: str, name: str = 'export'
) -> werkzeug.wrappers.Response:
    """Serve some specific file in the uploads folder.

    .. :quickref: File; Get an uploaded file directory.

    .. note::
        Only files uploaded using :http:post:`/api/v1/files/` may be retrieved.

    :param str file_name: The filename of the file to get.
    :returns: The requested file.

    :raises PermissionException: If there is no logged in user. (NOT_LOGGED_IN)
    """
    name = request.args.get('name', name)

    wanted_file = app.mirror_file_storage.get(file_name)

    too_old = wanted_file.map(
        lambda f: (get_request_start_time() - f.creation_time) > _MAX_AGE
    ).or_default(False)

    if wanted_file.is_nothing or too_old:
        raise APIException(
            'The specified file was not found',
            f'The file with name "{file_name}" was not found or is deleted.',
            APICodes.OBJECT_NOT_FOUND,
            404,
        )

    @callback_after_this_request
    def __delete_file() -> None:
        # Make sure we don't delete when receiving HEAD requests
        if request.method == 'GET' and wanted_file.is_just:
            wanted_file.value.delete()

    mimetype = request.args.get('mime', None)
    as_attachment = request.args.get('not_as_attachment', False)
    return send_file(
        wanted_file.value.open(),
        attachment_filename=name,
        as_attachment=as_attachment,
        mimetype=mimetype,
        cache_timeout=-1,
    )
