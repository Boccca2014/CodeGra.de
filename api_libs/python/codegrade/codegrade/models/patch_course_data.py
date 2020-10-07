from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from ..utils import maybe_to_dict
from .course_state import CourseState
from .types import File


@dataclass
class PatchCourseData:
    """"""

    name: "Optional[str]" = None
    state: "Optional[CourseState]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name
        if self.name is not None:
            res["name"] = name
        state = self.state.value if self.state else None

        if self.state is not None:
            res["state"] = state

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> PatchCourseData:
        base = {}
        name = d.get("name")

        state = None
        if d.get("state") is not None:
            state = CourseState(d.get("state"))

        return PatchCourseData(**base, name=name, state=state, raw_data=d,)
