"""This module implements the internal API for AutoTest runs.

All these routes need authentication, and can only be requested by ip addresses
which are registered as active runners.

SPDX-License-Identifier: AGPL-3.0-only
"""
import json
import typing as t

import requests
import werkzeug
import structlog
from flask import request, send_file, make_response
from werkzeug.wrappers import Response

from . import api
from .. import app, files, tasks, models, helpers, auto_test
from ..models import db
from ..helpers import (
    JSONResponse, EmptyResponse, jsonify, get_or_404, ensure_json_dict,
    request_arg_true, make_empty_response, filter_single_or_404,
    get_from_map_transaction, get_json_dict_from_request
)
from ..parsers import parse_enum
from ..features import Feature, feature_required
from ..exceptions import APICodes, APIException, PermissionException

logger = structlog.get_logger()
LocalRunner = t.NewType('LocalRunner', t.Tuple[str, bool])


def _ensure_from_latest_work(result: models.AutoTestResult) -> None:
    work = result.work

    if work.assignment.get_latest_submission_for_user(work.user).with_entities(
        models.Work.id
    ).scalar() != work.id:
        raise APIException(
            'You are not working on the newest submission',
            f'The submission {work.id} is not the newest submission',
            APICodes.NOT_NEWEST_SUBMSSION, 400
        )


def _get_local_runner(
    global_password: str, local_password: str
) -> LocalRunner:
    if global_password != app.config['AUTO_TEST_PASSWORD']:
        raise PermissionException(
            'You do not have permission to use this route',
            'No valid password given', APICodes.NOT_LOGGED_IN, 401
        )

    return LocalRunner(
        (local_password, not app.config['AUTO_TEST_DISABLE_ORIGIN_CHECK'])
    )


def _verify_and_get_runner(
    run: t.Optional[models.AutoTestRun], local: LocalRunner
) -> models.AutoTestRunner:
    password, check_ip = local
    exc = PermissionException(
        'You do not have permission to use this route',
        'No valid password given', APICodes.NOT_LOGGED_IN, 401
    )
    if run is None:
        raise PermissionException(
            'You cannot update runs which have finished',
            'The run does not exist (anymore)', APICodes.INCORRECT_PERMISSION,
            403
        )

    for runner in run.runners:
        if not password or not runner.id or password != str(runner.id):
            continue
        elif check_ip and runner.ipaddr != request.remote_addr:
            continue
        else:
            return runner

    raise exc


def _verify_global_header_password() -> LocalRunner:
    with get_from_map_transaction(
        # It seems that werkzeug `EnvironHeaders` is not considered a
        # mapping: https://github.com/python/typeshed/issues/3569
        t.cast(t.Mapping[str, object], request.headers)
    ) as [get, opt_get]:
        global_password = get('CG-Internal-Api-Password', str)
        local_password = opt_get('CG-Internal-Api-Runner-Password', str, '')
    return _get_local_runner(global_password, local_password)


@api.route('/auto_tests/', methods=['GET'])
@feature_required(Feature.AUTO_TEST)
def get_auto_test_status(
) -> t.Union[JSONResponse[auto_test.RunnerInstructions], EmptyResponse]:
    """Request an AutoTest to run.

    .. warning:: This route has side effects!

    This route only does something when the get parameter ``get`` is equal to
    ``tests_to_run``. This route may also be slow as it asks the broker if the
    requesting runner is allowed to be used.
    """
    _verify_global_header_password()
    to_get = request.args.get('get', object())

    if to_get == 'tests_to_run':
        runs = models.AutoTestRun.get_runs_that_need_runners()

        with helpers.BrokerSession(retries=2) as ses:
            for run in runs:
                logger.info(
                    'Trying to register job for runner',
                    run=run.__to_json__(),
                    job_id=run.get_job_id(),
                    runner_ip=request.remote_addr,
                )

                try:
                    ses.put(
                        f'/api/v1/jobs/{run.get_job_id()}/runners/',
                        json={
                            'runner_ip': request.remote_addr
                        },
                        timeout=5,
                    ).raise_for_status()
                except requests.RequestException:
                    logger.info(
                        'Run cannot be done by given runner',
                        exc_info=True,
                        run_id=run.id,
                    )
                else:
                    runner = run.add_active_runner(request.remote_addr)
                    db.session.commit()
                    return jsonify(run.get_instructions(runner))

    return make_empty_response()


