from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import StringIO
from typing import Any, Dict, Optional

from ..utils import maybe_to_dict
from .opt_frontend_opts_as_json import OptFrontendOptsAsJSON
from .types import File


@dataclass
class OptAllOptsAsJSON(OptFrontendOptsAsJSON):
    """The JSON representation of all options."""

    auto_test_heartbeat_interval: "Optional[float]" = None
    auto_test_heartbeat_max_missed: "Optional[int]" = None
    auto_test_max_jobs_per_runner: "Optional[int]" = None
    auto_test_max_concurrent_batch_runs: "Optional[int]" = None
    min_password_score: "Optional[int]" = None
    reset_token_time: "Optional[float]" = None
    setting_token_time: "Optional[float]" = None
    max_number_of_files: "Optional[int]" = None
    max_large_upload_size: "Optional[int]" = None
    max_normal_upload_size: "Optional[int]" = None
    max_file_size: "Optional[int]" = None
    jwt_access_token_expires: "Optional[float]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        auto_test_heartbeat_interval = self.auto_test_heartbeat_interval
        if self.auto_test_heartbeat_interval is not None:
            res["AUTO_TEST_HEARTBEAT_INTERVAL"] = auto_test_heartbeat_interval
        auto_test_heartbeat_max_missed = self.auto_test_heartbeat_max_missed
        if self.auto_test_heartbeat_max_missed is not None:
            res["AUTO_TEST_HEARTBEAT_MAX_MISSED"] = auto_test_heartbeat_max_missed
        auto_test_max_jobs_per_runner = self.auto_test_max_jobs_per_runner
        if self.auto_test_max_jobs_per_runner is not None:
            res["AUTO_TEST_MAX_JOBS_PER_RUNNER"] = auto_test_max_jobs_per_runner
        auto_test_max_concurrent_batch_runs = self.auto_test_max_concurrent_batch_runs
        if self.auto_test_max_concurrent_batch_runs is not None:
            res["AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS"] = auto_test_max_concurrent_batch_runs
        min_password_score = self.min_password_score
        if self.min_password_score is not None:
            res["MIN_PASSWORD_SCORE"] = min_password_score
        reset_token_time = self.reset_token_time
        if self.reset_token_time is not None:
            res["RESET_TOKEN_TIME"] = reset_token_time
        setting_token_time = self.setting_token_time
        if self.setting_token_time is not None:
            res["SETTING_TOKEN_TIME"] = setting_token_time
        max_number_of_files = self.max_number_of_files
        if self.max_number_of_files is not None:
            res["MAX_NUMBER_OF_FILES"] = max_number_of_files
        max_large_upload_size = self.max_large_upload_size
        if self.max_large_upload_size is not None:
            res["MAX_LARGE_UPLOAD_SIZE"] = max_large_upload_size
        max_normal_upload_size = self.max_normal_upload_size
        if self.max_normal_upload_size is not None:
            res["MAX_NORMAL_UPLOAD_SIZE"] = max_normal_upload_size
        max_file_size = self.max_file_size
        if self.max_file_size is not None:
            res["MAX_FILE_SIZE"] = max_file_size
        jwt_access_token_expires = self.jwt_access_token_expires
        if self.jwt_access_token_expires is not None:
            res["JWT_ACCESS_TOKEN_EXPIRES"] = jwt_access_token_expires

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> OptAllOptsAsJSON:
        base = asdict(OptFrontendOptsAsJSON.from_dict(d))
        base.pop("raw_data")
        auto_test_heartbeat_interval = d.get("AUTO_TEST_HEARTBEAT_INTERVAL")

        auto_test_heartbeat_max_missed = d.get("AUTO_TEST_HEARTBEAT_MAX_MISSED")

        auto_test_max_jobs_per_runner = d.get("AUTO_TEST_MAX_JOBS_PER_RUNNER")

        auto_test_max_concurrent_batch_runs = d.get("AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS")

        min_password_score = d.get("MIN_PASSWORD_SCORE")

        reset_token_time = d.get("RESET_TOKEN_TIME")

        setting_token_time = d.get("SETTING_TOKEN_TIME")

        max_number_of_files = d.get("MAX_NUMBER_OF_FILES")

        max_large_upload_size = d.get("MAX_LARGE_UPLOAD_SIZE")

        max_normal_upload_size = d.get("MAX_NORMAL_UPLOAD_SIZE")

        max_file_size = d.get("MAX_FILE_SIZE")

        jwt_access_token_expires = d.get("JWT_ACCESS_TOKEN_EXPIRES")

        return OptAllOptsAsJSON(
            **base,
            auto_test_heartbeat_interval=auto_test_heartbeat_interval,
            auto_test_heartbeat_max_missed=auto_test_heartbeat_max_missed,
            auto_test_max_jobs_per_runner=auto_test_max_jobs_per_runner,
            auto_test_max_concurrent_batch_runs=auto_test_max_concurrent_batch_runs,
            min_password_score=min_password_score,
            reset_token_time=reset_token_time,
            setting_token_time=setting_token_time,
            max_number_of_files=max_number_of_files,
            max_large_upload_size=max_large_upload_size,
            max_normal_upload_size=max_normal_upload_size,
            max_file_size=max_file_size,
            jwt_access_token_expires=jwt_access_token_expires,
            raw_data=d,
        )
