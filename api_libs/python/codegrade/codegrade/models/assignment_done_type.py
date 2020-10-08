from enum import Enum


class AssignmentDoneType(str, Enum):
    ASSIGNED_ONLY = "assigned_only"
    ALL_GRADERS = "all_graders"
