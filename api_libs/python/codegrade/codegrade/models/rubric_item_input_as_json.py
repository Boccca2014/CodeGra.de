from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .rubric_item_as_json_base import RubricItemAsJSONBase
from .types import File


@dataclass
class RubricItemInputAsJSON(RubricItemAsJSONBase):
    """The JSON needed to update a rubric item."""

    id: "Optional[int]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        id = self.id
        if self.id is not None:
            res["id"] = id

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> RubricItemInputAsJSON:
        base = asdict(RubricItemAsJSONBase.from_dict(d))
        base.pop("raw_data")
        id = d.get("id")

        return RubricItemInputAsJSON(**base, id=id, raw_data=d,)
