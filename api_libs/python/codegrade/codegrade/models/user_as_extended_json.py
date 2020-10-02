from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File
from .user_as_json import UserAsJSON


@dataclass
class UserAsExtendedJSON(UserAsJSON):
    """  """

    email: "Optional[str]" = None
    hidden: "Optional[bool]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        email = self.email
        if self.email is not None:
            res["email"] = email
        hidden = self.hidden
        if self.hidden is not None:
            res["hidden"] = hidden

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> UserAsExtendedJSON:
        base = asdict(UserAsJSON.from_dict(d))
        base.pop("raw_data")
        email = d.get("email")

        hidden = d.get("hidden")

        return UserAsExtendedJSON(**base, email=email, hidden=hidden, raw_data=d,)
