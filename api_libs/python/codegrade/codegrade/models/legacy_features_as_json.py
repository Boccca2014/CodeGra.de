from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .types import File


@dataclass
class LegacyFeaturesAsJSON:
    """The legacy features of CodeGrade.

Please don't use this object, but instead check for enabled settings."""

    automatic_lti_role: "bool"
    auto_test: "bool"
    blackboard_zip_upload: "bool"
    course_register: "bool"
    email_students: "bool"
    groups: "bool"
    incremental_rubric_submission: "bool"
    linters: "bool"
    lti: "bool"
    peer_feedback: "bool"
    register: "bool"
    render_html: "bool"
    rubrics: "bool"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        automatic_lti_role = self.automatic_lti_role
        res["AUTOMATIC_LTI_ROLE"] = automatic_lti_role
        auto_test = self.auto_test
        res["AUTO_TEST"] = auto_test
        blackboard_zip_upload = self.blackboard_zip_upload
        res["BLACKBOARD_ZIP_UPLOAD"] = blackboard_zip_upload
        course_register = self.course_register
        res["COURSE_REGISTER"] = course_register
        email_students = self.email_students
        res["EMAIL_STUDENTS"] = email_students
        groups = self.groups
        res["GROUPS"] = groups
        incremental_rubric_submission = self.incremental_rubric_submission
        res["INCREMENTAL_RUBRIC_SUBMISSION"] = incremental_rubric_submission
        linters = self.linters
        res["LINTERS"] = linters
        lti = self.lti
        res["LTI"] = lti
        peer_feedback = self.peer_feedback
        res["PEER_FEEDBACK"] = peer_feedback
        register = self.register
        res["REGISTER"] = register
        render_html = self.render_html
        res["RENDER_HTML"] = render_html
        rubrics = self.rubrics
        res["RUBRICS"] = rubrics

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> LegacyFeaturesAsJSON:
        base = {}
        automatic_lti_role = d["AUTOMATIC_LTI_ROLE"]

        auto_test = d["AUTO_TEST"]

        blackboard_zip_upload = d["BLACKBOARD_ZIP_UPLOAD"]

        course_register = d["COURSE_REGISTER"]

        email_students = d["EMAIL_STUDENTS"]

        groups = d["GROUPS"]

        incremental_rubric_submission = d["INCREMENTAL_RUBRIC_SUBMISSION"]

        linters = d["LINTERS"]

        lti = d["LTI"]

        peer_feedback = d["PEER_FEEDBACK"]

        register = d["REGISTER"]

        render_html = d["RENDER_HTML"]

        rubrics = d["RUBRICS"]

        return LegacyFeaturesAsJSON(
            **base,
            automatic_lti_role=automatic_lti_role,
            auto_test=auto_test,
            blackboard_zip_upload=blackboard_zip_upload,
            course_register=course_register,
            email_students=email_students,
            groups=groups,
            incremental_rubric_submission=incremental_rubric_submission,
            linters=linters,
            lti=lti,
            peer_feedback=peer_feedback,
            register=register,
            render_html=render_html,
            rubrics=rubrics,
            raw_data=d,
        )
