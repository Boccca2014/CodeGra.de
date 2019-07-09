"""This file contains utility functions for the broker.

SPDX-License-Identifier: AGPL-3.0-only
"""
import secrets

_PASS_LEN = 64


def make_password(nbytes: int = _PASS_LEN) -> str:
    """Generate a secure password.

    :param nbytes: Amount of bytes the password should be long, has to be > 32.
    :returns: A generated secure password.
    """
    assert nbytes > 32, 'Not secure enough'
    return secrets.token_hex(_PASS_LEN)
