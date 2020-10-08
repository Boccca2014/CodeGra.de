from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from ..utils import maybe_to_dict
from .types import File


@dataclass
class PutEnrollLinkCourseData:
    """"""

    role_id: "int"
    expiration_date: "datetime.datetime"
    id: "Optional[str]" = None
    allow_register: "Optional[bool]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        role_id = self.role_id
        res["role_id"] = role_id
        expiration_date = self.expiration_date.isoformat()

        res["expiration_date"] = expiration_date
        id = self.id
        if self.id is not None:
            res["id"] = id
        allow_register = self.allow_register
        if self.allow_register is not None:
            res["allow_register"] = allow_register

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> PutEnrollLinkCourseData:
        base = {}
        role_id = d["role_id"]

        expiration_date = datetime.datetime.fromisoformat(d["expiration_date"])

        id = d.get("id")

        allow_register = d.get("allow_register")

        return PutEnrollLinkCourseData(
            **base, role_id=role_id, expiration_date=expiration_date, id=id, allow_register=allow_register, raw_data=d,
        )
