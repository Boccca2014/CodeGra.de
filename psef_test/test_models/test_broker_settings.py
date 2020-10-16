import re
import datetime

import jwt
import pytest
import requests

import cg_broker.api
import cg_cache.inter_request
from psef.models import BrokerSetting


def test_broker_settings_get_session(
    describe, make_function_spy, test_client, stub_function, app
):
    with describe('setup'):
        mem_cache = cg_cache.inter_request.MemoryBackend(
            'test', datetime.timedelta(minutes=2)
        )
        host = 'https://www.mocky.io'
        setting = BrokerSetting._get_or_create(host, True)

    with describe('returns same'):
        with setting.get_session() as ses:
            assert ses.get('/v2/5d9e5e71320000c532329d38').json() == {
                'code': 5
            }

    with describe('sets correct header'):
        with setting.get_session() as ses:
            spy = make_function_spy(ses, 'send', pass_self=True)
            assert ses.get('/v2/5d9e5e71320000c532329d38').json() == {
                'code': 5
            }
            assert spy.called_amount == 1
            args, = spy.all_args
            signature = args[0].headers['CG-Application-Signature']

        def local_download(_, broker_id):
            return test_client.req(
                'get', f'/api/v-internal/brokers/{broker_id}', 200
            )['public_key']

        stub_function.stub(
            cg_broker.api,
            '_download_public_key',
            local_download,
            with_args=True
        )
        assert (
            cg_broker.api._verify_public_instance_jwt(
                mem_cache, signature, re.compile('.*')
            ) == app.config['EXTERNAL_URL']
        )


def test_broker_settings_timeout(describe):
    with describe('setup'):
        setting = BrokerSetting._get_or_create('https://httpstat.us/', True)
        url = '200?sleep=1000'

    with describe('default timeout is 10s'):
        with setting.get_session() as ses:
            assert ses.get(url).ok

    with describe('can override timeout'):
        with setting.get_session() as ses:
            with pytest.raises(requests.exceptions.RequestException):
                ses.get(url, timeout=0.5)


def test_broker_settings_get_or_create(describe, session):
    with describe('does not always create'):
        setting_id = BrokerSetting._get_or_create(
            'https://httpstat.us/', True
        ).id
        session.expire_all()
        assert BrokerSetting._get_or_create(
            'https://httpstat.us/', True
        ).id == setting_id

    with describe('entire url should match or it should create'):
        assert BrokerSetting._get_or_create(
            'https://httpstat.us/other', True
        ).id != setting_id
