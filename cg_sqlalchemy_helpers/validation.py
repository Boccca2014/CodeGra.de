"""This module implements a validation registration system for SQLAlchemy.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

import structlog
from sqlalchemy import event
from typing_extensions import Final

from cg_flask_helpers import callback_after_this_request

from . import types
from .types import DbColumn

logger = structlog.get_logger()


def _hashable(item: object) -> bool:
    try:
        hash(item)
    except TypeError:
        return False
    else:
        return True


_T_BASE = t.TypeVar('_T_BASE', bound=types.Base)  # pylint: disable=invalid-name

_CG_VALIDATOR_SET: Final = '_CG_VALIDATOR_SET'
_CG_VALIDATOR: Final = '_CG_VALIDATOR'


class Validator:
    """This class can do validation for database objects.

    It allows you to register validators for attributes, and these validator
    functions will be called before committing if the attributes were changed.
    """

    def __init__(self, session: types.MySession) -> None:
        self.__session = session
        self.__to_setup: t.List[t.Tuple[t.Callable[[types.Base], None],
                                        t.Callable[[],
                                                   t.Sequence[DbColumn,
                                                              ],
                                                   ],
                                        ],
                                ] = []
        self.__finalized = False
        self._update_session(session)

    def _update_session(self, session: types.MySession) -> None:
        self.__session = session

        @event.listens_for(session, 'before_commit')
        def _before_commit(_: object) -> None:
            if not self.__finalized:
                logger.error(
                    'Got commit before finalize was called',
                    report_to_sentry=True
                )
            for validator, target in session.info.get(_CG_VALIDATOR, []):
                validator(target)

    def _clear_info_data(self) -> None:
        self.__session.info.pop(_CG_VALIDATOR, None)
        self.__session.info.pop(_CG_VALIDATOR_SET, None)

    def __add_columns(
        self, fun: t.Callable[[types.Base], None],
        columns: t.Sequence[DbColumn]
    ) -> None:
        def __was_updated(
            target: types.Base,
            _value: object,
            _oldvalue: object,
            _initiator: object,
        ) -> None:
            item = (fun, target)
            is_hash = _hashable(item)
            info = self.__session.info

            validation_set = info.get(_CG_VALIDATOR_SET, None)
            if validation_set is None:
                validation_set = info[_CG_VALIDATOR_SET] = set()
                callback_after_this_request(self._clear_info_data)
            if is_hash and item in validation_set:
                return

            info.setdefault(_CG_VALIDATOR, []).append(item)
            if is_hash:
                validation_set.add(item)

        for col in columns:
            event.listen(col, 'set', __was_updated)

    def finalize(self) -> None:
        """Finalize the validator, this actually registers the validators with
        SQLAlchemy.
        """
        if self.__finalized:  # pragma: no cover
            logger.error('Finalized was called twice', report_to_sentry=True)

        for fun, get_columns in self.__to_setup:
            self.__add_columns(fun, get_columns())

        self.__to_setup.clear()
        self.__finalized = True

    def validates(self, get_columns: t.Callable[[], t.Sequence[DbColumn]]
                  ) -> t.Callable[[t.Callable[[_T_BASE], None]], t.
                                  Callable[[_T_BASE], None]]:
        """Register a validator for some columns.

        In the case that multiple columns are mutated it may happen that your
        validation function is called multiple times.

        :param get_columns: A function that should produce a sequence of
            columns, if any of these columns are changed the validator function
            will be called.

        :returns: A function that can be used to actually do the registration.
        """

        def __inner(fun: t.Callable[[_T_BASE], None]
                    ) -> t.Callable[[_T_BASE], None]:
            if self.__finalized:  #: pragma: no cover
                logger.error(
                    'Added validator after finalization',
                    report_to_sentry=True
                )

            # Because of contravariance we are not allowed to add the
            # ``_T_BASE`` callable to the ``__to_setup`` list. However this is
            # perfectly OK for our case. To make sure we do not make other
            # mistakes when appending we first store the function in a variable
            # with the correct type.
            register_fun: t.Callable[[types.Base], None
                                     ] = fun  # type: ignore[assignment]
            self.__to_setup.append((register_fun, get_columns))

            return fun

        return __inner
