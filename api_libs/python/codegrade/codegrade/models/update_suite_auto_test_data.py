from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .auto_test_step_base_input_as_json import AutoTestStepBaseInputAsJSON
from .types import File


@dataclass
class UpdateSuiteAutoTestData:
    """  """

    steps: "List[AutoTestStepBaseInputAsJSON]"
    rubric_row_id: "int"
    network_disabled: "bool"
    id: "Optional[int]" = None
    submission_info: "Optional[bool]" = None
    command_time_limit: "Optional[float]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        steps = []
        for steps_item_data in self.steps:
            steps_item = maybe_to_dict(steps_item_data)

            steps.append(steps_item)

        res["steps"] = steps
        rubric_row_id = self.rubric_row_id
        res["rubric_row_id"] = rubric_row_id
        network_disabled = self.network_disabled
        res["network_disabled"] = network_disabled
        id = self.id
        if self.id is not None:
            res["id"] = id
        submission_info = self.submission_info
        if self.submission_info is not None:
            res["submission_info"] = submission_info
        command_time_limit = self.command_time_limit
        if self.command_time_limit is not None:
            res["command_time_limit"] = command_time_limit

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> UpdateSuiteAutoTestData:
        base = {}
        steps = []
        for steps_item_data in d["steps"]:
            steps_item = AutoTestStepBaseInputAsJSON.from_dict(steps_item_data)

            steps.append(steps_item)

        rubric_row_id = d["rubric_row_id"]

        network_disabled = d["network_disabled"]

        id = d.get("id")

        submission_info = d.get("submission_info")

        command_time_limit = d.get("command_time_limit")

        return UpdateSuiteAutoTestData(
            **base,
            steps=steps,
            rubric_row_id=rubric_row_id,
            network_disabled=network_disabled,
            id=id,
            submission_info=submission_info,
            command_time_limit=command_time_limit,
            raw_data=d,
        )
