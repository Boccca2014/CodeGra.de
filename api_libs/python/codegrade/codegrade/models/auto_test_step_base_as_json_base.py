from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class AutoTestStepBaseAsJSONBase:
    """  """

    name: "str"
    type: "str"
    weight: "float"
    hidden: "bool"
    data: "Dict[Any, Any]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name
        res["name"] = name
        type = self.type
        res["type"] = type
        weight = self.weight
        res["weight"] = weight
        hidden = self.hidden
        res["hidden"] = hidden
        data = self.data

        res["data"] = data

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestStepBaseAsJSONBase:
        base = {}
        name = d["name"]

        type = d["type"]

        weight = d["weight"]

        hidden = d["hidden"]

        data = d["data"]

        return AutoTestStepBaseAsJSONBase(
            **base, name=name, type=type, weight=weight, hidden=hidden, data=data, raw_data=d,
        )
