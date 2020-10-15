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
class LTI1p1ProviderNonFinalizedAsJSON(LTI1p1ProviderBaseAsJSON):
    """The JSON representation of a non finalized provider."""

    finalized: "Literal[False, None]" = None
    edit_secret: "Optional[str]" = None
    lms_consumer_key: "Optional[str]" = None
    lms_consumer_secret: "Optional[str]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        finalized = self.finalized

        if self.finalized is not None:
            res["finalized"] = finalized
        edit_secret = self.edit_secret
        if self.edit_secret is not None:
            res["edit_secret"] = edit_secret
        lms_consumer_key = self.lms_consumer_key
        if self.lms_consumer_key is not None:
            res["lms_consumer_key"] = lms_consumer_key
        lms_consumer_secret = self.lms_consumer_secret
        if self.lms_consumer_secret is not None:
            res["lms_consumer_secret"] = lms_consumer_secret

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LTI1p1ProviderNonFinalizedAsJSON:
        base = asdict(LTI1p1ProviderBaseAsJSON.from_dict(d))
        base.pop("raw_data")
        if d.get("finalized") != False:
            raise ValueError("Wrong value for finalized: " + d.get("finalized"))
        finalized = d.get("finalized")

        edit_secret = d.get("edit_secret")

        lms_consumer_key = d.get("lms_consumer_key")

        lms_consumer_secret = d.get("lms_consumer_secret")

        return LTI1p1ProviderNonFinalizedAsJSON(
            **base,
            finalized=finalized,
            edit_secret=edit_secret,
            lms_consumer_key=lms_consumer_key,
            lms_consumer_secret=lms_consumer_secret,
            raw_data=d,
        )
