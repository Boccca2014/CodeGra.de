from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from ..utils import maybe_to_dict
from .email_notification_types import EmailNotificationTypes
from .notification_reasons import NotificationReasons
from .types import File


@dataclass
class PatchNotificationSettingUserSettingData:
    """"""

    reason: "NotificationReasons"
    value: "EmailNotificationTypes"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        reason = self.reason.value

        res["reason"] = reason
        value = self.value.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> PatchNotificationSettingUserSettingData:
        base = {}
        reason = NotificationReasons(d["reason"])

        value = EmailNotificationTypes(d["value"])

        return PatchNotificationSettingUserSettingData(**base, reason=reason, value=value, raw_data=d,)
