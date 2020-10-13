from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .email_notification_types import EmailNotificationTypes
from .notification_setting_option_json import NotificationSettingOptionJSON
from .types import File


@dataclass
class NotificationSettingJSON:
    """The JSON serialization schema for <span data-role="class">.NotificationsSetting</span>."""

    options: "List[NotificationSettingOptionJSON]"
    possible_values: "List[EmailNotificationTypes]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        options = []
        for options_item_data in self.options:
            options_item = maybe_to_dict(options_item_data)

            options.append(options_item)

        res["options"] = options
        possible_values = []
        for possible_values_item_data in self.possible_values:
            possible_values_item = possible_values_item_data.value

            possible_values.append(possible_values_item)

        res["possible_values"] = possible_values

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> NotificationSettingJSON:
        base = {}
        options = []
        for options_item_data in d["options"]:
            options_item = NotificationSettingOptionJSON.from_dict(cast(Dict[str, Any], options_item_data))

            options.append(options_item)

        possible_values = []
        for possible_values_item_data in d["possible_values"]:
            possible_values_item = EmailNotificationTypes(possible_values_item_data)

            possible_values.append(possible_values_item)

        return NotificationSettingJSON(**base, options=options, possible_values=possible_values, raw_data=d,)
