from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, Union, cast

from ..utils import maybe_to_dict
from .rubric_description_type import RubricDescriptionType
from .rubric_item_input_as_json import RubricItemInputAsJSON
from .types import File


@dataclass
class RubricRowBaseInputAsJSONBase:
    """The required part of the input data for a rubric row."""

    header: "str"
    description: "str"
    description_type: "Union[RubricDescriptionType]"
    items: "List[RubricItemInputAsJSON]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

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

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> RubricRowBaseInputAsJSONBase:
        base = {}
        header = d["header"]

        description = d["description"]

        def _parse_description_type(data: Dict[str, Any]) -> Union[RubricDescriptionType]:
            description_type: Union[RubricDescriptionType] = d["description_type"]
            description_type = RubricDescriptionType(description_type)

            return description_type

        description_type = _parse_description_type(d["description_type"])

        items = []
        for items_item_data in d["items"]:
            items_item = RubricItemInputAsJSON.from_dict(items_item_data)

            items.append(items_item)

        return RubricRowBaseInputAsJSONBase(
            **base, header=header, description=description, description_type=description_type, items=items, raw_data=d,
        )
