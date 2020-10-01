from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, Union, cast

from ..utils import maybe_to_dict
from .rubric_item_as_json import RubricItemAsJSON
from .rubric_lock_reason import RubricLockReason
from .types import File


@dataclass
class RubricRowBaseAsJSON:
    """  """

    id: "int"
    header: "str"
    description: "Optional[str]"
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
            **base, id=id, header=header, description=description, items=items, locked=locked, type=type, raw_data=d,
        )
