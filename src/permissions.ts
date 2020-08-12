/**
This file contains permissions


Do not edit this enum as it is automatically generated by
"generate_permissions_ts.py".

SPDX-License-Identifier: AGPL-3.0-only
*/

/* eslint-disable */
export type GlobalPermissionOptions =
    | 'can_add_users'
    | 'can_use_snippets'
    | 'can_edit_own_info'
    | 'can_edit_own_password'
    | 'can_create_courses'
    | 'can_manage_site_users'
    | 'can_search_users'
    | 'can_impersonate_users'
    | 'can_manage_lti_providers'
    | 'can_manage_sso_providers';
const makeGPerm = (value: GlobalPermissionOptions, name: string, description: string, warning: string | null) => ({ value, name, description, warning });
export const GlobalPermission = {
    canAddUsers: makeGPerm('can_add_users', 'Add users', 'Users with this permission can add other users to the website.', null),
    canUseSnippets: makeGPerm('can_use_snippets', 'Snippets', 'Users with this permission can use the snippets feature on the website.', null),
    canEditOwnInfo: makeGPerm('can_edit_own_info', 'Edit user info', 'Users with this permission can edit their own personal information.', null),
    canEditOwnPassword: makeGPerm('can_edit_own_password', 'Edit password', 'Users with this permission can edit their own password.', null),
    canCreateCourses: makeGPerm('can_create_courses', 'Create course', 'Users with this permission can create new courses.', null),
    canManageSiteUsers: makeGPerm('can_manage_site_users', 'Manage site users', 'Users with this permission can change the global permissions for other users on the site.', null),
    canSearchUsers: makeGPerm('can_search_users', 'Search users', 'Users with this permission can search for users on the side, this means they can see all other users on the site.', null),
    canImpersonateUsers: makeGPerm('can_impersonate_users', 'Impersonate users', 'Users with this permission can impersonate users, i.e. they can login as other users.', null),
    canManageLtiProviders: makeGPerm('can_manage_lti_providers', 'Manage LTI providers', 'Users with this permission can edit and list existing, and create new LTI providers.', 'This is a really powerful permission, only give to users you trust completely.'),
    canManageSsoProviders: makeGPerm('can_manage_sso_providers', 'Manage SSO Providers', 'Users with this permission can connect new SSO Identity Providers.', null),
};
export type GlobalPermission = typeof GlobalPermission[keyof typeof GlobalPermission];

export type CoursePermissionOptions =
    | 'can_submit_others_work'
    | 'can_submit_own_work'
    | 'can_edit_others_work'
    | 'can_grade_work'
    | 'can_see_grade_before_open'
    | 'can_see_others_work'
    | 'can_see_assignments'
    | 'can_see_hidden_assignments'
    | 'can_use_linter'
    | 'can_edit_assignment_info'
    | 'can_assign_graders'
    | 'can_edit_cgignore'
    | 'can_upload_bb_zip'
    | 'can_edit_course_roles'
    | 'can_edit_course_users'
    | 'can_create_assignment'
    | 'can_upload_after_deadline'
    | 'can_see_assignee'
    | 'manage_rubrics'
    | 'can_view_own_teacher_files'
    | 'can_see_grade_history'
    | 'can_delete_submission'
    | 'can_update_grader_status'
    | 'can_update_course_notifications'
    | 'can_edit_maximum_grade'
    | 'can_view_plagiarism'
    | 'can_manage_plagiarism'
    | 'can_list_course_users'
    | 'can_edit_own_groups'
    | 'can_edit_others_groups'
    | 'can_edit_groups_after_submission'
    | 'can_view_others_groups'
    | 'can_edit_group_assignment'
    | 'can_edit_group_set'
    | 'can_create_groups'
    | 'can_view_course_snippets'
    | 'can_manage_course_snippets'
    | 'can_view_hidden_fixtures'
    | 'can_run_autotest'
    | 'can_delete_autotest_run'
    | 'can_edit_autotest'
    | 'can_view_hidden_autotest_steps'
    | 'can_view_autotest_before_done'
    | 'can_view_autotest_step_details'
    | 'can_view_autotest_fixture'
    | 'can_view_autotest_output_files_before_done'
    | 'can_delete_assignments'
    | 'can_override_submission_limiting'
    | 'can_see_linter_feedback_before_done'
    | 'can_see_user_feedback_before_done'
    | 'can_view_analytics'
    | 'can_edit_others_comments'
    | 'can_add_own_inline_comments'
    | 'can_view_others_comment_edits'
    | 'can_view_feedback_author'
    | 'can_email_students'
    | 'can_view_inline_feedback_before_approved'
    | 'can_approve_inline_comments'
    | 'can_edit_peer_feedback_settings'
    | 'can_receive_login_links';
