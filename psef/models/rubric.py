"""This module defines a RubricRow.

SPDX-License-Identifier: AGPL-3.0-only
"""
import enum
import typing as t
import numbers

from sqlalchemy import select
from mypy_extensions import TypedDict

import psef
import cg_enum
import cg_json
from cg_dt_utils import DatetimeWithTimezone
from cg_sqlalchemy_helpers import hybrid_property, hybrid_expression
from cg_sqlalchemy_helpers.types import DbColumn, ColumnProxy

from . import Base, db
from . import work as work_models
from .. import helpers
from ..registry import rubric_row_types
from ..exceptions import APICodes, APIException

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import
    from . import auto_test as auto_test_models

T = t.TypeVar('T', bound=t.Type['RubricRowBase'])
_ALL_RUBRIC_ROW_TYPES = sorted(['normal', 'continuous'])


def _register(cls: T) -> T:
    name = cls.__mapper_args__['polymorphic_identity']

    assert isinstance(name, str)
    assert name in _ALL_RUBRIC_ROW_TYPES
    assert rubric_row_types.get(name) is None
    rubric_row_types.register(name)(cls)

    return cls


class WorkRubricItem(helpers.NotEqualMixin, Base):
    """The association table between a :class:`.work_models.Work` and a
    :class:`.RubricItem`.
    """

    def __init__(
        self,
        *,
        rubric_item: 'RubricItem',
        work: 'work_models.Work',
        multiplier: float = 1.0,
    ) -> None:
        assert rubric_item.id is not None
        assert work.id is not None

        super().__init__(
            rubric_item=rubric_item,
            work=work,
            rubricitem_id=rubric_item.id,
            work_id=work.id,
            multiplier=multiplier,
        )

    __tablename__ = 'work_rubric_item'
    __table_args__ = (
        db.CheckConstraint(
            'multiplier >= 0 AND multiplier <= 1', name='ck_multiplier_range'
        ),
    )

    work_id = db.Column(
        'work_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
        primary_key=True,
    )
    rubricitem_id = db.Column(
        'rubricitem_id',
        db.Integer,
        db.ForeignKey('RubricItem.id', ondelete='CASCADE'),
        nullable=False,
        primary_key=True,
    )
    multiplier = db.Column(
        'multiplier',
        db.Float,
        nullable=False,
        default=1.0,
        server_default='1.0',
    )

    work = db.relationship(lambda: work_models.Work, foreign_keys=work_id)
    rubric_item = db.relationship(
        lambda: RubricItem,
        foreign_keys=rubricitem_id,
        lazy='selectin',
    )

    def __eq__(self, other: object) -> bool:
        """Check if this rubric item is equal to another one.

        >>> w1 = psef.models.Work(id=1)
        >>> w2 = psef.models.Work(id=2)
        >>> r1 = RubricItem(id=1)
        >>> r2 = RubricItem(id=1)
        >>> wr1 = WorkRubricItem(rubric_item=r1, work=w1, multiplier=0.3)
        >>> wr2 = WorkRubricItem(rubric_item=r1, work=w1, multiplier=0.3)
        >>> wr1 == wr2
        True
        >>> wr1.multiplier = 0.1 + 0.2
        >>> wr1 == wr2
        True
        >>> repr(wr1) == repr(wr2)  # Rounding is different
        False
        >>> wr1 == object()
        False
        >>> wr1.multiplier = 0.4
        >>> wr1 == wr2
        False
        >>> wr1.multiplier = 0.3
        >>> wr1.work_id = 10
        >>> wr1 == wr2
        False
        """
        if not isinstance(other, WorkRubricItem):
            return NotImplemented
        return (
            self.work_id == other.work_id and
            self.rubricitem_id == other.rubricitem_id and
            helpers.FloatHelpers.eq(self.multiplier, other.multiplier)
        )

    def __hash__(self) -> int:
        # Note that `a == b` implies `hash(a) == hash(b)`, but that `hash(a) ==
        # hash(b)` does not imply `a == b`. So this hash might be imperfect, it
        # is correct.
        # We do not use the multiplier, as this is a float, and thus it has
        # rounding issues.
        assert self.rubricitem_id is not None
        assert self.work_id is not None
        return hash((self.rubricitem_id, self.work_id))

    def __repr__(self) -> str:
        return '<{} rubricitem_id={}, work_id={}, multiplier={}>'.format(
            self.__class__.__name__,
            self.rubricitem_id,
            self.work_id,
            self.multiplier,
        )

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            **self.rubric_item.__to_json__(),
            'achieved_points': self.points,
            'multiplier': self.multiplier,
        }

    def _get_points(self) -> float:
        """The amount of points achieved by the work.
        """
        return self.multiplier * self.rubric_item.points

    @hybrid_expression
    def _get_points_expr(cls: t.Type['WorkRubricItem']) -> DbColumn[float]:
        """Same as above, but this returns an expression used by
        sqlalchemy.
        """
        # pylint: disable=no-self-argument
        return select(
            [cls.multiplier * RubricItem.points]
        ).where(cls.rubricitem_id == RubricItem.id).label('points')

    points = hybrid_property(_get_points, expr=_get_points_expr)


