from __future__ import annotations

import json
from dataclasses import asdict, astuple, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .json_create_auto_test import JsonCreateAutoTest
from .types import File


@dataclass
class CreateAutoTestData:
    """  """

    json: "JsonCreateAutoTest"
    fixture: "Optional[List[File]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        json = maybe_to_dict(self.json)

        res["json"] = json
        if self.fixture is None:
            fixture = None
        else:
            fixture = []
            for fixture_item_data in self.fixture:
                fixture_item = fixture_item_data.to_tuple()

                fixture.append(fixture_item)

        if self.fixture is not None:
            res["fixture"] = fixture

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> CreateAutoTestData:
        base = {}
        json = JsonCreateAutoTest.from_dict(d["json"])

        fixture = []
        for fixture_item_data in d.get("fixture") or []:
            fixture_item = fixture_item_data

            fixture.append(fixture_item)

        return CreateAutoTestData(**base, json=json, fixture=fixture, raw_data=d,)
