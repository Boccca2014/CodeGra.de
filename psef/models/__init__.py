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
    from .file import (
        File, FileMixin, FileOwner, AutoTestFixture, NestedFileMixin,
        AutoTestOutputFile, PlagiarismBaseCodeFile
    )
    from .role import Role, CourseRole, AbstractRole
    from .user import User
    from .work import Work, WorkOrigin, GradeOrigin, GradeHistory
    from .group import Group, GroupSet
    from .proxy import Proxy, ProxyState
    from .course import (
        Course, CourseState, CourseSnippet, CourseRegistrationLink
    )
    from .linter import LinterState, LinterComment, LinterInstance
    from .rubric import RubricItem
    from .rubric import RubricRowBase as RubricRow
    from .rubric import WorkRubricItem
    from .comment import (
        CommentBase, CommentType, CommentReply, CommentReplyEdit,
        CommentReplyType
    )
    from .snippet import Snippet
    from .webhook import WebhookBase, GitCloneData
    from .analytics import BaseDataSource, AnalyticsWorkspace
    from .auto_test import (
        AutoTest, AutoTestRun, AutoTestSet, AutoTestSuite, AutoTestResult,
        AutoTestRunner
    )
    from .assignment import (
        Assignment, AssignmentKind, AssignmentLinter, AssignmentResult,
        AssignmentDoneType, AssignmentLoginLink, AssignmentStateEnum,
        AssignmentGraderDone, AssignmentAssignedGrader,
        AssignmentVisibilityState, AssignmentAmbiguousSettingTag,
        AssignmentPeerFeedbackSettings, AssignmentPeerFeedbackConnection
    )
    from .permission import Permission
    from .plagiarism import (
        PlagiarismRun, PlagiarismCase, PlagiarismMatch, PlagiarismState
    )
    from .link_tables import user_course
    from .task_result import TaskResult, TaskReturnType, TaskResultState
    from .blob_storage import BlobStorage
    from .lti_provider import (
        LTI1p1Provider, LTI1p3Provider, LTIProviderBase, UserLTIProvider,
        CourseLTIProvider
    )
    from .notification import Notification, NotificationReasons
    from .user_setting import (
        SettingBase, UIPreference, UIPreferenceName, NotificationsSetting,
        EmailNotificationTypes, NotificationSettingJSON
    )
    from .saml_provider import Saml2Provider, UserSamlProvider
    from .site_settings import SiteSetting
    from .auto_test_step import (
        AutoTestStepBase, AutoTestStepResult, AutoTestStepResultState
    )
    from .broker_settings import BrokerSetting
