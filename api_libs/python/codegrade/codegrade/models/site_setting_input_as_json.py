from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union

from ..utils import maybe_to_dict
from .types import File


@dataclass
class SiteSettingInputAsJSON1:
    """"""

    name: 'Literal["AUTO_TEST_MAX_TIME_COMMAND"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON1:
        base = {}
        if d["name"] != "AUTO_TEST_MAX_TIME_COMMAND":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON1(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON2:
    """"""

    name: 'Literal["AUTO_TEST_HEARTBEAT_INTERVAL"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON2:
        base = {}
        if d["name"] != "AUTO_TEST_HEARTBEAT_INTERVAL":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON2(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON3:
    """"""

    name: 'Literal["AUTO_TEST_HEARTBEAT_MAX_MISSED"]'
    value: "Optional[int]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON3:
        base = {}
        if d["name"] != "AUTO_TEST_HEARTBEAT_MAX_MISSED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON3(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON4:
    """"""

    name: 'Literal["AUTO_TEST_MAX_JOBS_PER_RUNNER"]'
    value: "Optional[int]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON4:
        base = {}
        if d["name"] != "AUTO_TEST_MAX_JOBS_PER_RUNNER":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON4(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON5:
    """"""

    name: 'Literal["AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS"]'
    value: "Optional[int]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON5:
        base = {}
        if d["name"] != "AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON5(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON6:
    """"""

    name: 'Literal["EXAM_LOGIN_MAX_LENGTH"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON6:
        base = {}
        if d["name"] != "EXAM_LOGIN_MAX_LENGTH":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON6(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON7:
    """"""

    name: 'Literal["LOGIN_TOKEN_BEFORE_TIME"]'
    value: "Optional[List[Union[int, str]]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = []
        for value_item_data in self.value:
            if isinstance(value_item_data, int):
                value_item = value_item_data
            else:
                value_item = value_item_data

            value.append(value_item)

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON7:
        base = {}
        if d["name"] != "LOGIN_TOKEN_BEFORE_TIME":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = []
        for value_item_data in d["value"]:

            def _parse_value_item(data: Dict[str, Any]) -> Union[int, str]:
                value_item: Union[int, str] = value_item_data
                if isinstance(value_item, int):
                    return value_item
                if isinstance(value_item, str):
                    return value_item

                raise AssertionError("Could not transform: {}".format(property.python_name))

            value_item = _parse_value_item(value_item_data)

            value.append(value_item)

        return SiteSettingInputAsJSON7(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON8:
    """"""

    name: 'Literal["MIN_PASSWORD_SCORE"]'
    value: "Optional[int]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON8:
        base = {}
        if d["name"] != "MIN_PASSWORD_SCORE":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON8(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON9:
    """"""

    name: 'Literal["RESET_TOKEN_TIME"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON9:
        base = {}
        if d["name"] != "RESET_TOKEN_TIME":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON9(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON10:
    """"""

    name: 'Literal["SETTING_TOKEN_TIME"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON10:
        base = {}
        if d["name"] != "SETTING_TOKEN_TIME":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON10(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON11:
    """"""

    name: 'Literal["SITE_EMAIL"]'
    value: "Optional[str]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON11:
        base = {}
        if d["name"] != "SITE_EMAIL":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON11(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON12:
    """"""

    name: 'Literal["MAX_NUMBER_OF_FILES"]'
    value: "Optional[int]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON12:
        base = {}
        if d["name"] != "MAX_NUMBER_OF_FILES":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON12(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON13:
    """"""

    name: 'Literal["MAX_LARGE_UPLOAD_SIZE"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON13:
        base = {}
        if d["name"] != "MAX_LARGE_UPLOAD_SIZE":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON13(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON14:
    """"""

    name: 'Literal["MAX_NORMAL_UPLOAD_SIZE"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON14:
        base = {}
        if d["name"] != "MAX_NORMAL_UPLOAD_SIZE":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON14(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON15:
    """"""

    name: 'Literal["MAX_FILE_SIZE"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON15:
        base = {}
        if d["name"] != "MAX_FILE_SIZE":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON15(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON16:
    """"""

    name: 'Literal["JWT_ACCESS_TOKEN_EXPIRES"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON16:
        base = {}
        if d["name"] != "JWT_ACCESS_TOKEN_EXPIRES":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON16(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON17:
    """"""

    name: 'Literal["MAX_LINES"]'
    value: "Optional[int]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON17:
        base = {}
        if d["name"] != "MAX_LINES":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON17(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON18:
    """"""

    name: 'Literal["NOTIFICATION_POLL_TIME"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON18:
        base = {}
        if d["name"] != "NOTIFICATION_POLL_TIME":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON18(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON19:
    """"""

    name: 'Literal["RELEASE_MESSAGE_MAX_TIME"]'
    value: "Optional[Union[int, str]]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        if self.value is None:
            value: Optional[Union[int, str]] = None
        elif isinstance(self.value, int):
            value = self.value
        else:
            value = self.value

        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON19:
        base = {}
        if d["name"] != "RELEASE_MESSAGE_MAX_TIME":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        def _parse_value(data: Optional[Dict[str, Any]]) -> Optional[Union[int, str]]:
            if data is None:
                return None

            value: Optional[Union[int, str]] = d["value"]
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return value

            raise AssertionError("Could not transform: {}".format(property.python_name))

        value = _parse_value(d["value"])

        return SiteSettingInputAsJSON19(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON20:
    """"""

    name: 'Literal["BLACKBOARD_ZIP_UPLOAD_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON20:
        base = {}
        if d["name"] != "BLACKBOARD_ZIP_UPLOAD_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON20(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON21:
    """"""

    name: 'Literal["RUBRICS_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON21:
        base = {}
        if d["name"] != "RUBRICS_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON21(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON22:
    """"""

    name: 'Literal["AUTOMATIC_LTI_ROLE_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON22:
        base = {}
        if d["name"] != "AUTOMATIC_LTI_ROLE_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON22(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON23:
    """"""

    name: 'Literal["LTI_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON23:
        base = {}
        if d["name"] != "LTI_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON23(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON24:
    """"""

    name: 'Literal["LINTERS_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON24:
        base = {}
        if d["name"] != "LINTERS_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON24(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON25:
    """"""

    name: 'Literal["INCREMENTAL_RUBRIC_SUBMISSION_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON25:
        base = {}
        if d["name"] != "INCREMENTAL_RUBRIC_SUBMISSION_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON25(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON26:
    """"""

    name: 'Literal["REGISTER_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON26:
        base = {}
        if d["name"] != "REGISTER_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON26(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON27:
    """"""

    name: 'Literal["GROUPS_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON27:
        base = {}
        if d["name"] != "GROUPS_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON27(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON28:
    """"""

    name: 'Literal["AUTO_TEST_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON28:
        base = {}
        if d["name"] != "AUTO_TEST_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON28(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON29:
    """"""

    name: 'Literal["COURSE_REGISTER_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON29:
        base = {}
        if d["name"] != "COURSE_REGISTER_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON29(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON30:
    """"""

    name: 'Literal["RENDER_HTML_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON30:
        base = {}
        if d["name"] != "RENDER_HTML_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON30(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON31:
    """"""

    name: 'Literal["EMAIL_STUDENTS_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON31:
        base = {}
        if d["name"] != "EMAIL_STUDENTS_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON31(**base, name=name, value=value, raw_data=d,)


@dataclass
class SiteSettingInputAsJSON32:
    """"""

    name: 'Literal["PEER_FEEDBACK_ENABLED"]'
    value: "Optional[bool]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        name = self.name

        res["name"] = name
        value = self.value
        res["value"] = value

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SiteSettingInputAsJSON32:
        base = {}
        if d["name"] != "PEER_FEEDBACK_ENABLED":
            raise ValueError("Wrong value for name: " + d["name"])
        name = d["name"]

        value = d["value"]

        return SiteSettingInputAsJSON32(**base, name=name, value=value, raw_data=d,)


SiteSettingInputAsJSON = Union[
    SiteSettingInputAsJSON1,
    SiteSettingInputAsJSON2,
    SiteSettingInputAsJSON3,
    SiteSettingInputAsJSON4,
    SiteSettingInputAsJSON5,
    SiteSettingInputAsJSON6,
    SiteSettingInputAsJSON7,
    SiteSettingInputAsJSON8,
    SiteSettingInputAsJSON9,
    SiteSettingInputAsJSON10,
    SiteSettingInputAsJSON11,
    SiteSettingInputAsJSON12,
    SiteSettingInputAsJSON13,
    SiteSettingInputAsJSON14,
    SiteSettingInputAsJSON15,
    SiteSettingInputAsJSON16,
    SiteSettingInputAsJSON17,
    SiteSettingInputAsJSON18,
    SiteSettingInputAsJSON19,
    SiteSettingInputAsJSON20,
    SiteSettingInputAsJSON21,
    SiteSettingInputAsJSON22,
    SiteSettingInputAsJSON23,
    SiteSettingInputAsJSON24,
    SiteSettingInputAsJSON25,
    SiteSettingInputAsJSON26,
    SiteSettingInputAsJSON27,
    SiteSettingInputAsJSON28,
    SiteSettingInputAsJSON29,
    SiteSettingInputAsJSON30,
    SiteSettingInputAsJSON31,
    SiteSettingInputAsJSON32,
]
