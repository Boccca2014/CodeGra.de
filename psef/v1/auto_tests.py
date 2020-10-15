"""This module defines all API routes with the main directory "auto_tests". The
APIs are used to create, start, and request information about AutoTests.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

import flask
import werkzeug
import structlog
from flask import Response, request, make_response
from typing_extensions import Literal, TypedDict
from werkzeug.datastructures import FileStorage

import cg_request_args as rqa
from cg_json import (
    JSONResponse, ExtendedJSONResponse, MultipleExtendedJSONResponse, jsonify,
    extended_jsonify
)
from cg_maybe import Maybe

from . import api
from .. import (
    app, auth, files, tasks, models, helpers, registry, exceptions,
    site_settings
)
from ..models import db
from ..helpers import (
    EmptyResponse, get_or_404, add_warning, jsonify_options,
    make_empty_response, filter_single_or_404, get_from_map_transaction,
    get_json_dict_from_request, callback_after_this_request
)
from ..exceptions import APICodes, APIWarnings, APIException
from ..permissions import CoursePermission as CPerm

logger = structlog.get_logger()


def _get_at_set_by_ids(
    auto_test_id: int, auto_test_set_id: int
) -> models.AutoTestSet:
    def also_error(at_set: models.AutoTestSet) -> bool:
        return (
            at_set.auto_test_id != auto_test_id or
            not at_set.auto_test.assignment.is_visible
        )

    return filter_single_or_404(
        models.AutoTestSet,
        models.AutoTestSet.id == auto_test_set_id,
        also_error=also_error,
    )


def _get_result_by_ids(
    auto_test_id: int, run_id: int, result_id: int, *, lock: bool = False
) -> models.AutoTestResult:
    test = get_or_404(
        models.AutoTest,
        auto_test_id,
        also_error=lambda at: not at.assignment.is_visible
    )

    def also_error(obj: models.AutoTestResult) -> bool:
        if obj.auto_test_run_id != run_id or obj.run.auto_test_id != test.id:
            return True
        elif obj.work.deleted:
            return True
        return False

    if lock:
        return filter_single_or_404(
            models.AutoTestResult,
            models.AutoTestResult.id == result_id,
            also_error=also_error,
            with_for_update=True,
            with_for_update_of=models.AutoTestResult,
        )
    return get_or_404(models.AutoTestResult, result_id, also_error=also_error)


class FixtureLike(TypedDict):
    """A AutoTest fixture where only the id is required.
    """
    #: The id of the fixture
    id: str


_ATUpdateMap = rqa.FixedMapping(
    rqa.OptionalArgument(
        'setup_script', rqa.SimpleValue.str,
        'The new setup script (per student) of the auto test.'
    ),
    rqa.OptionalArgument(
        'run_setup_script', rqa.SimpleValue.str,
        'The new run setup script (global) of the auto test.'
    ),
    rqa.OptionalArgument(
        'has_new_fixtures',
        rqa.SimpleValue.bool,
        'If true all other files in the request will be used as new fixtures',
    ),
    rqa.OptionalArgument(
        'grade_calculation',
        rqa.SimpleValue.str,
        'The way to do grade calculation for this AutoTest.',
    ),
    rqa.OptionalArgument(
        'results_always_visible',
        rqa.Nullable(rqa.SimpleValue.bool),
        """
        Should results be visible for students before the assignment is set to
        "done"?
        """,
    ),
    rqa.OptionalArgument(
        'prefer_teacher_revision',
        rqa.Nullable(rqa.SimpleValue.bool),
        """
        If ``true`` we will use the teacher revision if available when running
        tests.
        """,
    ),
    rqa.OptionalArgument(
        'fixtures',
        rqa.List(rqa.BaseFixedMapping.from_typeddict(FixtureLike)),
        'A list of old fixtures you want to keep',
    ),
)


def _update_auto_test(
    auto_test: models.AutoTest,
    new_fixtures: t.Sequence[FileStorage],
    old_fixtures: Maybe[t.Sequence[FixtureLike]],
    setup_script: Maybe[str],
    run_setup_script: Maybe[str],
    has_new_fixtures: Maybe[bool],
    grade_calculation: Maybe[str],
    results_always_visible: Maybe[t.Optional[bool]],
    prefer_teacher_revision: Maybe[t.Optional[bool]],
) -> None:
    if old_fixtures.is_just:
        old_fixture_set = set(int(f['id']) for f in old_fixtures.value)
        for f in auto_test.fixtures:
            if f.id not in old_fixture_set:
                f.delete_fixture()
        auto_test.fixtures = [
            f for f in auto_test.fixtures if f.id in old_fixture_set
        ]

    if has_new_fixtures.or_default(False):
        with app.file_storage.putter() as putter:
            max_size = app.max_single_file_size
            for new_fixture in new_fixtures:
                assert new_fixture.filename is not None
                backing_file = putter.from_stream(
                    new_fixture.stream, max_size=max_size
                )
                # This is already checked when getting the files from the
                # request.
                if backing_file.is_nothing:  # pragma: no cover
                    raise helpers.make_file_too_big_exception(
                        app.max_single_file_size, single_file=True
                    )
                auto_test.fixtures.append(
                    models.AutoTestFixture(
                        name=files.escape_logical_filename(
                            new_fixture.filename
                        ),
                        backing_file=backing_file.value,
                    )
                )

        renames = files.fix_duplicate_filenames(auto_test.fixtures)
        if renames:
            logger.info('Fixtures were renamed', renamed_fixtures=renames)
            add_warning(
                (
                    'Some fixtures were renamed as fixtures with the same name'
                    ' already existed'
                ), APIWarnings.RENAMED_FIXTURE
            )

    if setup_script.is_just:
        auto_test.setup_script = setup_script.value
    if run_setup_script.is_just:
        auto_test.run_setup_script = run_setup_script.value
    if grade_calculation.is_just:
        calc = registry.auto_test_grade_calculators.get(
            grade_calculation.value
        )
        if calc is None:
            raise APIException(
                'The given grade_calculation strategy is not found', (
                    f'The given grade_calculation strategy {grade_calculation}'
                    ' is not known'
                ), APICodes.OBJECT_NOT_FOUND, 404
            )
        auto_test.grade_calculator = calc
    if (
        prefer_teacher_revision.is_just and
        prefer_teacher_revision.value is not None
    ):
        auto_test.prefer_teacher_revision = prefer_teacher_revision.value
    if (
        results_always_visible.is_just and
        results_always_visible.value is not None
    ):
        auto_test.results_always_visible = results_always_visible.value


@api.route('/auto_tests/', methods=['POST'])
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('create')
@auth.login_required
def create_auto_test() -> JSONResponse[models.AutoTest]:
    """Create a new AutoTest configuration.

    .. :quickref: AutoTest; Create a new AutoTest configuration.

    :>json assignment_id: The assignment id this AutoTest should be linked to.
    :>json setup_script: The setup script per student that should be run
        (OPTIONAL).
    :>json run_setup_script: The setup for the entire run (OPTIONAL).
    :returns: The newly created AutoTest.
    """
    data, request_files = rqa.MultipartUpload(
        _ATUpdateMap.combine(
            rqa.FixedMapping(
                rqa.RequiredArgument(
                    'assignment_id',
                    rqa.SimpleValue.int,
                    """
            The id of the assignment in which you want to create this
            AutoTest. This assignment should have a rubric.
            """,
                ),
            ),
        ),
        file_key='fixture',
        multiple=True,
    ).from_flask()

    assignment = filter_single_or_404(
        models.Assignment,
        models.Assignment.id == data.assignment_id,
        models.Assignment.is_visible,
        with_for_update=True
    )
    already_has = assignment.auto_test_id is not None

    auto_test = models.AutoTest(
        assignment=assignment,
        finalize_script='',
    )
    db.session.add(auto_test)
    db.session.flush()

    auth.AutoTestPermissions(auto_test).ensure_may_add()

    if already_has:
        raise APIException(
            'The given assignment already has an auto test',
            f'The assignment "{assignment.id}" already has an auto test',
            APICodes.INVALID_STATE, 409
        )

    _update_auto_test(
        auto_test,
        request_files,
        data.fixtures,
        data.setup_script,
        data.run_setup_script,
        data.has_new_fixtures,
        data.grade_calculation,
        data.results_always_visible,
        data.prefer_teacher_revision,
    )

    db.session.commit()
    return jsonify(auto_test)


@api.route('/auto_tests/<int:auto_test_id>', methods=['DELETE'])
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('delete')
@auth.login_required
def delete_auto_test(auto_test_id: int) -> EmptyResponse:
    """Delete the given AutoTest.

    .. :quickref: AutoTest; Delete the given AutoTest.

    This route fails if the AutoTest has any runs, which should be deleted
    separately.

    :param auto_test_id: The AutoTest that should be deleted.
    :return: Nothing.
    """
    auto_test = filter_single_or_404(
        models.AutoTest,
        models.AutoTest.id == auto_test_id,
        with_for_update=True,
        also_error=lambda at: not at.assignment.is_visible,
    )

    auth.AutoTestPermissions(auto_test).ensure_may_edit()

    auto_test.ensure_no_runs()

    for fixture in auto_test.fixtures:
        fixture.delete_fixture()

    db.session.delete(auto_test)
    db.session.commit()

    return make_empty_response()


@api.route(
    '/auto_tests/<int:at_id>/fixtures/<int:fixture_id>', methods=['GET']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
def get_fixture_contents(
    at_id: int, fixture_id: int
) -> werkzeug.wrappers.Response:
    """Get the contents of the given :class:`.models.AutoTestFixture`.

    .. :quickref: AutoTest; Get the contents of a fixture.

    :param auto_test_id: The AutoTest this fixture is linked to.
    :param fixture_id: The id of the fixture which you want the content.
    :returns: The content of the given fixture.
    """
    fixture = get_or_404(
        models.AutoTestFixture,
        fixture_id,
        also_error=(
            lambda f: f.auto_test_id != at_id or not f.auto_test.assignment.
            is_visible
        )
    )

    auth.AutoTestFixturePermissions(fixture).ensure_may_see()

    contents = files.get_file_contents(fixture)
    res: werkzeug.wrappers.Response = make_response(contents)
    res.headers['Content-Type'] = 'application/octet-stream'
    return res


@api.route(
    '/auto_tests/<int:at_id>/fixtures/<int:fixture_id>/hide',
    methods=['POST', 'DELETE']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
def hide_or_open_fixture(at_id: int, fixture_id: int) -> EmptyResponse:
    """Change the visibility of the given fixture.

    .. :quickref: AutoTest; Change the hidden state of a fixture.

    Doing a ``POST`` request to this route will hide the fixture, doing a
    ``DELETE`` request to this route will set ``hidden`` to ``False``.

    :param auto_test_id: The AutoTest this fixture is linked to.
    :param fixture_id: The fixture which you to hide or show.
    """
    fixture = filter_single_or_404(
        models.AutoTestFixture,
        models.AutoTestFixture.id == fixture_id,
        also_error=(
            lambda f: f.auto_test_id != at_id or not f.auto_test.assignment.
            is_visible
        ),
    )

    auth.AutoTestFixturePermissions(fixture).ensure_may_edit()

    fixture.auto_test.ensure_no_runs()

    fixture.hidden = request.method == 'POST'
    db.session.commit()

    return make_empty_response()


@api.route('/auto_tests/<int:auto_test_id>', methods=['PATCH'])
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('patch')
@auth.login_required
def update_auto_test(auto_test_id: int) -> JSONResponse[models.AutoTest]:
    """Update the settings of an AutoTest configuration.

    .. :quickref: AutoTest; Change the settings/upload fixtures to an AutoTest.

    :>json old_fixtures: The old fixtures you want to keep in this AutoTest
        (OPTIONAL). Not providing this option keeps all old fixtures.
    :>json setup_script: The setup script of this AutoTest (OPTIONAL).
    :>json run_setup_script: The run setup script of this AutoTest (OPTIONAL).
    :>json has_new_fixtures: If set to true you should provide one or more new
        fixtures in the ``POST`` (OPTIONAL).
    :>json grade_calculation: The way the rubric grade should be calculated
        from the amount of achieved points (OPTIONAL).
    :param auto_test_id: The id of the AutoTest you want to update.
    :returns: The updated AutoTest.
    """
    data, request_files = rqa.MultipartUpload(
        _ATUpdateMap,
        file_key='fixture',
        multiple=True,
    ).from_flask()

    auto_test = get_or_404(
        models.AutoTest,
        auto_test_id,
        also_error=lambda at: not at.assignment.is_visible
    )
    auth.AutoTestPermissions(auto_test).ensure_may_edit()
    auto_test.ensure_no_runs()

    _update_auto_test(
        auto_test,
        request_files,
        data.fixtures,
        data.setup_script,
        data.run_setup_script,
        data.has_new_fixtures,
        data.grade_calculation,
        data.results_always_visible,
        data.prefer_teacher_revision,
    )
    db.session.commit()

    return jsonify(auto_test)


@api.route('/auto_tests/<int:auto_test_id>/sets/', methods=['POST'])
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('add_set', no_data=True)
@auth.login_required
def create_auto_test_set(auto_test_id: int
                         ) -> JSONResponse[models.AutoTestSet]:
    """Create a new set within an AutoTest

    .. :quickref: AutoTest; Create a set within an AutoTest.

    :param auto_test_id: The id of the AutoTest wherein you want to create a
        set.
    :returns: The newly created set.
    """
    auto_test = get_or_404(
        models.AutoTest,
        auto_test_id,
        also_error=lambda at: not at.assignment.is_visible
    )
    auth.AutoTestPermissions(auto_test).ensure_may_edit()

    auto_test.ensure_no_runs()

    auto_test.sets.append(models.AutoTestSet())
    db.session.commit()

    return jsonify(auto_test.sets[-1])


@api.route(
    '/auto_tests/<int:auto_test_id>/sets/<int:auto_test_set_id>',
    methods=['PATCH']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('update_set')
@auth.login_required
def update_auto_test_set(auto_test_id: int, auto_test_set_id: int
                         ) -> JSONResponse[models.AutoTestSet]:
    """Update the given :class:`.models.AutoTestSet`.

    .. :quickref: AutoTest; Update a single AutoTest set.

    :>json stop_points: The minimum amount of points a student should have
        after this set to continue testing.

    :param auto_test_id: The id of the :class:`.models.AutoTest` of the set
        that should be updated.
    :param auto_test_set_id: The id of the :class:`.models.AutoTestSet` that
        should be updated.
    :returns: The updated set.
    """
    data = rqa.FixedMapping(
        rqa.OptionalArgument(
            'stop_points', rqa.SimpleValue.float, """
            The minimum percentage a student should have achieved before the
            next tests will be run.
            """
        )
    ).from_flask()

    auto_test_set = _get_at_set_by_ids(auto_test_id, auto_test_set_id)
    auth.AutoTestPermissions(auto_test_set.auto_test).ensure_may_edit()

    auto_test_set.auto_test.ensure_no_runs()

    if data.stop_points.is_just:
        stop_points = data.stop_points.value
        if stop_points < 0:
            raise APIException(
                'You cannot set stop points to lower than 0',
                f"The given value for stop points ({stop_points}) isn't valid",
                APICodes.INVALID_PARAM, 400
            )
        elif stop_points > 1:
            raise APIException(
                'You cannot set stop points to higher than 1',
                f"The given value for stop points ({stop_points}) isn't valid",
                APICodes.INVALID_PARAM, 400
            )
        auto_test_set.stop_points = stop_points

    db.session.commit()

    return jsonify(auto_test_set)


@api.route(
    '/auto_tests/<int:auto_test_id>/sets/<int:auto_test_set_id>',
    methods=['DELETE']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('delete_set')
@auth.login_required
def delete_auto_test_set(
    auto_test_id: int, auto_test_set_id: int
) -> EmptyResponse:
    """Delete an :class:`.models.AutoTestSet`.

    .. :quickref: AutoTest; Delete a single AutoTest set.

    :param auto_test_id: The id of the :class:`.models.AutoTest` of the to be
        deleted set.
    :param auto_test_set_id: The id of the :class:`.models.AutoTestSet` that
        should be deleted.
    """
    auto_test_set = _get_at_set_by_ids(auto_test_id, auto_test_set_id)
    auth.AutoTestPermissions(auto_test_set.auto_test).ensure_may_edit()

    auto_test_set.auto_test.ensure_no_runs()

    db.session.delete(auto_test_set)
    db.session.commit()

    return make_empty_response()


@api.route(
    '/auto_tests/<int:auto_test_id>/sets/<int:set_id>/suites/',
    methods=['PATCH']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('update_suite')
@auth.login_required
def update_or_create_auto_test_suite(auto_test_id: int, set_id: int
                                     ) -> JSONResponse[models.AutoTestSuite]:
    """Update or create a :class:`.models.AutoTestSuite` (also known as
        category)

    .. :quickref: AutoTest; Update an AutoTest suite/category.

    :param auto_test_id: The id of the :class:`.models.AutoTest` in which this
        suite should be created.
    :param set_id: The id the :class:`.models.AutoTestSet` in which
        this suite should be created.
    :returns: The just updated or created :class:`.models.AutoTestSuite`.
    """
    data = rqa.FixedMapping(
        rqa.OptionalArgument(
            'id',
            rqa.SimpleValue.int,
            """
            The id of the suite you want to edit. If not provided we will
            create a new suite.
            """,
        ),
        rqa.RequiredArgument(
            'steps',
            rqa.List(
                rqa.BaseFixedMapping.from_typeddict(
                    models.AutoTestStepBase.InputAsJSON
                )
            ),
            """
            The steps that should be in this suite. They will be run as the
            order they are provided in.
            """,
        ),
        rqa.RequiredArgument(
            'rubric_row_id', rqa.SimpleValue.int,
            'The id of the rubric row that should be connected to this suite.'
        ),
        rqa.RequiredArgument(
            'network_disabled', rqa.SimpleValue.bool,
            'Should the network be disabled when running steps in this suite'
        ),
        rqa.OptionalArgument(
            'submission_info',
            rqa.SimpleValue.bool,
            """
            If passed as ``true`` we will provide information about the current
            submission while running steps. Defaults to ``false`` when creating
            new suites.
            """,
        ),
        rqa.OptionalArgument(
            'command_time_limit',
            rqa.SimpleValue.float,
            """
            The maximum amount of time a single step (or substeps) can take
            when running tests. If not provided the default value is depended
            on configuration of the instance.
            """,
        ),
    ).from_flask()
    auto_test_set = _get_at_set_by_ids(auto_test_id, set_id)
    auth.AutoTestPermissions(auto_test_set.auto_test).ensure_may_edit()

    auto_test_set.auto_test.ensure_no_runs()

    if data.id.is_just:
        time_limit = data.command_time_limit.or_default(None)
        suite = get_or_404(models.AutoTestSuite, data.id.value)
    else:
        # Make sure the time_limit is always set when creating a new suite
        default_time_limit = site_settings.Opt.AUTO_TEST_MAX_TIME_COMMAND

        def get_default_time_limit() -> float:
            return default_time_limit.value.total_seconds()

        time_limit = data.command_time_limit.or_default_lazy(
            get_default_time_limit
        )
        suite = models.AutoTestSuite(auto_test_set=auto_test_set)

    if time_limit is not None:
        if time_limit < 1:
            raise APIException(
                'The minimum value for a command time limit is 1 second', (
                    f'The given value for the time limit ({time_limit}) is too'
                    ' low'
                ), APICodes.INVALID_PARAM, 400
            )
        suite.command_time_limit = time_limit

    suite.network_disabled = data.network_disabled

    if data.submission_info.is_just:
        suite.submission_info = data.submission_info.value

    if suite.rubric_row_id != data.rubric_row_id:
        assig = suite.auto_test_set.auto_test.assignment
        rubric_row = get_or_404(
            models.RubricRow,
            data.rubric_row_id,
            also_error=lambda row: row.assignment != assig,
        )

        if rubric_row.id in assig.locked_rubric_rows:
            raise APIException(
                'This rubric is already in use by another suite',
                f'The rubric row "{rubric_row.id}" is already in use',
                APICodes.INVALID_STATE, 409
            )

        if rubric_row.is_selected():
            add_warning(
                'This rubric category is already used for manual grading',
                APIWarnings.IN_USE_RUBRIC_ROW
            )
        suite.rubric_row = rubric_row

    suite.set_steps(data.steps)

    db.session.commit()
    return jsonify(suite)


@api.route(
    '/auto_tests/<int:test_id>/sets/<int:set_id>/suites/<int:suite_id>',
    methods=['DELETE']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('delete_suite')
@auth.login_required
def delete_suite(test_id: int, set_id: int, suite_id: int) -> EmptyResponse:
    """Delete a :class:`.models.AutoTestSuite`.

    .. :quickref: AutoTest; Delete a suite of an AutoTest.

    :param test_id: The id of the :class:`.models.AutoTest` where the suite is
        located in.
    :param set_id: The id of the :class:`.models.AutoTestSet` where the suite
        is located in.
    :param suite_id: The id of the :class:`.models.AutoTestSuite` you want to
        delete.
    """
    suite = filter_single_or_404(
        models.AutoTestSuite,
        models.AutoTestSuite.id == suite_id,
        models.AutoTestSet.id == set_id,
        models.AutoTest.id == test_id,
    )
    auth.AutoTestPermissions(suite.auto_test_set.auto_test).ensure_may_edit()
    suite.auto_test_set.auto_test.ensure_no_runs()

    db.session.delete(suite)
    db.session.commit()
    return make_empty_response()


@api.route('/auto_tests/<int:auto_test_id>', methods=['GET'])
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('get')
@auth.login_required
def get_auto_test(
    auto_test_id: int,
) -> MultipleExtendedJSONResponse[models.AutoTest, models.AutoTestRun]:
    """Get the extended version of an :class:`.models.AutoTest` and its runs.

    .. :quickref: AutoTest; Get the extended version of an AutTest.

    :param auto_test_id: The id of the AutoTest to get.
    :returns: The extended serialization of an :class:`.models.AutoTest` and
        the extended serialization of its runs.
    """
    test = get_or_404(models.AutoTest, auto_test_id)
    auth.AutoTestPermissions(test).ensure_may_see()

    jsonify_options.get_options(
    ).latest_only = helpers.request_arg_true('latest_only')
    return MultipleExtendedJSONResponse.make(
        test, use_extended=models.AutoTestRun
    )


@api.route('/auto_tests/<int:auto_test_id>/runs/<int:run_id>', methods=['GET'])
@site_settings.Opt.AUTO_TEST_ENABLED.required
def get_auto_test_run(auto_test_id: int,
                      run_id: int) -> ExtendedJSONResponse[models.AutoTestRun]:
    """Get the extended version of an :class:`.models.AutoTestRun`.

    .. :quickref: AutoTest; Get the extended details of an AutoTest run.

    :param auto_test_id: The id of the AutoTest which is connected to the
        requested run.
    :param run_id: The id of the run to get.
    :returns: The extended version of an :class:`.models.AutoTestRun`, note
        that results will not be serialized as an extended version.
    """
    run = filter_single_or_404(
        models.AutoTestRun,
        models.AutoTestRun.id == run_id,
        also_error=lambda run: run.auto_test_id != auto_test_id
    )
    auth.AutoTestRunPermissions(run).ensure_may_see()

    jsonify_options.get_options(
    ).latest_only = helpers.request_arg_true('latest_only')
    return extended_jsonify(run, use_extended=models.AutoTestRun)


@api.route('/auto_tests/<int:auto_test_id>/runs/', methods=['POST'])
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('start_run', no_data=True)
@auth.login_required
def start_auto_test_run(auto_test_id: int) -> t.Union[JSONResponse[
    t.Mapping[str, Literal['']]], ExtendedJSONResponse[models.AutoTestRun]]:
    """Start a run for the given :class:`AutoTest`.

    .. :quickref: AutoTest; Start a run for a given AutoTest.

    :param auto_test_id: The id of the AutoTest for which you want to start a
        run.
    :returns: The started run or a empty mapping if you do not have permission
        to see AutoTest runs.
    :raises APIException: If there is already a run for the given AutoTest.
    """
    test = filter_single_or_404(
        models.AutoTest,
        models.AutoTest.id == auto_test_id,
        with_for_update=True
    )

    # This should really use `AutoTestRunPermissions.ensure_may_start` but as
    # the run is created while it is scheduled (and other (revealing) state
    # checks are done) this is not really possible.
    auth.AssignmentPermissions(test.assignment).ensure_may_see()
    auth.ensure_permission(CPerm.can_run_autotest, test.assignment.course_id)

    try:
        run = test.start_test_run()
    except exceptions.InvalidStateException as e:
        raise APIException(
            e.reason,
            f'The test "{test.id}" is not in a state to start a run"',
            APICodes.INVALID_STATE, 409
        ) from e

    db.session.commit()

    if auth.AutoTestPermissions(test).ensure_may_see.as_bool():
        return extended_jsonify(run, use_extended=models.AutoTestRun)
    else:
        return jsonify({})


@api.route(
    '/auto_tests/<int:auto_test_id>/runs/<int:run_id>', methods=['DELETE']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('stop_run')
@auth.login_required
def delete_auto_test_runs(auto_test_id: int, run_id: int) -> EmptyResponse:
    """Delete an AutoTest run, this makes it possible to edit the AutoTest.

    .. :quickref: AutoTest; Delete the the given AutoTest run.

    This also clears the rubric categories filled in by the AutoTest.

    :param auto_test_id: The id of the AutoTest of which the run should be
        deleted.
    :param run_id: The id of the run which should be deleted.
    """
    run = filter_single_or_404(
        models.AutoTestRun,
        models.AutoTestRun.id == run_id,
        also_error=lambda obj: obj.auto_test_id != auto_test_id,
        with_for_update=True,
    )
    auth.AutoTestRunPermissions(run).ensure_may_stop()

    job_id = run.get_job_id()
    callback_after_this_request(
        lambda: tasks.notify_broker_end_of_job(
            job_id,
            ignore_non_existing=True,
        )
    )

    run.delete_and_clear_rubric()
    db.session.commit()

    return make_empty_response()


@api.route(
    (
        '/auto_tests/<int:auto_test_id>/runs/<int:run_id>'
        '/users/<int:user_id>/results/'
    ),
    methods=['GET']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('get_results_by_user')
@auth.login_required
def get_auto_test_results_for_user(
    auto_test_id: int, run_id: int, user_id: int
) -> JSONResponse[t.List[models.AutoTestResult]]:
    """Get all AutoTest results for a given user.

    .. :quickref: AutoTest; Get all AutoTest results for a given.

    :param auto_test_id: The id of the AutoTest in which to get the results.
    :param run_id: The id of the AutoTestRun in which to get the results.
    :param user_id: The id of the user of which we should get the results.
    :returns: The list of AutoTest results for the given user, sorted from
        oldest to latest.

    If you don't have permission to see the results of the requested user an
    empty list will be returned.
    """

    def also_error(atr: models.AutoTestRun) -> bool:
        return (
            atr.auto_test_id != auto_test_id or
            not atr.auto_test.assignment.is_visible
        )

    run = filter_single_or_404(
        models.AutoTestRun,
        models.AutoTestRun.id == run_id,
        also_error=also_error,
    )
    user = get_or_404(models.User, user_id)
    auth.AutoTestRunPermissions(run).ensure_may_see()

    results = []
    for result in models.AutoTestResult.get_results_by_user(
        user.id
    ).filter(models.AutoTestResult.run == run).order_by(
        models.AutoTestResult.created_at
    ):
        if auth.AutoTestResultPermissions(result).ensure_may_see.as_bool():
            results.append(result)

    return jsonify(results)


@api.route(
    '/auto_tests/<int:auto_test_id>/runs/<int:run_id>/results/<int:result_id>',
    methods=['GET']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('get_result')
@auth.login_required
def get_auto_test_result(auto_test_id: int, run_id: int, result_id: int
                         ) -> ExtendedJSONResponse[models.AutoTestResult]:
    """Get the extended version of an AutoTest result.

    .. :quickref: AutoTest; Get the extended version of a single result.

    :param auto_test_id: The id of the AutoTest in which the result is located.
    :param run_id: The id of run in which the result is located.
    :param result_id: The id of the result you want to get.
    :returns: The extended version of a :class:`.models.AutoTestResult`.
    """
    result = _get_result_by_ids(auto_test_id, run_id, result_id)
    auth.AutoTestResultPermissions(result).ensure_may_see()
    return extended_jsonify(result, use_extended=models.AutoTestResult)


@api.route(
    (
        '/auto_tests/<int:auto_test_id>/runs/<int:run_id>/results'
        '/<int:result_id>/restart'
    ),
    methods=['POST']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('restart_result', no_data=True)
@auth.login_required
def restart_auto_test_result(auto_test_id: int, run_id: int, result_id: int
                             ) -> ExtendedJSONResponse[models.AutoTestResult]:
    """Restart an AutoTest result.

    .. :quickref: AutoTest; Restart a single result.

    :param auto_test_id: The id of the AutoTest in which the result is located.
    :param run_id: The id of run in which the result is located.
    :param result_id: The id of the result you want to restart.
    :returns: The extended version of a :class:`.models.AutoTestResult`.
    """
    result = _get_result_by_ids(auto_test_id, run_id, result_id, lock=True)

    auth.AutoTestResultPermissions(result).ensure_may_restart()

    work = result.work
    if work.assignment.get_latest_submission_for_user(work.user).with_entities(
        models.Work.id
    ).scalar() != work.id:
        raise APIException(
            'You cannot restart old submissions.',
            f'The submission {work.id} is not the latest submission.',
            APICodes.NOT_NEWEST_SUBMSSION, 400
        )

    if result.is_finished or result.runner is None:
        callback_after_this_request(
            lambda: tasks.adjust_amount_runners(run_id)
        )
    else:
        # XXX: We can probably do this in a more efficient way, while still
        # making sure the code of the student is downloaded again. However, we
        # hypothesized that this case (restarting a running result) will not
        # happen very often so it doesn't really make sense to optimize this
        # case.
        result.run.stop_runners([result.runner])

    result.clear()
    db.session.commit()

    return extended_jsonify(result, use_extended=models.AutoTestResult)


@api.route('/auto_tests/<int:auto_test_id>/copy', methods=['POST'])
@site_settings.Opt.AUTO_TEST_ENABLED.required
@rqa.swaggerize('copy')
@auth.login_required
def copy_auto_test(auto_test_id: int) -> JSONResponse[models.AutoTest]:
    """Copy the given AutoTest configuration.

    .. :quickref: AutoTest; Copy an AutoTest config to another assignment.

    :param auto_test_id: The id of the AutoTest config which should be copied.
    :returns: The copied AutoTest configuration.
    """
    data = rqa.FixedMapping(
        rqa.RequiredArgument(
            'assignment_id',
            rqa.SimpleValue.int,
            """
            The id of the assignment into which you want to copy this AutoTest.
            """,
        )
    ).from_flask()
    test = get_or_404(
        models.AutoTest,
        auto_test_id,
        also_error=lambda at: not at.assignment.is_visible
    )
    auth.AutoTestPermissions(test).ensure_may_see()

    for fixture in test.fixtures:
        auth.AutoTestFixturePermissions(fixture).ensure_may_see()
    for suite in test.all_suites:
        for step in suite.steps:
            auth.ensure_can_view_autotest_step_details(step)

    assignment = filter_single_or_404(
        models.Assignment,
        models.Assignment.id == data.assignment_id,
        with_for_update=True
    )
    auth.ensure_permission(CPerm.can_edit_autotest, assignment.course_id)

    if assignment.auto_test is not None:
        raise APIException(
            'The given assignment already has an AutoTest',
            f'The assignment "{assignment.id}" already has an auto test',
            APICodes.INVALID_STATE, 409
        )

    assignment.rubric_rows = []
    mapping = {}
    for old_row in test.assignment.rubric_rows:
        new_row = old_row.copy()
        mapping[old_row] = new_row
        assignment.rubric_rows.append(new_row)

    db.session.flush()

    with app.file_storage.putter() as putter:
        assignment.auto_test = test.copy(mapping, putter)
        db.session.flush()
    db.session.commit()
    return jsonify(assignment.auto_test)


@api.route(
    (
        '/auto_tests/<int:auto_test_id>/runs/<int:run_id>/results/'
        '<int:result_id>/suites/<int:suite_id>/proxy'
    ),
    methods=['POST']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@site_settings.Opt.RENDER_HTML_ENABLED.required
def get_auto_test_result_proxy(
    auto_test_id: int,
    run_id: int,
    result_id: int,
    suite_id: int,
) -> JSONResponse[models.Proxy]:
    """Create a proxy to view the files of the given AT result through.

    .. :quickref: AutoTest; Create a proxy to view the files a result.

    This allows you to view files of an AutoTest result (within a suite)
    without authentication for a limited time.

    :param auto_test_id: The id of the AutoTest in which the result is located.
    :param run_id: The id of run in which the result is located.
    :param result_id: The id of the result from which you want to get the
        files.
    :param suite_id: The suite from which you want to proxy the output files.
    :<json bool allow_remote_resources: Allow the proxy to load remote
        resources.
    :<json bool allow_remote_scripts: Allow the proxy to load remote scripts,
        and allow to usage of 'eval'.
    :returns: The created proxy.
    """
    with get_from_map_transaction(get_json_dict_from_request()) as [get, _]:
        allow_remote_resources = get('allow_remote_resources', bool)
        allow_remote_scripts = get('allow_remote_scripts', bool)

    result = _get_result_by_ids(auto_test_id, run_id, result_id)
    auth.AutoTestResultPermissions(result).ensure_may_see_output_files()

    base_file = filter_single_or_404(
        models.AutoTestOutputFile,
        models.AutoTestOutputFile.parent_id.is_(None),
        models.AutoTestOutputFile.auto_test_suite_id == suite_id,
        models.AutoTestOutputFile.result == result,
    )

    proxy = models.Proxy(
        base_at_result_file=base_file,
        allow_remote_resources=allow_remote_resources,
        allow_remote_scripts=allow_remote_scripts,
    )
    db.session.add(proxy)
    db.session.commit()
    return jsonify(proxy)


@api.route(
    '/auto_tests/<int:auto_test_id>/runs/<int:run_id>/step_results/<int:step_result_id>/attachment',
    methods=['GET']
)
@site_settings.Opt.AUTO_TEST_ENABLED.required
@auth.login_required
def get_auto_test_step_result_attachment(
    auto_test_id: int, run_id: int, step_result_id: int
) -> Response:
    """Get the attachment of an AutoTest step.

    .. :quickref: AutoTest; Get AutoTest step result attachment.

    :param auto_test_id: The id of the AutoTest in which the result is located.
    :param run_id: The id of run in which the result is located.
    :param step_result_id: The id of the step result of which you want the attachment.
    :returns: The attachment data, as an application/octet-stream.
    """
    test = get_or_404(
        models.AutoTest,
        auto_test_id,
        also_error=lambda at: not at.assignment.is_visible
    )
    auth.AutoTestPermissions(test).ensure_may_see()

    def also_error(obj: models.AutoTestStepResult) -> bool:
        result = obj.result
        if result.auto_test_run_id != run_id or result.run.auto_test_id != test.id:
            return True
        elif result.work.deleted:
            return True
        return False

    step_result = get_or_404(
        models.AutoTestStepResult,
        step_result_id,
        also_error=also_error,
    )

    auth.AutoTestResultPermissions(step_result.result).ensure_may_see()
    auth.ensure_can_view_autotest_step_details(step_result.step)

    if step_result.attachment.is_nothing:
        raise APIException(
            'This step did not produce an attachment',
            f'The step result {step_result.id} does not contain an attachment',
            APICodes.OBJECT_NOT_FOUND, 404
        )

    return flask.send_file(
        step_result.attachment.value.open(),
        mimetype='application/octet-stream'
    )
