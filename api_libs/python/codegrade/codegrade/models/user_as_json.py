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
class UserAsJSON(UserAsJSONWithoutGroup):
    """  """

    group: "Optional[Union[Optional[GroupAsJSON]]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        if self.group is None:
            group: Optional[Union[Optional[GroupAsJSON]]] = None
        if self.group is None:
            group = None
        else:
            group = maybe_to_dict(self.group) if self.group else None

        if self.group is not None:
            res["group"] = group

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> UserAsJSON:
        base = UserAsJSONWithoutGroup.from_dict(d).to_dict()

        def _parse_group(data: Optional[Dict[str, Any]]) -> Optional[Union[Optional[GroupAsJSON]]]:
            if data is None:
                return None

            group: Optional[Union[Optional[GroupAsJSON]]] = d.get("group")
            group = None
            if group is not None:
                group = GroupAsJSON.from_dict(cast(Dict[str, Any], group))

            return group

        group = _parse_group(d.get("group"))

        return UserAsJSON(**base, group=group, raw_data=d,)
