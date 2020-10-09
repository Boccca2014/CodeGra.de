from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import response_code_matches

if TYPE_CHECKING:
    from ..client import AuthenticatedClient, Client

from ..models.base_error import BaseError
from ..models.opt_all_opts_as_json import OptAllOptsAsJSON
from ..models.opt_frontend_opts_as_json import OptFrontendOptsAsJSON


async def get_all(
    *, client: "Client",
) -> Union[
    Union[OptFrontendOptsAsJSON, OptAllOptsAsJSON],
]:

    """ Get the settings for this CodeGrade instance. """
    url = "{}/api/v1/site_settings/".format(client.base_url,)

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
                lambda: OptFrontendOptsAsJSON.from_dict(cast(Dict[str, Any], response.json())),
                lambda: OptAllOptsAsJSON.from_dict(cast(Dict[str, Any], response.json())),
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
