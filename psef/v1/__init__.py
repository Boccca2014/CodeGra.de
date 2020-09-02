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
        code, login, courses, linters, snippets, assignments, permissions,
        submissions, files, about, roles, lti, users, plagiarism, groups,
        group_sets, auto_tests, webhooks, proxies, analytics, comments,
        notifications, user_settings, task_results, sso_providers, login_links
    )
    app.register_blueprint(api, url_prefix='/api/v1')
