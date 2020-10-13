"""This module defines the tables needed for the site settings.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

import cg_json
import cg_maybe
import cg_helpers
from cg_sqlalchemy_helpers import JSONB
from cg_cache.intra_request import cache_within_request
from cg_sqlalchemy_helpers.types import ColumnProxy
from cg_sqlalchemy_helpers.mixins import IdMixin, TimestampMixin

from . import Base, db

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from ..site_settings import Option

_T = t.TypeVar('_T')


class SiteSetting(Base, TimestampMixin):
    _name = db.Column('name', db.Unicode, nullable=False, primary_key=True)
    _value: ColumnProxy[t.Any] = db.Column('value', JSONB, nullable=True)

    @property
    def name(self) -> str:
        """The name of the option this setting row is for.
        """
        return self._name

    def get_value(self) -> cg_maybe.Maybe[t.Any]:
        """Get the value of this row.

        You probably want to use :meth:`.SiteSetting.get_option` instead of
        this method.
        """
        return cg_maybe.from_nullable(self._value)

    @classmethod
    def get_options(cls, opts: t.Sequence['Option[_T]']
                    ) -> t.Mapping['Option[_T]', _T]:
        """Get the values for the given options.

        This is basically the same as calling :meth:`.SiteSetting.get_option`
        in a loop, but faster.

        :param opts: The options to get the values for.
        """
        lookup = {
            row.name: cg_maybe.Just(row)
            for row in
            cls.query.filter(cls._name.in_([opt.name for opt in opts]))
        }

        return {
            opt: lookup.get(
                opt.name,
                cg_maybe.Nothing,
            ).chain(cls.get_value).or_default(
                opt.default,
            )
            for opt in opts
        }

    @classmethod
    @cache_within_request
    def get_option(cls, opt: 'Option[_T]') -> _T:
        """Get the value for the given option.

        :param opt: The option to get the value for.

        :returns: The value this option is set to, or its default value if it
                  is unset.
        """
        res = cg_maybe.from_nullable(
            cls.query.get(opt.name),
        ).chain(
            cls.get_value,
        ).map(
            opt.parser.try_parse,
        ).or_default(
            opt.default,
        )
        return res

    def _update(self, new_value: object) -> '_SiteSettingHistory':
        old_value = self._value
        self._value = new_value
        return _SiteSettingHistory(self, old_value=old_value)

    @classmethod
    def _create(cls, name: str, value: object) -> '_SiteSettingHistory':
        self = cls(_name=name, _value=value)
        return _SiteSettingHistory(self, old_value=None)

    @classmethod
    def set_option(
        cls, opt: 'Option[_T]', value: t.Optional[_T]
    ) -> '_SiteSettingHistory':
        """Set a new value for the given option.

        :param opt: The option to set.
        :param value: The value the option should have.

        :returns: A history object. To persist the new value you should add and
                  commit this object to the database.
        """
        cls.get_option.clear_cache()  # type: ignore[attr-defined]

        new_value = cg_helpers.on_not_none(
            value, cg_json.JSONResponse.dump_to_object
        )
        self = cls.query.get(opt.name)
        if self is None:
            return cls._create(name=opt.name, value=new_value)
        else:
            return self._update(new_value)  # pylint: disable=protected-access


class _SiteSettingHistory(Base, TimestampMixin, IdMixin):
    __tablename__ = 'site_setting_history'

    _setting_name = db.Column(
        'name',
        db.Unicode,
        db.ForeignKey('site_setting.name'),
        nullable=False,
    )
    _old_value = db.Column('old_value', JSONB, nullable=True)
    _new_value = db.Column('new_value', JSONB, nullable=True)

    _setting = db.relationship(
        SiteSetting,
        foreign_keys=_setting_name,
        uselist=False,
        lazy='selectin',
    )

    def __init__(self, setting: SiteSetting, old_value: object) -> None:
        super().__init__(
            _setting=setting,
            _setting_name=setting.name,
            _new_value=setting.get_value().or_default(None),
            _old_value=old_value,
        )
