from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import maybe_to_dict, response_code_matches, to_multipart, try_any

if TYPE_CHECKING:
    from ..client import AuthenticatedClient, Client

from typing import Dict, cast

from ..models.auto_test_as_json import AutoTestAsJSON
from ..models.auto_test_result_as_extended_json import AutoTestResultAsExtendedJSON
from ..models.auto_test_result_as_json import AutoTestResultAsJSON
from ..models.auto_test_run_as_extended_json import AutoTestRunAsExtendedJSON
from ..models.auto_test_set_as_json import AutoTestSetAsJSON
from ..models.auto_test_suite_as_json import AutoTestSuiteAsJSON
from ..models.base_error import BaseError
from ..models.copy_auto_test_data import CopyAutoTestData
from ..models.create_auto_test_data import CreateAutoTestData
from ..models.patch_auto_test_data import PatchAutoTestData
from ..models.result_data_get_auto_test_get import ResultDataGetAutoTestGet
from ..models.update_set_auto_test_data import UpdateSetAutoTestData
from ..models.update_suite_auto_test_data import UpdateSuiteAutoTestData


def create(
    multipart_data: CreateAutoTestData, *, client: "AuthenticatedClient", extra_parameters: Mapping[str, str] = None,
) -> Union[
    AutoTestAsJSON,
]:

    """Create a new AutoTest configuration."""
    url = "{}/api/v1/auto_tests/".format(client.base_url)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    if extra_parameters:
        params.update(extra_parameters)

    response = httpx.post(url=url, headers=headers, files=to_multipart(multipart_data.to_dict()), params=params,)

    if response_code_matches(response.status_code, 200):
        return AutoTestAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


def restart_result(
    *,
    client: "AuthenticatedClient",
    auto_test_id: "int",
    run_id: "int",
    result_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    AutoTestResultAsExtendedJSON,
]:

    """Restart an AutoTest result."""
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/{runId}/results/{resultId}/restart".format(
        client.base_url, autoTestId=auto_test_id, runId=run_id, resultId=result_id
    )

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    if extra_parameters:
        params.update(extra_parameters)

    response = httpx.post(url=url, headers=headers, params=params,)

    if response_code_matches(response.status_code, 200):
        return AutoTestResultAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json()))
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


def get_results_by_user(
    *,
    client: "AuthenticatedClient",
    auto_test_id: "int",
    run_id: "int",
    user_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    List[AutoTestResultAsJSON],
]:

    """Get all AutoTest results for a given user.

If you don't have permission to see the results of the requested user an empty list will be returned."""
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/{runId}/users/{userId}/results/".format(
        client.base_url, autoTestId=auto_test_id, runId=run_id, userId=user_id
    )

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
        return [AutoTestResultAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


def get_result(
    *,
    client: "AuthenticatedClient",
    auto_test_id: "int",
    run_id: "int",
    result_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    AutoTestResultAsExtendedJSON,
]:

    """Get the extended version of an AutoTest result."""
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/{runId}/results/{resultId}".format(
        client.base_url, autoTestId=auto_test_id, runId=run_id, resultId=result_id
    )

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
        return AutoTestResultAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json()))
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


def delete_suite(
    *,
    client: "AuthenticatedClient",
    test_id: "int",
    set_id: "int",
    suite_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    None,
]:

    """Delete a <span data-role=\"class\">.models.AutoTestSuite</span>."""
    url = "{}/api/v1/auto_tests/{testId}/sets/{setId}/suites/{suiteId}".format(
        client.base_url, testId=test_id, setId=set_id, suiteId=suite_id
    )

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


def update_suite(
    json_body: UpdateSuiteAutoTestData,
    *,
    client: "AuthenticatedClient",
    auto_test_id: "int",
    set_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    AutoTestSuiteAsJSON,
]:

    """Update or create a <span data-role=\"class\">.models.AutoTestSuite</span> (also known as category)"""
    url = "{}/api/v1/auto_tests/{autoTestId}/sets/{setId}/suites/".format(
        client.base_url, autoTestId=auto_test_id, setId=set_id
    )

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
        return AutoTestSuiteAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


