"""This module implements all kinds of helper functionalities for working with
SQLAlchemy especially in the context of Flask.

SPDX-License-Identifier: AGPL-3.0-only
"""
import re
import time
import uuid
import typing as t

import sqlalchemy
from flask import Flask, g
from sqlalchemy import event
from sqlalchemy.orm import deferred as _deferred
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import force_auto_coercion

from cg_dt_utils import DatetimeWithTimezone

from . import types
from .types import (
    ARRAY, JSONB, TIMESTAMP, CIText, Column, DbEnum, DbType, Integer, Unicode,
    Interval, UUIDType, Comparator, TypeDecorator, func, tuple_, distinct,
    expression, hybrid_property, hybrid_expression
)

UUID_LENGTH = len(str(uuid.uuid4()))  # 36

T = t.TypeVar('T')
deferred: t.Callable[[T], T] = _deferred


def make_db() -> types.MyDb:
    return t.cast(
        types.MyDb,
        SQLAlchemy(session_options={'autocommit': False, 'autoflush': False})
    )


_T = t.TypeVar('_T')


def init_app(db: types.MyDb, app: Flask) -> None:
    """Initialize the given app and the given db.

    :param db: The db to initialize. This function adds some listeners to some
        queries.
    :param app: The app to initialize with.
    :returns: Nothing, everything will be mutated in-place.
    """
    db.init_app(app)
    force_auto_coercion()

    with app.app_context():

        @app.before_request
        def __set_query_durations() -> None:
            g.queries_amount = 0
            g.queries_total_duration = 0
            g.queries_max_duration = None
            g.query_start = None

        @event.listens_for(db.engine, "before_cursor_execute")
        def __before_cursor_execute(*_args: object) -> None:
            if hasattr(g, 'query_start'):
                g.query_start = time.time()

        @event.listens_for(db.engine, "after_cursor_execute")
        def __after_cursor_execute(*_args: object) -> None:
            if hasattr(g, 'queries_amount'):
                g.queries_amount += 1
            if hasattr(g, 'query_start'):
                delta = time.time() - g.query_start
                if hasattr(g, 'queries_total_duration'):
                    g.queries_total_duration += delta
                if (
                    hasattr(g, 'queries_max_duration') and (
                        g.queries_max_duration is None or
                        delta > g.queries_max_duration
                    )
                ):
                    g.queries_max_duration = delta
