"""This module makes it possible to give options for the jsonification of
models.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import dataclasses

import flask

if t.TYPE_CHECKING:  # pragma: no cover
    from .. import models  # pylint: disable=unused-import


@dataclasses.dataclass
class Options:
    """Options used for jsonification.
    """
    add_permissions_to_user: t.Optional['models.User'] = None
    latest_only: bool = False
    add_role_to_course: bool = False


def get_options() -> Options:
    """Get a mutable options object.
    """
    if not hasattr(flask.g, 'jsonify_options'):
        flask.g.jsonify_options = Options()
    return flask.g.jsonify_options
