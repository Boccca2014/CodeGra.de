from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .types import File
from .user_as_extended_json import UserAsExtendedJSON


@dataclass
class ResultDataPostUserLogin:
    """When logging in this object will be given."""

    user: "Union[UserAsExtendedJSON]"
    access_token: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        if isinstance(self.user, UserAsExtendedJSON):
            user = maybe_to_dict(self.user)

        res["user"] = user
        access_token = self.access_token
        res["access_token"] = access_token

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> ResultDataPostUserLogin:
        base = {}

        def _parse_user(data: Dict[str, Any]) -> Union[UserAsExtendedJSON]:
            user: Union[UserAsExtendedJSON] = d["user"]
            user = UserAsExtendedJSON.from_dict(cast(Dict[str, Any], user))

            return user

        user = _parse_user(d["user"])

        access_token = d["access_token"]

        return ResultDataPostUserLogin(**base, user=user, access_token=access_token, raw_data=d,)
