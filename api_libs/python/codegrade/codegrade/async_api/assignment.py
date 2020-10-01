from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import response_code_matches

if TYPE_CHECKING:
    from ..client import AuthenticatedClient, Client

from typing import Dict, cast

from ..models.assignment_as_json import AssignmentAsJSON
from ..models.base_error import BaseError
from ..models.copy_rubric_assignment_data import CopyRubricAssignmentData
from ..models.course_as_extended_json import CourseAsExtendedJSON
from ..models.patch_assignment_data import PatchAssignmentData
from ..models.put_rubric_assignment_data import PutRubricAssignmentData
from ..models.rubric_row_base_as_json import RubricRowBaseAsJSON


async def get_all(
    *, client: "AuthenticatedClient",
) -> Union[
    List[AssignmentAsJSON],
]:

    """  """
    url = "{}/api/v1/assignments/".format(client.base_url,)

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
        return [AssignmentAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


async def get_rubric(
    *, client: "AuthenticatedClient", assignment_id: "int",
) -> Union[
    List[RubricRowBaseAsJSON],
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/rubrics/".format(client.base_url, assignmentId=assignment_id,)

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
        return [RubricRowBaseAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


async def put_rubric(
    *, client: "AuthenticatedClient", assignment_id: "int", json_body: PutRubricAssignmentData,
) -> Union[
    List[RubricRowBaseAsJSON],
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/rubrics/".format(client.base_url, assignmentId=assignment_id,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    json_json_body = maybe_to_dict(json_body)

    async with httpx.AsyncClient() as _client:
        response = await _client.put(url=url, headers=headers, json=json_json_body,)

    if response_code_matches(response.status_code, 200):
        return [RubricRowBaseAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


async def delete_rubric(
    *, client: "AuthenticatedClient", assignment_id: "int",
) -> Union[
    None,
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/rubrics/".format(client.base_url, assignmentId=assignment_id,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    async with httpx.AsyncClient() as _client:
        response = await _client.delete(url=url, headers=headers,)

    if response_code_matches(response.status_code, 204):
        return None
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


async def get_course(
    *, client: "AuthenticatedClient", assignment_id: "int",
) -> Union[
    CourseAsExtendedJSON,
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/course".format(client.base_url, assignmentId=assignment_id,)

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
        return CourseAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json()))
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


async def copy_rubric(
    *, client: "AuthenticatedClient", assignment_id: "int", json_body: CopyRubricAssignmentData,
) -> Union[
    List[RubricRowBaseAsJSON],
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/rubric".format(client.base_url, assignmentId=assignment_id,)

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
        return [RubricRowBaseAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


async def patch(
    *, client: "AuthenticatedClient", assignment_id: "int", json_body: PatchAssignmentData,
) -> Union[
    AssignmentAsJSON,
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}".format(client.base_url, assignmentId=assignment_id,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    json_json_body = maybe_to_dict(json_body)

    async with httpx.AsyncClient() as _client:
        response = await _client.patch(url=url, headers=headers, json=json_json_body,)

    if response_code_matches(response.status_code, 200):
        return AssignmentAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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
