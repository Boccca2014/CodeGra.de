from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class ResultDataGetUserSettingGetAllUiPreferences:
    """"""

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> ResultDataGetUserSettingGetAllUiPreferences:
        base = {}
        return ResultDataGetUserSettingGetAllUiPreferences(**base, raw_data=d,)
