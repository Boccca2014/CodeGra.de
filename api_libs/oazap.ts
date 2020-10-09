/**
 * CodeGrade
 * v1
 * DO NOT MODIFY - This file has been generated using oazapfts.
 * See https://www.npmjs.com/package/oazapfts
 */
import * as Oazapfts from "oazapfts/lib/runtime";
import * as codec from "purify-ts/Codec";
import { Right } from "purify-ts/Either";
const isObject = (obj: unknown) => {
    return typeof obj === "object" && obj !== null && !Array.isArray(obj);
};
export const intersect = <T, U>(t: codec.Codec<T>, u: codec.Codec<U>): codec.Codec<T & U> => codec.Codec.custom({
    decode: (input) => {
        const et = t.decode(input);
        if (et.isLeft()) {
            return et;
        }
        const eu = u.decode(input);
        if (eu.isLeft()) {
            return eu;
        }
        const valuet = et.extract() as T;
        const valueu = eu.extract() as U;
        return isObject(valuet) && isObject(valueu)
            ? Right(Object.assign(valuet, valueu))
            : Right(valueu as T & U);
    },
    encode: (x) => {
        const valuet = t.encode(x);
        const valueu = u.encode(x);
        return isObject(valuet) && isObject(valueu)
            ? Object.assign(valuet, valueu)
            : valueu;
    },
});
export const defaults: Oazapfts.RequestOpts = {
    baseUrl: "",
};
const oazapfts = Oazapfts.runtime(defaults);
export function coerceToString(obj: Object | null | undefined): string {
    if (obj == null)
        return "";
    else if (typeof obj === "string")
        return obj;
    return `${obj}`;
}
function maybeAddQuery(base: string, query: undefined | Record<string, number | boolean | string>) {
    const queryEntries = Object.entries({
        extended: true,
        no_role_name: true,
        no_course_in_assignment: true,
        ...query,
    });
    if (queryEntries.length > 0) {
        const params = queryEntries
            .reduce((acc, [key, value]) => {
            acc.append(key, coerceToString(value));
            return acc;
        }, new URLSearchParams())
            .toString();
        return `${base}?${params}`;
    }
    return base;
}
export const OptFrontendOptsAsJSON = codec.Codec.interface({ AUTO_TEST_MAX_TIME_COMMAND: codec.number, EXAM_LOGIN_MAX_LENGTH: codec.number, LOGIN_TOKEN_BEFORE_TIME: codec.array(codec.number), SITE_EMAIL: codec.string, MAX_LINES: codec.number, NOTIFICATION_POLL_TIME: codec.number, BLACKBOARD_ZIP_UPLOAD_ENABLED: codec.boolean, RUBRICS_ENABLED: codec.boolean, AUTOMATIC_LTI_ROLE_ENABLED: codec.boolean, LTI_ENABLED: codec.boolean, LINTERS_ENABLED: codec.boolean, INCREMENTAL_RUBRIC_SUBMISSION_ENABLED: codec.boolean, REGISTER_ENABLED: codec.boolean, GROUPS_ENABLED: codec.boolean, AUTO_TEST_ENABLED: codec.boolean, COURSE_REGISTER_ENABLED: codec.boolean, RENDER_HTML_ENABLED: codec.boolean, EMAIL_STUDENTS_ENABLED: codec.boolean, PEER_FEEDBACK_ENABLED: codec.boolean });
export type OptFrontendOptsAsJSON = codec.GetInterface<typeof OptFrontendOptsAsJSON>;
export const OptAllOptsAsJSON = intersect(OptFrontendOptsAsJSON, codec.Codec.interface({ AUTO_TEST_HEARTBEAT_INTERVAL: codec.number, AUTO_TEST_HEARTBEAT_MAX_MISSED: codec.number, AUTO_TEST_MAX_JOBS_PER_RUNNER: codec.number, AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS: codec.number, MIN_PASSWORD_SCORE: codec.number, RESET_TOKEN_TIME: codec.number, SETTING_TOKEN_TIME: codec.number, MAX_NUMBER_OF_FILES: codec.number, MAX_LARGE_UPLOAD_SIZE: codec.number, MAX_NORMAL_UPLOAD_SIZE: codec.number, MAX_FILE_SIZE: codec.number, JWT_ACCESS_TOKEN_EXPIRES: codec.number }));
export type OptAllOptsAsJSON = codec.GetInterface<typeof OptAllOptsAsJSON>;
export const APICodes = codec.oneOf([
    codec.exactly("INCORRECT_PERMISSION"),
    codec.exactly("NOT_LOGGED_IN"),
    codec.exactly("OBJECT_ID_NOT_FOUND"),
    codec.exactly("OBJECT_WRONG_TYPE"),
    codec.exactly("MISSING_REQUIRED_PARAM"),
    codec.exactly("INVALID_PARAM"),
    codec.exactly("REQUEST_TOO_LARGE"),
    codec.exactly("LOGIN_FAILURE"),
    codec.exactly("INACTIVE_USER"),
    codec.exactly("INVALID_URL"),
    codec.exactly("OBJECT_NOT_FOUND"),
    codec.exactly("BLOCKED_ASSIGNMENT"),
    codec.exactly("INVALID_CREDENTIALS"),
    codec.exactly("INVALID_STATE"),
    codec.exactly("INVALID_OAUTH_REQUEST"),
    codec.exactly("DISABLED_SETTING"),
    codec.exactly("UNKOWN_ERROR"),
    codec.exactly("INVALID_FILE_IN_ARCHIVE"),
    codec.exactly("NO_FILES_SUBMITTED"),
    codec.exactly("RATE_LIMIT_EXCEEDED"),
    codec.exactly("OBJECT_ALREADY_EXISTS"),
    codec.exactly("INVALID_ARCHIVE"),
    codec.exactly("ROUTE_NOT_FOUND"),
    codec.exactly("WEAK_PASSWORD"),
    codec.exactly("INSUFFICIENT_GROUP_SIZE"),
    codec.exactly("ASSIGNMENT_RESULT_GROUP_NOT_READY"),
    codec.exactly("ASSIGNMENT_GROUP_FULL"),
    codec.exactly("UNSUPPORTED"),
    codec.exactly("ASSIGNMENT_DEADLINE_UNSET"),
    codec.exactly("PARSING_FAILED"),
    codec.exactly("UNSAFE_ARCHIVE"),
    codec.exactly("LOCKED_UPDATE"),
    codec.exactly("NOT_NEWEST_SUBMSSION"),
    codec.exactly("UPLOAD_TYPE_DISABLED"),
    codec.exactly("WEBHOOK_DIFFERENT_BRANCH"),
    codec.exactly("WEBHOOK_UNKNOWN_EVENT_TYPE"),
    codec.exactly("WEBHOOK_UNKOWN_TYPE"),
    codec.exactly("WEBHOOK_INVALID_REQUEST"),
    codec.exactly("WEBHOOK_UNKNOWN_REQUEST"),
    codec.exactly("WEBHOOK_DISABLED"),
    codec.exactly("OBJECT_EXPIRED"),
    codec.exactly("TOO_MANY_SUBMISSIONS"),
    codec.exactly("COOL_OFF_PERIOD_ACTIVE"),
    codec.exactly("MAILING_FAILED"),
    codec.exactly("LTI1_3_ERROR"),
    codec.exactly("LTI1_3_COOKIE_ERROR"),
    codec.exactly("LTI1_1_ERROR")
]);
export type APICodes = codec.GetInterface<typeof APICodes>;
export const BaseError = codec.Codec.interface({ message: codec.optional(codec.string), description: codec.optional(codec.string), code: codec.optional(APICodes), request_id: codec.optional(codec.string) });
export type BaseError = codec.GetInterface<typeof BaseError>;
export const FileRuleInputData = codec.Codec.interface({ rule_type: codec.oneOf([
        codec.exactly("allow"),
        codec.exactly("deny"),
        codec.exactly("require")
    ]), file_type: codec.oneOf([
        codec.exactly("file"),
        codec.exactly("directory")
    ]), name: codec.string });
