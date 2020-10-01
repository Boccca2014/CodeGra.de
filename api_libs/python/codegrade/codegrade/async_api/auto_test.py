from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

import httpx

from ..errors import ApiResponseError
from ..utils import response_code_matches

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


async def create(
    *, client: "AuthenticatedClient", multipart_data: CreateAutoTestData,
) -> Union[
    AutoTestAsJSON,
]:

    """  """
    url = "{}/api/v1/auto_tests/".format(client.base_url,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    async with httpx.AsyncClient() as _client:
        response = await _client.post(url=url, headers=headers, files=multipart_data.to_dict(),)

    if response_code_matches(response.status_code, 200):
        return AutoTestAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


async def restart_result(
    *, client: "AuthenticatedClient", auto_test_id: "int", run_id: "int", result_id: "int",
) -> Union[
    AutoTestResultAsExtendedJSON,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/{runId}/results/{resultId}/restart".format(
        client.base_url, autoTestId=auto_test_id, runId=run_id, resultId=result_id,
    )

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    async with httpx.AsyncClient() as _client:
        response = await _client.post(url=url, headers=headers,)

    if response_code_matches(response.status_code, 200):
        return AutoTestResultAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json()))
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


async def get_results_by_user(
    *, client: "AuthenticatedClient", auto_test_id: "int", run_id: "int", user_id: "int",
) -> Union[
    List[AutoTestResultAsJSON],
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/{runId}/users/{userId}/results/".format(
        client.base_url, autoTestId=auto_test_id, runId=run_id, userId=user_id,
    )

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
        return [AutoTestResultAsJSON.from_dict(item) for item in cast(List[Dict[str, Any]], response.json())]
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


async def get_result(
    *, client: "AuthenticatedClient", auto_test_id: "int", run_id: "int", result_id: "int",
) -> Union[
    AutoTestResultAsExtendedJSON,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/{runId}/results/{resultId}".format(
        client.base_url, autoTestId=auto_test_id, runId=run_id, resultId=result_id,
    )

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
        return AutoTestResultAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json()))
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


async def delete_suite(
    *, client: "AuthenticatedClient", test_id: "int", set_id: "int", suite_id: "int",
) -> Union[
    None,
]:

    """  """
    url = "{}/api/v1/auto_tests/{testId}/sets/{setId}/suites/{suiteId}".format(
        client.base_url, testId=test_id, setId=set_id, suiteId=suite_id,
    )

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


async def update_suite(
    *, client: "AuthenticatedClient", auto_test_id: "int", set_id: "int", json_body: UpdateSuiteAutoTestData,
) -> Union[
    AutoTestSuiteAsJSON,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/sets/{setId}/suites/".format(
        client.base_url, autoTestId=auto_test_id, setId=set_id,
    )

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
        return AutoTestSuiteAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


async def delete_set(
    *, client: "AuthenticatedClient", auto_test_id: "int", auto_test_set_id: "int",
) -> Union[
    None,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/sets/{autoTestSetId}".format(
        client.base_url, autoTestId=auto_test_id, autoTestSetId=auto_test_set_id,
    )

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


async def update_set(
    *, client: "AuthenticatedClient", auto_test_id: "int", auto_test_set_id: "int", json_body: UpdateSetAutoTestData,
) -> Union[
    AutoTestSetAsJSON,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/sets/{autoTestSetId}".format(
        client.base_url, autoTestId=auto_test_id, autoTestSetId=auto_test_set_id,
    )

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
        return AutoTestSetAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


async def stop_run(
    *, client: "AuthenticatedClient", auto_test_id: "int", run_id: "int",
) -> Union[
    None,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/{runId}".format(
        client.base_url, autoTestId=auto_test_id, runId=run_id,
    )

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


async def add_set(
    *, client: "AuthenticatedClient", auto_test_id: "int",
) -> Union[
    AutoTestSetAsJSON,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/sets/".format(client.base_url, autoTestId=auto_test_id,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    async with httpx.AsyncClient() as _client:
        response = await _client.post(url=url, headers=headers,)

    if response_code_matches(response.status_code, 200):
        return AutoTestSetAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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


async def start_run(
    *, client: "AuthenticatedClient", auto_test_id: "int",
) -> Union[
    Union[AutoTestRunAsExtendedJSON, Dict[str, Any]],
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/runs/".format(client.base_url, autoTestId=auto_test_id,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    async with httpx.AsyncClient() as _client:
        response = await _client.post(url=url, headers=headers,)

    if response_code_matches(response.status_code, 200):
        return try_any(
            [
                lambda: AutoTestRunAsExtendedJSON.from_dict(cast(Dict[str, Any], response.json())),
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


async def copy(
    *, client: "AuthenticatedClient", auto_test_id: "int", json_body: CopyAutoTestData,
) -> Union[
    AutoTestAsJSON,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}/copy".format(client.base_url, autoTestId=auto_test_id,)

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
        return AutoTestAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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
    *, client: "AuthenticatedClient", auto_test_id: "int",
) -> Union[
    ResultDataGetAutoTestGet,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}".format(client.base_url, autoTestId=auto_test_id,)

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
        return ResultDataGetAutoTestGet.from_dict(cast(Dict[str, Any], response.json()))
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


async def delete(
    *, client: "AuthenticatedClient", auto_test_id: "int",
) -> Union[
    None,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}".format(client.base_url, autoTestId=auto_test_id,)

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


async def patch(
    *, client: "AuthenticatedClient", auto_test_id: "int", multipart_data: PatchAutoTestData,
) -> Union[
    AutoTestAsJSON,
]:

    """  """
    url = "{}/api/v1/auto_tests/{autoTestId}".format(client.base_url, autoTestId=auto_test_id,)

    headers: Dict[str, Any] = client.get_headers()

    params: Dict[str, Any] = {
        "no_course_in_assignment": "true",
        "no_role_name": "true",
        "no_assignment_in_case": "true",
        "extended": "true",
    }

    async with httpx.AsyncClient() as _client:
        response = await _client.patch(url=url, headers=headers, files=multipart_data.to_dict(),)

    if response_code_matches(response.status_code, 200):
        return AutoTestAsJSON.from_dict(cast(Dict[str, Any], response.json()))
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