@api.route(
    '/auto_tests/<int:auto_test_id>/runs/<int:run_id>', methods=['PATCH']
)
@feature_required(Feature.AUTO_TEST)
def update_run(auto_test_id: int, run_id: int) -> EmptyResponse:
    """Update the state of the given run.

    :>json state: The new state of the run (OPTIONAL).
    :>json setup_stdout: The stdout of the run (so the one which is executed
        only once during the run) setup script (OPTIONAL).
    :>json setup_stderr: Same as ``setup_stdout`` but for the stderr
        (OPTIONAL).
    """
    password = _verify_global_header_password()

    with get_from_map_transaction(get_json_dict_from_request()) as [_, opt]:
        state = opt('state', str, None)
        setup_stdout = opt('setup_stdout', str, None)
        setup_stderr = opt('setup_stderr', str, None)

    run = filter_single_or_404(
        models.AutoTestRun,
        models.AutoTestRun.id == run_id,
        also_error=lambda run: run.auto_test_id != auto_test_id,
        with_for_update=True,
    )
    runner = _verify_and_get_runner(run, password)

    if state == 'stopped':
        run.stop_runners([runner])
    else:
        if setup_stdout is not None:
            run.setup_stdout = setup_stdout
        if setup_stderr is not None:
            run.setup_stderr = setup_stderr

    db.session.commit()

    return make_empty_response()


@api.route(
    '/auto_tests/<int:auto_test_id>/results/<int:result_id>', methods=['GET']
)
@feature_required(Feature.AUTO_TEST)
def get_result_data(auto_test_id: int,
                    result_id: int) -> t.Union[Response, EmptyResponse]:
    """Get the submission files for the given result_id.

    The files are zipped and this zip is send. This zip DOES NOT contain a top
    level directory.
    """
    password = _verify_global_header_password()

    result = get_or_404(
        models.AutoTestResult,
        result_id,
        also_error=lambda res: res.run.auto_test_id != auto_test_id,
    )

    # Don't check that this is the latest submission as this request is
    # probably done by ``wget``, and we do not check why it fails, but if it
    # fails the entire run goes to a crashed state.
    _verify_and_get_runner(result.run, password)

    res: t.Union[Response, EmptyResponse] = make_empty_response()

    if request.args.get('type', None) == 'submission_files':
        if result.run.auto_test.prefer_teacher_revision:
            excluded_user = models.FileOwner.student
        else:
            excluded_user = models.FileOwner.teacher

        zip_file = result.work.create_zip(
            excluded_user, create_leading_directory=False
        )
        res = send_file(zip_file, attachment_filename='student.zip')

    return res


@api.route(
    '/auto_tests/<int:auto_test_id>/runs/<int:run_id>/heartbeats/',
    methods=['POST']
)
def post_heartbeat(auto_test_id: int, run_id: int) -> EmptyResponse:
    """Emit a heartbeat for the given AutoTest run.

    :param auto_test_id: The AutoTest where the given run is in.
    :param run_id: The id of the run for which you want to emit a heartbeat.
    """
    password = _verify_global_header_password()

    run = filter_single_or_404(
        models.AutoTestRun,
        models.AutoTestRun.id == run_id,
        also_error=lambda run: run.auto_test_id != auto_test_id,
    )
    runner = _verify_and_get_runner(run, password)

    logger.info(
        'Updating heartbeat',
        runner_id=runner.id.hex,
    )

    runner.last_heartbeat = helpers.get_request_start_time()
    db.session.commit()
    return make_empty_response()