export type FileRuleInputData = codec.GetInterface<typeof FileRuleInputData>;
export const OptionsInputData = codec.Codec.interface({ key: codec.oneOf([
        codec.exactly("delete_empty_directories"),
        codec.exactly("remove_leading_directories"),
        codec.exactly("allow_override")
    ]), value: codec.boolean });
export type OptionsInputData = codec.GetInterface<typeof OptionsInputData>;
export const SubmissionValidatorInputData = codec.Codec.interface({ policy: codec.oneOf([
        codec.exactly("deny_all_files"),
        codec.exactly("allow_all_files")
    ]), rules: codec.array(FileRuleInputData), options: codec.array(OptionsInputData) });
export type SubmissionValidatorInputData = codec.GetInterface<typeof SubmissionValidatorInputData>;
export const GroupSetAsJSON = codec.Codec.interface({ id: codec.number, minimum_size: codec.number, maximum_size: codec.number, assignment_ids: codec.array(codec.number) });
export type GroupSetAsJSON = codec.GetInterface<typeof GroupSetAsJSON>;
export const AssignmentPeerFeedbackSettingsAsJSON = codec.Codec.interface({ amount: codec.number, time: codec.maybe(codec.number), auto_approved: codec.boolean });
export type AssignmentPeerFeedbackSettingsAsJSON = codec.GetInterface<typeof AssignmentPeerFeedbackSettingsAsJSON>;
export const AssignmentKind = codec.oneOf([
    codec.exactly("normal"),
    codec.exactly("exam")
]);
export type AssignmentKind = codec.GetInterface<typeof AssignmentKind>;
export const AssignmentAsJSON = codec.Codec.interface({ id: codec.number, state: codec.string, description: codec.maybe(codec.string), created_at: codec.date, deadline: codec.maybe(codec.date), name: codec.string, is_lti: codec.boolean, course_id: codec.number, cgignore: codec.maybe(codec.oneOf([
        codec.string,
        SubmissionValidatorInputData
    ])), cgignore_version: codec.maybe(codec.string), whitespace_linter: codec.boolean, available_at: codec.maybe(codec.date), send_login_links: codec.boolean, fixed_max_rubric_points: codec.maybe(codec.number), max_grade: codec.maybe(codec.number), group_set: codec.maybe(codec.oneOf([
        GroupSetAsJSON
    ])), auto_test_id: codec.maybe(codec.number), files_upload_enabled: codec.boolean, webhook_upload_enabled: codec.boolean, max_submissions: codec.maybe(codec.number), cool_off_period: codec.number, amount_in_cool_off_period: codec.number, reminder_time: codec.maybe(codec.string), lms_name: codec.maybe(codec.string), peer_feedback_settings: codec.maybe(codec.oneOf([
        AssignmentPeerFeedbackSettingsAsJSON
    ])), done_type: codec.maybe(codec.string), done_email: codec.maybe(codec.string), division_parent_id: codec.maybe(codec.number), analytics_workspace_ids: codec.array(codec.number), kind: codec.oneOf([
        AssignmentKind
    ]) });
