"""This file contains all routes for proxies.

SPDX-License-Identifier: AGPL-3.0-only
"""
import hmac
import uuid
import typing as t
import mimetypes

import flask
import werkzeug
import structlog

from . import api
from .. import app, files, models, helpers, site_settings
from ..exceptions import APICodes, APIException

logger = structlog.get_logger()

_INDEX_FILES = ['index.html', 'index.htm', 'index.HTML', 'index.HTM']


def _make_also_error(
    wanted_state: models.ProxyState,
    *,
    ignore_expire: bool = False,
) -> t.Callable[[models.Proxy], bool]:
    def also_error(proxy: models.Proxy) -> bool:
        res = proxy.deleted or proxy.state != wanted_state
        if not ignore_expire:
            res = res or proxy.expired
        return res

    return also_error


def _show_session_error() -> werkzeug.wrappers.Response:
    return flask.Response(
        flask.render_template(
            'error_page.j2',
            error_title='Could not load session',
            error_message=(
                """
        There was a problem settings cookies, it seems like we are not allowed
        to do so. Cookies are required for rendering HTML safely, as we need
        them to remember which submission you are viewing. They will not be
        used for analytical purposes.

        <br>
        In some browsers, Safari for example, you need to allow third party
        cookies.
        """
            ),
        ),
        status=400
    )


def _get_url(proxy: models.Proxy, path: str) -> str:
    base_domain = app.config['PROXY_BASE_DOMAIN']
    if base_domain:  # pragma: no cover
        protocol = 'http:' if app.debug else 'https:'
        base_url = f'{protocol}//{proxy.id}.{base_domain}'

    else:
        assert app.debug, 'PROXY_BASE_DOMAIN should be set in production'
        base_url = f'/api/v1/proxies/{proxy.id}'
    return f'{base_url}/{path}'


def _proxy_pass_correct(proxy: models.Proxy) -> bool:
    return hmac.compare_digest(
        proxy.password, flask.session.get('proxy_pass', '')
    )


@api.route('/proxies/<uuid:proxy_id>/<path:path_str>', methods=['POST'])
@site_settings.Opt.RENDER_HTML_ENABLED.required
def start_proxy(
    proxy_id: uuid.UUID, path_str: str
) -> werkzeug.wrappers.Response:
    """Start using the given proxy.

    .. :quickref: Proxy; Start using a proxy.

    :param proxy_id: The proxy you want to start using.
    :param path_str: The initial file that should be served.
    :returns: A redirection to a url which can be used to get the requested
        file. This is done after setting some session variables that will be
        used for identification and authorization.
    """
    proxy = helpers.filter_single_or_404(
        models.Proxy,
        models.Proxy.id == proxy_id,
        with_for_update=True,
        also_error=_make_also_error(models.ProxyState.before_post),
    )
    proxy.state = models.ProxyState.in_use
    flask.session['proxy_pass'] = proxy.password
    flask.session['proxy_id'] = str(proxy.id)

    models.db.session.commit()
    res = flask.redirect(_get_url(proxy, path_str), code=303)
    res.headers['Referrer-Policy'] = 'no-referrer'
    return res


@api.route('/proxies/<path:path_str>', methods=['GET'])
@api.route('/proxies/', methods=['GET'])
@api.route('/proxies/<uuid:proxy_id>/', methods=['GET'])
@api.route('/proxies/<uuid:proxy_id>/<path:path_str>', methods=['GET'])
@site_settings.Opt.RENDER_HTML_ENABLED.required
def get_proxy_file(
    path_str: str = '', proxy_id: uuid.UUID = None
) -> werkzeug.wrappers.Response:
    """Get a file for the given proxy.

    .. :quickref: Proxy; Get a file from a proxy.

    :param proxy_id: The proxy in which you want to get a file.
    :param path: The path of the file you want to get.
    :returns: The found file, or a 404 error.
    """
    path, _ = files.split_path(path_str or '/')
    if proxy_id is None:
        if 'proxy_id' not in flask.session:
            return _show_session_error()
        proxy_id = flask.session['proxy_id']

    proxy = helpers.get_or_404(
        models.Proxy,
        proxy_id,
        also_error=_make_also_error(
            models.ProxyState.in_use, ignore_expire=True
        ),
    )

    if not _proxy_pass_correct(proxy):
        return _show_session_error()

    if proxy.expired:
        raise APIException(
            'This proxy has expired, please reload the page.',
            f'The proxy "{proxy.id}" has expired.',
            APICodes.OBJECT_EXPIRED,
            400,
        )

    found_file = proxy.get_file(path, dir_ok=True)

    if found_file is not None and found_file.is_directory:
        for f in _INDEX_FILES:
            found_file = proxy.get_file([*path, f], dir_ok=False)
            if found_file:
                break

    if found_file is None:
        raise APIException(
            'The given file could not be found.',
            f'The path "{path_str}" was not found in this proxy.',
            APICodes.OBJECT_NOT_FOUND, 404
        )
    ctype, _ = mimetypes.guess_type(path_str)
    res = flask.Response(found_file.open(), mimetype=ctype)
    res.headers['Content-Security-Policy'] = proxy.csp_header
    res.headers['Referrer-Policy'] = 'no-referrer'
    return res