@api.route(
    '/auto_tests/<int:auto_test_id>/fixtures/<int:fixture_id>',
    methods=['GET']
)
@feature_required(Feature.AUTO_TEST)
def get_fixture(
    auto_test_id: int, fixture_id: int
) -> werkzeug.wrappers.Response:
    """Get the contents of the given fixture.

    :param auto_test_id: The id of the AutoTest where this fixture is in.
    :param fixture_id: The id of the fixture to get.
    """
    password = _verify_global_header_password()

    fixture = get_or_404(
        models.AutoTestFixture,
        fixture_id,
        also_error=lambda obj: obj.auto_test_id != auto_test_id,
    )

    runs: t.Sequence[t.Optional[models.AutoTestRun]] = [None]
    runs = fixture.auto_test.get_all_runs() or runs
    for run in runs:
        try:
            _verify_and_get_runner(run, password)
        except Exception as e:  # pylint: disable=broad-except; #pragma: no cover
            exc = e
        else:
            break
    else:  # pragma: no cover
        raise exc

    contents = files.get_file_contents(fixture)
    res: werkzeug.wrappers.Response = make_response(contents)
    res.headers['Content-Type'] = 'application/octet-stream'
    return res


@api.route(
    '/auto_tests/<int:auto_test_id>/results/<int:result_id>',
    methods=['PATCH']
)
@feature_required(Feature.AUTO_TEST)
def update_result(auto_test_id: int,
                  result_id: int) -> JSONResponse[t.Dict[str, bool]]:
    """Update the the state of a result.

    This route does not update the results of steps!

    :param auto_test_id: The AutoTest configuration in which to update the
        result.
    :param result_id: The id of the result which you want to update.
    :>json state: The new state of the result (OPTIONAL).
    :>json setup_stdout: The output of the setup script (OPTIONAL).
    :>json setup_stderr: The output to stderr of the setup script (OPTIONAL).
    """
    password = _verify_global_header_password()

    with get_from_map_transaction(get_json_dict_from_request()) as [
        _, opt_get
    ]:
        state = opt_get('state', str, None)
        setup_stdout = opt_get('setup_stdout', str, None)
        setup_stderr = opt_get('setup_stderr', str, None)

    result = filter_single_or_404(
        models.AutoTestResult,
        models.AutoTestResult.id == result_id,
        also_error=lambda result: result.run.auto_test_id != auto_test_id,
        with_for_update=True,
    )
    _ensure_from_latest_work(result)
    runner = _verify_and_get_runner(result.run, password)

    logger.info(
        'Updating result',
        state=state,
        remote_addr=runner.ipaddr,
        result_runner=result.runner and result.runner.ipaddr,
        result_id=result.id,
    )

    if result.runner is not None and result.runner != runner:
        return jsonify({'taken': True})
    else:
        result.runner = runner

    if setup_stdout is not None:
        result.setup_stdout = setup_stdout
    if setup_stderr is not None:
        result.setup_stderr = setup_stderr
    if state is not None:
        new_state = parse_enum(state, models.AutoTestStepResultState)
        assert new_state is not None

        if new_state in {
            models.AutoTestStepResultState.not_started,
            models.AutoTestStepResultState.running,
            models.AutoTestStepResultState.passed,
        }:
            run_id = result.auto_test_run_id
            helpers.callback_after_this_request(
                lambda: tasks.update_latest_results_in_broker(run_id)
            )

        if new_state == models.AutoTestStepResultState.not_started:
            result.clear()
        else:
            result.state = new_state

    db.session.commit()
    return jsonify({'taken': False})


