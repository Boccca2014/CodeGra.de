from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .file_type import FileType
from .rule_type import RuleType
from .types import File


@dataclass
class FileRuleInputData:
    """  """

    rule_type: "RuleType"
    file_type: "FileType"
    name: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        rule_type = self.rule_type.value

        res["rule_type"] = rule_type
        file_type = self.file_type.value

        res["file_type"] = file_type
        name = self.name
        res["name"] = name

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> FileRuleInputData:
        base = {}
        rule_type = RuleType(d["rule_type"])

        file_type = FileType(d["file_type"])

        name = d["name"]

        return FileRuleInputData(**base, rule_type=rule_type, file_type=file_type, name=name, raw_data=d,)
