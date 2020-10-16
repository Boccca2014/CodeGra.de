from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, Union, cast

from ..utils import maybe_to_dict
from .assignment_kind import AssignmentKind
from .assignment_peer_feedback_settings_as_json import AssignmentPeerFeedbackSettingsAsJSON
from .group_set_as_json import GroupSetAsJSON
from .submission_validator_input_data import SubmissionValidatorInputData
from .types import File


@dataclass
class AssignmentAsJSON:
    """The serialization of an assignment.

See the comments in the source code for the meaning of each field."""

    id: "int"
    state: "str"
    description: "Optional[str]"
    created_at: "datetime.datetime"
    deadline: "Optional[datetime.datetime]"
    name: "str"
    is_lti: "bool"
    course_id: "int"
    cgignore: "Optional[Union[str, SubmissionValidatorInputData]]"
    cgignore_version: "Optional[str]"
    whitespace_linter: "bool"
    available_at: "Optional[datetime.datetime]"
    send_login_links: "bool"
    fixed_max_rubric_points: "Optional[float]"
    max_grade: "Optional[float]"
    group_set: "Optional[Union[GroupSetAsJSON]]"
    auto_test_id: "Optional[int]"
    files_upload_enabled: "bool"
    webhook_upload_enabled: "bool"
    max_submissions: "Optional[int]"
    cool_off_period: "float"
    amount_in_cool_off_period: "int"
    reminder_time: "Optional[str]"
    lms_name: "Optional[str]"
    peer_feedback_settings: "Optional[Union[AssignmentPeerFeedbackSettingsAsJSON]]"
    done_type: "Optional[str]"
    done_email: "Optional[str]"
    division_parent_id: "Optional[int]"
    analytics_workspace_ids: "List[int]"
    kind: "Union[AssignmentKind]"

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        id = self.id
        res["id"] = id
        state = self.state
        res["state"] = state
        description = self.description
        res["description"] = description
        created_at = self.created_at.isoformat()

        res["created_at"] = created_at
        deadline = self.deadline.isoformat() if self.deadline else None

        res["deadline"] = deadline
        name = self.name
        res["name"] = name
        is_lti = self.is_lti
        res["is_lti"] = is_lti
        course_id = self.course_id
        res["course_id"] = course_id
        if self.cgignore is None:
            cgignore: Optional[Union[str, SubmissionValidatorInputData]] = None
        elif isinstance(self.cgignore, str):
            cgignore = self.cgignore
        else:
            cgignore = maybe_to_dict(self.cgignore)

        res["cgignore"] = cgignore
        cgignore_version = self.cgignore_version
        res["cgignore_version"] = cgignore_version
        whitespace_linter = self.whitespace_linter
        res["whitespace_linter"] = whitespace_linter
        available_at = self.available_at.isoformat() if self.available_at else None

        res["available_at"] = available_at
        send_login_links = self.send_login_links
        res["send_login_links"] = send_login_links
        fixed_max_rubric_points = self.fixed_max_rubric_points
        res["fixed_max_rubric_points"] = fixed_max_rubric_points
        max_grade = self.max_grade
        res["max_grade"] = max_grade
        if self.group_set is None:
            group_set: Optional[Union[GroupSetAsJSON]] = None
        else:
            group_set = maybe_to_dict(self.group_set)

        res["group_set"] = group_set
        auto_test_id = self.auto_test_id
        res["auto_test_id"] = auto_test_id
        files_upload_enabled = self.files_upload_enabled
        res["files_upload_enabled"] = files_upload_enabled
        webhook_upload_enabled = self.webhook_upload_enabled
        res["webhook_upload_enabled"] = webhook_upload_enabled
        max_submissions = self.max_submissions
        res["max_submissions"] = max_submissions
        cool_off_period = self.cool_off_period
        res["cool_off_period"] = cool_off_period
        amount_in_cool_off_period = self.amount_in_cool_off_period
        res["amount_in_cool_off_period"] = amount_in_cool_off_period
        reminder_time = self.reminder_time
        res["reminder_time"] = reminder_time
        lms_name = self.lms_name
        res["lms_name"] = lms_name
        if self.peer_feedback_settings is None:
            peer_feedback_settings: Optional[Union[AssignmentPeerFeedbackSettingsAsJSON]] = None
        else:
            peer_feedback_settings = maybe_to_dict(self.peer_feedback_settings)

        res["peer_feedback_settings"] = peer_feedback_settings
        done_type = self.done_type
        res["done_type"] = done_type
        done_email = self.done_email
        res["done_email"] = done_email
        division_parent_id = self.division_parent_id
        res["division_parent_id"] = division_parent_id
        analytics_workspace_ids = self.analytics_workspace_ids

        res["analytics_workspace_ids"] = analytics_workspace_ids
        if isinstance(self.kind, AssignmentKind):
            kind = self.kind.value

        res["kind"] = kind

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> AssignmentAsJSON:
        base = {}
        id = d["id"]

        state = d["state"]

        description = d["description"]

        created_at = datetime.datetime.fromisoformat(d["created_at"])

        deadline = None
        if d["deadline"] is not None:
            deadline = datetime.datetime.fromisoformat(cast(str, d["deadline"]))

        name = d["name"]

        is_lti = d["is_lti"]

        course_id = d["course_id"]

        def _parse_cgignore(data: Optional[Dict[str, Any]]) -> Optional[Union[str, SubmissionValidatorInputData]]:
            if data is None:
                return None

            cgignore: Optional[Union[str, SubmissionValidatorInputData]] = d["cgignore"]
            if isinstance(cgignore, str):
                return cgignore
            cgignore = SubmissionValidatorInputData.from_dict(cast(Dict[str, Any], cgignore))

            return cgignore

        cgignore = _parse_cgignore(d["cgignore"])

        cgignore_version = d["cgignore_version"]

        whitespace_linter = d["whitespace_linter"]

        available_at = None
        if d["available_at"] is not None:
            available_at = datetime.datetime.fromisoformat(cast(str, d["available_at"]))

        send_login_links = d["send_login_links"]

        fixed_max_rubric_points = d["fixed_max_rubric_points"]

        max_grade = d["max_grade"]

        def _parse_group_set(data: Optional[Dict[str, Any]]) -> Optional[Union[GroupSetAsJSON]]:
            if data is None:
                return None

            group_set: Optional[Union[GroupSetAsJSON]] = d["group_set"]
            group_set = GroupSetAsJSON.from_dict(cast(Dict[str, Any], group_set))

            return group_set

        group_set = _parse_group_set(d["group_set"])

        auto_test_id = d["auto_test_id"]

        files_upload_enabled = d["files_upload_enabled"]

        webhook_upload_enabled = d["webhook_upload_enabled"]

        max_submissions = d["max_submissions"]

        cool_off_period = d["cool_off_period"]

        amount_in_cool_off_period = d["amount_in_cool_off_period"]

        reminder_time = d["reminder_time"]

        lms_name = d["lms_name"]

        def _parse_peer_feedback_settings(
            data: Optional[Dict[str, Any]]
        ) -> Optional[Union[AssignmentPeerFeedbackSettingsAsJSON]]:
            if data is None:
                return None

            peer_feedback_settings: Optional[Union[AssignmentPeerFeedbackSettingsAsJSON]] = d["peer_feedback_settings"]
            peer_feedback_settings = AssignmentPeerFeedbackSettingsAsJSON.from_dict(
                cast(Dict[str, Any], peer_feedback_settings)
            )

            return peer_feedback_settings

        peer_feedback_settings = _parse_peer_feedback_settings(d["peer_feedback_settings"])

        done_type = d["done_type"]

        done_email = d["done_email"]

        division_parent_id = d["division_parent_id"]

        analytics_workspace_ids = d["analytics_workspace_ids"]

        def _parse_kind(data: Dict[str, Any]) -> Union[AssignmentKind]:
            kind: Union[AssignmentKind] = d["kind"]
            kind = AssignmentKind(kind)

            return kind

        kind = _parse_kind(d["kind"])

        return AssignmentAsJSON(
            **base,
            id=id,
            state=state,
            description=description,
            created_at=created_at,
            deadline=deadline,
            name=name,
            is_lti=is_lti,
            course_id=course_id,
            cgignore=cgignore,
            cgignore_version=cgignore_version,
            whitespace_linter=whitespace_linter,
            available_at=available_at,
            send_login_links=send_login_links,
            fixed_max_rubric_points=fixed_max_rubric_points,
            max_grade=max_grade,
            group_set=group_set,
            auto_test_id=auto_test_id,
            files_upload_enabled=files_upload_enabled,
            webhook_upload_enabled=webhook_upload_enabled,
            max_submissions=max_submissions,
            cool_off_period=cool_off_period,
            amount_in_cool_off_period=amount_in_cool_off_period,
            reminder_time=reminder_time,
            lms_name=lms_name,
            peer_feedback_settings=peer_feedback_settings,
            done_type=done_type,
            done_email=done_email,
            division_parent_id=division_parent_id,
            analytics_workspace_ids=analytics_workspace_ids,
            kind=kind,
            raw_data=d,
        )
