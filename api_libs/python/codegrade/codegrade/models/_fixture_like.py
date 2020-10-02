from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class _FixtureLike:
    """  """

    id: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> _FixtureLike:
        base = {}
        id = d["id"]

        return _FixtureLike(**base, id=id, raw_data=d,)
