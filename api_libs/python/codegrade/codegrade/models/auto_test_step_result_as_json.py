from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .auto_test_step_base_as_json import AutoTestStepBaseAsJSON
from .auto_test_step_result_state import AutoTestStepResultState
from .types import File


@dataclass
class AutoTestStepResultAsJSON:
    """The step result as JSON."""

    id: "int"
    auto_test_step: "Union[AutoTestStepBaseAsJSON]"
    state: "Union[AutoTestStepResultState]"
    achieved_points: "float"
    log: "Optional[Dict[Any, Any]]"
    started_at: "Optional[datetime.datetime]"
    attachment_id: "Optional[str]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        if isinstance(self.auto_test_step, AutoTestStepBaseAsJSON):
            auto_test_step = maybe_to_dict(self.auto_test_step)

        res["auto_test_step"] = auto_test_step
        if isinstance(self.state, AutoTestStepResultState):
            state = self.state.value

        res["state"] = state
        achieved_points = self.achieved_points
        res["achieved_points"] = achieved_points
        log = self.log

        res["log"] = log
        started_at = self.started_at.isoformat() if self.started_at else None

        res["started_at"] = started_at
        attachment_id = self.attachment_id
        res["attachment_id"] = attachment_id

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestStepResultAsJSON:
        base = {}
        id = d["id"]

        def _parse_auto_test_step(data: Dict[str, Any]) -> Union[AutoTestStepBaseAsJSON]:
            auto_test_step: Union[AutoTestStepBaseAsJSON] = d["auto_test_step"]
            auto_test_step = AutoTestStepBaseAsJSON.from_dict(cast(Dict[str, Any], auto_test_step))

            return auto_test_step

        auto_test_step = _parse_auto_test_step(d["auto_test_step"])

        def _parse_state(data: Dict[str, Any]) -> Union[AutoTestStepResultState]:
            state: Union[AutoTestStepResultState] = d["state"]
            state = AutoTestStepResultState(state)

            return state

        state = _parse_state(d["state"])

        achieved_points = d["achieved_points"]

        log = d["log"]

        started_at = None
        if d["started_at"] is not None:
            started_at = datetime.datetime.fromisoformat(cast(str, d["started_at"]))

        attachment_id = d["attachment_id"]

        return AutoTestStepResultAsJSON(
            **base,
            id=id,
            auto_test_step=auto_test_step,
            state=state,
            achieved_points=achieved_points,
            log=log,
            started_at=started_at,
            attachment_id=attachment_id,
            raw_data=d,
        )
