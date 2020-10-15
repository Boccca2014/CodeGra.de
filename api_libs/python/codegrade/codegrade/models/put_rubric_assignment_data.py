from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .rubric_row_base_input_as_json import RubricRowBaseInputAsJSON
from .types import File


@dataclass
class PutRubricAssignmentData:
    """"""

    max_points: "Optional[float]" = None
    rows: "Optional[List[RubricRowBaseInputAsJSON]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        max_points = self.max_points
        if self.max_points is not None:
            res["max_points"] = max_points
        if self.rows is None:
            rows = None
        else:
            rows = []
            for rows_item_data in self.rows:
                rows_item = maybe_to_dict(rows_item_data)

                rows.append(rows_item)

        if self.rows is not None:
            res["rows"] = rows

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> PutRubricAssignmentData:
        base = {}
        max_points = d.get("max_points")

        rows = []
        for rows_item_data in d.get("rows") or []:
            rows_item = RubricRowBaseInputAsJSON.from_dict(cast(Dict[str, Any], rows_item_data))

            rows.append(rows_item)

        return PutRubricAssignmentData(**base, max_points=max_points, rows=rows, raw_data=d,)