@api.route(
    '/auto_tests/<int:auto_test_id>/results/<int:result_id>/step_results/',
    methods=['PUT']
)
@feature_required(Feature.AUTO_TEST)
def update_step_result(auto_test_id: int, result_id: int
                       ) -> JSONResponse[models.AutoTestStepResult]:
    """Update the result of a single step.

    :param auto_test_id: The AutoTest configuration in which to update the
        result.
    :param result_id: The id of the result in which to update the step.
    :>json state: The state in which the step is in right now.
    :>json log: The current log of the step.
    :>json auto_test_step_id: The step of which this is a result.
    :>json res_id: The step result you want to update (OPTIONAL). If you do not
        pass this option a step result is created.
    """
    password = _verify_global_header_password()

    content = ensure_json_dict(
        ('json' in request.files and json.load(request.files['json'])) or
        request.get_json()
    )

    with get_from_map_transaction(content) as [get, opt_get]:
        state = get('state', str)
        log = get('log', dict)
        auto_test_step_id = get('auto_test_step_id', int)
        res_id = opt_get('id', int, None)
        has_attachment = opt_get('has_attachment', bool, False)

    result = filter_single_or_404(
        models.AutoTestResult,
        models.AutoTestResult.id == result_id,
        also_error=lambda res: res.run.auto_test_id != auto_test_id,
        with_for_update=True,
        with_for_update_of=models.AutoTestResult,
    )
    _ensure_from_latest_work(result)
    _verify_and_get_runner(result.run, password)

    if res_id is None:
        step_result = models.AutoTestStepResult(
            step=get_or_404(
                models.AutoTestStepBase,  # type: ignore
                auto_test_step_id
            ),
            result=result
        )
        db.session.add(result)
    else:
        step_result = get_or_404(models.AutoTestStepResult, res_id)
        assert step_result.auto_test_result_id == result.id
        assert step_result.auto_test_step_id == auto_test_step_id

    new_state = parse_enum(state, models.AutoTestStepResultState)
    assert new_state is not None
    step_result.state = new_state

    step_result.log = log

    if has_attachment:
        step_result.update_attachment(request.files['attachment'])

    db.session.commit()

    return jsonify(step_result)


@api.route(
    '/auto_tests/<int:auto_test_id>/runs/<int:run_id>/results/',
    methods=['GET'],
)
def get_extra_results_to_process(
    auto_test_id: int, run_id: int
) -> JSONResponse[t.List[t.Mapping[str, int]]]:
    """Get extra results to run the tests for.

    :qparam last_call: If there are no extra results mark the requesting runner
        as done.
    """
    is_last_call = request_arg_true('last_call')
    password = _verify_global_header_password()

    run = filter_single_or_404(
        models.AutoTestRun,
        models.AutoTestRun.id == run_id,
        also_error=lambda run: run.auto_test_id != auto_test_id,
        with_for_update=is_last_call,
    )
    runner = _verify_and_get_runner(run, password)

    # Limit the results to the oldest few when requested. This should be the
    # oldest as otherwise we might not send old results that the runner doesn't
    # have yet.
    results = helpers.maybe_apply_sql_slice(run.get_results_to_run()).all()

    if is_last_call and not results:
        run.stop_runners([runner])
        db.session.commit()

    return jsonify(
        [
            {
                'result_id': res.id,
                'student_id': res.work.user_id,
            } for res in results
        ]
    )


@api.route(
    (
        '/auto_tests/<int:auto_test_id>/results/<int:result_id>'
        '/suites/<int:suite_id>/files/'
    ),
    methods=['POST']
)
@feature_required(Feature.AUTO_TEST)
def upload_output_files(
    auto_test_id: int, result_id: int, suite_id: int
) -> EmptyResponse:
    """Upload output files for the given AutoTest in the given suite.

    The uploaded file may be any file that can normally be used as a
    submission, but a compressed archive is preferred.
    """
    password = _verify_global_header_password()
    result = filter_single_or_404(
        models.AutoTestResult,
        models.AutoTestResult.id == result_id,
        also_error=lambda result: result.run.auto_test_id != auto_test_id,
        with_for_update=True,
    )
    _ensure_from_latest_work(result)
    _verify_and_get_runner(result.run, password)

    suite = get_or_404(
        models.AutoTestSuite,
        suite_id,
        also_error=(
            lambda suite: suite.auto_test_set.auto_test_id != auto_test_id
        ),
    )

    file_objects = helpers.get_files_from_request(
        max_size=app.max_file_size, keys=['file']
    )
    extracted = files.process_files(file_objects, app.max_file_size)

    models.AutoTestOutputFile.create_from_extract_directory(
        extracted,
        None,
        {
            'result': result,
            'suite': suite,
        },
    )
    db.session.commit()

    return make_empty_response()
