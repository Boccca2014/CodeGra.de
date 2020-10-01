from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .rubric_row_base_input_as_json_base import RubricRowBaseInputAsJSONBase
from .types import File


@dataclass
class RubricRowBaseInputAsJSON(RubricRowBaseInputAsJSONBase):
    """  """

    id: "Optional[int]" = None
    type: "Optional[str]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        id = self.id
        if self.id is not None:
            res["id"] = id
        type = self.type
        if self.type is not None:
            res["type"] = type

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> RubricRowBaseInputAsJSON:
        base = RubricRowBaseInputAsJSONBase.from_dict(d).to_dict()
        id = d.get("id")

        type = d.get("type")

        return RubricRowBaseInputAsJSON(**base, id=id, type=type, raw_data=d,)
