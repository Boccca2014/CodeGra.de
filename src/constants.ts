/* SPDX-License-Identifier: AGPL-3.0-only */
export const MANAGE_AUTOTEST_PERMISSIONS = Object.freeze(<const>[
    'can_run_autotest',
    'can_delete_autotest_run',
    'can_edit_autotest',
]);

export const MANAGE_ASSIGNMENT_PERMISSIONS = Object.freeze(<const>[
    'can_edit_assignment_info',
    'can_assign_graders',
    'can_edit_cgignore',
    'can_grade_work',
    'can_update_grader_status',
    'can_use_linter',
    'can_update_course_notifications',
    'manage_rubrics',
    'can_upload_bb_zip',
    'can_submit_others_work',
    'can_edit_maximum_grade',
    'can_view_plagiarism',
    'can_manage_plagiarism',
    'can_edit_group_assignment',
    ...MANAGE_AUTOTEST_PERMISSIONS,
]);

export const MANAGE_GENERAL_COURSE_PERMISSIONS = Object.freeze(<const>[
    'can_edit_course_users',
    'can_edit_course_roles',
    'can_edit_group_set',
    'can_manage_course_snippets',
    'can_view_course_snippets',
    'can_email_students',
    'can_archive_courses',
    'can_edit_course_info',
]);

export const MANAGE_SITE_PERIMSSIONS = Object.freeze(<const>[
    'can_manage_site_users',
    'can_impersonate_users',
    'can_manage_lti_providers',
]);

export const PASSWORD_UNIQUE_MESSAGE =
    'Please make sure you use a unique password, and at least different from the password you use for your LMS.';

export const NO_LOGIN_ALLOWED_ROUTES = new Set(<const>['login', 'register']);

export const NO_LOGIN_REQUIRED_ROUTES = new Set(<const>[
    'login',
    'forgot',
    'reset-password',
    'register',
    'lti-launch',
    'login_and_redirect',
    'unsubscribe',
    'lti_provider_setup',
    'assignment_login',
    'course_enroll',
    'sso_login',
]);

export const NO_SIDEBAR_ROUTES = new Set(<const>[
    'lti-launch',
    'unsubscribe',
    'lti_provider_setup',
    'assignment_login',
    'course_enroll',
    'sso_login',
]);

export const NO_FOOTER_ROUTES = new Set(<const>[
    'submission',
    'submission_file',
    'plagiarism_detail',
]);

// Indicates an object in the store that has been requested but not returned by
// the server, e.g. if it does not exist or the user has no permission to see
// the object.
export const NONEXISTENT = Symbol('NONEXISTENT');
export type NONEXISTENT = typeof NONEXISTENT;

// Indicates that a value has not yet been set (e.g. in a model cache).
export const UNSET_SENTINEL = Symbol('UNSET_SENTINEL');
export type UNSET_SENTINEL = typeof UNSET_SENTINEL;

export const RUBRIC_BADGE_AT =
    '<div class="ml-1 badge badge-primary" title="This is an AutoTest category">AT</div>';

export const COLOR_PAIRS = Object.freeze(
    [
        <const>{ background: 'rgb( 44,  62,  80)', color: 'light' },
        <const>{ background: 'rgb(112, 163, 162)', color: 'dark' },
        <const>{ background: 'rgb(203,  84,  82)', color: 'light' },
        <const>{ background: 'rgb(234, 182, 108)', color: 'dark' },
        <const>{ background: 'rgb(214, 206,  91)', color: 'dark' },
        <const>{ background: 'rgb(167, 174, 145)', color: 'dark' },
        <const>{ background: 'rgb(223, 211, 170)', color: 'dark' },
        <const>{ background: 'rgb(149, 111,  72)', color: 'light' },
        <const>{ background: 'rgb(101, 104, 108)', color: 'light' },
        <const>{ background: 'rgb( 89, 141, 134)', color: 'light' },
        <const>{ background: 'rgb(217, 126, 113)', color: 'dark' },
        <const>{ background: 'rgb(223, 184, 121)', color: 'dark' },
        <const>{ background: 'rgb( 79,  95,  86)', color: 'light' },
        <const>{ background: 'rgb(234, 219, 147)', color: 'dark' },
        <const>{ background: 'rgb(204,  58,  40)', color: 'light' },
        <const>{ background: 'rgb(215, 206, 166)', color: 'dark' },
        <const>{ background: 'rgb( 93, 141, 125)', color: 'light' },
        <const>{ background: 'rgb(230, 220, 205)', color: 'dark' },
        <const>{ background: 'rgb(180, 174, 164)', color: 'dark' },
        <const>{ background: 'rgb(210, 207, 159)', color: 'dark' },
        <const>{ background: 'rgb(231, 238, 233)', color: 'dark' },
    ].map(x => Object.freeze(x)), // This `x` is needed for type inference.
);

export const INITIAL_COURSES_AMOUNT = 30;
