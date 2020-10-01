from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from ..utils import maybe_to_dict
from .types import File


@dataclass
class LTIProviderBaseAsJSON:
    """  """

    id: "str"
    lms: "str"
    version: "str"
    created_at: "datetime.datetime"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        lms = self.lms
        res["lms"] = lms
        version = self.version
        res["version"] = version
        created_at = self.created_at.isoformat()

        res["created_at"] = created_at

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LTIProviderBaseAsJSON:
        base = {}
        id = d["id"]

        lms = d["lms"]

        version = d["version"]

        created_at = datetime.datetime.fromisoformat(d["created_at"])

        return LTIProviderBaseAsJSON(**base, id=id, lms=lms, version=version, created_at=created_at, raw_data=d,)
