from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .file_mixin_as_json import FileMixinAsJSON
from .types import File


@dataclass
class AutoTestFixtureAsJSON(FileMixinAsJSON):
    """  """

    hidden: "Optional[bool]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        hidden = self.hidden
        if self.hidden is not None:
            res["hidden"] = hidden

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestFixtureAsJSON:
        base = FileMixinAsJSON.from_dict(d).to_dict()
        hidden = d.get("hidden")

        return AutoTestFixtureAsJSON(**base, hidden=hidden, raw_data=d,)
