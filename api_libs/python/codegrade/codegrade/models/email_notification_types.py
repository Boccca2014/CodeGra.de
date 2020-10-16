from enum import Enum


class EmailNotificationTypes(str, Enum):
    DIRECT = "direct"
    DAILY = "daily"
    WEEKLY = "weekly"
    OFF = "off"
