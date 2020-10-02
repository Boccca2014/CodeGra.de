from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .auto_test_fixture_as_json import AutoTestFixtureAsJSON
from .auto_test_run_as_extended_json import AutoTestRunAsExtendedJSON
from .auto_test_set_as_json import AutoTestSetAsJSON
from .types import File


@dataclass
class ResultDataGetAutoTestGet:
    """  """

    id: "int"
    fixtures: "List[AutoTestFixtureAsJSON]"
    run_setup_script: "str"
    setup_script: "str"
    finalize_script: "str"
    grade_calculation: "Optional[str]"
    sets: "List[AutoTestSetAsJSON]"
    assignment_id: "int"
    runs: "List[AutoTestRunAsExtendedJSON]"
    results_always_visible: "Optional[bool]"
    prefer_teacher_revision: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        fixtures = []
        for fixtures_item_data in self.fixtures:
            fixtures_item = maybe_to_dict(fixtures_item_data)

            fixtures.append(fixtures_item)

        res["fixtures"] = fixtures
        run_setup_script = self.run_setup_script
        res["run_setup_script"] = run_setup_script
        setup_script = self.setup_script
        res["setup_script"] = setup_script
        finalize_script = self.finalize_script
        res["finalize_script"] = finalize_script
        grade_calculation = self.grade_calculation
        res["grade_calculation"] = grade_calculation
        sets = []
        for sets_item_data in self.sets:
            sets_item = maybe_to_dict(sets_item_data)

            sets.append(sets_item)

        res["sets"] = sets
        assignment_id = self.assignment_id
        res["assignment_id"] = assignment_id
        runs = []
        for runs_item_data in self.runs:
            runs_item = maybe_to_dict(runs_item_data)

            runs.append(runs_item)

        res["runs"] = runs
        results_always_visible = self.results_always_visible
        res["results_always_visible"] = results_always_visible
        prefer_teacher_revision = self.prefer_teacher_revision
        res["prefer_teacher_revision"] = prefer_teacher_revision

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> ResultDataGetAutoTestGet:
        base = {}
        id = d["id"]

        fixtures = []
        for fixtures_item_data in d["fixtures"]:
            fixtures_item = AutoTestFixtureAsJSON.from_dict(fixtures_item_data)

            fixtures.append(fixtures_item)

        run_setup_script = d["run_setup_script"]

        setup_script = d["setup_script"]

        finalize_script = d["finalize_script"]

        grade_calculation = d["grade_calculation"]

        sets = []
        for sets_item_data in d["sets"]:
            sets_item = AutoTestSetAsJSON.from_dict(sets_item_data)

            sets.append(sets_item)

        assignment_id = d["assignment_id"]

        runs = []
        for runs_item_data in d["runs"]:
            runs_item = AutoTestRunAsExtendedJSON.from_dict(runs_item_data)

            runs.append(runs_item)

        results_always_visible = d["results_always_visible"]

        prefer_teacher_revision = d["prefer_teacher_revision"]

        return ResultDataGetAutoTestGet(
            **base,
            id=id,
            fixtures=fixtures,
            run_setup_script=run_setup_script,
            setup_script=setup_script,
            finalize_script=finalize_script,
            grade_calculation=grade_calculation,
            sets=sets,
            assignment_id=assignment_id,
            runs=runs,
            results_always_visible=results_always_visible,
            prefer_teacher_revision=prefer_teacher_revision,
            raw_data=d,
        )
