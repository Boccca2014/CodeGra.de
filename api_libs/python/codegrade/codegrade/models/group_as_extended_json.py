from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .group_as_json import GroupAsJSON
from .types import File
from .user_as_json_without_group import UserAsJSONWithoutGroup


@dataclass
class GroupAsExtendedJSON(GroupAsJSON):
    """  """

    virtual_user: "Optional[Union[Optional[UserAsJSONWithoutGroup]]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        if self.virtual_user is None:
            virtual_user: Optional[Union[Optional[UserAsJSONWithoutGroup]]] = None
        else:
            virtual_user = maybe_to_dict(self.virtual_user) if self.virtual_user else None

        if self.virtual_user is not None:
            res["virtual_user"] = virtual_user

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> GroupAsExtendedJSON:
        base = GroupAsJSON.from_dict(d).to_dict()

        def _parse_virtual_user(data: Dict[str, Any]) -> Optional[Union[Optional[UserAsJSONWithoutGroup]]]:
            virtual_user: Optional[Union[Optional[UserAsJSONWithoutGroup]]] = d.get("virtual_user")
            virtual_user = None
            if virtual_user is not None:
                virtual_user = UserAsJSONWithoutGroup.from_dict(cast(Dict[str, Any], virtual_user))

            return virtual_user

        virtual_user = _parse_virtual_user(d.get("virtual_user"))

        return GroupAsExtendedJSON(**base, virtual_user=virtual_user, raw_data=d,)
