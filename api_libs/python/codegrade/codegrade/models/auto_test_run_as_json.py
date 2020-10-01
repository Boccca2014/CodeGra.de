from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from ..utils import maybe_to_dict
from .state import State
from .types import File


@dataclass
class AutoTestRunAsJSON:
    """  """

    id: "int"
    created_at: "datetime.datetime"
    state: "State"
    is_continuous: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        created_at = self.created_at.isoformat()

        res["created_at"] = created_at
        state = self.state.value

        res["state"] = state
        is_continuous = self.is_continuous
        res["is_continuous"] = is_continuous

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestRunAsJSON:
        base = {}
        id = d["id"]

        created_at = datetime.datetime.fromisoformat(d["created_at"])

        state = State(d["state"])

        is_continuous = d["is_continuous"]

        return AutoTestRunAsJSON(
            **base, id=id, created_at=created_at, state=state, is_continuous=is_continuous, raw_data=d,
        )
