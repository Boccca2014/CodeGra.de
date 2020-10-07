from enum import Enum


class AssignmentStateEnum(str, Enum):
    HIDDEN = "hidden"
    OPEN = "open"
    DONE = "done"