@enum.unique
class RubricDescriptionType(cg_enum.CGEnum):
    """The type of formatting used for the description of a rubric row or item.
    """
    #: The description is plain text.
    plain_text = enum.auto()
    #: The description should be interpreted as markdown.
    markdown = enum.auto()


class RubricLockReason(cg_json.SerializableEnum, enum.Enum):
    auto_test = enum.auto()


class RubricItem(helpers.NotEqualMixin, Base):
    """This class holds the information about a single option/item in a
    :class:`.RubricRowBase`.
    """
    __tablename__ = 'RubricItem'

    id = db.Column('id', db.Integer, primary_key=True)
    rubricrow_id = db.Column(
        'Rubricrow_id',
        db.Integer,
        db.ForeignKey('RubricRow.id', ondelete='CASCADE'),
        nullable=False,
    )
    header = db.Column('header', db.Unicode, default='', nullable=False)
    description_type = db.Column(
        'description_type',
        db.Enum(RubricDescriptionType),
        nullable=False,
        server_default=RubricDescriptionType.plain_text.name,
    )
    description = db.Column(
        'description', db.Unicode, default='', nullable=False
    )
    points = db.Column('points', db.Float, nullable=False)

    # This variable is generated from the backref from RubricRowBase
    rubricrow: ColumnProxy['RubricRowBase']

    class JSONBaseSerialization(TypedDict, total=True):
        """The base serialization of a rubric item.
        """
        description: str
        header: str
        points: numbers.Real

    class AsJSON(JSONBaseSerialization, total=True):
        """Serialization of rubric items for outgoing requests.
        """
        id: int
        description_type: RubricDescriptionType

    def __to_json__(self) -> AsJSON:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'id': self.id,
            'description': self.description,
            'description_type': self.description_type,
            'header': self.header,
            # A float is a ``Real``, mypy issue:
            # https://github.com/python/mypy/issues/2636
            'points': t.cast(numbers.Real, self.points),
        }

    def copy(self) -> 'RubricItem':
        return RubricItem(
            header=self.header,
            description=self.description,
            description_type=self.description_type,
            points=self.points,
        )

    def __eq__(self, other: object) -> bool:
        """Check if two rubric items are equal

        >>> RubricItem(id=5) == RubricItem(id=5)
        True
        >>> RubricItem(id=6) == RubricItem(id=5)
        False
        >>> RubricItem(id=6) == object()
        False
        """
        if isinstance(other, RubricItem):
            return self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)