const makeCPerm = (value: CoursePermissionOptions, name: string, description: string, warning: string | null) => ({ value, name, description, warning });
export const CoursePermission = {
    canSubmitOthersWork: makeCPerm('can_submit_others_work', 'Submit others work', 'Users with this permission can submit work to an assignment for other users. This means they can submit work that will have another user as the author.', null),
    canSubmitOwnWork: makeCPerm('can_submit_own_work', 'Submit own work', 'Users with this permission can submit their work to assignments of this course. Usually only students have this permission.', null),
    canEditOthersWork: makeCPerm('can_edit_others_work', 'Edit others work', 'Users with this permission can edit files in the submissions of this course. Usually TAs and teachers have this permission, so they can change files in the CodeGra.de filesystem if code doesn\'t compile, for example.', null),
    canGradeWork: makeCPerm('can_grade_work', 'Grade submission', 'Users with this permission can grade submissions.', null),
    canSeeGradeBeforeOpen: makeCPerm('can_see_grade_before_open', 'See grade before done', 'Users with this permission can see the grade for a submission before an assignment is set to "done".', null),
    canSeeOthersWork: makeCPerm('can_see_others_work', 'See others submission', 'Users with this permission can see submissions of other users of this course.', null),
    canSeeAssignments: makeCPerm('can_see_assignments', 'See assignments', 'Users with this permission can view the assignments of this course.', null),
    canSeeHiddenAssignments: makeCPerm('can_see_hidden_assignments', 'See hidden assignments', 'Users with this permission can view assignments of this course that are set to "hidden".', null),
    canUseLinter: makeCPerm('can_use_linter', 'Linter', 'Users with this permission can run linters on all submissions of an assignment.', null),
    canEditAssignmentInfo: makeCPerm('can_edit_assignment_info', 'Edit assignment info', 'Users with this permission can update the assignment info such as name, deadline and status.', null),
    canAssignGraders: makeCPerm('can_assign_graders', 'Assign graders', 'Users with this permission can assign a grader to submissions of assignments.', null),
    canEditCgignore: makeCPerm('can_edit_cgignore', 'Edit .cgignore', 'Users with this permission can edit the .cgignore file for an assignment.', null),
    canUploadBbZip: makeCPerm('can_upload_bb_zip', 'Upload BlackBoard zip', 'Users with this permission can upload a zip file with submissions in the BlackBoard format.', null),
    canEditCourseRoles: makeCPerm('can_edit_course_roles', 'Edit course roles', 'Users with this permission can assign or remove permissions from course roles and add new course roles.', 'With this permission a user can change all permissions for everyone in this course. Users can not remove this permission from themselves.'),
    canEditCourseUsers: makeCPerm('can_edit_course_users', 'Edit course users', 'Users with this permission can add users to this course and assign roles to those users.', null),
    canCreateAssignment: makeCPerm('can_create_assignment', 'Create assignment', 'Users with this permission can create new assignments for this course.', null),
    canUploadAfterDeadline: makeCPerm('can_upload_after_deadline', 'Upload after deadline', 'Users with this permission can submit their work after the deadline of an assignment.', null),
    canSeeAssignee: makeCPerm('can_see_assignee', 'See assignee', 'Users with this permission can see who is assigned to assess a submission.', null),
    manageRubrics: makeCPerm('manage_rubrics', 'Manage rubrics', 'Users with this permission can update the rubrics for the assignments of this course.', null),
    canViewOwnTeacherFiles: makeCPerm('can_view_own_teacher_files', 'View teacher revision', 'Users with this permission can view the teacher\'s revision of their submitted work.', null),
    canSeeGradeHistory: makeCPerm('can_see_grade_history', 'Grade history', 'Users with this permission can see the grade history of an assignment.', null),
    canDeleteSubmission: makeCPerm('can_delete_submission', 'Delete submission', 'Users with this permission can delete submissions.', null),
    canUpdateGraderStatus: makeCPerm('can_update_grader_status', 'Update grader status', 'Users with this permission can change the status of graders for this course, whether they are done grading their assigned submissions or not.', null),
    canUpdateCourseNotifications: makeCPerm('can_update_course_notifications', 'Update course notifications', 'Users with this permission can change the all notifications that are configured for this course. This includes when to send them and who to send them to.', null),
    canEditMaximumGrade: makeCPerm('can_edit_maximum_grade', 'Edit the maximum grade possible', 'Users with this permission can edit the maximum grade possible, and therefore also determine if getting a \'bonus\' for an assignment is also possible.', null),
    canViewPlagiarism: makeCPerm('can_view_plagiarism', 'View plagiarism', 'Users with this permission can view the summary of a plagiarism check and see details of a plagiarism case. To view a plagiarism case between this and another course, the user must also have either this permission, or both "See assignments" and "See other\'s work" in the other course.', 'This permission also implies the "See assignments" and "See other\'s work" permissions in this course.'),
    canManagePlagiarism: makeCPerm('can_manage_plagiarism', 'Manage plagiarism', 'Users with this permission can add and delete plagiarism runs.', null),
    canListCourseUsers: makeCPerm('can_list_course_users', 'List course users', 'Users with this permission can see all users of this course including the name of their role.', null),
    canEditOwnGroups: makeCPerm('can_edit_own_groups', 'Edit own groups', 'Users with this permission can edit groups they are in. This means they can join groups, add users to groups they are in and change the name of groups they are in. They cannot remove users from groups they are in, except for themselves.', null),
    canEditOthersGroups: makeCPerm('can_edit_others_groups', 'Edit others groups', 'Users with this permission can edit groups they are not in, they can add users, remove users and rename all groups. Users with this permission can also edit groups they are in.', null),
    canEditGroupsAfterSubmission: makeCPerm('can_edit_groups_after_submission', 'Edit groups after first submission', 'Users with this permission can edit groups which handed in a submission. Users with this permission cannot automatically edit groups, they also need either "Edit own groups" or "Edit others groups".', null),
    canViewOthersGroups: makeCPerm('can_view_others_groups', 'View others groups', 'Users with this permission can view groups they are not in, and the members of these groups.', null),
    canEditGroupAssignment: makeCPerm('can_edit_group_assignment', 'Edit group assignment', 'Users with this permission can change an assignment into a group assignment, and change the minimum and maximum required group size.', null),
    canEditGroupSet: makeCPerm('can_edit_group_set', 'Edit group set', 'Users with this permissions can create, delete and edit group sets.', null),
    canCreateGroups: makeCPerm('can_create_groups', 'Create groups', 'Users with this permission can create new groups in group assignments.', null),
    canViewCourseSnippets: makeCPerm('can_view_course_snippets', 'View course snippets', 'Users with this permission can see the snippets of this course, and use them while writing feedback.', null),
    canManageCourseSnippets: makeCPerm('can_manage_course_snippets', 'Manage course snippets', 'Users with this permission can create, edit, and delete snippets for this course.', null),
    canViewHiddenFixtures: makeCPerm('can_view_hidden_fixtures', 'View hidden AutoTest fixtures', 'Users with this permission can view hidden autotest fixtures.', null),
    canRunAutotest: makeCPerm('can_run_autotest', 'Run an AutoTest configuration', 'Users with this permission can start AutoTest runs', null),
    canDeleteAutotestRun: makeCPerm('can_delete_autotest_run', 'Delete an AutoTest run', 'Users with this permission can delete AutoTest runs', null),
    canEditAutotest: makeCPerm('can_edit_autotest', 'Edit the configuration of an AutoTest', 'Users with this permission can create, delete, edit the fixtures of, setup scripts of, and test sets of an AutoTest', null),
    canViewHiddenAutotestSteps: makeCPerm('can_view_hidden_autotest_steps', 'View the details of hidden AutoTest steps', 'Users with this permission can view hidden AutoTest steps if they have the permission to view the summary of this step', null),
    canViewAutotestBeforeDone: makeCPerm('can_view_autotest_before_done', 'View AutoTest details before done', 'Users with this permission can view AutoTest, such as sets, before the state of the assignment is "Open"', null),
    canViewAutotestStepDetails: makeCPerm('can_view_autotest_step_details', 'View the details of AutoTest steps', 'Users with this permission are allowed to see the details of non hidden AutoTest steps', null),
    canViewAutotestFixture: makeCPerm('can_view_autotest_fixture', 'View non hidden AutoTest fixtures', 'Users with this permission are allowed to see non hidden AutoTest fixtures', null),
    canViewAutotestOutputFilesBeforeDone: makeCPerm('can_view_autotest_output_files_before_done', 'View AutoTest output files before done', 'Users with this permission can view output files created during an AutoTest before the assignment state is "done"', null),
    canDeleteAssignments: makeCPerm('can_delete_assignments', 'Delete assignments', 'Users with this permission can delete assignments within this course.', 'With this permission a user can delete assignments which cannot be reverted.'),
    canOverrideSubmissionLimiting: makeCPerm('can_override_submission_limiting', 'Override submission limiting', 'Users with this permission can create new submissions, even if the maximum amount of submissions has been reacher, or if a cool-off period is in effect.', null),
    canSeeLinterFeedbackBeforeDone: makeCPerm('can_see_linter_feedback_before_done', 'See linter feedback before done', 'Users with this permission can see the output of linters before an assignment is set to "done"', null),
    canSeeUserFeedbackBeforeDone: makeCPerm('can_see_user_feedback_before_done', 'See feedback before done', 'Users with this permission can see feedback before an assignment is set to "done"', null),
    canViewAnalytics: makeCPerm('can_view_analytics', 'Can view analytics', 'Users with this permission can view the analytics dashboard of an assignment.', 'With this permission a user can request all the grades, and count all the feedback for all the submissions in this course. Use with caution!'),
    canEditOthersComments: makeCPerm('can_edit_others_comments', 'Edit inline comments by others', 'Users with this permission can edit inline comments left by other users', null),
    canAddOwnInlineComments: makeCPerm('can_add_own_inline_comments', 'Add inline comments to own submissions', 'Users with this permission can add and reply to inline comments on submissions they are the author of', null),
    canViewOthersCommentEdits: makeCPerm('can_view_others_comment_edits', 'View others comment edits', 'Users with this permission may see the edit history of comments placed by others', null),
    canViewFeedbackAuthor: makeCPerm('can_view_feedback_author', 'View feedback author', 'Users with this permission can view the author of inline and general feedback', null),
    canEmailStudents: makeCPerm('can_email_students', 'Can email students', 'Users with this permission can email students using the contact student button.', null),
    canViewInlineFeedbackBeforeApproved: makeCPerm('can_view_inline_feedback_before_approved', 'View peer feedback before approved', 'Users with this permission can view unapproved inline comments, comments that need approval include peer feedback comments. Users still need to have the permission to see the feedback, so this permission alone is not enough to see peer feedback.', null),
    canApproveInlineComments: makeCPerm('can_approve_inline_comments', 'Approve inline comments', 'Users with this permission can approve inline comments, comments that need approval include peer feedback comments.', null),
    canEditPeerFeedbackSettings: makeCPerm('can_edit_peer_feedback_settings', 'Edit peer feedback settings', 'Users with this permission can edit the peer feedback status of an assignment.', null),
    canReceiveLoginLinks: makeCPerm('can_receive_login_links', 'Receive login links', 'Users with this permission will (and can) receive login links if this is enabled for the assignment. You should not give this permission to users with powerful permissions (such as "Can grade work").', null),
};
export type CoursePermission = typeof CoursePermission[keyof typeof CoursePermission];
/* eslint-enable */
