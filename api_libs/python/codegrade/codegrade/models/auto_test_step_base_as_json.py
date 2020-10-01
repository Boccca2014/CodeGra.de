from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .auto_test_step_base_as_json_base import AutoTestStepBaseAsJSONBase
from .types import File


@dataclass
class AutoTestStepBaseAsJSON(AutoTestStepBaseAsJSONBase):
    """  """

    id: "Optional[int]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        id = self.id
        if self.id is not None:
            res["id"] = id

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestStepBaseAsJSON:
        base = AutoTestStepBaseAsJSONBase.from_dict(d).to_dict()
        id = d.get("id")

        return AutoTestStepBaseAsJSON(**base, id=id, raw_data=d,)