export type AssignmentAsJSON = codec.GetInterface<typeof AssignmentAsJSON>;
export const FixtureLike = codec.Codec.interface({ id: codec.string });
export type FixtureLike = codec.GetInterface<typeof FixtureLike>;
export const JsonCreateAutoTest = codec.Codec.interface({ setup_script: codec.optional(codec.string), run_setup_script: codec.optional(codec.string), has_new_fixtures: codec.optional(codec.boolean), grade_calculation: codec.optional(codec.string), results_always_visible: codec.optional(codec.maybe(codec.boolean)), prefer_teacher_revision: codec.optional(codec.maybe(codec.boolean)), fixtures: codec.optional(codec.array(FixtureLike)), assignment_id: codec.number });
export type JsonCreateAutoTest = codec.GetInterface<typeof JsonCreateAutoTest>;
export const CreateAutoTestData = codec.Codec.interface({ json: JsonCreateAutoTest, fixture: codec.optional(codec.array(codec.string)) });
export type CreateAutoTestData = codec.GetInterface<typeof CreateAutoTestData>;
export const FileMixinAsJSON = codec.Codec.interface({ id: codec.string, name: codec.string });
export type FileMixinAsJSON = codec.GetInterface<typeof FileMixinAsJSON>;
export const AutoTestFixtureAsJSON = intersect(FileMixinAsJSON, codec.Codec.interface({ hidden: codec.boolean }));
export type AutoTestFixtureAsJSON = codec.GetInterface<typeof AutoTestFixtureAsJSON>;
export const AutoTestStepBaseAsJSONBase = codec.Codec.interface({ name: codec.string, type: codec.string, weight: codec.number, hidden: codec.boolean, data: codec.unknown });
export type AutoTestStepBaseAsJSONBase = codec.GetInterface<typeof AutoTestStepBaseAsJSONBase>;
export const AutoTestStepBaseAsJSON = intersect(AutoTestStepBaseAsJSONBase, codec.Codec.interface({ id: codec.number }));
export type AutoTestStepBaseAsJSON = codec.GetInterface<typeof AutoTestStepBaseAsJSON>;
export const RubricItemAsJSONBase = codec.Codec.interface({ description: codec.string, header: codec.string, points: codec.number });
export type RubricItemAsJSONBase = codec.GetInterface<typeof RubricItemAsJSONBase>;
export const RubricItemAsJSON = intersect(RubricItemAsJSONBase, codec.Codec.interface({ id: codec.number }));
export type RubricItemAsJSON = codec.GetInterface<typeof RubricItemAsJSON>;
export const RubricLockReason = codec.exactly("auto_test");
export type RubricLockReason = codec.GetInterface<typeof RubricLockReason>;
export const RubricRowBaseAsJSON = codec.Codec.interface({ id: codec.number, header: codec.string, description: codec.maybe(codec.string), items: codec.array(RubricItemAsJSON), locked: codec.oneOf([
        codec.boolean,
        RubricLockReason
    ]), type: codec.string });
export type RubricRowBaseAsJSON = codec.GetInterface<typeof RubricRowBaseAsJSON>;
export const AutoTestSuiteAsJSON = codec.Codec.interface({ id: codec.number, steps: codec.array(AutoTestStepBaseAsJSON), rubric_row: codec.oneOf([
        RubricRowBaseAsJSON
    ]), network_disabled: codec.boolean, submission_info: codec.boolean, command_time_limit: codec.maybe(codec.number) });
export type AutoTestSuiteAsJSON = codec.GetInterface<typeof AutoTestSuiteAsJSON>;
export const AutoTestSetAsJSON = codec.Codec.interface({ id: codec.number, suites: codec.array(AutoTestSuiteAsJSON), stop_points: codec.number });
export type AutoTestSetAsJSON = codec.GetInterface<typeof AutoTestSetAsJSON>;
export const AutoTestRunAsJSON = codec.Codec.interface({ id: codec.number, created_at: codec.date, state: codec.exactly("running"), is_continuous: codec.boolean });
export type AutoTestRunAsJSON = codec.GetInterface<typeof AutoTestRunAsJSON>;
export const AutoTestAsJSON = codec.Codec.interface({ id: codec.number, fixtures: codec.array(AutoTestFixtureAsJSON), run_setup_script: codec.string, setup_script: codec.string, finalize_script: codec.string, grade_calculation: codec.maybe(codec.string), sets: codec.array(AutoTestSetAsJSON), assignment_id: codec.number, runs: codec.array(AutoTestRunAsJSON), results_always_visible: codec.maybe(codec.boolean), prefer_teacher_revision: codec.maybe(codec.boolean) });
export type AutoTestAsJSON = codec.GetInterface<typeof AutoTestAsJSON>;
export const LTIProviderBaseBaseAsJSON = codec.Codec.interface({ id: codec.string, lms: codec.string, created_at: codec.date, intended_use: codec.string });
export type LTIProviderBaseBaseAsJSON = codec.GetInterface<typeof LTIProviderBaseBaseAsJSON>;
export const LTI1p3ProviderBaseAsJSON = intersect(LTIProviderBaseBaseAsJSON, codec.Codec.interface({ capabilities: codec.record(codec.string, codec.oneOf([
        codec.string,
        codec.boolean
    ])), version: codec.exactly("lti1.3"), iss: codec.string }));
