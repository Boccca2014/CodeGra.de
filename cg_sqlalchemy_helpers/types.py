"""
This module DOES NOT define any thing. It is only used for type information
about sqlalchemy.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import typing as t
# pylint: skip-file
from uuid import UUID
from typing import Union
from typing import Optional as Opt
from datetime import timedelta

from typing_extensions import Literal, Protocol

import cg_dt_utils

T = t.TypeVar('T')
ZZ = t.TypeVar('ZZ')
T_CONTRA = t.TypeVar('T_CONTRA', contravariant=True)
Z = t.TypeVar('Z')
Y = t.TypeVar('Y')
U = t.TypeVar('U')
E = t.TypeVar('E', bound=enum.Enum)
DbSelf = t.TypeVar('DbSelf', bound='MyDb')
QuerySelf = t.TypeVar('QuerySelf', bound='MyNonOrderableQuery')
_T_BASE = t.TypeVar('_T_BASE', bound='Base')
_Y_BASE = t.TypeVar('_Y_BASE', bound='Base')
T_DB_COLUMN = t.TypeVar('T_DB_COLUMN', bound='DbColumn')
T_NUM = t.TypeVar('T_NUM', bound=t.Union[int, float])

Never = t.NewType('Never', object)


class MySession:  # pragma: no cover
    info: dict

    def bulk_save_objects(self, objs: t.Sequence['Base']) -> None:
        ...

    def execute(self, query: object) -> object:
        ...

    @t.overload
    def query(self, __x: 'ExistsColumn') -> '_MyExistsQuery':
        ...

    @t.overload
    def query(self, __x: 'DbColumn[T]') -> 'MyQueryTuple[T]':
        ...

    @t.overload  # NOQA
    def query(self, __x: 'RawTable') -> 'MyQuery[RawTable]':
        ...

    @t.overload  # NOQA
    def query(self, __x: t.Type[_T_BASE]) -> 'MyQuery[_T_BASE]':
        ...

    @t.overload  # NOQA
    def query(
        self,
        __y: 'DbColumn[T]',
        __x: t.Type[_T_BASE],
    ) -> 'MyQuery[t.Tuple[T, _T_BASE]]':
        ...

    @t.overload  # NOQA
    def query(
        self,
        __y: 'DbColumn[T]',
        __x: 'DbColumn[Z]',
    ) -> 'MyQuery[t.Tuple[T, Z]]':
        ...

    @t.overload  # NOQA
    def query(
        self, __x: t.Type[_T_BASE], __y: 'DbColumn[Z]'
    ) -> 'MyQuery[t.Tuple[_T_BASE, Z]]':
        ...

    @t.overload  # NOQA
    def query(
        self, __x: t.Type[_T_BASE], __y: t.Type[_Y_BASE]
    ) -> 'MyQuery[t.Tuple[_T_BASE, _Y_BASE]]':
        ...

    @t.overload  # NOQA
    def query(
        self,
        __x: 'DbColumn[T]',
        __y: 'DbColumn[Z]',
        __z: 'DbColumn[Y]',
    ) -> 'MyQuery[t.Tuple[T, Z, Y]]':
        ...

    @t.overload  # NOQA
    def query(
        self,
        __x: 'DbColumn[T]',
        __y: 'DbColumn[Z]',
        __z: 'DbColumn[Y]',
        __j: 'DbColumn[U]',
    ) -> 'MyQuery[t.Tuple[T, Z, Y, U]]':
        ...

    def query(self, *args: t.Any) -> 't.Union[MyQuery, _MyExistsQuery]':
        ...

    def add(self, arg: 'Base') -> None:
        ...

    def add_all(self, arg: t.Sequence['Base']) -> None:
        ...

    def flush(self) -> None:
        ...

    def commit(self) -> None:
        ...

    def delete(self, arg: 'Base') -> None:
        ...

    def expunge(self, arg: 'Base') -> None:
        ...

    def expire(self, obj: 'Base') -> None:
        ...

    def expire_all(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def begin_nested(self) -> t.ContextManager:
        ...


class DbType(t.Generic[T_CONTRA]):  # pragma: no cover
    ...


class DbEnum(t.Generic[T_CONTRA], DbType[T_CONTRA]):  # pragma: no cover
    ...


class _ForeignKey:  # pragma: no cover
    ...


class _ImmutableColumnProxy(t.Generic[T, U]):
    @t.overload
    def __get__(self, _: None, owner: t.Type[object]) -> U:
        ...

    @t.overload
    def __get__(self, _: Z, owner: t.Type[Z]) -> T:
        ...

    def __get__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        ...

    __set__ = NotImplemented
    __delete__ = NotImplemented


class ImmutableColumnProxy(
    t.Generic[T], _ImmutableColumnProxy[T, 'DbColumn[T]']
):
    ...


class _MutableColumnProxy(t.Generic[T, Y, Z], _ImmutableColumnProxy[T, Z]):
    def __set__(self, instance: object, value: Y) -> None:
        ...


class MutableColumnProxy(t.Generic[T, Y], ImmutableColumnProxy[T]):
    def __set__(self, instance: object, value: Y) -> None:
        ...


class ColumnProxy(t.Generic[T_CONTRA], MutableColumnProxy[T_CONTRA, T_CONTRA]):
    ...


_CP = ColumnProxy


class RawTable:  # pragma: no cover
    class _Column(t.Generic[T]):
        def __getattr__(self, _: str) -> T:
            pass

    c: _Column['DbColumn[t.Any]']


class _Backref:
    ...


class MyDb:  # pragma: no cover
    session: MySession
    Float: DbType[float]
    Integer: DbType[int]
    Unicode: DbType[str]
    Boolean: DbType[bool]
    String: t.Callable[[DbSelf, int], DbType[str]]
    LargeBinary: DbType[bytes]
    Interval: DbType[timedelta]
    init_app: t.Callable
    engine: t.Any

    def ForeignKey(
        self,
        _name: t.Union[str, 'DbColumn[T]', 'ColumnProxy[T]'],
        *,
        ondelete: t.Union[None, Literal['SET NULL', 'CASCADE']] = None,
    ) -> _ForeignKey:
        ...

    def TIMESTAMP(self, *, timezone: Literal[True]
                  ) -> DbType[cg_dt_utils.DatetimeWithTimezone]:
        ...

    def Table(self, name: str, *args: T) -> RawTable:
        ...

    @t.overload
    def Enum(self, typ: t.Type[E], name: str = None,
             native_enum: bool = True) -> DbEnum[E]:
        ...

    @t.overload
    def Enum(self, *typ: T, name: str, native_enum: bool = True) -> DbEnum[T]:
        ...

    def Enum(self, *args: t.Any, **kwargs: t.Any) -> DbEnum[t.Any]:
        ...

    @t.overload
    def Column(
        self,
        name: str,
        type_: DbType[T],
        _fk: t.Optional[_ForeignKey] = None,
        *,
        unique: bool = False,
        nullable: Literal[True] = True,
        default: t.Union[T, t.Callable[[], T], None] = None,
        index: bool = False,
        server_default: t.Any = ...,
    ) -> 'ColumnProxy[t.Optional[T]]':
        ...

    @t.overload
    def Column(
        self,
        name: str,
        type_: DbType[T],
        *,
        unique: bool = False,
        primary_key: Literal[True],
        default: t.Callable[[], T] = ...,
        index: bool = False,
        nullable: Literal[False] = False,
    ) -> 'ColumnProxy[T]':
        ...

    @t.overload
    def Column(
        self,
        name: str,
        type_: DbType[T_CONTRA],
        _fk: t.Optional[_ForeignKey] = None,
        *,
        unique: bool = False,
        nullable: Literal[False],
        default: t.Union[None, T_CONTRA, t.Callable[[], T_CONTRA]] = None,
        **rest: t.Any
    ) -> 'ColumnProxy[T_CONTRA]':
        ...

    @t.overload  # NOQA
    def Column(
        self,
        type_: DbType[T],
        _fk: t.Optional[_ForeignKey] = None,
        *,
        nullable: Literal[False],
        default: t.Union[T, t.Callable[[], T]] = ...,
        **rest: t.Any
    ) -> 'ColumnProxy[T]':
        ...

    @t.overload  # NOQA
    def Column(
        self,
        type_: DbType[T],
        _fk: t.Optional[_ForeignKey] = None,
        *,
        unique: bool = False,
        nullable: Literal[True] = True,
        default: t.Union[T, t.Callable[[], T], None] = None,
        **rest: t.Any
    ) -> 'ColumnProxy[t.Optional[T]]':
        ...

    def Column(self, *args: t.Any, **kwargs: t.Any) -> t.Any:  # NOQA
        ...

    def PrimaryKeyConstraint(self, *args: t.Any) -> t.Any:
        ...

    def CheckConstraint(
        self, *args: t.Any, name: t.Optional[str] = None
    ) -> t.Any:
        ...

    def UniqueConstraint(
        self, *args: t.Any, name: t.Optional[str] = None
    ) -> t.Any:
        ...

    @t.overload
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *args: t.Any,
        foreign_keys: Union[_CP[Opt[int]], _CP[Opt[str]], _CP[
            Opt[UUID]], 'DbColumn[Opt[int]]', 'DbColumn[Opt[str]]',
                            'DbColumn[Opt[UUID]]'],
        **kwargs: t.Any,
    ) -> 'ColumnProxy[t.Optional[T]]':
        ...

    @t.overload  # NOQA
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *args: t.Any,
        foreign_keys: Union[_CP[int], _CP[UUID], _CP[str]],
        innerjoin: Literal[True] = None,
        **kwargs: t.Any,
    ) -> 'ColumnProxy[T]':
        ...

    @t.overload
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *,
        back_populates: str,
        cascade: str = '',
        uselist: Literal[True] = True,
        passive_deletes: bool = False,
        innerjoin: bool = None,
    ) -> '_MutableColumnProxy[t.List[T], t.List[T], DbColumn[T]]':
        ...

    @t.overload
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *,
        innerjoin: Literal[True],
        uselist: Literal[False],
        back_populates: str,
        cascade: str = '',
        lazy: Literal['select', 'join', 'selectin'] = 'select',
    ) -> 'ColumnProxy[T]':
        ...

    @t.overload
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *,
        uselist: Literal[False],
        back_populates: str,
        cascade: str = '',
        innerjoin: Literal[False] = False,
        lazy: Literal['select', 'join', 'selectin'] = 'select',
        primaryjoin: t.Callable[[], 'DbColumn[bool]'] = None,
    ) -> 'ColumnProxy[Opt[T]]':
        ...

    @t.overload
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *,
        remote_side: t.List[ColumnProxy[t.Any]],
        backref: _Backref,
    ) -> 'ColumnProxy[Opt[T]]':
        ...

    @t.overload
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *,
        backref: _Backref,
        uselist: Literal[True],
        passive_deletes: bool = False,
        lazy: Literal['select', 'join', 'selectin'] = 'select',
    ) -> '_MutableColumnProxy[t.List[T], t.List[T], DbColumn[T]]':
        ...

    @t.overload  # NOQA
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *,
        uselist: Literal[True],
        passive_deletes: bool = False,
        cascade: str = '',
        back_populates: str = None,
        backref: _Backref = None,
        order_by: t.Union[t.Callable[[], 'DbColumn'], t.
                          Callable[[], 'ColumnOrder']] = None,
        lazy: Literal['select', 'joined', 'selectin'] = 'select',
        primaryjoin: t.Callable[[], 'DbColumn[bool]'] = None,
    ) -> '_MutableColumnProxy[t.List[T], t.List[T], DbColumn[T]]':
        ...

    @t.overload  # NOQA
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *,
        uselist: Literal[True],
        passive_deletes: bool = False,
        cascade: str = '',
        back_populates: str = None,
        backref: _Backref = None,
        order_by: t.Union[t.Callable[[], 'DbColumn'], t.
                          Callable[[], 'ColumnOrder']] = None,
        lazy: Literal['dynamic'],
        primaryjoin: t.Callable[[], 'DbColumn[bool]'] = None,
    ) -> '_ImmutableColumnProxy[MyQuery[T], DbColumn[T]]':
        ...

    @t.overload  # NOQA
    def relationship(
        self,
        name: Union[t.Callable[[], t.Type[T]], t.Type[T]],
        *,
        uselist: Literal[True],
        back_populates: str,
        lazy: Literal['raise'],
    ) -> '_ImmutableColumnProxy[t.NoReturn, t.NoReturn]':
        ...

    @t.overload  # NOQA
    def relationship(
        self,
        name: t.Callable[[], t.Type[_T_BASE]],
        *,
        uselist: Literal[True],
        passive_deletes: bool = False,
        secondary: 'RawTable',
        cascade: str = '',
        lazy: Literal['select', 'join', 'selectin'] = 'select',
        order_by: t.Union[t.Callable[[], 'DbColumn'], t.
                          Callable[[], 'ColumnOrder']] = None,
    ) -> '_MutableColumnProxy[t.List[_T_BASE], t.List[_T_BASE], DbColumn[_T_BASE]]':
        ...

    @t.overload  # NOQA
    def relationship(
        self,
        name: str,
        *,
        backref: _Backref = None,
        collection_class: object,
        secondary: 'RawTable' = None,
        cascade: str = '',
    ) -> t.Any:
        ...

    def relationship(self, *args: t.Any, **kwargs: t.Any) -> t.Any:  # NOQA
        ...

    def backref(self, name: str, *args: t.Any, **kwargs: t.Any) -> _Backref:
        ...


class ColumnOrder:
    ...


class DbColumn(t.Generic[T]):  # pragma: no cover
    '''This class is used for type checking only.

    It has no implementation and instantiating an instance raises an error.
    '''

    def compile(
        self, *, dialect: object = None, compile_kwargs: t.Dict[str, object]
    ) -> object:
        ...

    def __init__(self) -> None:
        raise ValueError

    def any(self, cond: 'DbColumn[bool]' = None) -> 'DbColumn[bool]':
        ...

    def __getitem__(
        self: 'DbColumn[t.Optional[t.Mapping[str, object]]]', key: str
    ) -> 'IndexedJSONColumn':
        ...

    def notin_(
        self, val: t.Union[t.Iterable[T], 'DbColumn[T]',
                           'MyNonOrderableQuery[T]', 'RawTable']
    ) -> 'DbColumn[bool]':
        ...

    def in_(
        self, val: t.Union[t.Sequence[T], 'DbColumn[T]',
                           'MyNonOrderableQuery[t.Tuple[T]]', 'RawTable']
    ) -> 'DbColumn[bool]':
        ...

    def isnot(self, val: t.Optional[T]) -> 'DbColumn[bool]':
        ...

    def label(self, name: str) -> 'DbColumn[T]':
        ...

    def is_(self, val: T) -> 'DbColumn[bool]':
        ...

    def __invert__(self: 'DbColumn[bool]') -> 'DbColumn[bool]':
        ...

    def desc(self) -> ColumnOrder:
        ...

    def asc(self) -> ColumnOrder:
        ...

    @t.overload
    def has(self: 'DbColumn[t.List[Y]]', __arg: Y) -> 'DbColumn[bool]':
        ...

    @t.overload
    def has(self, **kwargs: object) -> 'DbColumn[bool]':
        ...

    def has(self, *args: object, **kwargs: object) -> t.Any:
        ...

    def __mul__(
        self: 'DbColumn[float]', other: 't.Union[DbColumn[float], float]'
    ) -> 'DbColumn[float]':
        ...

    def __eq__(  # type: ignore
        self, other: Union[t.Optional[T], 'DbColumn[T]', 'DbColumn[t.Optional[T]]',
                           'MyNonOrderableQuery[T]']
    ) -> 'DbColumn[bool]':
        ...

    def __ne__(  # type: ignore
        self, other: Union[t.Optional[T], 'DbColumn[T]', 'DbColumn[t.Optional[T]]',
                           'MyNonOrderableQuery[T]']
    ) -> 'DbColumn[bool]':
        ...

    def __ge__(
        self, other: t.Union[T, 'DbColumn[T]', 'DbColumn[t.Optional[T]]']
    ) -> 'DbColumn[bool]':
        ...

    def __gt__(
        self, other: t.Union[T, 'DbColumn[T]', 'DbColumn[t.Optional[T]]']
    ) -> 'DbColumn[bool]':
        ...

    def __lt__(
        self, other: t.Union[T, 'DbColumn[T]', 'DbColumn[t.Optional[T]]']
    ) -> 'DbColumn[bool]':
        ...

    def __or__(self, other: 'DbColumn[bool]') -> 'DbColumn[bool]':
        ...

    def __truediv__(
        self: 'DbColumn[T_NUM]', other: 'DbColumn[T_NUM]'
    ) -> 'DbColumn[T_NUM]':
        ...

    def cast(self, other: DbType[Y]) -> 'DbColumn[Y]':
        ...


class FilterableDbColumn(t.Generic[T], DbColumn[T]):  # pragma: no cover
    def filter(
        self: 'FilterableDbColumn[T]', *criterion: 'FilterColumn'
    ) -> 'FilterableDbColumn[T]':
        ...


class IndexedJSONColumn(DbColumn[Never]):
    def __getitem__(self, key: str) -> 'IndexedJSONColumn':
        ...

    def as_string(self) -> 'DbColumn[t.Optional[str]]':
        ...

    def as_integer(self) -> 'DbColumn[t.Optional[int]]':
        ...


class ExistsColumn:
    def __invert__(self) -> 'ExistsColumn':
        ...


FilterColumn = t.Union[DbColumn[bool], DbColumn[Literal[True]], DbColumn[
    Literal[False]], ExistsColumn]


class Mapper(t.Generic[_T_BASE]):
    @property
    def polymorphic_map(self) -> t.Dict[object, 'Mapper[_T_BASE]']:
        ...

    @property
    def class_(self) -> _T_BASE:
        ...


class _QueryProxy:
    def __get__(self, _: object, type: t.Type[_T_BASE]) -> 'MyQuery[_T_BASE]':
        ...


class Base:  # pragma: no cover
    query: t.ClassVar[_QueryProxy]

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        pass


class MyNonOrderableQuery(t.Generic[T]):  # pragma: no cover
    delete: t.Callable[[QuerySelf], None]
    subquery: t.Callable[[QuerySelf, str], RawTable]
    limit: t.Callable[[QuerySelf, int], QuerySelf]
    first: t.Callable[[QuerySelf], t.Optional[T]]
    exists: t.Callable[[QuerySelf], ExistsColumn]
    count: t.Callable[[QuerySelf], int]
    one: t.Callable[[QuerySelf], T]
    yield_per: t.Callable[[QuerySelf, int], QuerySelf]

    def __iter__(self) -> t.Iterator[T]:
        ...

    def distinct(self: QuerySelf, on: DbColumn = None) -> 'QuerySelf':
        pass

    def all(self) -> t.List[T]:
        ...

    def with_for_update(
        self: QuerySelf,
        *,
        read: bool = False,
        of: t.Optional[t.Type[Base]] = None,
    ) -> 'QuerySelf':
        ...

    def one_or_none(self) -> t.Optional[T]:
        ...

    def select_from(self: QuerySelf, other: t.Type[Base]) -> 'QuerySelf':
        ...

    def slice(self: QuerySelf, start: int, end: int) -> 'QuerySelf':
        ...

    def get(self, arg: t.Any) -> t.Optional[T]:
        ...

    def update(
        self,
        vals: t.Mapping[t.Union[str, DbColumn], t.Any],
        synchronize_session: t.Union[str, bool] = '__NOT_REAL__'
    ) -> None:
        ...

    def from_self(self, *args: t.Type[Z]) -> 'MyNonOrderableQuery[Z]':
        ...

    def join(
        self: QuerySelf,
        to_join: t.Union[t.Type['Base'], RawTable, 'DbColumn[_T_BASE]'],
        cond: DbColumn[bool] = None,
        *,
        isouter: bool = False,
    ) -> QuerySelf:
        ...

    def filter(self: QuerySelf, *args: FilterColumn) -> QuerySelf:
        ...

    def filter_by(
        self: QuerySelf, *args: t.Any, **kwargs: t.Any
    ) -> 'QuerySelf':
        ...

    def options(self: QuerySelf, *args: t.Any) -> 'QuerySelf':
        ...

    def having(self: QuerySelf, *args: t.Any) -> 'QuerySelf':
        ...

    def group_by(self: QuerySelf, arg: t.Any) -> 'QuerySelf':
        ...

    @t.overload
    def with_entities(
        self: 'MyNonOrderableQuery[t.Tuple[_T_BASE, _Y_BASE]]',
        __arg: t.Type[_T_BASE],
    ) -> 'MyQuery[_T_BASE]':
        ...

    @t.overload
    def with_entities(self, __arg: DbColumn[Z]) -> 'MyQueryTuple[Z]':
        ...

    @t.overload
    def with_entities(
        self, __arg1: DbColumn[Z], __arg2: DbColumn[Y]
    ) -> 'MyQuery[t.Tuple[Z, Y]]':
        ...

    @t.overload
    def with_entities(
        self, __arg1: DbColumn[Z], __arg2: DbColumn[Y], __arg3: DbColumn[U]
    ) -> 'MyQuery[t.Tuple[Z, Y, U]]':
        ...

    @t.overload
    def with_entities(
        self, __arg1: DbColumn[Z], __arg2: DbColumn[Y], __arg3: DbColumn[U],
        __arg4: DbColumn[ZZ]
    ) -> 'MyQuery[t.Tuple[Z, Y, U, ZZ]]':
        ...

    def with_entities(self, *args: t.Any) -> 'MyQuery[t.Any]':
        ...

    def union(self: QuerySelf, *q: QuerySelf) -> 'QuerySelf':
        ...


class MyQuery(t.Generic[T], MyNonOrderableQuery[T]):
    def order_by(
        self: QuerySelf, *args: t.Union[DbColumn, ColumnOrder]
    ) -> 'QuerySelf':
        ...

    def from_self(self, *args: t.Type[Z]) -> 'MyQuery[Z]':
        ...


class MyQueryTuple(t.Generic[T], MyQuery[t.Tuple[T]]):
    def as_scalar(self) -> 'MyQuery[T]':
        ...

    def scalar(self) -> t.Optional[T]:
        ...

    def label(self, name: str) -> 'DbColumn[T]':
        ...


class _MyExistsQuery:
    def scalar(self) -> bool:
        ...


_MyQuery = MyQuery


def cast_as_non_null(col: DbColumn[t.Optional[T]]) -> DbColumn[T]:
    """Get the given nullable column as non nullable.

    This function is useful when you for rows where this column is not
    ``NULL``, however ``mypy`` will no understand that filter. You can see this
    function as a safer variant of `typing.cast`.

    :returns: Its input completely unaltered.
    """
    return col  # type: ignore


MYPY = False
if t.TYPE_CHECKING and MYPY:

    @t.overload
    def hybrid_property(fget: t.Callable[[Z], T]) -> ImmutableColumnProxy[T]:
        ...

    @t.overload
    def hybrid_property(
        fget: t.Callable[[Z], T],
        *,
        expr: t.Callable[[t.Type[Z]], DbColumn[T]],
    ) -> ImmutableColumnProxy[T]:
        ...

    @t.overload
    def hybrid_property(
        fget: t.Callable[[Z], T],
        *,
        custom_comparator: t.Callable[[t.Type[Z]], Y],
    ) -> _ImmutableColumnProxy[T, Y]:
        ...

    @t.overload
    def hybrid_property(
        fget: t.Callable[[Z], T],
        fset: t.Callable[[Z, Y], None],
        fdel: None = None,
        expr: t.Callable[[t.Type[Z]], DbColumn[T]] = None,
    ) -> _MutableColumnProxy[T, Y, DbColumn[T]]:
        ...

    def hybrid_property(*args: object, **kwargs: object) -> t.Any:
        ...

    hybrid_expression = staticmethod

    class Comparator(t.Generic[T]):
        def __init__(self, __name: DbColumn[T]) -> None:
            ...

        def __clause_element__(self) -> DbColumn[T]:
            ...

    JSONB = DbType[t.Mapping[str, object]]()

    CIText = DbType[str]()

    def TIMESTAMP(*, timezone: Literal[True]
                  ) -> DbType[cg_dt_utils.DatetimeWithTimezone]:
        ...

    class ARRAY(t.Generic[T], DbType[t.Tuple[T, ...]]):
        # We restrict the usage of array to single dimension arrays that are
        # immutable in Python. We do this because multi dimensional arrays and
        # mutable arrays have some foot guns and are not necessary at current
        # moment.
        def __init__(
            self,
            item_type: DbType[T],
            *,
            dimensions: Literal[1],
            as_tuple: Literal[True],
        ) -> None:
            ...

    class TypeDecorator:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def result_processor(self, dialect: object,
                             coltype: object) -> t.Callable[[object], object]:
            return lambda x: x

    class func:
        @staticmethod
        def count(_to_count: DbColumn[t.Any] = None) -> DbColumn[int]:
            ...

        @staticmethod
        def random() -> DbColumn[object]:
            ...

        @staticmethod
        def min(col: DbColumn[T]) -> FilterableDbColumn[t.Optional[T]]:
            ...

        @staticmethod
        def max(col: DbColumn[T]) -> FilterableDbColumn[t.Optional[T]]:
            ...

        @staticmethod
        def sum(col: DbColumn[T_NUM]) -> DbColumn[t.Optional[T_NUM]]:
            ...

        @staticmethod
        def lower(col: DbColumn[str]) -> DbColumn[str]:
            ...

    def distinct(_distinct: T_DB_COLUMN) -> T_DB_COLUMN:
        ...

    def tuple_(itemA: DbColumn[T],
               itemB: DbColumn[Z]) -> DbColumn[t.Tuple[T, Z]]:
        ...

    class expression:
        func: func

        @staticmethod
        def and_(*to_and: FilterColumn) -> DbColumn[bool]:
            ...

        @staticmethod
        def or_(*to_or: FilterColumn) -> DbColumn[bool]:
            ...

        @staticmethod
        def null() -> DbColumn[None]:
            ...

        @staticmethod
        def false() -> DbColumn[Literal[False]]:
            ...

        @staticmethod
        def literal(value: T) -> DbColumn[T]:
            ...
else:
    from sqlalchemy.ext.hybrid import hybrid_property
    from sqlalchemy.ext.hybrid import Comparator as _Comparator
    from sqlalchemy import TypeDecorator, TIMESTAMP
    from sqlalchemy.dialects.postgresql import JSONB, ARRAY
    from sqlalchemy.sql import expression
    from sqlalchemy import func
    from citext import CIText
    from sqlalchemy import distinct, tuple_

    def hybrid_expression(fun: T) -> T:
        return fun

    class FakeGenericMeta(type):
        def __getitem__(self: T, _: t.Any) -> T:
            return self

    class Comparator(_Comparator, metaclass=FakeGenericMeta):
        ...
