/* eslint-disable */
export interface FrontendSiteSettings {
    // The default amount of time a step/substep in AutoTest can run. This can
    // be overridden by the teacher.
    AUTO_TEST_MAX_TIME_COMMAND: number;
    // The maximum time-delta an exam may take. Increasing this value also
    // increases the maximum amount of time the login tokens send via email are
    // valid. Therefore, you should make this too long.
    EXAM_LOGIN_MAX_LENGTH: number;
    // This determines how long before the exam we will send the login emails
    // to the students (only when enabled of course).
    LOGIN_TOKEN_BEFORE_TIME: readonly number[];
    // The email shown to users as the email of CodeGrade.
    SITE_EMAIL: string;
    // The maximum amount of lines that we should in render in one go. If a
    // file contains more lines than this we will show a warning asking the
    // user what to do.
    MAX_LINES: number;
    // The amount of time to wait between two consecutive polls to see if a
    // user has new notifications. Setting this value too low will cause
    // unnecessary stres on the server.
    NOTIFICATION_POLL_TIME: number;
    // What is the maximum amount of time after a release a message should be
    // shown on the HomeGrid. **Note**: this is the amount of time after the
    // release, not after this instance has been upgraded to this release.
    RELEASE_MESSAGE_MAX_TIME: number;
    // If enabled teachers are allowed to bulk upload submissions (and create
    // users) using a zip file in a format created by Blackboard.
    BLACKBOARD_ZIP_UPLOAD_ENABLED: boolean;
    // If enabled teachers can use rubrics on CodeGrade. Disabling this feature
    // will not delete existing rubrics.
    RUBRICS_ENABLED: boolean;
    // Currently unused
    AUTOMATIC_LTI_ROLE_ENABLED: boolean;
    // Should LTI be enabled.
    LTI_ENABLED: boolean;
    // Should linters be enabled
    LINTERS_ENABLED: boolean;
    // Should rubrics be submitted incrementally, so if a user selects a item
    // should this be automatically be submitted to the server, or should it
    // only be possible to submit a complete rubric at once. This feature is
    // useless if `rubrics` is not set to `true`.
    INCREMENTAL_RUBRIC_SUBMISSION_ENABLED: boolean;
    // Should it be possible to register on the website. This makes it possible
    // for any body to register an account on the website.
    REGISTER_ENABLED: boolean;
    // Should group assignments be enabled.
    GROUPS_ENABLED: boolean;
    // Should auto test be enabled.
    AUTO_TEST_ENABLED: boolean;
    // Should it be possible for teachers to create links that users can use to
    // register in a course. Links to enroll can be created even if this
    // feature is disabled.
    COURSE_REGISTER_ENABLED: boolean;
    // Should it be possible to render html files within CodeGrade. This opens
    // up more attack surfaces as it is now possible by design for students to
    // run javascript. This is all done in a sandboxed iframe but still.
    RENDER_HTML_ENABLED: boolean;
    // Should it be possible to email students.
    EMAIL_STUDENTS_ENABLED: boolean;
    // Should peer feedback be enabled.
    PEER_FEEDBACK_ENABLED: boolean;
}

export interface SiteSettings extends FrontendSiteSettings {
    // The amount of time there can be between two heartbeats of a runner.
    // Changing this to a lower value might cause some runners to crash.
    AUTO_TEST_HEARTBEAT_INTERVAL: number;
    // The max amount of heartbeats that we may miss from a runner before we
    // kill it and start a new one.
    AUTO_TEST_HEARTBEAT_MAX_MISSED: number;
    // This value determines the amount of runners we request for a single
    // assignment. The amount of runners requested is equal to the amount of
    // students not yet started divided by this value.
    AUTO_TEST_MAX_JOBS_PER_RUNNER: number;
    // The maximum amount of batch AutoTest runs we will do at a time. AutoTest
    // batch runs are runs that are done after the deadline for configurations
    // that have hidden tests. Increasing this variable might cause heavy
    // server load.
    AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS: number;
    // The minimum strength passwords by users should have. The higher this
    // value the stronger the password should be. When increasing the strength
    // all users with too weak passwords will be shown a warning on the next
    // login.
    MIN_PASSWORD_SCORE: number;
    // The amount of time a reset token is valid. You should not increase this
    // value too much as users might be not be too careful with these tokens.
    // Increasing this value will allow **all** existing tokens to live longer.
    RESET_TOKEN_TIME: number;
    // The amount of time the link send in notification emails to change the
    // notification preferences works to actually change the notifications.
    SETTING_TOKEN_TIME: number;
    // The maximum amount of files and directories allowed in a single archive.
    MAX_NUMBER_OF_FILES: number;
    // The maximum size of uploaded files that are mostly uploaded by "trusted"
    // users. Examples of these kind of files include AutoTest fixtures and
    // plagiarism base code.
    MAX_LARGE_UPLOAD_SIZE: number;
    // The maximum total size of uploaded files that are uploaded by normal
    // users. This is also the maximum total size of submissions. Increasing
    // this size might cause a hosting costs to increase.
    MAX_NORMAL_UPLOAD_SIZE: number;
    // The maximum size of a single file uploaded by normal users. This limit
    // is really here to prevent users from uploading extremely large files
    // which can't really be downloaded/shown anyway.
    MAX_FILE_SIZE: number;
    // The time a login session is valid. After this amount of time a user will
    // always need to re-authenticate.
    JWT_ACCESS_TOKEN_EXPIRES: number;
}

