from enum import Enum


class IgnoreVersion(str, Enum):
    EMPTYSUBMISSIONFILTER = "EmptySubmissionFilter"
    IGNOREFILTERMANAGER = "IgnoreFilterManager"
    SUBMISSIONVALIDATOR = "SubmissionValidator"
