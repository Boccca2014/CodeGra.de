from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, Union, cast

from ..utils import maybe_to_dict
from .rubric_description_type import RubricDescriptionType
from .rubric_item_as_json import RubricItemAsJSON
from .rubric_lock_reason import RubricLockReason
from .types import File


@dataclass
class RubricRowBaseAsJSON:
    """The JSON representation of a rubric row."""

    id: "int"
    header: "str"
    description: "Optional[str]"
    description_type: "Union[RubricDescriptionType]"
    items: "List[RubricItemAsJSON]"
    locked: "Union[bool, RubricLockReason]"
    type: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        header = self.header
        res["header"] = header
        description = self.description
        res["description"] = description
        if isinstance(self.description_type, RubricDescriptionType):
            description_type = self.description_type.value

        res["description_type"] = description_type
        items = []
        for items_item_data in self.items:
            items_item = maybe_to_dict(items_item_data)

            items.append(items_item)

        res["items"] = items
        if isinstance(self.locked, bool):
            locked = self.locked
        else:
            locked = self.locked.value

        res["locked"] = locked
        type = self.type
        res["type"] = type

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> RubricRowBaseAsJSON:
        base = {}
        id = d["id"]

        header = d["header"]

        description = d["description"]

        def _parse_description_type(data: Dict[str, Any]) -> Union[RubricDescriptionType]:
            description_type: Union[RubricDescriptionType] = d["description_type"]
            description_type = RubricDescriptionType(description_type)

            return description_type

        description_type = _parse_description_type(d["description_type"])

        items = []
        for items_item_data in d["items"]:
            items_item = RubricItemAsJSON.from_dict(items_item_data)

            items.append(items_item)

        def _parse_locked(data: Dict[str, Any]) -> Union[bool, RubricLockReason]:
            locked: Union[bool, RubricLockReason] = d["locked"]
            if isinstance(locked, bool):
                return locked
            locked = RubricLockReason(locked)

            return locked

        locked = _parse_locked(d["locked"])

        type = d["type"]

        return RubricRowBaseAsJSON(
            **base,
            id=id,
            header=header,
            description=description,
            description_type=description_type,
            items=items,
            locked=locked,
            type=type,
            raw_data=d,
        )
