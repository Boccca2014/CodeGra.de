from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class AssignmentPeerFeedbackSettingsAsJSON:
    """  """

    amount: "int"
    time: "Optional[float]"
    auto_approved: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        amount = self.amount
        res["amount"] = amount
        time = self.time
        res["time"] = time
        auto_approved = self.auto_approved
        res["auto_approved"] = auto_approved

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AssignmentPeerFeedbackSettingsAsJSON:
        base = {}
        amount = d["amount"]

        time = d["time"]

        auto_approved = d["auto_approved"]

        return AssignmentPeerFeedbackSettingsAsJSON(
            **base, amount=amount, time=time, auto_approved=auto_approved, raw_data=d,
        )
