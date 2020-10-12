import typing as t
import datetime
import dataclasses

from typing_extensions import Literal, Protocol

import cg_json
import cg_maybe
import cg_helpers
import cg_request_args as rqa
from cg_sqlalchemy_helpers import JSONB
from cg_cache.intra_request import cache_within_request
from cg_object_storage.types import FileSize
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
        return self._name

    def get_value(self) -> cg_maybe.Maybe[t.Any]:
        return cg_maybe.from_nullable(self._value)

    @classmethod
    def get_options(cls, opts: t.Sequence['Option[_T]']
                    ) -> t.Mapping['Option[_T]', _T]:
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
        cls.get_option.clear_cache()  # type: ignore[attr-defined]

        new_value = cg_helpers.on_not_none(
            value, cg_json.JSONResponse.dump_to_object
        )
        self = cls.query.get(opt.name)
        if self is None:
            return cls._create(name=opt.name, value=new_value)
        else:
            return self._update(new_value)


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
