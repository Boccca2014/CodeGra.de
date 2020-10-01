from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import maybe_to_dict, response_code_matches, to_multipart, try_any

if TYPE_CHECKING:
    from ..client import AuthenticatedClient, Client

from ..models.base_error import BaseError
from ..models.group_as_extended_json import GroupAsExtendedJSON


def get(
    *, client: "AuthenticatedClient", group_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    GroupAsExtendedJSON,
]:

    """  """
    url = "{}/api/v1/groups/{groupId}".format(client.base_url, groupId=group_id)

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
        return GroupAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json()))
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
