from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class CourseSnippetAsJSON:
    """  """

    id: "int"
    key: "str"
    value: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        key = self.key
        res["key"] = key
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> CourseSnippetAsJSON:
        base = {}
        id = d["id"]

        key = d["key"]

        value = d["value"]

        return CourseSnippetAsJSON(**base, id=id, key=key, value=value, raw_data=d,)
