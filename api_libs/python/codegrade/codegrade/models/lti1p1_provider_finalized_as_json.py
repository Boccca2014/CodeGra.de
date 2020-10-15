from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from typing_extensions import Literal

from ..utils import maybe_to_dict
from .lti1p1_provider_base_as_json import LTI1p1ProviderBaseAsJSON
from .types import File


@dataclass
class LTI1p1ProviderFinalizedAsJSON(LTI1p1ProviderBaseAsJSON):
    """The JSON representation of a finalized provider."""

    finalized: "Literal[True, None]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        finalized = self.finalized

        if self.finalized is not None:
            res["finalized"] = finalized

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LTI1p1ProviderFinalizedAsJSON:
        base = asdict(LTI1p1ProviderBaseAsJSON.from_dict(d))
        base.pop("raw_data")
        if d.get("finalized") != True:
            raise ValueError("Wrong value for finalized: " + d.get("finalized"))
        finalized = d.get("finalized")

        return LTI1p1ProviderFinalizedAsJSON(**base, finalized=finalized, raw_data=d,)
