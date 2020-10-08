from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class FixtureLike:
    """A AutoTest fixture where only the id is required."""

    id: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> FixtureLike:
        base = {}
        id = d["id"]

        return FixtureLike(**base, id=id, raw_data=d,)
