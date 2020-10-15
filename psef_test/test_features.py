# SPDX-License-Identifier: AGPL-3.0-only
import pytest

import psef.models as m
import psef.site_settings as ss


def test_disable_features(
    test_client, logged_in, ta_user, monkeypatch, app, error_template
):
    ss.Opt.BLACKBOARD_ZIP_UPLOAD_ENABLED.set_and_commit_value(False)

    with logged_in(ta_user):
        res = test_client.req(
            'post',
            '/api/v1/assignments/5/submissions/',
            400,
            result={
                **error_template,
                'disabled_setting': {
                    'name': 'BLACKBOARD_ZIP_UPLOAD_ENABLED',
                    'value': False,
                    'default': True,
                },
            }
        )
        assert 'option is not enabled' in res['message']
