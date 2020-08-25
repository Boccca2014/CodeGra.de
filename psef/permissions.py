"""This file contains all permissions used by CodeGrade in a python enum.

.. warning::

  Do not edit this enum as it is automatically generated by
  "generate_permissions_py.py".

SPDX-License-Identifier: AGPL-3.0-only
"""
# pylint: skip-file
# flake8: noqa=E501
# yapf: disable

import enum
import typing as t
import dataclasses

from . import exceptions

AnyPermission = t.TypeVar(  # pylint: disable=invalid-name
    'AnyPermission', 'GlobalPermission', 'CoursePermission'
)
__T = t.TypeVar('__T', bound='BasePermission')  # pylint: disable=invalid-name

_PermissionValue = t.NamedTuple('_PermissionValue', [('item', object), ('default_value', bool)])


def init_app(app: t.Any, skip_perm_check: bool) -> None:
    """Initialize flask app
    """
    if skip_perm_check:
        return
    database_permissions_sanity_check(app)  # pragma: no cover


def database_permissions_sanity_check(app: t.Any) -> None:
    """Check if database has all the correct permissions.
    """
    from . import models
    with app.app_context():
        import structlog

        logger = structlog.get_logger()

        from_enum = set((p, p.value.default_value) for p in list(GlobalPermission) + list(CoursePermission))
        from_database = set((p.value, p.default_value) for p in models.db.session.query(models.Permission).all())
        if from_enum != from_database:  # pragma: no cover
            logger.error('Not all permissions were found in the database', difference=from_enum ^ from_database)
            assert from_enum == from_database


CoursePermMap = t.NewType('CoursePermMap', t.Mapping[str, bool])
GlobalPermMap = t.NewType('GlobalPermMap', t.Mapping[str, bool])


class BasePermission(enum.Enum):
    """The base of a permission.

    Do not use this class to get permissions, as it has none!
    """

    @staticmethod
    def create_map(mapping: t.Any) -> t.Any:
        """Create a map.
        """
        return {k.name: v for k, v in mapping.items()}

    @classmethod
    def get_by_name(cls: t.Type['__T'], name: str) -> '__T':
        """Get a permission by name.

        :param name: The name of the permission.
        :returns: The found permission.

        :raises exceptions.APIException: When the permission was not found.
        """
        try:
            return cls[name]
        except KeyError:
            raise exceptions.APIException(
                ('The requested permission '
                 '"{}" does not exist').format(name),
                'The requested course permission was not found',
                exceptions.APICodes.OBJECT_NOT_FOUND, 404
            )

    def __to_json__(self) -> str:  # pragma: no cover
        """Convert a permission to json.

        :returns: The name of the permission.
        """
        return self.name


    def __lt__(self, other: 'BasePermission') -> bool:  # pragma: no cover
        return self.value < other.value  # pylint: disable=comparison-with-callable


@enum.unique
class GlobalPermission(BasePermission):
    """The global permissions used by CodeGrade.

    .. warning::

      Do not edit this enum as it is automatically generated by
      "generate_permissions_py.py".

    :ivar can_add_users: Users with this permission can add other users to the website.
    :ivar can_use_snippets: Users with this permission can use the snippets feature on the website.
    :ivar can_edit_own_info: Users with this permission can edit their own personal information.
    :ivar can_edit_own_password: Users with this permission can edit their own password.
    :ivar can_create_courses: Users with this permission can create new courses.
    :ivar can_manage_site_users: Users with this permission can change the global permissions for other users on the site.
    :ivar can_search_users: Users with this permission can search for users on the side, this means they can see all other users on the site.
    :ivar can_impersonate_users: Users with this permission can impersonate users, i.e. they can login as other users.
    :ivar can_manage_lti_providers: Users with this permission can edit and list existing, and create new LTI providers.
    :ivar can_manage_sso_providers: Users with this permission can connect new SSO Identity Providers.
    """

    @staticmethod
    def create_map(mapping: t.Mapping['GlobalPermission', bool]) -> GlobalPermMap:
        return BasePermission.create_map(mapping)

    can_add_users = _PermissionValue(item=0, default_value=False)
    can_use_snippets = _PermissionValue(item=1, default_value=True)
    can_edit_own_info = _PermissionValue(item=2, default_value=True)
    can_edit_own_password = _PermissionValue(item=3, default_value=True)
    can_create_courses = _PermissionValue(item=4, default_value=False)
    can_manage_site_users = _PermissionValue(item=5, default_value=False)
    can_search_users = _PermissionValue(item=6, default_value=True)
    can_impersonate_users = _PermissionValue(item=7, default_value=False)
    can_manage_lti_providers = _PermissionValue(item=8, default_value=False)
    can_manage_sso_providers = _PermissionValue(item=9, default_value=False)


