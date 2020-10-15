from enum import Enum


class NotificationReasons(str, Enum):
    ASSIGNEE = "assignee"
    AUTHOR = "author"
    REPLIED = "replied"
