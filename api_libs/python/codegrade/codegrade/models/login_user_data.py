from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union

from ..utils import maybe_to_dict
from .types import File


@dataclass
class LoginUserData_1:
    """ The data required when you want to login """

    username: "str"
    password: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        username = self.username
        res["username"] = username
        password = self.password
        res["password"] = password

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LoginUserData_1:
        base = {}
        username = d["username"]

        password = d["password"]

        return LoginUserData_1(**base, username=username, password=password, raw_data=d,)


@dataclass
class LoginUserData_2:
    """ The data required when you want to impersonate a user """

    username: "str"
    own_password: "str"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        username = self.username
        res["username"] = username
        own_password = self.own_password
        res["own_password"] = own_password

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LoginUserData_2:
        base = {}
        username = d["username"]

        own_password = d["own_password"]

        return LoginUserData_2(**base, username=username, own_password=own_password, raw_data=d,)


LoginUserData = Union[
    LoginUserData_1, LoginUserData_2,
]
