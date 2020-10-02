from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class FileTree_AsJSONFile:
    """  """

    id: "str"
    name: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        name = self.name
        res["name"] = name

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> FileTree_AsJSONFile:
        base = {}
        id = d["id"]

        name = d["name"]

        return FileTree_AsJSONFile(**base, id=id, name=name, raw_data=d,)
