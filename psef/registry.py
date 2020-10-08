"""This module is a central place to define registers to prevent circular
imports.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

from .helpers import register

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    # pylint: disable=unused-import
    from .models import RubricItem, WebhookBase, AutoTestStepBase
    from .lti.v1_1 import LTI
    from .models.rubric import RubricRowBase
    from .models.analytics import BaseDataSource
    from .models.auto_test import GradeCalculator
    from .models.lti_provider import LTIProviderBase
    from .lti.v1_3.lms_capabilities import LMSCapabilities

Register = register.Register
TableRegister = register.TableRegister

auto_test_handlers = Register[str, t.
                              Type['AutoTestStepBase']]('AutoTestHandlers')

auto_test_grade_calculators = Register[str, 'GradeCalculator'](
    'AutoTestGradeCalculators'
)

webhook_handlers = TableRegister[t.Type['WebhookBase']]('WebhookHandlers')

rubric_row_types = Register[str, t.Type['RubricRowBase']]('RubricRowTypes')

lti_provider_handlers = TableRegister[t.Type['LTIProviderBase']
                                      ]('LTIProviderHandlers')

lti_1_3_lms_capabilities = Register[str, 'LMSCapabilities'](
    'LTI1p3LMSCapabilities'
)

analytics_data_sources = Register[str, t.Type['BaseDataSource']](
    'AnalyticsDataSources'
)

lti_1_1_providers: register.Register[str, t.Type['LTI']] = register.Register(
    'LTI1p1Providers'
)
