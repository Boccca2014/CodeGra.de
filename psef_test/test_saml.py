import io
import json
import uuid
import contextlib
import subprocess
from datetime import timedelta

import furl
import flask
import freezegun

import psef
import dotdict
import helpers
import psef.models as m
from cg_dt_utils import DatetimeWithTimezone


def test_create_provider(
    test_client, stub_function, logged_in, describe, admin_user, session
):
    with describe('setup'), logged_in(admin_user):
        user = helpers.create_user_with_role(session, 'BLAH', [])

    with describe('Can create provider'), logged_in(admin_user):
        provider1 = helpers.create_sso_provider(
            test_client,
            stub_function,
            'SSO Prov 1',
            ui_info={
                'name': 'A name',
                'description': 'A desc',
                'logo': None,
            }
        )
        assert provider1['ui_info']['name'] == 'A name'
        assert provider1['ui_info']['description'] == 'A desc'
        assert provider1['ui_info']['logo'] is None

    with describe('Can create a provider where no metadata is returned'
                  ), logged_in(admin_user):
        provider2 = helpers.create_sso_provider(
            test_client,
            stub_function,
            'SSO Prov 2',
            description='TEST SSO',
            ui_info={
                'name': None,
                'description': None,
                'logo': None,
            }
        )
        assert provider2['ui_info']['name'] == 'SSO Prov 2'
        assert provider2['ui_info']['description'] == 'TEST SSO'
        assert provider2['ui_info']['logo'] is None

    with describe('Cannot add with invalid metadata url'
                  ), logged_in(admin_user):
        err = helpers.create_sso_provider(
            test_client,
            stub_function,
            'SSO Prov 2',
            description='TEST SSO',
            ui_info='NOT VALID',
            err=400,
            no_call=False,
        )
        assert 'Could not parse the metadata' in err['message']

    with describe('Cannot create a provider as a normal user'
                  ), logged_in(user):
        helpers.create_sso_provider(test_client, stub_function, 'ERR', err=403)

    with describe('Can list created providers without logging in'):
        test_client.req(
            'get',
            '/api/v1/sso_providers/',
            200,
            result=[provider1, provider2],
        )

    with describe('Can retrieve default logo of providers'):
        response = test_client.get(
            f'/api/v1/sso_providers/{helpers.get_id(provider1)}/default_logo'
        )
        assert response.status_code == 200
        popen = subprocess.Popen(['file', '-'],
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        file_stdout, _ = popen.communicate(input=response.get_data())
        assert b'SVG' in file_stdout
        assert b'image' in file_stdout


def test_getting_metadata(
    test_client, describe, logged_in, admin_user, stub_function
):
    with describe('setup'), logged_in(admin_user):
        with open(
            helpers.test_data('test_saml_xml', 'valid_with_logo.xml')
        ) as f:
            xml = f.read()
        stub_function(
            m.saml_provider._MetadataParser, 'get_metadata', lambda: xml
        )

        prov = helpers.create_sso_provider(
            test_client, stub_function, 'Prov', no_stub=True
        )

    with describe('can retrieve metadata and is valid'):
        response = test_client.get(
            f'/api/sso/saml2/metadata/{helpers.get_id(prov)}'
        )
        assert response.status_code == 200
        assert response.content_type == 'text/xml'


def test_invalid_saml_flows(
    test_client, describe, logged_in, admin_user, stub_function, app
):
    with describe('setup'), logged_in(admin_user):
        with open(
            helpers.test_data('test_saml_xml', 'valid_with_logo.xml')
        ) as f:
            xml = f.read()

        stub_function(
            m.saml_provider._MetadataParser, 'get_metadata', lambda: xml
        )

        prov = helpers.create_sso_provider(
            test_client, stub_function, 'Prov', no_stub=True
        )

        def assert_empty_session():
            for key in flask.session:
                assert not key.startswith('[SAML]')

        errors = is_auth = redirect_url = nameid_format = nameid = attributes = None

        def set_data():
            nonlocal errors, is_auth, redirect_url, nameid_format, nameid, attributes
            errors = []
            is_auth = True
            redirect_url = app.config['EXTERNAL_URL']
            nameid_format = psef.saml2.OneLogin_Saml2_Constants.NAMEID_PERSISTENT
            nameid = 'WOO'
            attributes = {
                psef.saml2._AttributeNames.UID: ['uid'],
                psef.saml2._AttributeNames.EMAIL: ['email'],
                psef.saml2._AttributeNames.FULL_NAME: ['full name'],
            }

        set_data()
        describe.add_hook(set_data)
        stubs = dotdict.dotdict()

        @contextlib.contextmanager
        def auth_stubbed():
            with stub_function.temp_stubs() as stubber:
                stubs.process = stubber.stub(
                    psef.saml2.OneLogin_Saml2_Auth, 'process_response'
                )

                stubs.get_errors = stubber.stub(
                    psef.saml2.OneLogin_Saml2_Auth,
                    'get_errors', lambda: errors
                )

                stubs.is_auth = stubber.stub(
                    psef.saml2.OneLogin_Saml2_Auth,
                    'is_authenticated', lambda: is_auth
                )

                stubs.redirect = stubber.stub(
                    psef.saml2.OneLogin_Saml2_Auth,
                    'redirect_to', lambda: redirect_url
                )

                stubber.stub(
                    psef.saml2.OneLogin_Saml2_Auth,
                    'get_nameid_format', lambda: nameid_format
                )

                stubber.stub(
                    psef.saml2.OneLogin_Saml2_Auth,
                    'get_nameid', lambda: nameid
                )

                stubber.stub(
                    psef.saml2.OneLogin_Saml2_Auth,
                    'get_attributes', lambda: attributes
                )
                yield
            stubs.clear()

    with describe('can do login when all is good'), test_client as client:
        login = client.get(f'/api/sso/saml2/login/{helpers.get_id(prov)}')
        redirect_url = furl.furl(login.headers['Location']).args['RelayState']

        with auth_stubbed():
            res = client.post(
                f'/api/sso/saml2/acs/{helpers.get_id(prov)}',
                data={'RelayState': 'relay_state'}
            )

            assert 300 <= res.status_code < 400
            assert res.headers['Location'] == redirect_url
            assert len(stubs) == 4
            assert all(v.called for v in stubs.values())
            assert stubs.redirect.all_args == [{0: 'relay_state'}]
            assert flask.session.get('[SAML]_DB_BLOB_ID')

    with describe('handles errors'), test_client as client:
        errors = ['WOW NOT&GOOD']
        with auth_stubbed():
            res = client.post(
                f'/api/sso/saml2/acs/{helpers.get_id(prov)}',
                data={'RelayState': 'relay_state'}
            )
            assert res.status_code == 400
            assert flask.escape('WOW NOT&GOOD').encode() in res.get_data()
            assert b'WOW NOT&GOOD' not in res.get_data()
            assert b'Something went wrong during login' in res.get_data()
            assert_empty_session()

    with describe('RelayState is required'), test_client as client:
        with auth_stubbed():
            res = client.post(
                f'/api/sso/saml2/acs/{helpers.get_id(prov)}', data={}
            )
            assert res.status_code == 400
            assert b'No redirection target found' in res.get_data()
            assert_empty_session()

    with describe('cannot redirect outside of url'), test_client as client:
        redirect_url = 'https://google.com!'
        with auth_stubbed():
            res = client.post(
                f'/api/sso/saml2/acs/{helpers.get_id(prov)}',
                data={'RelayState': 'relay_state'}
            )
            assert res.status_code == 400
            assert b'Wrong redirection target found' in res.get_data()
            assert_empty_session()

    with describe('requires persistent nameid'), test_client as client:
        nameid_format = psef.saml2.OneLogin_Saml2_Constants.NAMEID_TRANSIENT
        with auth_stubbed():
            res = client.post(
                f'/api/sso/saml2/acs/{helpers.get_id(prov)}',
                data={'RelayState': 'relay_state'}
            )

            assert res.status_code == 400
            assert b'Got a wrong type of name id' in res.get_data()
            assert_empty_session()

    with describe('all attributes are required'), test_client as client:
        del attributes[psef.saml2._AttributeNames.UID]

        with auth_stubbed():
            res = client.post(
                f'/api/sso/saml2/acs/{helpers.get_id(prov)}',
                data={'RelayState': 'relay_state'}
            )

            assert res.status_code == 400
            assert b'Not all required data found' in res.get_data()
            assert_empty_session()

    with describe(
        'Display name can be used instead of full name'
    ), test_client as client:
        del attributes[psef.saml2._AttributeNames.FULL_NAME]
        attributes[psef.saml2._AttributeNames.DISPLAY_NAME] = ['DISPLAY NAME']

        with auth_stubbed():
            res = client.post(
                f'/api/sso/saml2/acs/{helpers.get_id(prov)}',
                data={'RelayState': 'relay_state'}
            )
            assert 302 <= res.status_code < 400

            blob_id = flask.session['[SAML]_DB_BLOB_ID']
            blob = m.BlobStorage.query.get(blob_id)
            user = m.User.query.get(blob.as_json()['user_id'])
            assert user.name == 'DISPLAY NAME'


def test_valid_saml_flows(
    test_client, describe, logged_in, admin_user, stub_function, app, session,
    monkeypatch
):
    with describe('setup'), logged_in(admin_user):
        with open(
            helpers.test_data('test_saml_xml', 'valid_with_logo.xml')
        ) as f:
            xml = f.read()

        with open(
            helpers.test_data('test_saml_xml', 'valid_response.json')
        ) as f:
            valid_response = json.load(f)

        stub_function(
            m.saml_provider._MetadataParser, 'get_metadata', lambda: xml
        )

        prov = helpers.to_db_object(
            helpers.create_sso_provider(
                test_client, stub_function, 'Prov', no_stub=True
            ), m.Saml2Provider
        )

        token = valid_response.pop('token')
        request_time = DatetimeWithTimezone.fromisoformat(
            valid_response.pop('request_time')
        )
        auth_n_request = valid_response.pop('AuthNRequest')
        prov.id = valid_response.pop('prov_id')
        prov._key_data = valid_response.pop('key').encode('utf8')
        prov._cert_data = valid_response.pop('cert').encode('utf8')

        host = valid_response['http_host']
        http = 'https' if valid_response['https'] == 'on' else 'http'
        external_url = furl.furl()
        external_url.scheme = http
        external_url.host = host

        session.commit()
        stub_function(
            psef.saml2, '_prepare_flask_request', lambda: valid_response
        )

    with test_client as client, freezegun.freeze_time(request_time):
        with describe('can do login when all is good'):
            client.get(f'/api/sso/saml2/login/{helpers.get_id(prov)}')
            with client.session_transaction() as sess:
                sess['[SAML]_AuthNRequestID'] = auth_n_request
                sess['[SAML]_TOKEN'] = token

            with monkeypatch.context() as ctx:
                ctx.setitem(app.config, 'EXTERNAL_URL', external_url.tostr())

                res = client.post(
                    f'/api/sso/saml2/acs/{helpers.get_id(prov)}',
                    data='Not used'
                )

            assert 300 <= res.status_code < 400
            loc = res.headers['Location']

            base = furl.furl(external_url.tostr()).add(path='/sso_login/')

            assert loc.startswith(base.tostr())
            assert token == loc.split('/')[-1]
            db_base_id = flask.session['[SAML]_DB_BLOB_ID']

            assert m.BlobStorage.query.get(db_base_id) is not None

        with describe('cannot use jwt route without token in session'):
            with client.session_transaction() as sess:
                assert sess.pop('[SAML]_TOKEN') == token

            err = client.req('post', f'/api/sso/saml2/jwts/{token}', 409)
            assert 'Could not find all required data' in err['message']

        with describe('cannot use jwt route without correct token in session'):
            with client.session_transaction() as sess:
                sess['[SAML]_TOKEN'] = 'incorrect_token'
                sess['[SAML]_DB_BLOB_ID'] = db_base_id

            assert m.BlobStorage.query.get(db_base_id) is not None
            err = client.req('post', f'/api/sso/saml2/jwts/{token}', 400)
            assert 'Invalid token provided' in err['message']

        with describe(
            'cannot use jwt route without correct token in url and session'
        ):
            wrong_token = str(uuid.uuid4())
            with client.session_transaction() as sess:
                sess['[SAML]_TOKEN'] = wrong_token
                sess['[SAML]_DB_BLOB_ID'] = db_base_id

            err = client.req('post', f'/api/sso/saml2/jwts/{wrong_token}', 400)
            assert 'Invalid token provided' in err['message']

        with describe('cannot use jwt route without correct token in url'):
            with client.session_transaction() as sess:
                sess['[SAML]_TOKEN'] = token
                sess['[SAML]_DB_BLOB_ID'] = db_base_id

            err = client.req('post', f'/api/sso/saml2/jwts/{wrong_token}', 400)
            assert 'Invalid token provided' in err['message']

        with describe(
            'cannot use blob after some time'
        ), freezegun.freeze_time(request_time + timedelta(minutes=15)):
            with client.session_transaction() as sess:
                sess['[SAML]_TOKEN'] = token
                sess['[SAML]_DB_BLOB_ID'] = db_base_id

            client.req('post', f'/api/sso/saml2/jwts/{token}', 404)

        with describe('can use one time if all is right'):
            with client.session_transaction() as sess:
                sess['[SAML]_TOKEN'] = token
                sess['[SAML]_DB_BLOB_ID'] = db_base_id

            res = client.req('post', f'/api/sso/saml2/jwts/{token}', 200)
            assert isinstance(res.get('access_token'), str)

            # Cannot use again
            with client.session_transaction() as sess:
                sess['[SAML]_TOKEN'] = token
                sess['[SAML]_DB_BLOB_ID'] = db_base_id
            client.req('post', f'/api/sso/saml2/jwts/{token}', 404)
