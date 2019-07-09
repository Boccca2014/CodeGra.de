# SPDX-License-Identifier: AGPL-3.0-only
import pytest
import requests

from psef import tasks, models


@pytest.mark.parametrize('use_transaction', [False], indirect=True)
def test_simple_about_with_live_server(live_server):
    live_server_url = live_server()
    res = requests.get(f'{live_server_url}/api/v1/about')
    assert res.status_code == 200


def test_about_health_status(test_client, app, monkeypatch):
    monkeypatch.setitem(app.config, 'HEALTH_KEY', None)
    test_client.req(
        'get',
        '/api/v1/about',
        200,
        query={'health': None},
        result={
            'version': object,
            'features': dict,
        },
    )

    monkeypatch.setitem(app.config, 'HEALTH_KEY', 'good key')
    test_client.req(
        'get',
        '/api/v1/about',
        200,
        query={'health': 'not key'},
        result={
            'version': object,
            'features': dict,
        },
    )

    raise_error = False

    class Inspect:
        def __call__(self, *args, **kwargs):
            if raise_error:
                raise Exception('ERR!')
            return True

        def ping(self, *args, **kwargs):
            return self()

    test_client.req(
        'get',
        '/api/v1/about',
        200,
        query={'health': 'good key'},
        result={
            'version': object,
            'features': dict,
            'health': {
                'application': True,
                'database': True,
                'uploads': True,
                'mirror_uploads': True,
            },
        }
    )

    raise_error = True

    monkeypatch.setattr(models.Permission, 'get_all_permissions', Inspect())

    test_client.req(
        'get',
        '/api/v1/about',
        500,
        query={'health': 'good key'},
        result={
            'version': object,
            'features': dict,
            'health': {
                'application': True,
                'database': False,
                'uploads': True,
                'mirror_uploads': True,
            },
        },
    )
