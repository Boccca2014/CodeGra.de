from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class RubricItemAsJSONBase:
    """  """

    description: "str"
    header: "str"
    points: "float"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        description = self.description
        res["description"] = description
        header = self.header
        res["header"] = header
        points = self.points
        res["points"] = points

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> RubricItemAsJSONBase:
        base = {}
        description = d["description"]

        header = d["header"]

        points = d["points"]

        return RubricItemAsJSONBase(**base, description=description, header=header, points=points, raw_data=d,)