class RubricRowBase(helpers.NotEqualMixin, Base):
    """Describes a row of some rubric.

    This class forms the link between :class:`.Assignment` and
    :class:`.RubricItem` and holds information about the row.

    :ivar ~.RubricRowBase.assignment_id: The assignment id of the assignment
        that belows to this rubric row.
    """
    __tablename__ = 'RubricRow'
    id = db.Column('id', db.Integer, primary_key=True)
    assignment_id = db.Column(
        'Assignment_id', db.Integer, db.ForeignKey('Assignment.id')
    )
    header = db.Column('header', db.Unicode, nullable=False)
    description = db.Column('description', db.Unicode, default='')
    description_type = db.Column(
        'description_type',
        db.Enum(RubricDescriptionType),
        nullable=False,
        server_default=RubricDescriptionType.plain_text.name,
    )
    created_at = db.Column(
        'created_at',
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow
    )
    items = db.relationship(
        lambda: RubricItem,
        backref=db.backref("rubricrow"),
        cascade='delete-orphan, delete, save-update',
        order_by=RubricItem.points.asc,
        uselist=True,
    )

    assignment = db.relationship(
        lambda: psef.models.Assignment,
        foreign_keys=assignment_id,
        back_populates='rubric_rows',
        lazy='select',
    )

    rubric_row_type = db.Column(
        'rubric_row_type',
        db.Enum(*_ALL_RUBRIC_ROW_TYPES, name='rubricrowtype'),
        nullable=False,
        server_default='normal',
    )

    __mapper_args__ = {
        'polymorphic_on': rubric_row_type,
        'polymorphic_identity': 'non_existing'
    }

    def _get_item(self, item_id: t.Union[int, RubricItem]) -> RubricItem:
        """Get an item from this row

        >>> item1 = RubricItem(id=1, rubricrow_id=4)
        >>> item2 = RubricItem(id=2, rubricrow_id=4)
        >>> item3 = RubricItem(id=3, rubricrow_id=10)
        >>> row = _NormalRubricRow(id=4, items=[item1, item2])
        >>> row._get_item(2) == item2
        True
        >>> row._get_item(item2) == item2
        True
        >>> row._get_item(10)
        Traceback (most recent call last):
        ...
        APIException:
        >>> row._get_item(item3)
        Traceback (most recent call last):
        ...
        APIException:
        """
        if isinstance(item_id, int):
            for item in self.items:
                if item.id == item_id:
                    return item
        elif item_id.rubricrow_id == self.id:
            return item_id
        else:
            item_id = item_id.id

        raise APIException(
            "This rubric row doesn't contain the requested rubric item",
            f'The item {item_id} is not in rubric row {self.id}',
            APICodes.OBJECT_ID_NOT_FOUND, 404
        )

    def copy(self) -> 'RubricRowBase':
        return RubricRowBase(
            created_at=DatetimeWithTimezone.utcnow(),
            description=self.description,
            description_type=self.description_type,
            header=self.header,
            assignment_id=self.assignment_id,
            items=[item.copy() for item in self.items],
            rubric_row_type=self.rubric_row_type,
        )

    def is_selected(self) -> bool:
        """Is this rubric row selected at least once.
        """
        return db.session.query(
            db.session.query(WorkRubricItem).filter(
                t.cast(DbColumn[int], WorkRubricItem.rubricitem_id).in_(
                    [item.id for item in self.items]
                )
            ).exists()
        ).scalar() or False

    @property
    def is_valid(self) -> bool:
        """Check if the current row is valid.

        :returns: ``False`` if the row has no items or if the max points of the
            items is not > 0.
        """
        if not self.items:
            return False
        return max(it.points for it in self.items) >= 0

    @property
    def locked(self) -> t.Union[RubricLockReason, bool]:
        """Is this rubric row locked.

        If it is locked the reason is returned.
        """
        if self.assignment is None:
            return False
        return self.assignment.locked_rubric_rows.get(self.id, False)

    class AsJSON(TypedDict, total=True):
        """JSON serialization of a rubric row.
        """
        id: int
        header: str
        description: t.Optional[str]
        description_type: RubricDescriptionType
        items: t.List[RubricItem]
        locked: t.Union[RubricLockReason, bool]
        type: str

    def __to_json__(self) -> AsJSON:
        """Creates a JSON serializable representation of this object.
        """
        return {
            'id': self.id,
            'header': self.header,
            'description': self.description,
            'description_type': self.description_type,
            'items': self.items,
            'locked': self.locked,
            'type': self.rubric_row_type,
        }

    def update_items_from_json(
        self, items: t.List[RubricItem.JSONBaseSerialization]
    ) -> None:
        """Update the items of this row in place.

        .. warning::

            All items not present in the given ``items`` list will be deleted
            from the rubric row.

        :param items: The items (:class:`.RubricItem`) that should be added or
            updated. If ``id`` is in an item it should be an ``int`` and the
            rubric item with the corresponding ``id`` will be updated instead
            of added.
        :returns: Nothing.
        """
        if (
            self.locked == RubricLockReason.auto_test and self.assignment and
            self.assignment.auto_test and self.assignment.auto_test.run
        ):
            new_ids = set(t.cast(dict, item).get('id', None) for item in items)
            old_ids = set(item.id for item in self.items)
            if new_ids != old_ids:
                row_name = self.header
                raise APIException(
                    (
                        f'No items can be added or deleted from row'
                        f' "{row_name}" as it is locked for an AutoTestRun.'
                    ), (
                        'Some items were added or removed, but this is not'
                        ' allowed as an AutoTest run has already been done'
                    ), APICodes.LOCKED_UPDATE, 400
                )

        # We store all new items in this list and not `self.items` as we need
        # to search for items in `self.items` if a rubric item needs to be
        # updated (instead of added).
        new_items: t.List[RubricItem] = []

        for item in items:
            item_description: str = item['description']
            item_header: str = item['header']
            points: numbers.Real = item['points']

            if 'id' in item:
                helpers.ensure_keys_in_dict(item, [('id', int)])
                item_id = t.cast(int, item['id'])  # type: ignore
                rubric_item = self._get_item(item_id)
                rubric_item.header = item_header
                rubric_item.description = item_description
                rubric_item.points = float(points)
            else:
                rubric_item = RubricItem(
                    rubricrow=self,
                    description=item_description,
                    description_type=RubricDescriptionType.markdown,
                    header=item_header,
                    points=points
                )

            new_items.append(rubric_item)

        self.items = new_items

    def update_from_json(
        self, header: str, description: str,
        items: t.List[RubricItem.JSONBaseSerialization]
    ) -> None:
        """Update this rubric in place.

        .. warning::

            All items not present in the given ``items`` list will be deleted
            from the rubric row.

        :param header: The new header of the row.
        :param description: The new description of the row.
        :param items: The items that should be in this row (see warning). The
            format is the same as the items passed to
            :meth:`.RubricRowBase.update_items_from_json`.
        :returns: Nothing.
        """
        self.header = header
        self.description = description
        self.update_items_from_json(items)

    @classmethod
    def create_from_json(
        cls: t.Type['RubricRowBase'], header: str, description: str,
        items: t.List[RubricItem.JSONBaseSerialization]
    ) -> 'RubricRowBase':
        """Create a new rubric row for an assignment.

        :param header: The name of the new rubric row.
        :param description: The description of the new rubric row.
        :param items: The items that should be added to this row. The format is
            the same as the items passed to
            :meth:`.RubricRowBase.update_items_from_json`.
        :returns: The newly created row.
        """
        self = cls(
            header=header,
            description=description,
            description_type=RubricDescriptionType.markdown,
        )
        self.update_items_from_json(items)

        return self

    def __eq__(self, other: object) -> bool:
        """Check if two rubric items are equal

        >>> RubricRowBase(id=5) == RubricRowBase(id=5)
        True
        >>> RubricRowBase(id=6) == RubricRowBase(id=5)
        False
        >>> RubricRowBase(id=6) == object()
        False
        """
        if isinstance(other, RubricRowBase):
            return self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def make_work_rubric_item(
        self, work: 'work_models.Work', item_id: t.Union[int, RubricItem],
        multiplier: float
    ) -> WorkRubricItem:
        """Make a :class:`.WorkRubricItem` for a manual grade.

        :param work: The work to create the :class:`.WorkRubricItem` for.
        :param item_id: The item where the :class:`.WorkRubricItem` should be
            connected to.
        :param multiplier: The multiplier to use, this should always be 1.0 for
            a normal rubric row.
        """
        return WorkRubricItem(
            rubric_item=self._get_item(item_id),
            work=work,
            multiplier=multiplier
        )

    def make_work_rubric_item_for_auto_test(
        self,
        work: 'work_models.Work',
        percentage: float,
        grade_calculator: 'auto_test_models.GradeCalculator',
    ) -> WorkRubricItem:
        """Create a :class:`.WorkRubricItem` for an AutoTest.

        :param work: The work to create the :class:`.WorkRubricItem` for.
        :param percentage: The percentage achieved in the AT category.
        :param grade_calculator: The grade calculator to use, this is not used
            by continuous rubric rows.
        """
        raise NotImplementedError


