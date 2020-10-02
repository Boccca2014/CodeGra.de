from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from ._fixture_like import _FixtureLike
from .types import File


@dataclass
class JsonPatchAutoTest:
    """  """

    setup_script: "Optional[str]" = None
    run_setup_script: "Optional[str]" = None
    has_new_fixtures: "Optional[bool]" = None
    grade_calculation: "Optional[str]" = None
    results_always_visible: "Optional[bool]" = None
    prefer_teacher_revision: "Optional[bool]" = None
    fixtures: "Optional[List[_FixtureLike]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        setup_script = self.setup_script
        if self.setup_script is not None:
            res["setup_script"] = setup_script
        run_setup_script = self.run_setup_script
        if self.run_setup_script is not None:
            res["run_setup_script"] = run_setup_script
        has_new_fixtures = self.has_new_fixtures
        if self.has_new_fixtures is not None:
            res["has_new_fixtures"] = has_new_fixtures
        grade_calculation = self.grade_calculation
        if self.grade_calculation is not None:
            res["grade_calculation"] = grade_calculation
        results_always_visible = self.results_always_visible
        if self.results_always_visible is not None:
            res["results_always_visible"] = results_always_visible
        prefer_teacher_revision = self.prefer_teacher_revision
        if self.prefer_teacher_revision is not None:
            res["prefer_teacher_revision"] = prefer_teacher_revision
        if self.fixtures is None:
            fixtures = None
        else:
            fixtures = []
            for fixtures_item_data in self.fixtures:
                fixtures_item = maybe_to_dict(fixtures_item_data)

                fixtures.append(fixtures_item)

        if self.fixtures is not None:
            res["fixtures"] = fixtures

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> JsonPatchAutoTest:
        base = {}
        setup_script = d.get("setup_script")

        run_setup_script = d.get("run_setup_script")

        has_new_fixtures = d.get("has_new_fixtures")

        grade_calculation = d.get("grade_calculation")

        results_always_visible = d.get("results_always_visible")

        prefer_teacher_revision = d.get("prefer_teacher_revision")

        fixtures = []
        for fixtures_item_data in d.get("fixtures") or []:
            fixtures_item = _FixtureLike.from_dict(fixtures_item_data)

            fixtures.append(fixtures_item)

        return JsonPatchAutoTest(
            **base,
            setup_script=setup_script,
            run_setup_script=run_setup_script,
            has_new_fixtures=has_new_fixtures,
            grade_calculation=grade_calculation,
            results_always_visible=results_always_visible,
            prefer_teacher_revision=prefer_teacher_revision,
            fixtures=fixtures,
            raw_data=d,
        )
