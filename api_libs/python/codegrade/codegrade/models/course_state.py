from enum import Enum


class CourseState(str, Enum):
    VISIBLE = "visible"
    ARCHIVED = "archived"
    DELETED = "deleted"