export type LTI1p3ProviderBaseAsJSON = codec.GetInterface<typeof LTI1p3ProviderBaseAsJSON>;
export const LTI1p3ProviderFinalizedAsJSON = intersect(LTI1p3ProviderBaseAsJSON, codec.Codec.interface({ finalized: codec.exactly(true) }));
export type LTI1p3ProviderFinalizedAsJSON = codec.GetInterface<typeof LTI1p3ProviderFinalizedAsJSON>;
export const LTI1p3ProviderNonFinalizedAsJSON = intersect(LTI1p3ProviderBaseAsJSON, codec.Codec.interface({ finalized: codec.exactly(false), auth_login_url: codec.maybe(codec.string), auth_token_url: codec.maybe(codec.string), client_id: codec.maybe(codec.string), key_set_url: codec.maybe(codec.string), auth_audience: codec.maybe(codec.string), custom_fields: codec.record(codec.string, codec.string), public_jwk: codec.record(codec.string, codec.string), public_key: codec.string, edit_secret: codec.maybe(codec.string) }));
export type LTI1p3ProviderNonFinalizedAsJSON = codec.GetInterface<typeof LTI1p3ProviderNonFinalizedAsJSON>;
export const LTI1p1ProviderBaseAsJSON = intersect(LTIProviderBaseBaseAsJSON, codec.Codec.interface({ version: codec.exactly("lti1.1") }));
export type LTI1p1ProviderBaseAsJSON = codec.GetInterface<typeof LTI1p1ProviderBaseAsJSON>;
export const LTI1p1ProviderFinalizedAsJSON = intersect(LTI1p1ProviderBaseAsJSON, codec.Codec.interface({ finalized: codec.exactly(true) }));
export type LTI1p1ProviderFinalizedAsJSON = codec.GetInterface<typeof LTI1p1ProviderFinalizedAsJSON>;
export const LTI1p1ProviderNonFinalizedAsJSON = intersect(LTI1p1ProviderBaseAsJSON, codec.Codec.interface({ finalized: codec.exactly(false), edit_secret: codec.maybe(codec.string), lms_consumer_key: codec.string, lms_consumer_secret: codec.string }));
export type LTI1p1ProviderNonFinalizedAsJSON = codec.GetInterface<typeof LTI1p1ProviderNonFinalizedAsJSON>;
export const CourseState = codec.oneOf([
    codec.exactly("visible"),
    codec.exactly("archived"),
    codec.exactly("deleted")
]);
export type CourseState = codec.GetInterface<typeof CourseState>;
export const CourseAsJSON = codec.Codec.interface({ id: codec.number, name: codec.string, created_at: codec.date, is_lti: codec.boolean, virtual: codec.boolean, lti_provider: codec.maybe(codec.oneOf([
        LTI1p3ProviderFinalizedAsJSON,
        LTI1p3ProviderNonFinalizedAsJSON,
        LTI1p1ProviderFinalizedAsJSON,
        LTI1p1ProviderNonFinalizedAsJSON
    ])), state: codec.oneOf([
        CourseState
    ]) });
export type CourseAsJSON = codec.GetInterface<typeof CourseAsJSON>;
export const CourseSnippetAsJSON = codec.Codec.interface({ id: codec.number, key: codec.string, value: codec.string });
export type CourseSnippetAsJSON = codec.GetInterface<typeof CourseSnippetAsJSON>;
export const CourseAsExtendedJSON = intersect(CourseAsJSON, codec.Codec.interface({ assignments: codec.array(AssignmentAsJSON), group_sets: codec.array(GroupSetAsJSON), snippets: codec.array(CourseSnippetAsJSON) }));
export type CourseAsExtendedJSON = codec.GetInterface<typeof CourseAsExtendedJSON>;
export const LoginUserData = codec.oneOf([
    codec.Codec.interface({ username: codec.string, password: codec.string }),
    codec.Codec.interface({ username: codec.string, own_password: codec.string })
]);
export type LoginUserData = codec.GetInterface<typeof LoginUserData>;
export const UserAsJSONWithoutGroup = codec.Codec.interface({ id: codec.number, name: codec.string, username: codec.string, is_test_student: codec.boolean });
export type UserAsJSONWithoutGroup = codec.GetInterface<typeof UserAsJSONWithoutGroup>;
export const GroupAsJSON = codec.Codec.interface({ id: codec.number, members: codec.array(UserAsJSONWithoutGroup), name: codec.string, group_set_id: codec.number, created_at: codec.date });
export type GroupAsJSON = codec.GetInterface<typeof GroupAsJSON>;
export const UserAsJSON = intersect(UserAsJSONWithoutGroup, codec.Codec.interface({ group: codec.maybe(codec.oneOf([
        GroupAsJSON
    ])) }));
