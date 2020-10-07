from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from typing_extensions import Literal

from ..utils import maybe_to_dict
from .lti1p3_provider_base_as_json import LTI1p3ProviderBaseAsJSON
from .types import File


@dataclass
class LTI1p3ProviderNonFinalizedAsJSON(LTI1p3ProviderBaseAsJSON):
    """A non finalized provider as JSON."""

    finalized: "Literal[False, None]" = None
    auth_login_url: "Optional[str]" = None
    auth_token_url: "Optional[str]" = None
    client_id: "Optional[str]" = None
    key_set_url: "Optional[str]" = None
    auth_audience: "Optional[str]" = None
    custom_fields: "Optional[Dict[Any, Any]]" = None
    public_jwk: "Optional[Dict[Any, Any]]" = None
    public_key: "Optional[str]" = None
    edit_secret: "Optional[str]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        finalized = self.finalized

        if self.finalized is not None:
            res["finalized"] = finalized
        auth_login_url = self.auth_login_url
        if self.auth_login_url is not None:
            res["auth_login_url"] = auth_login_url
        auth_token_url = self.auth_token_url
        if self.auth_token_url is not None:
            res["auth_token_url"] = auth_token_url
        client_id = self.client_id
        if self.client_id is not None:
            res["client_id"] = client_id
        key_set_url = self.key_set_url
        if self.key_set_url is not None:
            res["key_set_url"] = key_set_url
        auth_audience = self.auth_audience
        if self.auth_audience is not None:
            res["auth_audience"] = auth_audience
        custom_fields = self.custom_fields if self.custom_fields else None

        if self.custom_fields is not None:
            res["custom_fields"] = custom_fields
        public_jwk = self.public_jwk if self.public_jwk else None

        if self.public_jwk is not None:
            res["public_jwk"] = public_jwk
        public_key = self.public_key
        if self.public_key is not None:
            res["public_key"] = public_key
        edit_secret = self.edit_secret
        if self.edit_secret is not None:
            res["edit_secret"] = edit_secret

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LTI1p3ProviderNonFinalizedAsJSON:
        base = asdict(LTI1p3ProviderBaseAsJSON.from_dict(d))
        base.pop("raw_data")
        finalized = d.get("finalized")

        auth_login_url = d.get("auth_login_url")

        auth_token_url = d.get("auth_token_url")

        client_id = d.get("client_id")

        key_set_url = d.get("key_set_url")

        auth_audience = d.get("auth_audience")

        custom_fields = None
        if d.get("custom_fields") is not None:
            custom_fields = d.get("custom_fields")

        public_jwk = None
        if d.get("public_jwk") is not None:
            public_jwk = d.get("public_jwk")

        public_key = d.get("public_key")

        edit_secret = d.get("edit_secret")

        return LTI1p3ProviderNonFinalizedAsJSON(
            **base,
            finalized=finalized,
            auth_login_url=auth_login_url,
            auth_token_url=auth_token_url,
            client_id=client_id,
            key_set_url=key_set_url,
            auth_audience=auth_audience,
            custom_fields=custom_fields,
            public_jwk=public_jwk,
            public_key=public_key,
            edit_secret=edit_secret,
            raw_data=d,
        )
