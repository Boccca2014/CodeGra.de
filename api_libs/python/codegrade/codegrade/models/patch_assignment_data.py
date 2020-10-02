from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional, Union, cast

from ..utils import maybe_to_dict
from .assignment_done_type import AssignmentDoneType
from .assignment_kind import AssignmentKind
from .assignment_state_enum import AssignmentStateEnum
from .ignore_version import IgnoreVersion
from .submission_validator_input_data import SubmissionValidatorInputData
from .types import File


@dataclass
class PatchAssignmentData:
    """  """

    state: "Optional[AssignmentStateEnum]" = None
    name: "Optional[str]" = None
    deadline: "Optional[datetime.datetime]" = None
    max_grade: "Optional[int]" = None
    group_set_id: "Optional[int]" = None
    available_at: "Optional[datetime.datetime]" = None
    send_login_links: "Optional[bool]" = None
    kind: "Optional[AssignmentKind]" = None
    files_upload_enabled: "Optional[bool]" = None
    webhook_upload_enabled: "Optional[bool]" = None
    max_submissions: "Optional[int]" = None
    cool_off_period: "Optional[float]" = None
    amount_in_cool_off_period: "Optional[int]" = None
    ignore: "Optional[Union[Optional[str], Optional[SubmissionValidatorInputData]]]" = None
    ignore_version: "Optional[IgnoreVersion]" = None
    done_type: "Optional[AssignmentDoneType]" = None
    reminder_time: "Optional[datetime.datetime]" = None
    done_email: "Optional[str]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {}

        state = self.state.value if self.state else None

        if self.state is not None:
            res["state"] = state
        name = self.name
        if self.name is not None:
            res["name"] = name
        deadline = self.deadline.isoformat() if self.deadline else None

        if self.deadline is not None:
            res["deadline"] = deadline
        max_grade = self.max_grade
        if self.max_grade is not None:
            res["max_grade"] = max_grade
        group_set_id = self.group_set_id
        if self.group_set_id is not None:
            res["group_set_id"] = group_set_id
        available_at = self.available_at.isoformat() if self.available_at else None

        if self.available_at is not None:
            res["available_at"] = available_at
        send_login_links = self.send_login_links
        if self.send_login_links is not None:
            res["send_login_links"] = send_login_links
        kind = self.kind.value if self.kind else None

        if self.kind is not None:
            res["kind"] = kind
        files_upload_enabled = self.files_upload_enabled
        if self.files_upload_enabled is not None:
            res["files_upload_enabled"] = files_upload_enabled
        webhook_upload_enabled = self.webhook_upload_enabled
        if self.webhook_upload_enabled is not None:
            res["webhook_upload_enabled"] = webhook_upload_enabled
        max_submissions = self.max_submissions
        if self.max_submissions is not None:
            res["max_submissions"] = max_submissions
        cool_off_period = self.cool_off_period
        if self.cool_off_period is not None:
            res["cool_off_period"] = cool_off_period
        amount_in_cool_off_period = self.amount_in_cool_off_period
        if self.amount_in_cool_off_period is not None:
            res["amount_in_cool_off_period"] = amount_in_cool_off_period
        if self.ignore is None:
            ignore: Optional[Union[Optional[str], Optional[SubmissionValidatorInputData]]] = None
        elif isinstance(self.ignore, str):
            ignore = self.ignore
        else:
            ignore = maybe_to_dict(self.ignore) if self.ignore else None

        if self.ignore is not None:
            res["ignore"] = ignore
        ignore_version = self.ignore_version.value if self.ignore_version else None

        if self.ignore_version is not None:
            res["ignore_version"] = ignore_version
        done_type = self.done_type.value if self.done_type else None

        if self.done_type is not None:
            res["done_type"] = done_type
        reminder_time = self.reminder_time.isoformat() if self.reminder_time else None

        if self.reminder_time is not None:
            res["reminder_time"] = reminder_time
        done_email = self.done_email
        if self.done_email is not None:
            res["done_email"] = done_email

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> PatchAssignmentData:
        base = {}
        state = None
        if d.get("state") is not None:
            state = AssignmentStateEnum(d.get("state"))

        name = d.get("name")

        deadline = None
        if d.get("deadline") is not None:
            deadline = datetime.datetime.fromisoformat(cast(str, d.get("deadline")))

        max_grade = d.get("max_grade")

        group_set_id = d.get("group_set_id")

        available_at = None
        if d.get("available_at") is not None:
            available_at = datetime.datetime.fromisoformat(cast(str, d.get("available_at")))

        send_login_links = d.get("send_login_links")

        kind = None
        if d.get("kind") is not None:
            kind = AssignmentKind(d.get("kind"))

        files_upload_enabled = d.get("files_upload_enabled")

        webhook_upload_enabled = d.get("webhook_upload_enabled")

        max_submissions = d.get("max_submissions")

        cool_off_period = d.get("cool_off_period")

        amount_in_cool_off_period = d.get("amount_in_cool_off_period")

        def _parse_ignore(
            data: Dict[str, Any]
        ) -> Optional[Union[Optional[str], Optional[SubmissionValidatorInputData]]]:
            ignore: Optional[Union[Optional[str], Optional[SubmissionValidatorInputData]]] = d.get("ignore")
            if isinstance(ignore, Optional[str]):
                return ignore
            ignore = None
            if ignore is not None:
                ignore = SubmissionValidatorInputData.from_dict(cast(Dict[str, Any], ignore))

            return ignore

        ignore = _parse_ignore(d.get("ignore"))

        ignore_version = None
        if d.get("ignore_version") is not None:
            ignore_version = IgnoreVersion(d.get("ignore_version"))

        done_type = None
        if d.get("done_type") is not None:
            done_type = AssignmentDoneType(d.get("done_type"))

        reminder_time = None
        if d.get("reminder_time") is not None:
            reminder_time = datetime.datetime.fromisoformat(cast(str, d.get("reminder_time")))

        done_email = d.get("done_email")

        return PatchAssignmentData(
            **base,
            state=state,
            name=name,
            deadline=deadline,
            max_grade=max_grade,
            group_set_id=group_set_id,
            available_at=available_at,
            send_login_links=send_login_links,
            kind=kind,
            files_upload_enabled=files_upload_enabled,
            webhook_upload_enabled=webhook_upload_enabled,
            max_submissions=max_submissions,
            cool_off_period=cool_off_period,
            amount_in_cool_off_period=amount_in_cool_off_period,
            ignore=ignore,
            ignore_version=ignore_version,
            done_type=done_type,
            reminder_time=reminder_time,
            done_email=done_email,
            raw_data=d,
        )
