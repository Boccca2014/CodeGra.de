from enum import Enum


class RuleType(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE = "require"
