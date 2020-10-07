from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import response_code_matches

if TYPE_CHECKING:
    from ..client import AuthenticatedClient, Client

from typing import Dict, cast

from ..models.base_error import BaseError
from ..models.course_as_extended_json import CourseAsExtendedJSON
from ..models.course_registration_link_as_json import CourseRegistrationLinkAsJSON
from ..models.course_snippet_as_json import CourseSnippetAsJSON
from ..models.group_set_as_json import GroupSetAsJSON
from ..models.patch_course_data import PatchCourseData
from ..models.put_enroll_link_course_data import PutEnrollLinkCourseData


async def get_all(
    *, client: "AuthenticatedClient",
) -> Union[
    List[CourseAsExtendedJSON],
]:

    """ Return all Course objects the current user is a member of. """
    url = "{}/api/v1/courses/".format(client.base_url,)

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
        return [CourseAsExtendedJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


async def put_enroll_link(
    *, client: "Client", course_id: "int", json_body: PutEnrollLinkCourseData,
) -> Union[
    CourseRegistrationLinkAsJSON,
]:

    """ Create or edit an enroll link. """
    url = "{}/api/v1/courses/{courseId}/registration_links/".format(client.base_url, courseId=course_id,)

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
        return CourseRegistrationLinkAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


async def get_group_sets(
    *, client: "AuthenticatedClient", course_id: "int",
) -> Union[
    List[GroupSetAsJSON],
]:

    """ Get the all the group sets of a given course. """
    url = "{}/api/v1/courses/{courseId}/group_sets/".format(client.base_url, courseId=course_id,)

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
        return [GroupSetAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


async def get_snippets(
    *, client: "AuthenticatedClient", course_id: "int",
) -> Union[
    List[CourseSnippetAsJSON],
]:

    """ Get all snippets (<span data-role=\"class\">.models.CourseSnippet</span>) of the given """
    url = "{}/api/v1/courses/{courseId}/snippets/".format(client.base_url, courseId=course_id,)

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
        return [CourseSnippetAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


async def delete_role(
    *, client: "AuthenticatedClient", course_id: "int", role_id: "int",
) -> Union[
    None,
]:

    """ Remove a CourseRole from the given Course. """
    url = "{}/api/v1/courses/{courseId}/roles/{roleId}".format(client.base_url, courseId=course_id, roleId=role_id,)

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


async def get(
    *, client: "AuthenticatedClient", course_id: "int",
) -> Union[
    CourseAsExtendedJSON,
]:

    """ Return course data for a given <span data-role=\"class\">.models.Course</span>. """
    url = "{}/api/v1/courses/{courseId}".format(client.base_url, courseId=course_id,)

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


async def patch(
    *, client: "AuthenticatedClient", course_id: "int", json_body: PatchCourseData,
) -> Union[
    CourseAsExtendedJSON,
]:

    """ Update the given <span data-role=\"class\">.models.Course</span> with new values. """
    url = "{}/api/v1/courses/{courseId}".format(client.base_url, courseId=course_id,)

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