export const FRONTEND_SETTINGS_DEFAULTS = Object.freeze(<const>{
    AUTO_TEST_MAX_TIME_COMMAND: 300.0,
    EXAM_LOGIN_MAX_LENGTH: 43200.0,
    LOGIN_TOKEN_BEFORE_TIME: [172800.0, 1800.0],
    SITE_EMAIL: "info@codegrade.com",
    MAX_LINES: 2500,
    NOTIFICATION_POLL_TIME: 30.0,
    RELEASE_MESSAGE_MAX_TIME: 2592000.0,
    BLACKBOARD_ZIP_UPLOAD_ENABLED: true,
    RUBRICS_ENABLED: true,
    AUTOMATIC_LTI_ROLE_ENABLED: true,
    LTI_ENABLED: true,
    LINTERS_ENABLED: true,
    INCREMENTAL_RUBRIC_SUBMISSION_ENABLED: true,
    REGISTER_ENABLED: false,
    GROUPS_ENABLED: false,
    AUTO_TEST_ENABLED: false,
    COURSE_REGISTER_ENABLED: false,
    RENDER_HTML_ENABLED: false,
    EMAIL_STUDENTS_ENABLED: false,
    PEER_FEEDBACK_ENABLED: false,
});

export const ALL_SITE_SETTINGS = Object.freeze(<const>[
    { name: 'AUTO_TEST_MAX_TIME_COMMAND', typ: 'number', doc: 'The default amount of time a step/substep in AutoTest can run. This can be overridden by the teacher.', format: 'timedelta', group: "General", list: false },
    { name: 'AUTO_TEST_HEARTBEAT_INTERVAL', typ: 'number', doc: 'The amount of time there can be between two heartbeats of a runner. Changing this to a lower value might cause some runners to crash.', format: 'timedelta', group: "General", list: false },
    { name: 'AUTO_TEST_HEARTBEAT_MAX_MISSED', typ: 'number', doc: 'The max amount of heartbeats that we may miss from a runner before we kill it and start a new one.', format: '', group: "General", list: false },
    { name: 'AUTO_TEST_MAX_JOBS_PER_RUNNER', typ: 'number', doc: 'This value determines the amount of runners we request for a single assignment. The amount of runners requested is equal to the amount of students not yet started divided by this value.', format: '', group: "General", list: false },
    { name: 'AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS', typ: 'number', doc: 'The maximum amount of batch AutoTest runs we will do at a time. AutoTest batch runs are runs that are done after the deadline for configurations that have hidden tests. Increasing this variable might cause heavy server load.', format: '', group: "General", list: false },
    { name: 'EXAM_LOGIN_MAX_LENGTH', typ: 'number', doc: 'The maximum time-delta an exam may take. Increasing this value also increases the maximum amount of time the login tokens send via email are valid. Therefore, you should make this too long.', format: 'timedelta', group: "General", list: false },
    { name: 'LOGIN_TOKEN_BEFORE_TIME', typ: 'number', doc: 'This determines how long before the exam we will send the login emails to the students (only when enabled of course).', format: 'timedelta', group: "General", list: true },
    { name: 'MIN_PASSWORD_SCORE', typ: 'number', doc: 'The minimum strength passwords by users should have. The higher this value the stronger the password should be. When increasing the strength all users with too weak passwords will be shown a warning on the next login.', format: '', group: "General", list: false },
    { name: 'RESET_TOKEN_TIME', typ: 'number', doc: 'The amount of time a reset token is valid. You should not increase this value too much as users might be not be too careful with these tokens. Increasing this value will allow **all** existing tokens to live longer.', format: 'timedelta', group: "General", list: false },
    { name: 'SETTING_TOKEN_TIME', typ: 'number', doc: 'The amount of time the link send in notification emails to change the notification preferences works to actually change the notifications.', format: 'timedelta', group: "General", list: false },
    { name: 'SITE_EMAIL', typ: 'string', doc: 'The email shown to users as the email of CodeGrade.', format: '', group: "General", list: false },
    { name: 'MAX_NUMBER_OF_FILES', typ: 'number', doc: 'The maximum amount of files and directories allowed in a single archive.', format: '', group: "General", list: false },
    { name: 'MAX_LARGE_UPLOAD_SIZE', typ: 'number', doc: 'The maximum size of uploaded files that are mostly uploaded by "trusted" users. Examples of these kind of files include AutoTest fixtures and plagiarism base code.', format: 'filesize', group: "General", list: false },
    { name: 'MAX_NORMAL_UPLOAD_SIZE', typ: 'number', doc: 'The maximum total size of uploaded files that are uploaded by normal users. This is also the maximum total size of submissions. Increasing this size might cause a hosting costs to increase.', format: 'filesize', group: "General", list: false },
    { name: 'MAX_FILE_SIZE', typ: 'number', doc: "The maximum size of a single file uploaded by normal users. This limit is really here to prevent users from uploading extremely large files which can't really be downloaded/shown anyway.", format: 'filesize', group: "General", list: false },
    { name: 'JWT_ACCESS_TOKEN_EXPIRES', typ: 'number', doc: 'The time a login session is valid. After this amount of time a user will always need to re-authenticate.', format: 'timedelta', group: "General", list: false },
    { name: 'MAX_LINES', typ: 'number', doc: 'The maximum amount of lines that we should in render in one go. If a file contains more lines than this we will show a warning asking the user what to do.', format: '', group: "General", list: false },
    { name: 'NOTIFICATION_POLL_TIME', typ: 'number', doc: 'The amount of time to wait between two consecutive polls to see if a user has new notifications. Setting this value too low will cause unnecessary stres on the server.', format: 'timedelta', group: "General", list: false },
    { name: 'RELEASE_MESSAGE_MAX_TIME', typ: 'number', doc: 'What is the maximum amount of time after a release a message should be shown on the HomeGrid. **Note**: this is the amount of time after the release, not after this instance has been upgraded to this release.', format: 'timedelta', group: "General", list: false },
    { name: 'BLACKBOARD_ZIP_UPLOAD_ENABLED', typ: 'boolean', doc: 'If enabled teachers are allowed to bulk upload submissions (and create users) using a zip file in a format created by Blackboard.', format: '', group: "Features", list: false },
    { name: 'RUBRICS_ENABLED', typ: 'boolean', doc: 'If enabled teachers can use rubrics on CodeGrade. Disabling this feature will not delete existing rubrics.', format: '', group: "Features", list: false },
    { name: 'AUTOMATIC_LTI_ROLE_ENABLED', typ: 'boolean', doc: 'Currently unused', format: '', group: "Features", list: false },
    { name: 'LTI_ENABLED', typ: 'boolean', doc: 'Should LTI be enabled.', format: '', group: "Features", list: false },
    { name: 'LINTERS_ENABLED', typ: 'boolean', doc: 'Should linters be enabled', format: '', group: "Features", list: false },
    { name: 'INCREMENTAL_RUBRIC_SUBMISSION_ENABLED', typ: 'boolean', doc: 'Should rubrics be submitted incrementally, so if a user selects a item should this be automatically be submitted to the server, or should it only be possible to submit a complete rubric at once. This feature is useless if `rubrics` is not set to `true`.', format: '', group: "Features", list: false },
    { name: 'REGISTER_ENABLED', typ: 'boolean', doc: 'Should it be possible to register on the website. This makes it possible for any body to register an account on the website.', format: '', group: "Features", list: false },
    { name: 'GROUPS_ENABLED', typ: 'boolean', doc: 'Should group assignments be enabled.', format: '', group: "Features", list: false },
    { name: 'AUTO_TEST_ENABLED', typ: 'boolean', doc: 'Should auto test be enabled.', format: '', group: "Features", list: false },
    { name: 'COURSE_REGISTER_ENABLED', typ: 'boolean', doc: 'Should it be possible for teachers to create links that users can use to register in a course. Links to enroll can be created even if this feature is disabled.', format: '', group: "Features", list: false },
    { name: 'RENDER_HTML_ENABLED', typ: 'boolean', doc: 'Should it be possible to render html files within CodeGrade. This opens up more attack surfaces as it is now possible by design for students to run javascript. This is all done in a sandboxed iframe but still.', format: '', group: "Features", list: false },
    { name: 'EMAIL_STUDENTS_ENABLED', typ: 'boolean', doc: 'Should it be possible to email students.', format: '', group: "Features", list: false },
    { name: 'PEER_FEEDBACK_ENABLED', typ: 'boolean', doc: 'Should peer feedback be enabled.', format: '', group: "Features", list: false },
]);

