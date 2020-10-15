from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .auto_test_suite_as_json import AutoTestSuiteAsJSON
from .types import File


@dataclass
class AutoTestSetAsJSON:
    """The result as JSON."""

    id: "int"
    suites: "List[AutoTestSuiteAsJSON]"
    stop_points: "float"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        suites = []
        for suites_item_data in self.suites:
            suites_item = maybe_to_dict(suites_item_data)

            suites.append(suites_item)

        res["suites"] = suites
        stop_points = self.stop_points
        res["stop_points"] = stop_points

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AutoTestSetAsJSON:
        base = {}
        id = d["id"]

        suites = []
        for suites_item_data in d["suites"]:
            suites_item = AutoTestSuiteAsJSON.from_dict(cast(Dict[str, Any], suites_item_data))

            suites.append(suites_item)

        stop_points = d["stop_points"]

        return AutoTestSetAsJSON(**base, id=id, suites=suites, stop_points=stop_points, raw_data=d,)
