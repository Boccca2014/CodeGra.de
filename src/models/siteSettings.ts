export interface FrontendOptions {
    // Should peer feedback be enabled.
    AUTO_TEST_MAX_TIME_COMMAND: number;
    // Should peer feedback be enabled.
    EXAM_LOGIN_MAX_LENGTH: number;
    // Should peer feedback be enabled.
    LOGIN_TOKEN_BEFORE_TIME: readonly number[];
    // Should peer feedback be enabled.
    SITE_EMAIL: string;
    // Should peer feedback be enabled.
    MAX_LINES: number;
    // Should peer feedback be enabled.
    NOTIFICATION_POLL_TIME: number;
    // Should peer feedback be enabled.
    BLACKBOARD_ZIP_UPLOAD_ENABLED: boolean;
    // Should peer feedback be enabled.
    RUBRICS_ENABLED: boolean;
    // Should peer feedback be enabled.
    AUTOMATIC_LTI_ROLE_ENABLED: boolean;
    // Should peer feedback be enabled.
    LTI_ENABLED: boolean;
    // Should peer feedback be enabled.
    LINTERS_ENABLED: boolean;
    // Should peer feedback be enabled.
    INCREMENTAL_RUBRIC_SUBMISSION_ENABLED: boolean;
    // Should peer feedback be enabled.
    REGISTER_ENABLED: boolean;
    // Should peer feedback be enabled.
    GROUPS_ENABLED: boolean;
    // Should peer feedback be enabled.
    AUTO_TEST_ENABLED: boolean;
    // Should peer feedback be enabled.
    COURSE_REGISTER_ENABLED: boolean;
    // Should peer feedback be enabled.
    RENDER_HTML_ENABLED: boolean;
    // Should peer feedback be enabled.
    EMAIL_STUDENTS_ENABLED: boolean;
    // Should peer feedback be enabled.
    PEER_FEEDBACK_ENABLED: boolean;
}

export const FrontendOptionsDefaults = Object.freeze(<const>{
    AUTO_TEST_MAX_TIME_COMMAND: 300.0,
    EXAM_LOGIN_MAX_LENGTH: 43200.0,
    LOGIN_TOKEN_BEFORE_TIME: [172800.0, 1800.0],
    SITE_EMAIL: "info@codegrade.com",
    MAX_LINES: 2500,
    NOTIFICATION_POLL_TIME: 30.0,
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
