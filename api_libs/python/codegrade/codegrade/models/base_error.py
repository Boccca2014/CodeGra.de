from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional, cast

from ..utils import maybe_to_dict
from .api_codes import APICodes
from .types import File


@dataclass
class BaseError(Exception):
    """  """

    message: "Optional[str]" = None
    description: "Optional[str]" = None
    code: "Optional[APICodes]" = None
    request_id: "Optional[str]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return repr(self)

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        message = self.message
        if self.message is not None:
            res["message"] = message
        description = self.description
        if self.description is not None:
            res["description"] = description
        code = self.code.value if self.code else None

        if self.code is not None:
            res["code"] = code
        request_id = self.request_id
        if self.request_id is not None:
            res["request_id"] = request_id

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> BaseError:
        base = {}
        message = d.get("message")

        description = d.get("description")

        code = None
        if d.get("code") is not None:
            code = APICodes(d.get("code"))

        request_id = d.get("request_id")

        return BaseError(
            **base, message=message, description=description, code=code, request_id=request_id, raw_data=d,
        )
