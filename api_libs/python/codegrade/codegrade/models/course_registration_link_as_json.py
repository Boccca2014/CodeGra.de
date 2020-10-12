from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .course_role_as_json import CourseRoleAsJSON
from .types import File


@dataclass
class CourseRegistrationLinkAsJSON:
    """The JSON representation of a course registration link."""

    id: "str"
    expiration_date: "datetime.datetime"
    role: "Union[CourseRoleAsJSON]"
    allow_register: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        expiration_date = self.expiration_date.isoformat()

        res["expiration_date"] = expiration_date
        if isinstance(self.role, CourseRoleAsJSON):
            role = maybe_to_dict(self.role)

        res["role"] = role
        allow_register = self.allow_register
        res["allow_register"] = allow_register

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> CourseRegistrationLinkAsJSON:
        base = {}
        id = d["id"]

        expiration_date = datetime.datetime.fromisoformat(d["expiration_date"])

        def _parse_role(data: Dict[str, Any]) -> Union[CourseRoleAsJSON]:
            role: Union[CourseRoleAsJSON] = d["role"]
            role = CourseRoleAsJSON.from_dict(cast(Dict[str, Any], role))

            return role

        role = _parse_role(d["role"])

        allow_register = d["allow_register"]

        return CourseRegistrationLinkAsJSON(
            **base, id=id, expiration_date=expiration_date, role=role, allow_register=allow_register, raw_data=d,
        )
