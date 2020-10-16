import pytest
import requests

# SPDX-License-Identifier: AGPL-3.0-only
import psef
import requests_stubs
from psef import tasks, models


@pytest.mark.parametrize('fresh_db', [True], indirect=True)
def test_simple_about_with_live_server(live_server):
    live_server_url = live_server()
    res = requests.get(f'{live_server_url}/api/v1/about')
    assert res.status_code == 200


def test_about_health_status(
    test_client, app, monkeypatch, stub_function_class
):
    monkeypatch.setitem(app.config, 'HEALTH_KEY', None)

    test_client.req(
        'get',
        '/api/v1/about',
        200,
        query={'health': None},
        result={
            'version': object,
            'commit': str,
            'features': dict,
            'release': dict,
            'settings': dict,
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
            'commit': str,
            'features': dict,
            'release': dict,
            'settings': dict,
        },
    )

    stub_session_cls = requests_stubs.session_maker()
    stub_broker_ses = stub_function_class(stub_session_cls, with_args=True)
    monkeypatch.setattr(psef.helpers, 'BrokerSession', stub_broker_ses)

    raise_db_error = False

    class Inspect:
        def __call__(self, *args, **kwargs):
            if raise_db_error:
                raise Exception('ERR!')
            return psef.permissions.CoursePermission

        def ping(self, *args, **kwargs):
            return self()

    monkeypatch.setattr(models.Permission, 'get_all_permissions', Inspect())
    monkeypatch.setitem(app.config, 'MIN_FREE_DISK_SPACE', 0)

    test_client.req(
        'get',
        '/api/v1/about',
        200,
        query={'health': 'good key'},
        result={
            'version': object,
            'commit': str,
            'features': dict,
            'release': dict,
            'settings': dict,
            'health': {
                'application': True,
                'database': True,
                'uploads': True,
                'mirror_uploads': True,
                'temp_dir': True,
                'broker': True,
            },
        }
    )
    assert len(stub_session_cls.all_calls) == 1
    assert stub_session_cls.all_calls[0]['args'][0] == '/api/v1/ping'
    stub_session_cls.reset_cls()

    raise_db_error = True

    test_client.req(
        'get',
        '/api/v1/about',
        500,
        query={'health': 'good key'},
        result={
            'version': object,
            'commit': str,
            'features': dict,
            'release': dict,
            'settings': dict,
            'health': {
                'application': True,
                'database': False,
                'uploads': True,
                'mirror_uploads': True,
                'temp_dir': True,
                'broker': True,
            },
        },
    )

    # Should even be called when other tests fail
    assert len(stub_session_cls.all_calls) == 1
    stub_session_cls.reset_cls()
    raise_db_error = False

    class ErrorResposne:
        def raise_for_status(self):
            raise requests.RequestException()

    stub_session_cls.Response = ErrorResposne

    test_client.req(
        'get',
        '/api/v1/about',
        500,
        query={'health': 'good key'},
        result={
            'version': object,
            'commit': str,
            'features': dict,
            'release': dict,
            'settings': dict,
            'health': {
                'application': True,
                'database': True,
                'uploads': True,
                'mirror_uploads': True,
                'temp_dir': True,
                'broker': False,
            },
        },
    )

    # We shouldn't do any retrying or anything
    assert len(stub_session_cls.all_calls) == 1
    stub_session_cls.reset_cls()

    monkeypatch.setitem(app.config, 'MIN_FREE_DISK_SPACE', float('inf'))
    test_client.req(
        'get',
        '/api/v1/about',
        500,
        query={'health': 'good key'},
        result={
            'version': object,
            'commit': str,
            'features': dict,
            'release': dict,
            'settings': dict,
            'health': {
                'application': True,
                'database': True,
                'uploads': False,
                'mirror_uploads': False,
                'temp_dir': True,
                'broker': True,
            },
        },
    )
