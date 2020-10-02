from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, Union, cast

from ..utils import maybe_to_dict
from .auto_test_step_base_as_json import AutoTestStepBaseAsJSON
from .rubric_row_base_as_json import RubricRowBaseAsJSON
from .types import File


@dataclass
class AutoTestSuiteAsJSON:
    """  """

    id: "int"
    steps: "List[AutoTestStepBaseAsJSON]"
    rubric_row: "Union[RubricRowBaseAsJSON]"
    network_disabled: "bool"
    submission_info: "bool"
    command_time_limit: "Optional[float]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        steps = []
        for steps_item_data in self.steps:
            steps_item = maybe_to_dict(steps_item_data)

            steps.append(steps_item)

        res["steps"] = steps
        if isinstance(self.rubric_row, RubricRowBaseAsJSON):
            rubric_row = maybe_to_dict(self.rubric_row)

        res["rubric_row"] = rubric_row
        network_disabled = self.network_disabled
        res["network_disabled"] = network_disabled
        submission_info = self.submission_info
        res["submission_info"] = submission_info
        command_time_limit = self.command_time_limit
        res["command_time_limit"] = command_time_limit

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestSuiteAsJSON:
        base = {}
        id = d["id"]

        steps = []
        for steps_item_data in d["steps"]:
            steps_item = AutoTestStepBaseAsJSON.from_dict(steps_item_data)

            steps.append(steps_item)

        def _parse_rubric_row(data: Dict[str, Any]) -> Union[RubricRowBaseAsJSON]:
            rubric_row: Union[RubricRowBaseAsJSON] = d["rubric_row"]
            rubric_row = RubricRowBaseAsJSON.from_dict(rubric_row)

            return rubric_row

        rubric_row = _parse_rubric_row(d["rubric_row"])

        network_disabled = d["network_disabled"]

        submission_info = d["submission_info"]

        command_time_limit = d["command_time_limit"]

        return AutoTestSuiteAsJSON(
            **base,
            id=id,
            steps=steps,
            rubric_row=rubric_row,
            network_disabled=network_disabled,
            submission_info=submission_info,
            command_time_limit=command_time_limit,
            raw_data=d,
        )
