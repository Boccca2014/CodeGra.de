from enum import Enum


class Key(str, Enum):
    DELETE_EMPTY_DIRECTORIES = "delete_empty_directories"
    REMOVE_LEADING_DIRECTORIES = "remove_leading_directories"
    ALLOW_OVERRIDE = "allow_override"
