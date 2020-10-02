""" Contains all the data models used in inputs/outputs """

from ._fixture_like import _FixtureLike
from .api_codes import APICodes
from .assignment_as_json import AssignmentAsJSON
from .assignment_done_type import AssignmentDoneType
from .assignment_kind import AssignmentKind
from .assignment_peer_feedback_settings_as_json import AssignmentPeerFeedbackSettingsAsJSON
from .assignment_state_enum import AssignmentStateEnum
from .auto_test_as_json import AutoTestAsJSON
from .auto_test_fixture_as_json import AutoTestFixtureAsJSON
from .auto_test_result_as_extended_json import AutoTestResultAsExtendedJSON
from .auto_test_result_as_json import AutoTestResultAsJSON
from .auto_test_run_as_extended_json import AutoTestRunAsExtendedJSON
from .auto_test_run_as_json import AutoTestRunAsJSON
from .auto_test_set_as_json import AutoTestSetAsJSON
from .auto_test_step_base_as_json import AutoTestStepBaseAsJSON
from .auto_test_step_base_as_json_base import AutoTestStepBaseAsJSONBase
from .auto_test_step_base_input_as_json import AutoTestStepBaseInputAsJSON
from .auto_test_step_result_as_json import AutoTestStepResultAsJSON
from .auto_test_step_result_state import AutoTestStepResultState
from .auto_test_suite_as_json import AutoTestSuiteAsJSON
from .base_error import BaseError
from .copy_auto_test_data import CopyAutoTestData
from .copy_rubric_assignment_data import CopyRubricAssignmentData
from .course_as_extended_json import CourseAsExtendedJSON
from .course_as_json import CourseAsJSON
from .course_snippet_as_json import CourseSnippetAsJSON
from .course_state import CourseState
from .create_auto_test_data import CreateAutoTestData
from .file_mixin_as_json import FileMixinAsJSON
from .file_rule_input_data import FileRuleInputData
from .file_tree_as_json import FileTreeAsJSON
from .file_tree_as_json_file import FileTree_AsJSONFile
from .file_type import FileType
from .group_as_extended_json import GroupAsExtendedJSON
from .group_as_json import GroupAsJSON
from .group_set_as_json import GroupSetAsJSON
from .ignore_version import IgnoreVersion
from .json_create_auto_test import JsonCreateAutoTest
from .json_patch_auto_test import JsonPatchAutoTest
from .key import Key
from .login_user_data import LoginUserData
from .lti1p1_provider_base_as_json import LTI1p1ProviderBaseAsJSON
from .lti1p1_provider_finalized_as_json import LTI1p1ProviderFinalizedAsJSON
from .lti1p1_provider_non_finalized_as_json import LTI1p1ProviderNonFinalizedAsJSON
from .lti1p3_provider_base_as_json import LTI1p3ProviderBaseAsJSON
from .lti1p3_provider_finalized_as_json import LTI1p3ProviderFinalizedAsJSON
from .lti1p3_provider_non_finalized_as_json import LTI1p3ProviderNonFinalizedAsJSON
from .lti_provider_base_base_as_json import LTIProviderBaseBaseAsJSON
from .options_input_data import OptionsInputData
from .patch_assignment_data import PatchAssignmentData
from .patch_auto_test_data import PatchAutoTestData
from .patch_course_data import PatchCourseData
from .policy import Policy
from .put_rubric_assignment_data import PutRubricAssignmentData
from .result_data_get_auto_test_get import ResultDataGetAutoTestGet
from .result_data_post_user_login import ResultDataPostUserLogin
from .rubric_item_as_json import RubricItemAsJSON
from .rubric_item_as_json_base import RubricItemAsJSONBase
from .rubric_item_input_as_json import RubricItemInputAsJSON
from .rubric_lock_reason import RubricLockReason
from .rubric_row_base_as_json import RubricRowBaseAsJSON
from .rubric_row_base_input_as_json import RubricRowBaseInputAsJSON
from .rubric_row_base_input_as_json_base import RubricRowBaseInputAsJSONBase
from .rule_type import RuleType
from .submission_validator_input_data import SubmissionValidatorInputData
from .types import *
from .update_set_auto_test_data import UpdateSetAutoTestData
from .update_suite_auto_test_data import UpdateSuiteAutoTestData
from .user_as_extended_json import UserAsExtendedJSON
from .user_as_json import UserAsJSON
from .user_as_json_without_group import UserAsJSONWithoutGroup
