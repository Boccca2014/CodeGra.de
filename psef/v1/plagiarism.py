"""
This module defines all API routes with the main directory "assignments". Thus
the APIs in this module are mostly used to manipulate
:class:`.models.Assignment` objects and their relations.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from sqlalchemy.orm import defaultload

from . import api
from .. import auth, models, helpers, plagiarism
from ..helpers import (
    JSONResponse, EmptyResponse, ExtendedJSONResponse, jsonify,
    extended_jsonify, make_empty_response
)
from ..permissions import CoursePermission as CPerm


@api.route('/plagiarism/<int:plagiarism_id>', methods=['DELETE'])
def delete_plagiarism_run(plagiarism_id: int, ) -> EmptyResponse:
    """Delete a given plagiarism run and all its cases.

    .. :quickref: Plagiarism; Delete a plagiarism run and all its cases.

    .. warning::

        This is irreversible, so make sure the user really wants this!

    :param int plagiarism_id: The id of the run to delete.
    :returns: Nothing.

    :raises PermissionException: If the user can not manage plagiarism runs or
        cases for the course associated with the run. (INCORRECT_PERMISSION)
    """
    run = helpers.get_or_404(
        models.PlagiarismRun,
        plagiarism_id,
        also_error=lambda p: not p.assignment.is_visible
    )
    auth.ensure_permission(
        CPerm.can_manage_plagiarism, run.assignment.course_id
    )
    run.schedule_delete_base_code()
    models.db.session.delete(run)
    models.db.session.commit()
    return make_empty_response()


@api.route('/plagiarism/<int:plagiarism_id>', methods=['GET'])
def get_plagiarism_run(
    plagiarism_id: int,
) -> t.Union[JSONResponse[models.PlagiarismRun], ExtendedJSONResponse[
    models.PlagiarismRun]]:
    """Get a :class:`.models.PlagiarismRun`.

    .. :quickref: Plagiarism; Get a single plagiarism run.

    :qparam boolean extended: Whether to get an extended or normal
        :class:`.models.PlagiarismRun` object. The default value is ``false``,
        you can enable extended by passing ``true``, ``1`` or an empty string.

    :param int plagiarism_id: The of the plagiarism run.
    :returns: An single plagiarism run.

    :raises PermissionException: If the user can not view plagiarism runs or
        cases for the course associated with the run. (INCORRECT_PERMISSION)
    """
    run = helpers.get_or_404(
        models.PlagiarismRun,
        plagiarism_id,
        options=[
            defaultload(models.PlagiarismRun.cases).defaultload(
                models.PlagiarismCase.work1
            ).selectinload(models.Work.selected_items),
            defaultload(models.PlagiarismRun.cases).defaultload(
                models.PlagiarismCase.work2
            ).selectinload(models.Work.selected_items),
        ],
        also_error=lambda p: not p.assignment.is_visible
    )
    auth.AssignmentPermissions(run.assignment).ensure_may_see_plagiarism()

    if helpers.extended_requested():
        helpers.add_deprecate_warning(
            'The extended route for a Plagiarism run will be deleted,'
            ' use the normal route in combination with'
            ' "/plagiarism/<plagiarism_id>/cases/" instead.'
        )
        return extended_jsonify(run, use_extended=models.PlagiarismRun)
    return jsonify(run)


@api.route('/plagiarism/<int:plagiarism_id>/cases/', methods=['GET'])
def get_plagiarism_run_cases(
    plagiarism_id: int,
) -> JSONResponse[t.Iterable[models.PlagiarismCase]]:
    """Get all the :class:`.models.PlagiarismCase`s for the given
    :class:`.models.PlagiarismRun`.

    .. :quickref: Plagiarism; Get the cases for a plagiarism run.

    :qparam int limit: The amount of cases to get. Defaults to infinity.
    :qparam int offset: The amount of cases that should be skipped, only used
        when limit is given. Defaults to 0.

    :param int plagiarism_id: The of the plagiarism run.
    :returns: An array of JSON serialized plagiarism cases.

    :raises PermissionException: If the user can not view plagiarism runs or
        cases for the course associated with the run. (INCORRECT_PERMISSION)
    """
    run = helpers.get_or_404(
        models.PlagiarismRun,
        plagiarism_id,
        options=[],
        also_error=lambda p: not p.assignment.is_visible
    )
    auth.AssignmentPermissions(run.assignment).ensure_may_see_plagiarism()

    sql = models.PlagiarismCase.query.filter_by(
        plagiarism_run_id=run.id
    ).order_by(
        t.cast(
            models.DbColumn[float],
            models.PlagiarismCase.match_avg,
        ).desc()
    ).options(
        defaultload(models.PlagiarismCase.work1).selectinload(
            models.Work.selected_items
        ),
        defaultload(models.PlagiarismCase.work2).selectinload(
            models.Work.selected_items
        ),
    )
    sql = helpers.maybe_apply_sql_slice(sql)

    return jsonify(sql.all())


@api.route(
    '/plagiarism/<int:plagiarism_id>/cases/<int:case_id>',
    methods=['GET'],
)
def get_plagiarism_case(
    plagiarism_id: int,
    case_id: int,
) -> ExtendedJSONResponse[models.PlagiarismCase]:
    """Get the extended view of a single :class:`.models.PlagiarismCase` object.

    .. :quickref: Plagiarism; Get a single plagiarism case.

    :param int plagiarism_id: The id of the run the case should belong to.
    :param int case_id: The id of the case requested.
    :returns: The extended JSON serialization of the plagiarism case requested.

    :raises PermissionException: If the user can not view plagiarism runs or
        cases for the course associated with the run. (INCORRECT_PERMISSION)
    """
    # We use the `plagiarism_id` and the `case_id` so we can later make the
    # `case_id` only unique within a single run.
    case = helpers.filter_single_or_404(
        models.PlagiarismCase,
        models.PlagiarismCase.id == case_id,
        models.PlagiarismCase.plagiarism_run_id == plagiarism_id,
        also_error=lambda c: c.work1.deleted or c.work2.deleted,
    )

    checker = auth.PlagiarismCasePermissions(case)
    auth.PermissionChecker.all(
        checker.ensure_may_see,
        checker.ensure_may_see_other_assignment,
        checker.ensure_may_see_other_submission,
    ).check()

    return extended_jsonify(
        case,
        use_extended=models.PlagiarismCase,
    )


@api.route('/plagiarism/', methods=['GET'])
def get_plag_opts() -> JSONResponse[t.List[t.Dict[str, object]]]:
    """Get all plagiarism providers for this instance.

    .. :quickref: Plagiarism; Get all plagiarism providers.

    :returns: An array of plagiarism providers.
    :>jsonarr str name: The name of the plagiarism provider.
    :>jsonarr bool base_code: Does this plagiarism provider support base code.
    :>jsonarr array options: The extra possible options for this provider, this
        is an array of JSON serialized :class:`.plagiarism.Option` classes.
    """
    return jsonify(
        [
            {
                'name': cls.__name__,
                'options': cls.get_options(),
                'base_code': cls.supports_base_code(),
                'progress': cls.supports_progress(),
            } for cls in sorted(
                helpers.get_all_subclasses(plagiarism.PlagiarismProvider),
                key=lambda o: o.__name__
            )
        ]
    )
