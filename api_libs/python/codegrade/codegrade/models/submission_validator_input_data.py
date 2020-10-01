from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .file_rule_input_data import FileRuleInputData
from .options_input_data import OptionsInputData
from .policy import Policy
from .types import File


@dataclass
class SubmissionValidatorInputData:
    """  """

    policy: "Policy"
    rules: "List[FileRuleInputData]"
    options: "List[OptionsInputData]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        policy = self.policy.value

        res["policy"] = policy
        rules = []
        for rules_item_data in self.rules:
            rules_item = maybe_to_dict(rules_item_data)

            rules.append(rules_item)

        res["rules"] = rules
        options = []
        for options_item_data in self.options:
            options_item = maybe_to_dict(options_item_data)

            options.append(options_item)

        res["options"] = options

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SubmissionValidatorInputData:
        base = {}
        policy = Policy(d["policy"])

        rules = []
        for rules_item_data in d["rules"]:
            rules_item = FileRuleInputData.from_dict(rules_item_data)

            rules.append(rules_item)

        options = []
        for options_item_data in d["options"]:
            options_item = OptionsInputData.from_dict(options_item_data)

            options.append(options_item)

        return SubmissionValidatorInputData(**base, policy=policy, rules=rules, options=options, raw_data=d,)
