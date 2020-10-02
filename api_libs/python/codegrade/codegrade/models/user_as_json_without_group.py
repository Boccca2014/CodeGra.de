from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class UserAsJSONWithoutGroup:
    """  """

    id: "int"
    name: "str"
    username: "str"
    is_test_student: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        name = self.name
        res["name"] = name
        username = self.username
        res["username"] = username
        is_test_student = self.is_test_student
        res["is_test_student"] = is_test_student

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> UserAsJSONWithoutGroup:
        base = {}
        id = d["id"]

        name = d["name"]

        username = d["username"]

        is_test_student = d["is_test_student"]

        return UserAsJSONWithoutGroup(
            **base, id=id, name=name, username=username, is_test_student=is_test_student, raw_data=d,
        )
