from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .key import Key
from .types import File


@dataclass
class OptionsInputData:
    """The input data for a single option for the SubmissionValidator."""

    key: "Key"
    value: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        key = self.key.value

        res["key"] = key
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> OptionsInputData:
        base = {}
        key = Key(d["key"])

        value = d["value"]

        return OptionsInputData(**base, key=key, value=value, raw_data=d,)
