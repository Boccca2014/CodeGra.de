"""
This module defines all API routes with the main directory "files". These APIs
serve to upload and download temporary files which are not stored explicitly in
the database.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
from datetime import timedelta

import werkzeug
from flask import request, safe_join, send_from_directory
from werkzeug.exceptions import NotFound

from cg_dt_utils import DatetimeWithTimezone

from . import api
from .. import app, auth, files, tasks
from ..auth import APICodes, APIException
from ..helpers import (
    JSONResponse, jsonify, get_request_start_time, callback_after_this_request
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
    if (
        request.content_length and
        request.content_length > app.config['MAX_FILE_SIZE']
    ):
        raise APIException(
            'Uploaded file is too big.',
            'Request is bigger than maximum upload size of {}.'.format(
                app.config['MAX_FILE_SIZE']
            ), APICodes.REQUEST_TOO_LARGE, 400
        )

    path, name = files.random_file_path(True)
    with open(path, 'wb') as f:
        files.limited_copy(request.stream, f, app.max_single_file_size)

    tasks.delete_file_at_time(
        filename=name,
        in_mirror_dir=True,
        deletion_time=(get_request_start_time() + _MAX_AGE).isoformat(),
    )

    return jsonify(name, status_code=201)


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

    directory = app.config['MIRROR_UPLOAD_DIR']
    error = False

    @callback_after_this_request
    def __delete_file() -> None:
        # Make sure we don't delete when receiving HEAD requests
        if request.method == 'GET' and not error:
            filename = safe_join(directory, file_name)
            os.unlink(filename)

    try:
        full_path = files.safe_join(directory, file_name)
        if os.path.isfile(full_path):
            mtime = os.path.getmtime(full_path)
            age = get_request_start_time(
            ) - DatetimeWithTimezone.utcfromtimestamp(mtime)
            if age > _MAX_AGE:
                raise NotFound

        mimetype = request.args.get('mime', None)
        as_attachment = request.args.get('not_as_attachment', False)
        return send_from_directory(
            directory,
            file_name,
            attachment_filename=name,
            as_attachment=as_attachment,
            mimetype=mimetype,
            cache_timeout=-1,
        )
    except NotFound as exc:
        error = True
        raise APIException(
            'The specified file was not found',
            f'The file with name "{file_name}" was not found or is deleted.',
            APICodes.OBJECT_NOT_FOUND,
            404,
        ) from exc
