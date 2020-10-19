from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from ..utils import maybe_to_dict
from .types import File
from .ui_preference_name import UIPreferenceName


@dataclass
class PatchUiPreferenceUserSettingData:
    """"""

    name: "UIPreferenceName"
    value: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name.value

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> PatchUiPreferenceUserSettingData:
        base = {}
        name = UIPreferenceName(d["name"])

        value = d["value"]

        return PatchUiPreferenceUserSettingData(**base, name=name, value=value, raw_data=d,)
