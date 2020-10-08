from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .abstract_role_as_json import AbstractRoleAsJSON
from .course_as_json import CourseAsJSON
from .types import File


@dataclass
class CourseRoleAsJSON(AbstractRoleAsJSON):
    """The JSON representation of a course role."""

    course: "Optional[Union[Optional[CourseAsJSON]]]" = None
    hidden: "Optional[bool]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        if self.course is None:
            course: Optional[Union[Optional[CourseAsJSON]]] = None
        else:
            course = maybe_to_dict(self.course) if self.course else None

        if self.course is not None:
            res["course"] = course
        hidden = self.hidden
        if self.hidden is not None:
            res["hidden"] = hidden

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> CourseRoleAsJSON:
        base = asdict(AbstractRoleAsJSON.from_dict(d))
        base.pop("raw_data")

        def _parse_course(data: Dict[str, Any]) -> Optional[Union[Optional[CourseAsJSON]]]:
            course: Optional[Union[Optional[CourseAsJSON]]] = d.get("course")
            course = None
            if course is not None:
                course = CourseAsJSON.from_dict(cast(Dict[str, Any], course))

            return course

        course = _parse_course(d.get("course"))

        hidden = d.get("hidden")

        return CourseRoleAsJSON(**base, course=course, hidden=hidden, raw_data=d,)
