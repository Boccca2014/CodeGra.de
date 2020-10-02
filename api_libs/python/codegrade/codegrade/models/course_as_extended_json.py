from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .assignment_as_json import AssignmentAsJSON
from .course_as_json import CourseAsJSON
from .course_snippet_as_json import CourseSnippetAsJSON
from .group_set_as_json import GroupSetAsJSON
from .types import File


@dataclass
class CourseAsExtendedJSON(CourseAsJSON):
    """  """

    assignments: "Optional[List[AssignmentAsJSON]]" = None
    group_sets: "Optional[List[GroupSetAsJSON]]" = None
    snippets: "Optional[List[CourseSnippetAsJSON]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        if self.assignments is None:
            assignments = None
        else:
            assignments = []
            for assignments_item_data in self.assignments:
                assignments_item = maybe_to_dict(assignments_item_data)

                assignments.append(assignments_item)

        if self.assignments is not None:
            res["assignments"] = assignments
        if self.group_sets is None:
            group_sets = None
        else:
            group_sets = []
            for group_sets_item_data in self.group_sets:
                group_sets_item = maybe_to_dict(group_sets_item_data)

                group_sets.append(group_sets_item)

        if self.group_sets is not None:
            res["group_sets"] = group_sets
        if self.snippets is None:
            snippets = None
        else:
            snippets = []
            for snippets_item_data in self.snippets:
                snippets_item = maybe_to_dict(snippets_item_data)

                snippets.append(snippets_item)

        if self.snippets is not None:
            res["snippets"] = snippets

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> CourseAsExtendedJSON:
        base = asdict(CourseAsJSON.from_dict(d))
        base.pop("raw_data")
        assignments = []
        for assignments_item_data in d.get("assignments") or []:
            assignments_item = AssignmentAsJSON.from_dict(assignments_item_data)

            assignments.append(assignments_item)

        group_sets = []
        for group_sets_item_data in d.get("group_sets") or []:
            group_sets_item = GroupSetAsJSON.from_dict(group_sets_item_data)

            group_sets.append(group_sets_item)

        snippets = []
        for snippets_item_data in d.get("snippets") or []:
            snippets_item = CourseSnippetAsJSON.from_dict(snippets_item_data)

            snippets.append(snippets_item)

        return CourseAsExtendedJSON(
            **base, assignments=assignments, group_sets=group_sets, snippets=snippets, raw_data=d,
        )
