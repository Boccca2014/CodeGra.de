"""The module implementing version one of the codegra.de API.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from flask import Blueprint

api = Blueprint('api', __name__)  # pylint: disable=invalid-name


def init_app(app: t.Any) -> None:
    """Initialize app by registering this blueprint.

    :param app: The flask app to register.
    :returns: Nothing
    """
    # These imports are done for the side effect of registering routes, so they
    # are NOT unused.
    from . import (  # pylint: disable=unused-import, import-outside-toplevel
        lti, code, about, files, login, roles, users, groups, courses, linters,
        proxies, comments, snippets, webhooks, analytics, auto_tests,
        group_sets, plagiarism, assignments, login_links, permissions,
        submissions, task_results, notifications, sso_providers, user_settings
    )
    app.register_blueprint(api, url_prefix='/api/v1')
