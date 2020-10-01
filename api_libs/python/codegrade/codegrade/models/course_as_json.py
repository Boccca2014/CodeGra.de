from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .course_state import CourseState
from .lti_provider_base_as_json import LTIProviderBaseAsJSON
from .types import File


@dataclass
class CourseAsJSON:
    """  """

    id: "int"
    name: "str"
    created_at: "datetime.datetime"
    is_lti: "bool"
    virtual: "bool"
    lti_provider: "Optional[Union[LTIProviderBaseAsJSON]]"
    state: "Union[CourseState]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        name = self.name
        res["name"] = name
        created_at = self.created_at.isoformat()

        res["created_at"] = created_at
        is_lti = self.is_lti
        res["is_lti"] = is_lti
        virtual = self.virtual
        res["virtual"] = virtual
        if self.lti_provider is None:
            lti_provider = None
        if isinstance(self.lti_provider, LTIProviderBaseAsJSON):
            lti_provider = maybe_to_dict(self.lti_provider)

        res["lti_provider"] = lti_provider
        if isinstance(self.state, CourseState):
            state = self.state.value

        res["state"] = state

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> CourseAsJSON:
        base = {}
        id = d["id"]

        name = d["name"]

        created_at = datetime.datetime.fromisoformat(d["created_at"])

        is_lti = d["is_lti"]

        virtual = d["virtual"]

        def _parse_lti_provider(data: Optional[Dict[str, Any]]) -> Optional[Union[LTIProviderBaseAsJSON]]:
            if data is None:
                return None

            lti_provider: Optional[Union[LTIProviderBaseAsJSON]] = d["lti_provider"]
            lti_provider = LTIProviderBaseAsJSON.from_dict(lti_provider)

            return lti_provider

        lti_provider = _parse_lti_provider(d["lti_provider"])

        def _parse_state(data: Dict[str, Any]) -> Union[CourseState]:
            state: Union[CourseState] = d["state"]
            state = CourseState(state)

            return state

        state = _parse_state(d["state"])

        return CourseAsJSON(
            **base,
            id=id,
            name=name,
            created_at=created_at,
            is_lti=is_lti,
            virtual=virtual,
            lti_provider=lti_provider,
            state=state,
            raw_data=d,
        )
