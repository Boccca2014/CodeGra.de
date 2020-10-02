from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .auto_test_result_as_json import AutoTestResultAsJSON
from .auto_test_step_result_as_json import AutoTestStepResultAsJSON
from .types import File


@dataclass
class AutoTestResultAsExtendedJSON(AutoTestResultAsJSON):
    """  """

    setup_stdout: "Optional[str]" = None
    setup_stderr: "Optional[str]" = None
    step_results: "Optional[List[AutoTestStepResultAsJSON]]" = None
    approx_waiting_before: "Optional[int]" = None
    final_result: "Optional[bool]" = None
    suite_files: "Optional[Dict[Any, Any]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        setup_stdout = self.setup_stdout
        if self.setup_stdout is not None:
            res["setup_stdout"] = setup_stdout
        setup_stderr = self.setup_stderr
        if self.setup_stderr is not None:
            res["setup_stderr"] = setup_stderr
        if self.step_results is None:
            step_results = None
        else:
            step_results = []
            for step_results_item_data in self.step_results:
                step_results_item = maybe_to_dict(step_results_item_data)

                step_results.append(step_results_item)

        if self.step_results is not None:
            res["step_results"] = step_results
        approx_waiting_before = self.approx_waiting_before
        if self.approx_waiting_before is not None:
            res["approx_waiting_before"] = approx_waiting_before
        final_result = self.final_result
        if self.final_result is not None:
            res["final_result"] = final_result
        suite_files = self.suite_files if self.suite_files else None

        if self.suite_files is not None:
            res["suite_files"] = suite_files

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestResultAsExtendedJSON:
        base = asdict(AutoTestResultAsJSON.from_dict(d))
        base.pop("raw_data")
        setup_stdout = d.get("setup_stdout")

        setup_stderr = d.get("setup_stderr")

        step_results = []
        for step_results_item_data in d.get("step_results") or []:
            step_results_item = AutoTestStepResultAsJSON.from_dict(step_results_item_data)

            step_results.append(step_results_item)

        approx_waiting_before = d.get("approx_waiting_before")

        final_result = d.get("final_result")

        suite_files = None
        if d.get("suite_files") is not None:
            suite_files = d.get("suite_files")

        return AutoTestResultAsExtendedJSON(
            **base,
            setup_stdout=setup_stdout,
            setup_stderr=setup_stderr,
            step_results=step_results,
            approx_waiting_before=approx_waiting_before,
            final_result=final_result,
            suite_files=suite_files,
            raw_data=d,
        )
