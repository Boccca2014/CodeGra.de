from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .auto_test_result_as_json import AutoTestResultAsJSON
from .auto_test_run_as_json import AutoTestRunAsJSON
from .types import File


@dataclass
class AutoTestRunAsExtendedJSON(AutoTestRunAsJSON):
    """The run as extended JSON."""

    results: "Optional[List[AutoTestResultAsJSON]]" = None
    setup_stdout: "Optional[str]" = None
    setup_stderr: "Optional[str]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        if self.results is None:
            results = None
        else:
            results = []
            for results_item_data in self.results:
                results_item = maybe_to_dict(results_item_data)

                results.append(results_item)

        if self.results is not None:
            res["results"] = results
        setup_stdout = self.setup_stdout
        if self.setup_stdout is not None:
            res["setup_stdout"] = setup_stdout
        setup_stderr = self.setup_stderr
        if self.setup_stderr is not None:
            res["setup_stderr"] = setup_stderr

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestRunAsExtendedJSON:
        base = asdict(AutoTestRunAsJSON.from_dict(d))
        base.pop("raw_data")
        results = []
        for results_item_data in d.get("results") or []:
            results_item = AutoTestResultAsJSON.from_dict(cast(Dict[str, Any], results_item_data))

            results.append(results_item)

        setup_stdout = d.get("setup_stdout")

        setup_stderr = d.get("setup_stderr")

        return AutoTestRunAsExtendedJSON(
            **base, results=results, setup_stdout=setup_stdout, setup_stderr=setup_stderr, raw_data=d,
        )
