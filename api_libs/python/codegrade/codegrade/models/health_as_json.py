from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class HealthAsJSON:
    """Information about the health of this instance."""

    application: "bool"
    database: "bool"
    uploads: "bool"
    broker: "bool"
    mirror_uploads: "bool"
    temp_dir: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        application = self.application
        res["application"] = application
        database = self.database
        res["database"] = database
        uploads = self.uploads
        res["uploads"] = uploads
        broker = self.broker
        res["broker"] = broker
        mirror_uploads = self.mirror_uploads
        res["mirror_uploads"] = mirror_uploads
        temp_dir = self.temp_dir
        res["temp_dir"] = temp_dir

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> HealthAsJSON:
        base = {}
        application = d["application"]

        database = d["database"]

        uploads = d["uploads"]

        broker = d["broker"]

        mirror_uploads = d["mirror_uploads"]

        temp_dir = d["temp_dir"]

        return HealthAsJSON(
            **base,
            application=application,
            database=database,
            uploads=uploads,
            broker=broker,
            mirror_uploads=mirror_uploads,
            temp_dir=temp_dir,
            raw_data=d,
        )
