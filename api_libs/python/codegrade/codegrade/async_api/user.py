from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import response_code_matches

if TYPE_CHECKING:
    from ..client import AuthenticatedClient, Client

from typing import Dict, cast

from ..models.base_error import BaseError
from ..models.login_user_data import LoginUserData
from ..models.result_data_post_user_login import ResultDataPostUserLogin
from ..models.user_as_extended_json import UserAsExtendedJSON
from ..models.user_as_json import UserAsJSON


async def get(
    *, client: "AuthenticatedClient",
) -> Union[
    Union[UserAsExtendedJSON, UserAsJSON, Dict[str, Any]],
]:

    """  """
    url = "{}/api/v1/login".format(client.base_url,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    async with httpx.AsyncClient() as _client:
        response = await _client.get(url=url, headers=headers,)

    if response_code_matches(response.status_code, 200):
        return try_any(
            [
                lambda: UserAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json())),
                lambda: UserAsJSON.from_dict(cast(Dict[str, Any], response.json())),
                lambda: response.json(),
            ]
        )
    if response_code_matches(response.status_code, 400):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 409):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 401):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 403):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, "5XX"):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    else:
        raise ApiResponseError(response=response)


async def login(
    *, client: "Client", json_body: LoginUserData,
) -> Union[
    ResultDataPostUserLogin,
]:

    """  """
    url = "{}/api/v1/login".format(client.base_url,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    json_json_body = maybe_to_dict(json_body)

    async with httpx.AsyncClient() as _client:
        response = await _client.post(url=url, headers=headers, json=json_json_body,)

    if response_code_matches(response.status_code, 200):
        return ResultDataPostUserLogin.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 400):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 409):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 401):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, 403):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    if response_code_matches(response.status_code, "5XX"):
        return BaseError.from_dict(cast(Dict[str, Any], response.json()))
    else:
        raise ApiResponseError(response=response)
