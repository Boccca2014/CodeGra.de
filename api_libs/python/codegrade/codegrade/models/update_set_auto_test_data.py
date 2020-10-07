from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class UpdateSetAutoTestData:
    """"""

    stop_points: "Optional[float]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        stop_points = self.stop_points
        if self.stop_points is not None:
            res["stop_points"] = stop_points

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> UpdateSetAutoTestData:
        base = {}
        stop_points = d.get("stop_points")

        return UpdateSetAutoTestData(**base, stop_points=stop_points, raw_data=d,)
