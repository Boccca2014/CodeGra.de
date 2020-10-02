from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class GroupSetAsJSON:
    """  """

    id: "int"
    minimum_size: "int"
    maximum_size: "int"
    assignment_ids: "List[int]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        minimum_size = self.minimum_size
        res["minimum_size"] = minimum_size
        maximum_size = self.maximum_size
        res["maximum_size"] = maximum_size
        assignment_ids = self.assignment_ids

        res["assignment_ids"] = assignment_ids

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> GroupSetAsJSON:
        base = {}
        id = d["id"]

        minimum_size = d["minimum_size"]

        maximum_size = d["maximum_size"]

        assignment_ids = d["assignment_ids"]

        return GroupSetAsJSON(
            **base,
            id=id,
            minimum_size=minimum_size,
            maximum_size=maximum_size,
            assignment_ids=assignment_ids,
            raw_data=d,
        )
