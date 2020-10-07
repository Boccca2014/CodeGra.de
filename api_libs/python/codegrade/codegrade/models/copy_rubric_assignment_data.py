from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class CopyRubricAssignmentData:
    """"""

    old_assignment_id: "int"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        old_assignment_id = self.old_assignment_id
        res["old_assignment_id"] = old_assignment_id

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> CopyRubricAssignmentData:
        base = {}
        old_assignment_id = d["old_assignment_id"]

        return CopyRubricAssignmentData(**base, old_assignment_id=old_assignment_id, raw_data=d,)
