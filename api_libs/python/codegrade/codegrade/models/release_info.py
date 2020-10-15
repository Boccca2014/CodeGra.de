from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .base_release_info import BaseReleaseInfo
from .types import File
from .ui_preference_name import UIPreferenceName


@dataclass
class ReleaseInfo(BaseReleaseInfo):
    """Information about the release running on the server."""

    version: "Optional[str]" = None
    date: "Optional[datetime.datetime]" = None
    message: "Optional[str]" = None
    ui_preference: "Optional[Union[Optional[UIPreferenceName]]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        version = self.version
        if self.version is not None:
            res["version"] = version
        date = self.date.isoformat() if self.date else None

        if self.date is not None:
            res["date"] = date
        message = self.message
        if self.message is not None:
            res["message"] = message
        if self.ui_preference is None:
            ui_preference: Optional[Union[Optional[UIPreferenceName]]] = None
        else:
            ui_preference = self.ui_preference.value if self.ui_preference else None

        if self.ui_preference is not None:
            res["ui_preference"] = ui_preference

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> ReleaseInfo:
        base = asdict(BaseReleaseInfo.from_dict(d))
        base.pop("raw_data")
        version = d.get("version")

        date = None
        if d.get("date") is not None:
            date = datetime.datetime.fromisoformat(cast(str, d.get("date")))

        message = d.get("message")

        def _parse_ui_preference(data: Dict[str, Any]) -> Optional[Union[Optional[UIPreferenceName]]]:
            ui_preference: Optional[Union[Optional[UIPreferenceName]]] = d.get("ui_preference")
            ui_preference = None
            if ui_preference is not None:
                ui_preference = UIPreferenceName(ui_preference)

            return ui_preference

        ui_preference = _parse_ui_preference(d.get("ui_preference"))

        return ReleaseInfo(
            **base, version=version, date=date, message=message, ui_preference=ui_preference, raw_data=d,
        )
