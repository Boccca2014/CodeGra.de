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
class LTI1p3ProviderBaseAsJSON(LTIProviderBaseBaseAsJSON):
    """  """

    capabilities: "Optional[Dict[Any, Any]]" = None
    version: 'Literal["lti1.3", None]' = None
    iss: "Optional[str]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        capabilities = self.capabilities if self.capabilities else None

        if self.capabilities is not None:
            res["capabilities"] = capabilities
        version = self.version

        if self.version is not None:
            res["version"] = version
        iss = self.iss
        if self.iss is not None:
            res["iss"] = iss

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LTI1p3ProviderBaseAsJSON:
        base = asdict(LTIProviderBaseBaseAsJSON.from_dict(d))
        base.pop("raw_data")
        capabilities = None
        if d.get("capabilities") is not None:
            capabilities = d.get("capabilities")

        version = d.get("version")

        iss = d.get("iss")

        return LTI1p3ProviderBaseAsJSON(**base, capabilities=capabilities, version=version, iss=iss, raw_data=d,)
