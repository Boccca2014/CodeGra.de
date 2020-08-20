"""
This module defines all the objects in the database in their relation.

``psef.models.assignment``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.assignment
    :members:
    :show-inheritance:

``psef.models.comment``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.comment
    :members:
    :show-inheritance:

``psef.models.course``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.course
    :members:
    :show-inheritance:

``psef.models.file``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.file
    :members:
    :show-inheritance:

``psef.models.group``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.group
    :members:
    :show-inheritance:

``psef.models.link_tables``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.link_tables
    :members:
    :show-inheritance:

``psef.models.linter``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.linter
    :members:
    :show-inheritance:

``psef.models.lti_provider``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.lti_provider
    :members:
    :show-inheritance:

``psef.models.permission``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.permission
    :members:
    :show-inheritance:

``psef.models.plagiarism``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.plagiarism
    :members:
    :show-inheritance:

``psef.models.role``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.role
    :members:
    :show-inheritance:

``psef.models.rubric``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.rubric
    :members:
    :show-inheritance:

``psef.models.snippet``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.snippet
    :members:
    :show-inheritance:

``psef.models.user``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.user
    :members:
    :show-inheritance:

``psef.models.work``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.work
    :members:
    :show-inheritance:

``psef.models.auto_test``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.auto_test
    :members:
    :show-inheritance:

``psef.models.auto_test_step``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.auto_test_step
    :members:
    :show-inheritance:

``psef.models.user_setting``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.user_setting
    :members:
    :show-inheritance:

``psef.models.notification``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.notification
    :members:
    :show-inheritance:

``psef.models.task_result``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: psef.models.task_result
    :members:
    :show-inheritance:

SPDX-License-Identifier: AGPL-3.0-only
"""

import typing as t

import cg_sqlalchemy_helpers
import cg_sqlalchemy_helpers.validation
from cg_sqlalchemy_helpers import UUID_LENGTH
from cg_cache.intra_request import cache_within_request
from cg_sqlalchemy_helpers.types import (  # pylint: disable=unused-import
    MyDb, MyQuery, DbColumn, _MyQuery
)

from .. import PsefFlask, signals

db: MyDb = cg_sqlalchemy_helpers.make_db()  # pylint: disable=invalid-name

validator: cg_sqlalchemy_helpers.validation.Validator
validator = cg_sqlalchemy_helpers.validation.Validator(db.session)

signals.FINALIZE_APP.connect_immediate(lambda _: validator.finalize())


def init_app(app: PsefFlask) -> None:
    """Initialize the database connections and set some listeners.

    :param app: The flask app to initialize for.
    :returns: Nothing
    """
    cg_sqlalchemy_helpers.init_app(db, app)


if t.TYPE_CHECKING:  # pragma: no cover
    from cg_sqlalchemy_helpers.types import Base
else:
    Base = db.Model  # pylint: disable=invalid-name

if True:  # pylint: disable=using-constant-test
    from .course import Course, CourseSnippet, CourseRegistrationLink
    from .assignment import (
        Assignment, AssignmentLinter, AssignmentResult, AssignmentDoneType,
        AssignmentGraderDone, AssignmentAssignedGrader, AssignmentStateEnum,
        AssignmentAmbiguousSettingTag, AssignmentVisibilityState,
        AssignmentPeerFeedbackSettings, AssignmentPeerFeedbackConnection,
        AssignmentLoginLink, AssignmentKind
    )
    from .permission import Permission
    from .user import User
    from .lti_provider import (
        LTIProviderBase, LTI1p1Provider, UserLTIProvider, LTI1p3Provider,
        CourseLTIProvider
    )
    from .file import (
        File, FileOwner, AutoTestFixture, FileMixin, NestedFileMixin,
        AutoTestOutputFile
    )
    from .work import Work, GradeHistory, GradeOrigin, WorkOrigin
    from .linter import LinterState, LinterComment, LinterInstance
    from .plagiarism import (
        PlagiarismState, PlagiarismRun, PlagiarismCase, PlagiarismMatch
    )
    from .comment import (
        CommentBase, CommentReply, CommentReplyEdit, CommentReplyType,
        CommentType
    )
    from .role import AbstractRole, Role, CourseRole
    from .snippet import Snippet
    from .rubric import RubricItem, RubricRowBase as RubricRow, WorkRubricItem
    from .group import GroupSet, Group
    from .link_tables import user_course
    from .auto_test import (
        AutoTest, AutoTestSet, AutoTestSuite, AutoTestResult, AutoTestRun,
        AutoTestRunner
    )
    from .auto_test_step import (
        AutoTestStepResultState, AutoTestStepResult, AutoTestStepBase
    )
    from .webhook import WebhookBase, GitCloneData
    from .blob_storage import BlobStorage
    from .proxy import Proxy, ProxyState
    from .analytics import AnalyticsWorkspace, BaseDataSource
    from .notification import Notification, NotificationReasons
    from .user_setting import (
        NotificationsSetting, SettingBase, EmailNotificationTypes,
        NotificationSettingJSON
    )
    from .task_result import TaskResult, TaskResultState
    from .saml_provider import Saml2Provider, UserSamlProvider
