from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from typing_extensions import Literal

from ..utils import maybe_to_dict
from .lti_provider_base_base_as_json import LTIProviderBaseBaseAsJSON
from .types import File


@dataclass
class LTI1p1ProviderBaseAsJSON(LTIProviderBaseBaseAsJSON):
    """The base JSON representation of a LTI 1.1 provider."""

    version: 'Literal["lti1.1", None]' = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        version = self.version

        if self.version is not None:
            res["version"] = version

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LTI1p1ProviderBaseAsJSON:
        base = asdict(LTIProviderBaseBaseAsJSON.from_dict(d))
        base.pop("raw_data")
        if d.get("version") != "lti1.1":
            raise ValueError("Wrong value for version: " + d.get("version"))
        version = d.get("version")

        return LTI1p1ProviderBaseAsJSON(**base, version=version, raw_data=d,)