@enum.unique
class CoursePermission(BasePermission):
    """The course permissions used by CodeGrade.

    .. warning::

      Do not edit this enum as it is automatically generated by
      "generate_permissions_py.py".

    :ivar can_submit_others_work: Users with this permission can submit work to an assignment for other users. This means they can submit work that will have another user as the author.
    :ivar can_submit_own_work: Users with this permission can submit their work to assignments of this course. Usually only students have this permission.
    :ivar can_edit_others_work: Users with this permission can edit files in the submissions of this course. Usually TAs and teachers have this permission, so they can change files in the CodeGra.de filesystem if code doesn't compile, for example.
    :ivar can_grade_work: Users with this permission can grade submissions.
    :ivar can_see_grade_before_open: Users with this permission can see the grade for a submission before an assignment is set to "done".
    :ivar can_see_others_work: Users with this permission can see submissions of other users of this course.
    :ivar can_see_assignments: Users with this permission can view the assignments of this course.
    :ivar can_see_hidden_assignments: Users with this permission can view assignments of this course that are set to "hidden".
    :ivar can_use_linter: Users with this permission can run linters on all submissions of an assignment.
    :ivar can_edit_assignment_info: Users with this permission can update the assignment info such as name, deadline and status.
    :ivar can_assign_graders: Users with this permission can assign a grader to submissions of assignments.
    :ivar can_edit_cgignore: Users with this permission can edit the .cgignore file for an assignment.
    :ivar can_upload_bb_zip: Users with this permission can upload a zip file with submissions in the BlackBoard format.
    :ivar can_edit_course_roles: Users with this permission can assign or remove permissions from course roles and add new course roles.
    :ivar can_edit_course_users: Users with this permission can add users to this course and assign roles to those users.
    :ivar can_create_assignment: Users with this permission can create new assignments for this course.
    :ivar can_upload_after_deadline: Users with this permission can submit their work after the deadline of an assignment.
    :ivar can_see_assignee: Users with this permission can see who is assigned to assess a submission.
    :ivar manage_rubrics: Users with this permission can update the rubrics for the assignments of this course.
    :ivar can_view_own_teacher_files: Users with this permission can view the teacher's revision of their submitted work.
    :ivar can_see_grade_history: Users with this permission can see the grade history of an assignment.
    :ivar can_delete_submission: Users with this permission can delete submissions.
    :ivar can_update_grader_status: Users with this permission can change the status of graders for this course, whether they are done grading their assigned submissions or not.
    :ivar can_update_course_notifications: Users with this permission can change the all notifications that are configured for this course. This includes when to send them and who to send them to.
    :ivar can_edit_maximum_grade: Users with this permission can edit the maximum grade possible, and therefore also determine if getting a 'bonus' for an assignment is also possible.
    :ivar can_view_plagiarism: Users with this permission can view the summary of a plagiarism check and see details of a plagiarism case. To view a plagiarism case between this and another course, the user must also have either this permission, or both "See assignments" and "See other's work" in the other course.
    :ivar can_manage_plagiarism: Users with this permission can add and delete plagiarism runs.
    :ivar can_list_course_users: Users with this permission can see all users of this course including the name of their role.
    :ivar can_edit_own_groups: Users with this permission can edit groups they are in. This means they can join groups, add users to groups they are in and change the name of groups they are in. They cannot remove users from groups they are in, except for themselves.
    :ivar can_edit_others_groups: Users with this permission can edit groups they are not in, they can add users, remove users and rename all groups. Users with this permission can also edit groups they are in.
    :ivar can_edit_groups_after_submission: Users with this permission can edit groups which handed in a submission. Users with this permission cannot automatically edit groups, they also need either "Edit own groups" or "Edit others groups".
    :ivar can_view_others_groups: Users with this permission can view groups they are not in, and the members of these groups.
    :ivar can_edit_group_assignment: Users with this permission can change an assignment into a group assignment, and change the minimum and maximum required group size.
    :ivar can_edit_group_set: Users with this permissions can create, delete and edit group sets.
    :ivar can_create_groups: Users with this permission can create new groups in group assignments.
    :ivar can_view_course_snippets: Users with this permission can see the snippets of this course, and use them while writing feedback.
    :ivar can_manage_course_snippets: Users with this permission can create, edit, and delete snippets for this course.
    :ivar can_view_hidden_fixtures: Users with this permission can view hidden autotest fixtures.
    :ivar can_run_autotest: Users with this permission can start AutoTest runs
    :ivar can_delete_autotest_run: Users with this permission can delete AutoTest runs
    :ivar can_edit_autotest: Users with this permission can create, delete, edit the fixtures of, setup scripts of, and test sets of an AutoTest
    :ivar can_view_hidden_autotest_steps: Users with this permission can view hidden AutoTest steps if they have the permission to view the summary of this step
    :ivar can_view_autotest_before_done: Users with this permission can view AutoTest, such as sets, before the state of the assignment is "Open"
    :ivar can_view_autotest_step_details: Users with this permission are allowed to see the details of non hidden AutoTest steps
    :ivar can_view_autotest_fixture: Users with this permission are allowed to see non hidden AutoTest fixtures
    :ivar can_view_autotest_output_files_before_done: Users with this permission can view output files created during an AutoTest before the assignment state is "done"
    :ivar can_delete_assignments: Users with this permission can delete assignments within this course.
    :ivar can_override_submission_limiting: Users with this permission can create new submissions, even if the maximum amount of submissions has been reacher, or if a cool-off period is in effect.
    :ivar can_see_linter_feedback_before_done: Users with this permission can see the output of linters before an assignment is set to "done"
    :ivar can_see_user_feedback_before_done: Users with this permission can see feedback before an assignment is set to "done"
    :ivar can_view_analytics: Users with this permission can view the analytics dashboard of an assignment.
    :ivar can_edit_others_comments: Users with this permission can edit inline comments left by other users
    :ivar can_add_own_inline_comments: Users with this permission can add and reply to inline comments on submissions they are the author of
    :ivar can_view_others_comment_edits: Users with this permission may see the edit history of comments placed by others
    :ivar can_view_feedback_author: Users with this permission can view the author of inline and general feedback
    :ivar can_email_students: Users with this permission can email students using the contact student button.
    :ivar can_view_inline_feedback_before_approved: Users with this permission can view unapproved inline comments, comments that need approval include peer feedback comments. Users still need to have the permission to see the feedback, so this permission alone is not enough to see peer feedback.
    :ivar can_approve_inline_comments: Users with this permission can approve inline comments, comments that need approval include peer feedback comments.
    :ivar can_edit_peer_feedback_settings: Users with this permission can edit the peer feedback status of an assignment.
    :ivar can_receive_login_links: Users with this permission will receive login links if this is enabled for the assignment. You should not give this permission to users with powerful permissions (such as "Can grade work").
    """

    @staticmethod
    def create_map(mapping: t.Mapping['CoursePermission', bool]) -> CoursePermMap:
        return BasePermission.create_map(mapping)

    can_submit_others_work = _PermissionValue(item=0, default_value=False)
    can_submit_own_work = _PermissionValue(item=1, default_value=True)
    can_edit_others_work = _PermissionValue(item=2, default_value=False)
    can_grade_work = _PermissionValue(item=3, default_value=False)
    can_see_grade_before_open = _PermissionValue(item=4, default_value=False)
    can_see_others_work = _PermissionValue(item=5, default_value=False)
    can_see_assignments = _PermissionValue(item=6, default_value=True)
    can_see_hidden_assignments = _PermissionValue(item=7, default_value=False)
    can_use_linter = _PermissionValue(item=8, default_value=False)
    can_edit_assignment_info = _PermissionValue(item=9, default_value=False)
    can_assign_graders = _PermissionValue(item=10, default_value=False)
    can_edit_cgignore = _PermissionValue(item=11, default_value=False)
    can_upload_bb_zip = _PermissionValue(item=12, default_value=False)
    can_edit_course_roles = _PermissionValue(item=13, default_value=False)
    can_edit_course_users = _PermissionValue(item=14, default_value=False)
    can_create_assignment = _PermissionValue(item=15, default_value=False)
    can_upload_after_deadline = _PermissionValue(item=16, default_value=False)
    can_see_assignee = _PermissionValue(item=17, default_value=False)
    manage_rubrics = _PermissionValue(item=18, default_value=False)
    can_view_own_teacher_files = _PermissionValue(item=19, default_value=True)
    can_see_grade_history = _PermissionValue(item=20, default_value=False)
    can_delete_submission = _PermissionValue(item=21, default_value=False)
    can_update_grader_status = _PermissionValue(item=22, default_value=False)
    can_update_course_notifications = _PermissionValue(item=23, default_value=False)
    can_edit_maximum_grade = _PermissionValue(item=24, default_value=False)
    can_view_plagiarism = _PermissionValue(item=25, default_value=False)
    can_manage_plagiarism = _PermissionValue(item=26, default_value=False)
    can_list_course_users = _PermissionValue(item=27, default_value=True)
    can_edit_own_groups = _PermissionValue(item=28, default_value=True)
    can_edit_others_groups = _PermissionValue(item=29, default_value=False)
    can_edit_groups_after_submission = _PermissionValue(item=30, default_value=False)
    can_view_others_groups = _PermissionValue(item=31, default_value=True)
    can_edit_group_assignment = _PermissionValue(item=32, default_value=False)
    can_edit_group_set = _PermissionValue(item=33, default_value=False)
    can_create_groups = _PermissionValue(item=34, default_value=True)
    can_view_course_snippets = _PermissionValue(item=35, default_value=False)
    can_manage_course_snippets = _PermissionValue(item=36, default_value=False)
    can_view_hidden_fixtures = _PermissionValue(item=37, default_value=False)
    can_run_autotest = _PermissionValue(item=38, default_value=False)
    can_delete_autotest_run = _PermissionValue(item=39, default_value=False)
    can_edit_autotest = _PermissionValue(item=40, default_value=False)
    can_view_hidden_autotest_steps = _PermissionValue(item=41, default_value=False)
    can_view_autotest_before_done = _PermissionValue(item=42, default_value=False)
    can_view_autotest_step_details = _PermissionValue(item=43, default_value=True)
    can_view_autotest_fixture = _PermissionValue(item=44, default_value=True)
    can_view_autotest_output_files_before_done = _PermissionValue(item=45, default_value=False)
    can_delete_assignments = _PermissionValue(item=46, default_value=False)
    can_override_submission_limiting = _PermissionValue(item=47, default_value=False)
    can_see_linter_feedback_before_done = _PermissionValue(item=48, default_value=False)
    can_see_user_feedback_before_done = _PermissionValue(item=49, default_value=False)
    can_view_analytics = _PermissionValue(item=50, default_value=False)
    can_edit_others_comments = _PermissionValue(item=51, default_value=False)
    can_add_own_inline_comments = _PermissionValue(item=52, default_value=False)
    can_view_others_comment_edits = _PermissionValue(item=53, default_value=False)
    can_view_feedback_author = _PermissionValue(item=54, default_value=True)
    can_email_students = _PermissionValue(item=55, default_value=False)
    can_view_inline_feedback_before_approved = _PermissionValue(item=56, default_value=False)
    can_approve_inline_comments = _PermissionValue(item=57, default_value=False)
    can_edit_peer_feedback_settings = _PermissionValue(item=58, default_value=False)
    can_receive_login_links = _PermissionValue(item=59, default_value=True)


@dataclasses.dataclass(frozen=True)
class UnknownPermission:
    name: str

    @property
    def default_value(self) -> None:  # pragma: no cover
        raise AssertionError('This is not a real permission')

# yapf: enable
