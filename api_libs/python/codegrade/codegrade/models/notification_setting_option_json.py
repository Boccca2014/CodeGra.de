from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .email_notification_types import EmailNotificationTypes
from .notification_reasons import NotificationReasons
from .types import File


@dataclass
class NotificationSettingOptionJSON:
    """The JSON serialization schema for a single notification setting option."""

    reason: "Union[NotificationReasons]"
    explanation: "str"
    value: "Union[EmailNotificationTypes]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        if isinstance(self.reason, NotificationReasons):
            reason = self.reason.value

        res["reason"] = reason
        explanation = self.explanation
        res["explanation"] = explanation
        if isinstance(self.value, EmailNotificationTypes):
            value = self.value.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> NotificationSettingOptionJSON:
        base = {}

        def _parse_reason(data: Dict[str, Any]) -> Union[NotificationReasons]:
            reason: Union[NotificationReasons] = d["reason"]
            reason = NotificationReasons(reason)

            return reason

        reason = _parse_reason(d["reason"])

        explanation = d["explanation"]

        def _parse_value(data: Dict[str, Any]) -> Union[EmailNotificationTypes]:
            value: Union[EmailNotificationTypes] = d["value"]
            value = EmailNotificationTypes(value)

            return value

        value = _parse_value(d["value"])

        return NotificationSettingOptionJSON(**base, reason=reason, explanation=explanation, value=value, raw_data=d,)