export type UserAsJSON = codec.GetInterface<typeof UserAsJSON>;
export const UserAsExtendedJSON = intersect(UserAsJSON, codec.Codec.interface({ email: codec.string, hidden: codec.boolean }));
export type UserAsExtendedJSON = codec.GetInterface<typeof UserAsExtendedJSON>;
export const ResultDataPostUserLogin = codec.Codec.interface({ user: codec.oneOf([
        UserAsExtendedJSON
    ]), access_token: codec.string });
export type ResultDataPostUserLogin = codec.GetInterface<typeof ResultDataPostUserLogin>;
export const AutoTestStepResultState = codec.oneOf([
    codec.exactly("not_started"),
    codec.exactly("running"),
    codec.exactly("passed"),
    codec.exactly("failed"),
    codec.exactly("timed_out"),
    codec.exactly("skipped")
]);
export type AutoTestStepResultState = codec.GetInterface<typeof AutoTestStepResultState>;
export const AutoTestResultAsJSON = codec.Codec.interface({ id: codec.number, created_at: codec.date, started_at: codec.maybe(codec.date), work_id: codec.number, state: codec.oneOf([
        AutoTestStepResultState
    ]), points_achieved: codec.number });
export type AutoTestResultAsJSON = codec.GetInterface<typeof AutoTestResultAsJSON>;
export const AutoTestStepResultAsJSON = codec.Codec.interface({ id: codec.number, auto_test_step: codec.oneOf([
        AutoTestStepBaseAsJSON
    ]), state: codec.oneOf([
        AutoTestStepResultState
    ]), achieved_points: codec.number, log: codec.maybe(codec.unknown), started_at: codec.maybe(codec.date), attachment_id: codec.maybe(codec.string) });
export type AutoTestStepResultAsJSON = codec.GetInterface<typeof AutoTestStepResultAsJSON>;
export const FileTree_AsJSONFile = codec.Codec.interface({ id: codec.string, name: codec.string });
export type FileTree_AsJSONFile = codec.GetInterface<typeof FileTree_AsJSONFile>;
export const FileTreeAsJSON = intersect(FileTree_AsJSONFile, codec.Codec.interface({ entries: codec.optional(codec.array(codec.unknown)) }));
export type FileTreeAsJSON = codec.GetInterface<typeof FileTreeAsJSON>;
export const AutoTestResultAsExtendedJSON = intersect(AutoTestResultAsJSON, codec.Codec.interface({ setup_stdout: codec.maybe(codec.string), setup_stderr: codec.maybe(codec.string), step_results: codec.array(AutoTestStepResultAsJSON), approx_waiting_before: codec.maybe(codec.number), final_result: codec.boolean, suite_files: codec.record(codec.string, codec.array(FileTreeAsJSON)) }));
export type AutoTestResultAsExtendedJSON = codec.GetInterface<typeof AutoTestResultAsExtendedJSON>;
export const AutoTestStepBaseInputAsJSON = intersect(AutoTestStepBaseAsJSONBase, codec.Codec.interface({ id: codec.optional(codec.number) }));
export type AutoTestStepBaseInputAsJSON = codec.GetInterface<typeof AutoTestStepBaseInputAsJSON>;
export const UpdateSuiteAutoTestData = codec.Codec.interface({ id: codec.optional(codec.number), steps: codec.array(AutoTestStepBaseInputAsJSON), rubric_row_id: codec.number, network_disabled: codec.boolean, submission_info: codec.optional(codec.boolean), command_time_limit: codec.optional(codec.number) });
export type UpdateSuiteAutoTestData = codec.GetInterface<typeof UpdateSuiteAutoTestData>;
export const RubricItemInputAsJSON = intersect(RubricItemAsJSONBase, codec.Codec.interface({ id: codec.optional(codec.number) }));
export type RubricItemInputAsJSON = codec.GetInterface<typeof RubricItemInputAsJSON>;
export const RubricRowBaseInputAsJSONBase = codec.Codec.interface({ header: codec.string, description: codec.string, items: codec.array(RubricItemInputAsJSON) });
export type RubricRowBaseInputAsJSONBase = codec.GetInterface<typeof RubricRowBaseInputAsJSONBase>;
export const RubricRowBaseInputAsJSON = intersect(RubricRowBaseInputAsJSONBase, codec.Codec.interface({ id: codec.optional(codec.number), type: codec.optional(codec.string) }));
export type RubricRowBaseInputAsJSON = codec.GetInterface<typeof RubricRowBaseInputAsJSON>;
export const PutRubricAssignmentData = codec.Codec.interface({ max_points: codec.optional(codec.maybe(codec.number)), rows: codec.optional(codec.array(RubricRowBaseInputAsJSON)) });
export type PutRubricAssignmentData = codec.GetInterface<typeof PutRubricAssignmentData>;
export const CopyRubricAssignmentData = codec.Codec.interface({ old_assignment_id: codec.number });
export type CopyRubricAssignmentData = codec.GetInterface<typeof CopyRubricAssignmentData>;
export const UpdateSetAutoTestData = codec.Codec.interface({ stop_points: codec.optional(codec.number) });
export type UpdateSetAutoTestData = codec.GetInterface<typeof UpdateSetAutoTestData>;
export const AutoTestRunAsExtendedJSON = intersect(AutoTestRunAsJSON, codec.Codec.interface({ results: codec.array(AutoTestResultAsJSON), setup_stdout: codec.string, setup_stderr: codec.string }));
export type AutoTestRunAsExtendedJSON = codec.GetInterface<typeof AutoTestRunAsExtendedJSON>;
export const CopyAutoTestData = codec.Codec.interface({ assignment_id: codec.number });
export type CopyAutoTestData = codec.GetInterface<typeof CopyAutoTestData>;
export const PutEnrollLinkCourseData = codec.Codec.interface({ id: codec.optional(codec.string), role_id: codec.number, expiration_date: codec.date, allow_register: codec.optional(codec.boolean) });
export type PutEnrollLinkCourseData = codec.GetInterface<typeof PutEnrollLinkCourseData>;
export const AbstractRoleAsJSON = codec.Codec.interface({ id: codec.number, name: codec.string });
export type AbstractRoleAsJSON = codec.GetInterface<typeof AbstractRoleAsJSON>;
export const CourseRoleAsJSON = intersect(AbstractRoleAsJSON, codec.Codec.interface({ course: codec.oneOf([
        CourseAsJSON
    ]), hidden: codec.boolean }));
