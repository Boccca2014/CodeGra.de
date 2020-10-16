from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .base_about_as_json import BaseAboutAsJSON
from .health_as_json import HealthAsJSON
from .types import File


@dataclass
class AboutAsJSON(BaseAboutAsJSON):
    """Information about this CodeGrade instance."""

    health: "Optional[Union[Optional[HealthAsJSON]]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        if self.health is None:
            health: Optional[Union[Optional[HealthAsJSON]]] = None
        else:
            health = maybe_to_dict(self.health) if self.health else None

        if self.health is not None:
            res["health"] = health

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AboutAsJSON:
        base = asdict(BaseAboutAsJSON.from_dict(d))
        base.pop("raw_data")

        def _parse_health(data: Dict[str, Any]) -> Optional[Union[Optional[HealthAsJSON]]]:
            health: Optional[Union[Optional[HealthAsJSON]]] = d.get("health")
            health = None
            if health is not None:
                health = HealthAsJSON.from_dict(cast(Dict[str, Any], health))

            return health

        health = _parse_health(d.get("health"))

        return AboutAsJSON(**base, health=health, raw_data=d,)
