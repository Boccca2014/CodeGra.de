from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .auto_test_step_result_state import AutoTestStepResultState
from .types import File


@dataclass
class AutoTestResultAsJSON:
    """  """

    id: "int"
    created_at: "datetime.datetime"
    started_at: "Optional[datetime.datetime]"
    work_id: "int"
    state: "Union[AutoTestStepResultState]"
    points_achieved: "float"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        created_at = self.created_at.isoformat()

        res["created_at"] = created_at
        started_at = self.started_at.isoformat() if self.started_at else None

        res["started_at"] = started_at
        work_id = self.work_id
        res["work_id"] = work_id
        if isinstance(self.state, AutoTestStepResultState):
            state = self.state.value

        res["state"] = state
        points_achieved = self.points_achieved
        res["points_achieved"] = points_achieved

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestResultAsJSON:
        base = {}
        id = d["id"]

        created_at = datetime.datetime.fromisoformat(d["created_at"])

        started_at = None
        if d["started_at"] is not None:
            started_at = datetime.datetime.fromisoformat(cast(str, d["started_at"]))

        work_id = d["work_id"]

        def _parse_state(data: Dict[str, Any]) -> Union[AutoTestStepResultState]:
            state: Union[AutoTestStepResultState] = d["state"]
            state = AutoTestStepResultState(state)

            return state

        state = _parse_state(d["state"])

        points_achieved = d["points_achieved"]

        return AutoTestResultAsJSON(
            **base,
            id=id,
            created_at=created_at,
            started_at=started_at,
            work_id=work_id,
            state=state,
            points_achieved=points_achieved,
            raw_data=d,
        )
