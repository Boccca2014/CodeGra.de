from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class BaseReleaseInfo:
    """The part of the release info that will always be present."""

    commit: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        commit = self.commit
        res["commit"] = commit

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> BaseReleaseInfo:
        base = {}
        commit = d["commit"]

        return BaseReleaseInfo(**base, commit=commit, raw_data=d,)
