"""The module implementing the internal API of the codegrade.

.. warning::

    This API is not stable, and is only for internal use. Don't program tools
    against it!

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from flask import Blueprint

from ..helpers import add_warning
from ..exceptions import APIWarnings

api = Blueprint('internal_api', __name__)  # pylint: disable=invalid-name


@api.before_request
def add_warning_header() -> None:
    """Add warning describing that this is an internal api.
    """
    add_warning(
        'This API is only for internal use!',
        APIWarnings.INTERNAL_API,
        no_log=True,
    )


def init_app(app: t.Any) -> None:
    """Initialize app by registering this blueprint.

    :param app: The flask app to register.
    :returns: Nothing
    """
    # These imports are done for the side effect of registering routes, so they
    # are NOT unused.
    from . import \
        auto_tests  # pylint: disable=unused-import, import-outside-toplevel
    app.register_blueprint(api, url_prefix='/api/v-internal')
