from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class CopyAutoTestData:
    """  """

    assignment_id: "int"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        assignment_id = self.assignment_id
        res["assignment_id"] = assignment_id

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> CopyAutoTestData:
        base = {}
        assignment_id = d["assignment_id"]

        return CopyAutoTestData(**base, assignment_id=assignment_id, raw_data=d,)
