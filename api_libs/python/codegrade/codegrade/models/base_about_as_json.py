from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .legacy_features_as_json import LegacyFeaturesAsJSON
from .opt_frontend_opts_as_json import OptFrontendOptsAsJSON
from .release_info import ReleaseInfo
from .types import File


@dataclass
class BaseAboutAsJSON:
    """The base information about this instance."""

    version: "Optional[str]"
    commit: "str"
    features: "Union[LegacyFeaturesAsJSON]"
    settings: "Union[OptFrontendOptsAsJSON]"
    release: "Union[ReleaseInfo]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        version = self.version
        res["version"] = version
        commit = self.commit
        res["commit"] = commit
        if isinstance(self.features, LegacyFeaturesAsJSON):
            features = maybe_to_dict(self.features)

        res["features"] = features
        if isinstance(self.settings, OptFrontendOptsAsJSON):
            settings = maybe_to_dict(self.settings)

        res["settings"] = settings
        if isinstance(self.release, ReleaseInfo):
            release = maybe_to_dict(self.release)

        res["release"] = release

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> BaseAboutAsJSON:
        base = {}
        version = d["version"]

        commit = d["commit"]

        def _parse_features(data: Dict[str, Any]) -> Union[LegacyFeaturesAsJSON]:
            features: Union[LegacyFeaturesAsJSON] = d["features"]
            features = LegacyFeaturesAsJSON.from_dict(cast(Dict[str, Any], features))

            return features

        features = _parse_features(d["features"])

        def _parse_settings(data: Dict[str, Any]) -> Union[OptFrontendOptsAsJSON]:
            settings: Union[OptFrontendOptsAsJSON] = d["settings"]
            settings = OptFrontendOptsAsJSON.from_dict(cast(Dict[str, Any], settings))

            return settings

        settings = _parse_settings(d["settings"])

        def _parse_release(data: Dict[str, Any]) -> Union[ReleaseInfo]:
            release: Union[ReleaseInfo] = d["release"]
            release = ReleaseInfo.from_dict(cast(Dict[str, Any], release))

            return release

        release = _parse_release(d["release"])

        return BaseAboutAsJSON(
            **base, version=version, commit=commit, features=features, settings=settings, release=release, raw_data=d,
        )
