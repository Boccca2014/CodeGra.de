from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from ..utils import maybe_to_dict
from .types import File


@dataclass
class LTIProviderBaseBaseAsJSON:
    """  """

    id: "str"
    lms: "str"
    created_at: "datetime.datetime"
    intended_use: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        lms = self.lms
        res["lms"] = lms
        created_at = self.created_at.isoformat()

        res["created_at"] = created_at
        intended_use = self.intended_use
        res["intended_use"] = intended_use

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LTIProviderBaseBaseAsJSON:
        base = {}
        id = d["id"]

        lms = d["lms"]

        created_at = datetime.datetime.fromisoformat(d["created_at"])

        intended_use = d["intended_use"]

        return LTIProviderBaseBaseAsJSON(
            **base, id=id, lms=lms, created_at=created_at, intended_use=intended_use, raw_data=d,
        )
