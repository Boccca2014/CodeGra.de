from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import maybe_to_dict, response_code_matches, to_multipart, try_any

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


def get_all(
    *, client: "AuthenticatedClient", extra_parameters: Mapping[str, str] = None,
) -> Union[
    List[AssignmentAsJSON],
]:

    """  """
    url = "{}/api/v1/assignments/".format(client.base_url)

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
        return [AssignmentAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


def get_rubric(
    *, client: "AuthenticatedClient", assignment_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    List[RubricRowBaseAsJSON],
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/rubrics/".format(client.base_url, assignmentId=assignment_id)

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
        return [RubricRowBaseAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


def put_rubric(
    json_body: PutRubricAssignmentData,
    *,
    client: "AuthenticatedClient",
    assignment_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    List[RubricRowBaseAsJSON],
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/rubrics/".format(client.base_url, assignmentId=assignment_id)

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

    response = httpx.put(url=url, headers=headers, json=json_json_body, params=params,)

    if response_code_matches(response.status_code, 200):
        return [RubricRowBaseAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


def delete_rubric(
    *, client: "AuthenticatedClient", assignment_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    None,
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/rubrics/".format(client.base_url, assignmentId=assignment_id)

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


def get_course(
    *, client: "AuthenticatedClient", assignment_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    CourseAsExtendedJSON,
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/course".format(client.base_url, assignmentId=assignment_id)

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


def copy_rubric(
    json_body: CopyRubricAssignmentData,
    *,
    client: "AuthenticatedClient",
    assignment_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    List[RubricRowBaseAsJSON],
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}/rubric".format(client.base_url, assignmentId=assignment_id)

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
        return [RubricRowBaseAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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
    json_body: PatchAssignmentData,
    *,
    client: "AuthenticatedClient",
    assignment_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    AssignmentAsJSON,
]:

    """  """
    url = "{}/api/v1/assignments/{assignmentId}".format(client.base_url, assignmentId=assignment_id)

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
        return AssignmentAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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
