from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import maybe_to_dict, response_code_matches, to_multipart, try_any

if TYPE_CHECKING:
    from ..client import AuthenticatedClient, Client

from typing import Dict, cast

from ..models.base_error import BaseError
from ..models.course_as_extended_json import CourseAsExtendedJSON
from ..models.course_snippet_as_json import CourseSnippetAsJSON
from ..models.group_set_as_json import GroupSetAsJSON
from ..models.patch_course_data import PatchCourseData


def get_all(
    *, client: "AuthenticatedClient", extra_parameters: Mapping[str, str] = None,
) -> Union[
    List[CourseAsExtendedJSON],
]:

    """  """
    url = "{}/api/v1/courses/".format(client.base_url)

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
        return [CourseAsExtendedJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


def get_group_sets(
    *, client: "AuthenticatedClient", course_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    List[GroupSetAsJSON],
]:

    """  """
    url = "{}/api/v1/courses/{courseId}/group_sets/".format(client.base_url, courseId=course_id)

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
        return [GroupSetAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


def get_snippets(
    *, client: "AuthenticatedClient", course_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    List[CourseSnippetAsJSON],
]:

    """  """
    url = "{}/api/v1/courses/{courseId}/snippets/".format(client.base_url, courseId=course_id)

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
        return [CourseSnippetAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


def delete_role(
    *, client: "AuthenticatedClient", course_id: "int", role_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    None,
]:

    """  """
    url = "{}/api/v1/courses/{courseId}/roles/{roleId}".format(client.base_url, courseId=course_id, roleId=role_id)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    if extra_parameters:
        params.update(extra_parameters)

    response = httpx.delete(url=url, headers=headers, params=params,)

    if response_code_matches(response.status_code, 204):
        return None
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


def get(
    *, client: "AuthenticatedClient", course_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    CourseAsExtendedJSON,
]:

    """  """
    url = "{}/api/v1/courses/{courseId}".format(client.base_url, courseId=course_id)

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
        return CourseAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json()))
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


def patch(
    json_body: PatchCourseData,
    *,
    client: "AuthenticatedClient",
    course_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    CourseAsExtendedJSON,
]:

    """  """
    url = "{}/api/v1/courses/{courseId}".format(client.base_url, courseId=course_id)

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

    response = httpx.patch(url=url, headers=headers, json=json_json_body, params=params,)

    if response_code_matches(response.status_code, 200):
        return CourseAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json()))
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
