from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .types import File
from .user_as_json_without_group import UserAsJSONWithoutGroup


@dataclass
class GroupAsJSON:
    """The group as JSON."""

    id: "int"
    members: "List[UserAsJSONWithoutGroup]"
    name: "str"
    group_set_id: "int"
    created_at: "datetime.datetime"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        members = []
        for members_item_data in self.members:
            members_item = maybe_to_dict(members_item_data)

            members.append(members_item)

        res["members"] = members
        name = self.name
        res["name"] = name
        group_set_id = self.group_set_id
        res["group_set_id"] = group_set_id
        created_at = self.created_at.isoformat()

        res["created_at"] = created_at

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> GroupAsJSON:
        base = {}
        id = d["id"]

        members = []
        for members_item_data in d["members"]:
            members_item = UserAsJSONWithoutGroup.from_dict(cast(Dict[str, Any], members_item_data))

            members.append(members_item)

        name = d["name"]

        group_set_id = d["group_set_id"]

        created_at = datetime.datetime.fromisoformat(d["created_at"])

        return GroupAsJSON(
            **base, id=id, members=members, name=name, group_set_id=group_set_id, created_at=created_at, raw_data=d,
        )