@_register
class _NormalRubricRow(RubricRowBase):
    __mapper_args__ = {'polymorphic_identity': 'normal'}

    def make_work_rubric_item(
        self, work: 'work_models.Work', item_id: t.Union[int, RubricItem],
        multiplier: float
    ) -> WorkRubricItem:
        if multiplier != 1.0:
            raise APIException(
                'Normal rubric rows only support 1.0 as multiplier',
                f'The rubric row {self.id} got a multiplier of {multiplier}',
                APICodes.INVALID_PARAM, 400
            )

        return super().make_work_rubric_item(work, item_id, multiplier)

    def make_work_rubric_item_for_auto_test(
        self,
        work: 'work_models.Work',
        percentage: float,
        grade_calculator: 'auto_test_models.GradeCalculator',
    ) -> WorkRubricItem:
        return WorkRubricItem(
            work=work,
            rubric_item=grade_calculator(self.items, percentage),
            multiplier=1.0
        )


@_register
class _ContinuousRubricRow(RubricRowBase):
    __mapper_args__ = {'polymorphic_identity': 'continuous'}

    def make_work_rubric_item_for_auto_test(
        self,
        work: 'work_models.Work',
        percentage: float,
        grade_calculator: 'auto_test_models.GradeCalculator',
    ) -> WorkRubricItem:
        assert 0.0 <= percentage <= 1.0
        return WorkRubricItem(
            work=work,
            rubric_item=self.items[-1],
            multiplier=percentage,
        )

    def update_items_from_json(
        self, items: t.List[RubricItem.JSONBaseSerialization]
    ) -> None:
        if len(items) != 1:
            raise APIException(
                'Continuous rubric rows only support exactly one item.',
                f'The row {self.id} was given {len(items)} item(s).',
                APICodes.INVALID_PARAM,
                409,
            )

        return super().update_items_from_json(items)
