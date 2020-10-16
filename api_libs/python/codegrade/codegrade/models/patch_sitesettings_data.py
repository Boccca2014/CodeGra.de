from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .site_setting_input_as_json import SiteSettingInputAsJSON
from .types import File


@dataclass
class PatchSitesettingsData:
    """"""

    updates: "List[SiteSettingInputAsJSON]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        updates = []
        for updates_item_data in self.updates:
            updates_item = maybe_to_dict(updates_item_data)

            updates.append(updates_item)

        res["updates"] = updates

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> PatchSitesettingsData:
        base = {}
        updates = []
        for updates_item_data in d["updates"]:
            from . import site_setting_input_as_json

            err = None
            for opt in [
                site_setting_input_as_json.SiteSettingInputAsJSON1,
                site_setting_input_as_json.SiteSettingInputAsJSON2,
                site_setting_input_as_json.SiteSettingInputAsJSON3,
                site_setting_input_as_json.SiteSettingInputAsJSON4,
                site_setting_input_as_json.SiteSettingInputAsJSON5,
                site_setting_input_as_json.SiteSettingInputAsJSON6,
                site_setting_input_as_json.SiteSettingInputAsJSON7,
                site_setting_input_as_json.SiteSettingInputAsJSON8,
                site_setting_input_as_json.SiteSettingInputAsJSON9,
                site_setting_input_as_json.SiteSettingInputAsJSON10,
                site_setting_input_as_json.SiteSettingInputAsJSON11,
                site_setting_input_as_json.SiteSettingInputAsJSON12,
                site_setting_input_as_json.SiteSettingInputAsJSON13,
                site_setting_input_as_json.SiteSettingInputAsJSON14,
                site_setting_input_as_json.SiteSettingInputAsJSON15,
                site_setting_input_as_json.SiteSettingInputAsJSON16,
                site_setting_input_as_json.SiteSettingInputAsJSON17,
                site_setting_input_as_json.SiteSettingInputAsJSON18,
                site_setting_input_as_json.SiteSettingInputAsJSON19,
                site_setting_input_as_json.SiteSettingInputAsJSON20,
                site_setting_input_as_json.SiteSettingInputAsJSON21,
                site_setting_input_as_json.SiteSettingInputAsJSON22,
                site_setting_input_as_json.SiteSettingInputAsJSON23,
                site_setting_input_as_json.SiteSettingInputAsJSON24,
                site_setting_input_as_json.SiteSettingInputAsJSON25,
                site_setting_input_as_json.SiteSettingInputAsJSON26,
                site_setting_input_as_json.SiteSettingInputAsJSON27,
                site_setting_input_as_json.SiteSettingInputAsJSON28,
                site_setting_input_as_json.SiteSettingInputAsJSON29,
                site_setting_input_as_json.SiteSettingInputAsJSON30,
                site_setting_input_as_json.SiteSettingInputAsJSON31,
                site_setting_input_as_json.SiteSettingInputAsJSON32,
            ]:
                try:
                    updates_item = opt.from_dict(cast(Dict[str, Any], updates_item_data))
                except Exception as exc:
                    err = exc
                else:
                    break
            else:
                raise err
            del err

            updates.append(updates_item)

        return PatchSitesettingsData(**base, updates=updates, raw_data=d,)