export type CourseRoleAsJSON = codec.GetInterface<typeof CourseRoleAsJSON>;
export const CourseRegistrationLinkAsJSON = codec.Codec.interface({ id: codec.string, expiration_date: codec.date, role: codec.oneOf([
        CourseRoleAsJSON
    ]), allow_register: codec.boolean });
export type CourseRegistrationLinkAsJSON = codec.GetInterface<typeof CourseRegistrationLinkAsJSON>;
export const AssignmentStateEnum = codec.oneOf([
    codec.exactly("hidden"),
    codec.exactly("open"),
    codec.exactly("done")
]);
export type AssignmentStateEnum = codec.GetInterface<typeof AssignmentStateEnum>;
export const AssignmentDoneType = codec.oneOf([
    codec.exactly("assigned_only"),
    codec.exactly("all_graders")
]);
export type AssignmentDoneType = codec.GetInterface<typeof AssignmentDoneType>;
export const PatchAssignmentData = codec.Codec.interface({ state: codec.optional(AssignmentStateEnum), name: codec.optional(codec.string), deadline: codec.optional(codec.date), max_grade: codec.optional(codec.maybe(codec.number)), group_set_id: codec.optional(codec.maybe(codec.number)), available_at: codec.optional(codec.maybe(codec.date)), send_login_links: codec.optional(codec.boolean), kind: codec.optional(AssignmentKind), files_upload_enabled: codec.optional(codec.boolean), webhook_upload_enabled: codec.optional(codec.boolean), max_submissions: codec.optional(codec.maybe(codec.number)), cool_off_period: codec.optional(codec.number), amount_in_cool_off_period: codec.optional(codec.number), ignore: codec.optional(codec.oneOf([
        codec.string,
        SubmissionValidatorInputData
    ])), ignore_version: codec.optional(codec.oneOf([
        codec.exactly("EmptySubmissionFilter"),
        codec.exactly("IgnoreFilterManager"),
        codec.exactly("SubmissionValidator")
    ])), done_type: codec.optional(codec.maybe(AssignmentDoneType)), reminder_time: codec.optional(codec.maybe(codec.date)), done_email: codec.optional(codec.maybe(codec.string)) });
export type PatchAssignmentData = codec.GetInterface<typeof PatchAssignmentData>;
export const JsonPatchAutoTest = codec.Codec.interface({ setup_script: codec.optional(codec.string), run_setup_script: codec.optional(codec.string), has_new_fixtures: codec.optional(codec.boolean), grade_calculation: codec.optional(codec.string), results_always_visible: codec.optional(codec.maybe(codec.boolean)), prefer_teacher_revision: codec.optional(codec.maybe(codec.boolean)), fixtures: codec.optional(codec.array(FixtureLike)) });
export type JsonPatchAutoTest = codec.GetInterface<typeof JsonPatchAutoTest>;
export const PatchAutoTestData = codec.Codec.interface({ json: JsonPatchAutoTest, fixture: codec.optional(codec.array(codec.string)) });
export type PatchAutoTestData = codec.GetInterface<typeof PatchAutoTestData>;
export const ResultDataGetAutoTestGet = codec.Codec.interface({ id: codec.number, fixtures: codec.array(AutoTestFixtureAsJSON), run_setup_script: codec.string, setup_script: codec.string, finalize_script: codec.string, grade_calculation: codec.maybe(codec.string), sets: codec.array(AutoTestSetAsJSON), assignment_id: codec.number, runs: codec.array(AutoTestRunAsExtendedJSON), results_always_visible: codec.maybe(codec.boolean), prefer_teacher_revision: codec.maybe(codec.boolean) });
export type ResultDataGetAutoTestGet = codec.GetInterface<typeof ResultDataGetAutoTestGet>;
export const PatchCourseData = codec.Codec.interface({ name: codec.optional(codec.string), state: codec.optional(CourseState) });
export type PatchCourseData = codec.GetInterface<typeof PatchCourseData>;
export const GroupAsExtendedJSON = intersect(GroupAsJSON, codec.Codec.interface({ virtual_user: codec.oneOf([
        UserAsJSONWithoutGroup
    ]) }));
