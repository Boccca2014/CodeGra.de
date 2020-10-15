from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .rubric_item_input_as_json import RubricItemInputAsJSON
from .types import File


@dataclass
class RubricRowBaseInputAsJSONBase:
    """The required part of the input data for a rubric row."""

    header: "str"
    description: "str"
    items: "List[RubricItemInputAsJSON]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        header = self.header
        res["header"] = header
        description = self.description
        res["description"] = description
        items = []
        for items_item_data in self.items:
            items_item = maybe_to_dict(items_item_data)

            items.append(items_item)

        res["items"] = items

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> RubricRowBaseInputAsJSONBase:
        base = {}
        header = d["header"]

        description = d["description"]

        items = []
        for items_item_data in d["items"]:
            items_item = RubricItemInputAsJSON.from_dict(cast(Dict[str, Any], items_item_data))

            items.append(items_item)

        return RubricRowBaseInputAsJSONBase(**base, header=header, description=description, items=items, raw_data=d,)
