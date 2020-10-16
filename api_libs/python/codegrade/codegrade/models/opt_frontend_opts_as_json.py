from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class OptFrontendOptsAsJSON:
    """The JSON representation of options visible to all users."""

    auto_test_max_time_command: "float"
    exam_login_max_length: "float"
    login_token_before_time: "List[float]"
    site_email: "str"
    max_lines: "int"
    notification_poll_time: "float"
    release_message_max_time: "float"
    blackboard_zip_upload_enabled: "bool"
    rubrics_enabled: "bool"
    automatic_lti_role_enabled: "bool"
    lti_enabled: "bool"
    linters_enabled: "bool"
    incremental_rubric_submission_enabled: "bool"
    register_enabled: "bool"
    groups_enabled: "bool"
    auto_test_enabled: "bool"
    course_register_enabled: "bool"
    render_html_enabled: "bool"
    email_students_enabled: "bool"
    peer_feedback_enabled: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        auto_test_max_time_command = self.auto_test_max_time_command
        res["AUTO_TEST_MAX_TIME_COMMAND"] = auto_test_max_time_command
        exam_login_max_length = self.exam_login_max_length
        res["EXAM_LOGIN_MAX_LENGTH"] = exam_login_max_length
        login_token_before_time = self.login_token_before_time

        res["LOGIN_TOKEN_BEFORE_TIME"] = login_token_before_time
        site_email = self.site_email
        res["SITE_EMAIL"] = site_email
        max_lines = self.max_lines
        res["MAX_LINES"] = max_lines
        notification_poll_time = self.notification_poll_time
        res["NOTIFICATION_POLL_TIME"] = notification_poll_time
        release_message_max_time = self.release_message_max_time
        res["RELEASE_MESSAGE_MAX_TIME"] = release_message_max_time
        blackboard_zip_upload_enabled = self.blackboard_zip_upload_enabled
        res["BLACKBOARD_ZIP_UPLOAD_ENABLED"] = blackboard_zip_upload_enabled
        rubrics_enabled = self.rubrics_enabled
        res["RUBRICS_ENABLED"] = rubrics_enabled
        automatic_lti_role_enabled = self.automatic_lti_role_enabled
        res["AUTOMATIC_LTI_ROLE_ENABLED"] = automatic_lti_role_enabled
        lti_enabled = self.lti_enabled
        res["LTI_ENABLED"] = lti_enabled
        linters_enabled = self.linters_enabled
        res["LINTERS_ENABLED"] = linters_enabled
        incremental_rubric_submission_enabled = self.incremental_rubric_submission_enabled
        res["INCREMENTAL_RUBRIC_SUBMISSION_ENABLED"] = incremental_rubric_submission_enabled
        register_enabled = self.register_enabled
        res["REGISTER_ENABLED"] = register_enabled
        groups_enabled = self.groups_enabled
        res["GROUPS_ENABLED"] = groups_enabled
        auto_test_enabled = self.auto_test_enabled
        res["AUTO_TEST_ENABLED"] = auto_test_enabled
        course_register_enabled = self.course_register_enabled
        res["COURSE_REGISTER_ENABLED"] = course_register_enabled
        render_html_enabled = self.render_html_enabled
        res["RENDER_HTML_ENABLED"] = render_html_enabled
        email_students_enabled = self.email_students_enabled
        res["EMAIL_STUDENTS_ENABLED"] = email_students_enabled
        peer_feedback_enabled = self.peer_feedback_enabled
        res["PEER_FEEDBACK_ENABLED"] = peer_feedback_enabled

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> OptFrontendOptsAsJSON:
        base = {}
        auto_test_max_time_command = d["AUTO_TEST_MAX_TIME_COMMAND"]

        exam_login_max_length = d["EXAM_LOGIN_MAX_LENGTH"]

        login_token_before_time = d["LOGIN_TOKEN_BEFORE_TIME"]

        site_email = d["SITE_EMAIL"]

        max_lines = d["MAX_LINES"]

        notification_poll_time = d["NOTIFICATION_POLL_TIME"]

        release_message_max_time = d["RELEASE_MESSAGE_MAX_TIME"]

        blackboard_zip_upload_enabled = d["BLACKBOARD_ZIP_UPLOAD_ENABLED"]

        rubrics_enabled = d["RUBRICS_ENABLED"]

        automatic_lti_role_enabled = d["AUTOMATIC_LTI_ROLE_ENABLED"]

        lti_enabled = d["LTI_ENABLED"]

        linters_enabled = d["LINTERS_ENABLED"]

        incremental_rubric_submission_enabled = d["INCREMENTAL_RUBRIC_SUBMISSION_ENABLED"]

        register_enabled = d["REGISTER_ENABLED"]

        groups_enabled = d["GROUPS_ENABLED"]

        auto_test_enabled = d["AUTO_TEST_ENABLED"]

        course_register_enabled = d["COURSE_REGISTER_ENABLED"]

        render_html_enabled = d["RENDER_HTML_ENABLED"]

        email_students_enabled = d["EMAIL_STUDENTS_ENABLED"]

        peer_feedback_enabled = d["PEER_FEEDBACK_ENABLED"]

        return OptFrontendOptsAsJSON(
            **base,
            auto_test_max_time_command=auto_test_max_time_command,
            exam_login_max_length=exam_login_max_length,
            login_token_before_time=login_token_before_time,
            site_email=site_email,
            max_lines=max_lines,
            notification_poll_time=notification_poll_time,
            release_message_max_time=release_message_max_time,
            blackboard_zip_upload_enabled=blackboard_zip_upload_enabled,
            rubrics_enabled=rubrics_enabled,
            automatic_lti_role_enabled=automatic_lti_role_enabled,
            lti_enabled=lti_enabled,
            linters_enabled=linters_enabled,
            incremental_rubric_submission_enabled=incremental_rubric_submission_enabled,
            register_enabled=register_enabled,
            groups_enabled=groups_enabled,
            auto_test_enabled=auto_test_enabled,
            course_register_enabled=course_register_enabled,
            render_html_enabled=render_html_enabled,
            email_students_enabled=email_students_enabled,
            peer_feedback_enabled=peer_feedback_enabled,
            raw_data=d,
        )
