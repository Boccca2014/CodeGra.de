from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import maybe_to_dict, response_code_matches, to_multipart, try_any

if TYPE_CHECKING:
    from ..client import AuthenticatedClient, Client

from typing import Dict, cast

from ..models.base_error import BaseError
from ..models.login_user_data import LoginUserData
from ..models.result_data_post_user_login import ResultDataPostUserLogin
from ..models.user_as_extended_json import UserAsExtendedJSON
from ..models.user_as_json import UserAsJSON


def get(
    *, client: "AuthenticatedClient", extra_parameters: Mapping[str, str] = None,
) -> Union[
    Union[UserAsExtendedJSON, UserAsJSON, Dict[str, Any]],
]:

    """Get the info of the currently logged in user."""
    url = "{}/api/v1/login".format(client.base_url)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    if extra_parameters:
        params.update(extra_parameters)

    response = httpx.get(url=url, headers=headers, params=params,)

    if response_code_matches(response.status_code, 200):
        return try_any(
            [
                lambda: UserAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json())),
                lambda: UserAsJSON.from_dict(cast(Dict[str, Any], response.json())),
                lambda: response.json(),
            ]
        )
    if response_code_matches(response.status_code, 400):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 409):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 401):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 403):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, "5XX"):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    else:
        raise ApiResponseError(response=response)


def login(
    json_body: LoginUserData, *, client: "Client", extra_parameters: Mapping[str, str] = None,
) -> Union[
    ResultDataPostUserLogin,
]:

    """Login using your username and password."""
    url = "{}/api/v1/login".format(client.base_url)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    if extra_parameters:
        params.update(extra_parameters)

    json_json_body = maybe_to_dict(json_body)

    response = httpx.post(url=url, headers=headers, json=json_json_body, params=params,)

    if response_code_matches(response.status_code, 200):
        return ResultDataPostUserLogin.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 400):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 409):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 401):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 403):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, "5XX"):
        raise BaseError.from_dict(cast(Dict[str, Any], response.json()))
    else:
        raise ApiResponseError(response=response)