def delete_set(
    *,
    client: "AuthenticatedClient",
    auto_test_id: "int",
    auto_test_set_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    None,
]:

    """Delete an <span data-role=\"class\">.models.AutoTestSet</span>."""
    url = "{}/api/v1/auto_tests/{autoTestId}/sets/{autoTestSetId}".format(
        client.base_url, autoTestId=auto_test_id, autoTestSetId=auto_test_set_id
    )

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


def update_set(
    json_body: UpdateSetAutoTestData,
    *,
    client: "AuthenticatedClient",
    auto_test_id: "int",
    auto_test_set_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    AutoTestSetAsJSON,
]:

    """Update the given <span data-role=\"class\">.models.AutoTestSet</span>."""
    url = "{}/api/v1/auto_tests/{autoTestId}/sets/{autoTestSetId}".format(
        client.base_url, autoTestId=auto_test_id, autoTestSetId=auto_test_set_id
    )

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
        return AutoTestSetAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


def stop_run(
    *, client: "AuthenticatedClient", auto_test_id: "int", run_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    None,
]:

    """Delete an AutoTest run, this makes it possible to edit the AutoTest.

This also clears the rubric categories filled in by the AutoTest."""
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/{runId}".format(
        client.base_url, autoTestId=auto_test_id, runId=run_id
    )

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


def add_set(
    *, client: "AuthenticatedClient", auto_test_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    AutoTestSetAsJSON,
]:

    """Create a new set within an AutoTest"""
    url = "{}/api/v1/auto_tests/{autoTestId}/sets/".format(client.base_url, autoTestId=auto_test_id)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    if extra_parameters:
        params.update(extra_parameters)

    response = httpx.post(url=url, headers=headers, params=params,)

    if response_code_matches(response.status_code, 200):
        return AutoTestSetAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


def start_run(
    *, client: "AuthenticatedClient", auto_test_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    Union[AutoTestRunAsExtendedJSON, Dict[str, Any]],
]:

    """Start a run for the given <span data-role=\"class\">AutoTest</span>."""
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/".format(client.base_url, autoTestId=auto_test_id)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    if extra_parameters:
        params.update(extra_parameters)

    response = httpx.post(url=url, headers=headers, params=params,)

    if response_code_matches(response.status_code, 200):
        return try_any(
            [
                lambda: AutoTestRunAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json())),
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


def copy(
    json_body: CopyAutoTestData,
    *,
    client: "AuthenticatedClient",
    auto_test_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    AutoTestAsJSON,
]:

    """Copy the given AutoTest configuration."""
    url = "{}/api/v1/auto_tests/{autoTestId}/copy".format(client.base_url, autoTestId=auto_test_id)

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
        return AutoTestAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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
    *, client: "AuthenticatedClient", auto_test_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    ResultDataGetAutoTestGet,
]:

    """Get the extended version of an <span data-role=\"class\">.models.AutoTest</span> and its runs."""
    url = "{}/api/v1/auto_tests/{autoTestId}".format(client.base_url, autoTestId=auto_test_id)

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
        return ResultDataGetAutoTestGet.from_dict(cast(Dict[str, Any], response.json()))
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


def delete(
    *, client: "AuthenticatedClient", auto_test_id: "int", extra_parameters: Mapping[str, str] = None,
) -> Union[
    None,
]:

    """Delete the given AutoTest.

This route fails if the AutoTest has any runs, which should be deleted separately."""
    url = "{}/api/v1/auto_tests/{autoTestId}".format(client.base_url, autoTestId=auto_test_id)

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


def patch(
    multipart_data: PatchAutoTestData,
    *,
    client: "AuthenticatedClient",
    auto_test_id: "int",
    extra_parameters: Mapping[str, str] = None,
) -> Union[
    AutoTestAsJSON,
]:

    """Update the settings of an AutoTest configuration."""
    url = "{}/api/v1/auto_tests/{autoTestId}".format(client.base_url, autoTestId=auto_test_id)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    if extra_parameters:
        params.update(extra_parameters)

    response = httpx.patch(url=url, headers=headers, files=to_multipart(multipart_data.to_dict()), params=params,)

    if response_code_matches(response.status_code, 200):
        return AutoTestAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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
