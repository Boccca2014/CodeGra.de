from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from typing_extensions import Literal

from ..utils import maybe_to_dict
from .types import File


@dataclass
class AutoTestRunAsJSON:
    """The run as JSON."""

    id: "int"
    created_at: "datetime.datetime"
    state: 'Literal["running"]'
    is_continuous: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        created_at = self.created_at.isoformat()

        res["created_at"] = created_at
        state = self.state

        res["state"] = state
        is_continuous = self.is_continuous
        res["is_continuous"] = is_continuous

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestRunAsJSON:
        base = {}
        id = d["id"]

        created_at = datetime.datetime.fromisoformat(d["created_at"])

        state = d["state"]

        is_continuous = d["is_continuous"]

        return AutoTestRunAsJSON(
            **base, id=id, created_at=created_at, state=state, is_continuous=is_continuous, raw_data=d,
        )