export type GroupAsExtendedJSON = codec.GetInterface<typeof GroupAsExtendedJSON>;
export namespace Assignment {
    /**
     * Get All
     */
    export function getAll({}: {}, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery("/api/v1/assignments/", query), codec.array(AssignmentAsJSON), BaseError, {
            ...opts
        });
    }
    /**
     * Get Rubric
     */
    export function getRubric({ assignmentId }: {
        assignmentId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/assignments/${encodeURIComponent(coerceToString(assignmentId))}/rubrics/`, query), codec.array(RubricRowBaseAsJSON), BaseError, {
            ...opts
        });
    }
    /**
     * Delete Rubric
     */
    export function deleteRubric({ assignmentId }: {
        assignmentId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/assignments/${encodeURIComponent(coerceToString(assignmentId))}/rubrics/`, query), codec.optional(codec.nullType), BaseError, {
            ...opts,
            method: "DELETE"
        });
    }
    /**
     * Put Rubric
     */
    export function putRubric({ assignmentId, body }: {
        assignmentId: number;
        body: PutRubricAssignmentData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/assignments/${encodeURIComponent(coerceToString(assignmentId))}/rubrics/`, query), codec.array(RubricRowBaseAsJSON), BaseError, oazapfts.json({
            ...opts,
            method: "PUT",
            body
        }));
    }
    /**
     * Get Course
     */
    export function getCourse({ assignmentId }: {
        assignmentId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/assignments/${encodeURIComponent(coerceToString(assignmentId))}/course`, query), CourseAsExtendedJSON, BaseError, {
            ...opts
        });
    }
    /**
     * Copy Rubric
     */
    export function copyRubric({ assignmentId, body }: {
        assignmentId: number;
        body: CopyRubricAssignmentData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/assignments/${encodeURIComponent(coerceToString(assignmentId))}/rubric`, query), codec.array(RubricRowBaseAsJSON), BaseError, oazapfts.json({
            ...opts,
            method: "POST",
            body
        }));
    }
    /**
     * Patch
     */
    export function patch({ assignmentId, body }: {
        assignmentId: number;
        body: PatchAssignmentData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/assignments/${encodeURIComponent(coerceToString(assignmentId))}`, query), AssignmentAsJSON, BaseError, oazapfts.json({
            ...opts,
            method: "PATCH",
            body
        }));
    }
}
export namespace AutoTest {
    /**
     * Create
     */
    export function create({ body }: {
        body: CreateAutoTestData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery("/api/v1/auto_tests/", query), AutoTestAsJSON, BaseError, oazapfts.multipart({
            ...opts,
            method: "POST",
            body
        }));
    }
    /**
     * Restart Result
     */
    export function restartResult({ autoTestId, runId, resultId }: {
        autoTestId: number;
        runId: number;
        resultId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/runs/${encodeURIComponent(coerceToString(runId))}/results/${encodeURIComponent(coerceToString(resultId))}/restart`, query), AutoTestResultAsExtendedJSON, BaseError, {
            ...opts,
            method: "POST"
        });
    }
    /**
     * Get Results By User
     */
    export function getResultsByUser({ autoTestId, runId, userId }: {
        autoTestId: number;
        runId: number;
        userId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/runs/${encodeURIComponent(coerceToString(runId))}/users/${encodeURIComponent(coerceToString(userId))}/results/`, query), codec.array(AutoTestResultAsJSON), BaseError, {
            ...opts
        });
    }
    /**
     * Get Result
     */
    export function getResult({ autoTestId, runId, resultId }: {
        autoTestId: number;
        runId: number;
        resultId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/runs/${encodeURIComponent(coerceToString(runId))}/results/${encodeURIComponent(coerceToString(resultId))}`, query), AutoTestResultAsExtendedJSON, BaseError, {
            ...opts
        });
    }
    /**
     * Delete Suite
     */
    export function deleteSuite({ testId, setId, suiteId }: {
        testId: number;
        setId: number;
        suiteId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(testId))}/sets/${encodeURIComponent(coerceToString(setId))}/suites/${encodeURIComponent(coerceToString(suiteId))}`, query), codec.optional(codec.nullType), BaseError, {
            ...opts,
            method: "DELETE"
        });
    }
    /**
     * Update Suite
     */
    export function updateSuite({ autoTestId, setId, body }: {
        autoTestId: number;
        setId: number;
        body: UpdateSuiteAutoTestData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/sets/${encodeURIComponent(coerceToString(setId))}/suites/`, query), AutoTestSuiteAsJSON, BaseError, oazapfts.json({
            ...opts,
            method: "PATCH",
            body
        }));
    }
    /**
     * Update Set
     */
    export function updateSet({ autoTestId, autoTestSetId, body }: {
        autoTestId: number;
        autoTestSetId: number;
        body: UpdateSetAutoTestData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/sets/${encodeURIComponent(coerceToString(autoTestSetId))}`, query), AutoTestSetAsJSON, BaseError, oazapfts.json({
            ...opts,
            method: "PATCH",
            body
        }));
    }
    /**
     * Delete Set
     */
    export function deleteSet({ autoTestId, autoTestSetId }: {
        autoTestId: number;
        autoTestSetId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/sets/${encodeURIComponent(coerceToString(autoTestSetId))}`, query), codec.optional(codec.nullType), BaseError, {
            ...opts,
            method: "DELETE"
        });
    }
    /**
     * Stop Run
     */
    export function stopRun({ autoTestId, runId }: {
        autoTestId: number;
        runId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/runs/${encodeURIComponent(coerceToString(runId))}`, query), codec.optional(codec.nullType), BaseError, {
            ...opts,
            method: "DELETE"
        });
    }
    /**
     * Add Set
     */
    export function addSet({ autoTestId }: {
        autoTestId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/sets/`, query), AutoTestSetAsJSON, BaseError, {
            ...opts,
            method: "POST"
        });
    }
    /**
     * Start Run
     */
    export function startRun({ autoTestId }: {
        autoTestId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/runs/`, query), codec.oneOf([
            codec.record(codec.string, codec.exactly("")),
            AutoTestRunAsExtendedJSON
        ]), BaseError, {
            ...opts,
            method: "POST"
        });
    }
    /**
     * Copy
     */
    export function copy({ autoTestId, body }: {
        autoTestId: number;
        body: CopyAutoTestData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}/copy`, query), AutoTestAsJSON, BaseError, oazapfts.json({
            ...opts,
            method: "POST",
            body
        }));
    }
    /**
     * Delete
     */
    export function deleteApiV1AutoTestsByAutoTestId({ autoTestId }: {
        autoTestId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}`, query), codec.optional(codec.nullType), BaseError, {
            ...opts,
            method: "DELETE"
        });
    }
    /**
     * Patch
     */
    export function patch({ autoTestId, body }: {
        autoTestId: number;
        body: PatchAutoTestData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}`, query), AutoTestAsJSON, BaseError, oazapfts.multipart({
            ...opts,
            method: "PATCH",
            body
        }));
    }
    /**
     * Get
     */
    export function getApiV1AutoTestsByAutoTestId({ autoTestId }: {
        autoTestId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/auto_tests/${encodeURIComponent(coerceToString(autoTestId))}`, query), ResultDataGetAutoTestGet, BaseError, {
            ...opts
        });
    }
}
export namespace Course {
    /**
     * Get All
     */
    export function getAll({}: {}, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery("/api/v1/courses/", query), codec.array(CourseAsExtendedJSON), BaseError, {
            ...opts
        });
    }
    /**
     * Put Enroll Link
     */
    export function putEnrollLink({ courseId, body }: {
        courseId: number;
        body: PutEnrollLinkCourseData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/courses/${encodeURIComponent(coerceToString(courseId))}/registration_links/`, query), CourseRegistrationLinkAsJSON, BaseError, oazapfts.json({
            ...opts,
            method: "PUT",
            body
        }));
    }
    /**
     * Get Group Sets
     */
    export function getGroupSets({ courseId }: {
        courseId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/courses/${encodeURIComponent(coerceToString(courseId))}/group_sets/`, query), codec.array(GroupSetAsJSON), BaseError, {
            ...opts
        });
    }
    /**
     * Get Snippets
     */
    export function getSnippets({ courseId }: {
        courseId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/courses/${encodeURIComponent(coerceToString(courseId))}/snippets/`, query), codec.array(CourseSnippetAsJSON), BaseError, {
            ...opts
        });
    }
    /**
     * Delete Role
     */
    export function deleteRole({ courseId, roleId }: {
        courseId: number;
        roleId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/courses/${encodeURIComponent(coerceToString(courseId))}/roles/${encodeURIComponent(coerceToString(roleId))}`, query), codec.optional(codec.nullType), BaseError, {
            ...opts,
            method: "DELETE"
        });
    }
    /**
     * Get
     */
    export function getApiV1CoursesByCourseId({ courseId }: {
        courseId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/courses/${encodeURIComponent(coerceToString(courseId))}`, query), CourseAsExtendedJSON, BaseError, {
            ...opts
        });
    }
    /**
     * Patch
     */
    export function patch({ courseId, body }: {
        courseId: number;
        body: PatchCourseData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/courses/${encodeURIComponent(coerceToString(courseId))}`, query), CourseAsExtendedJSON, BaseError, oazapfts.json({
            ...opts,
            method: "PATCH",
            body
        }));
    }
}
export namespace Group {
    /**
     * Get
     */
    export function getApiV1GroupsByGroupId({ groupId }: {
        groupId: number;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery(`/api/v1/groups/${encodeURIComponent(coerceToString(groupId))}`, query), GroupAsExtendedJSON, BaseError, {
            ...opts
        });
    }
}
export namespace SiteSettings {
    /**
     * Get All
     */
    export function getAll({}: {}, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery("/api/v1/site_settings/", query), codec.oneOf([
            OptAllOptsAsJSON,
            OptFrontendOptsAsJSON
        ]), BaseError, {
            ...opts
        });
    }
}
export namespace User {
    /**
     * Login
     */
    export function login({ body }: {
        body: LoginUserData;
    }, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery("/api/v1/login", query), ResultDataPostUserLogin, BaseError, oazapfts.json({
            ...opts,
            method: "POST",
            body
        }));
    }
    /**
     * Get
     */
    export function getApiV1Login({}: {}, { query, opts }: {
        query?: Record<string, boolean | string | number>;
        opts?: Oazapfts.RequestOpts;
    } = {}) {
        return oazapfts.fetchJson(maybeAddQuery("/api/v1/login", query), codec.oneOf([
            UserAsJSON,
            codec.record(codec.string, codec.string),
            UserAsExtendedJSON
        ]), BaseError, {
            ...opts
        });
    }
}
