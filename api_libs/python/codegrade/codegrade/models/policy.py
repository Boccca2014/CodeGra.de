from enum import Enum


class Policy(str, Enum):
    DENY_ALL_FILES = "deny_all_files"
    ALLOW_ALL_FILES = "allow_all_files"
