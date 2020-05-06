"""This module is a central place to define registers to prevent circular
imports.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from .helpers import register

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    # pylint: disable=unused-import
    from .models import AutoTestStepBase, RubricItem, WebhookBase
    from .models.rubric import RubricRowBase
    from .models.auto_test import GradeCalculator
    from .models.lti_provider import LTIProviderBase
    from .lti.v1_3.lms_capabilities import LMSCapabilities
    from .models.analytics import BaseDataSource

Register = register.Register
TableRegister = register.TableRegister

auto_test_handlers = Register[str, t.Type['AutoTestStepBase']]()

auto_test_grade_calculators = Register[str, 'GradeCalculator']()

webhook_handlers = TableRegister[str, t.Type['WebhookBase']]()

rubric_row_types = Register[str, t.Type['RubricRowBase']]()

lti_provider_handlers = TableRegister[str, t.Type['LTIProviderBase']]()

lti_1_3_lms_capabilities = Register[str, 'LMSCapabilities']()

analytics_data_sources = Register[str, t.Type['BaseDataSource']]()
