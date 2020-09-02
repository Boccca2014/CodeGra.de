import uuid

import pytest

import psef_test.helpers as helpers
from psef import models as m
from psef.models.saml_provider import (
    Saml2Provider, UserSamlProvider, _MetadataParser
)


@pytest.mark.parametrize(
    'filename,err,data_for',
    [
        ('valid_with_logo.xml', False, {'description', 'name', 'logo'}),
        ('invalid.xml', True, set()),
        ('valid_without_logo.xml', False, {'description', 'name'}),
        ('valid_without_ui_info_data.xml', False, set()),
        ('valid_without_ui_info.xml', False, set()),
        (
            'valid_with_multiple_names.xml',
            False,
            {'description', 'name', 'logo'},
        ),
    ],
)
def test_parse_metadata(describe, filename, err, data_for):
    with describe('setup'):
        with open(helpers.test_data('test_saml_xml', filename)) as f:
            xml = f.read()

    with describe('do test'):
        if err:
            with pytest.raises(Exception):
                _MetadataParser.parse(xml)
            return

        result = _MetadataParser.parse(xml)
        assert isinstance(result, dict)
        assert isinstance(result['idp'], dict)
        ui_info = result['idp']['ui_info']
        assert isinstance(ui_info, dict)
        assert sorted(ui_info.keys()) == [
            'description',
            'logo',
            'name',
        ]
        for key, value in ui_info.items():
            if key in data_for:
                assert value is not None
                assert value
            else:
                assert value is None


def test_user_saml_data(
    describe, test_client, logged_in, admin_user, stub_function, app
):
    with describe('setup'), logged_in(admin_user):
        prov1, prov2 = [
            helpers.to_db_object(
                helpers.create_sso_provider(
                    test_client, stub_function, f'P{i}'
                ),
                Saml2Provider,
            ) for i in range(1, 3)
        ]

    with describe('can add new user'):
        u1 = UserSamlProvider.get_or_create_user(
            'nameid_user1', prov1, 'wanted', 'My Name', 'user@user.com'
        )
        u1.role.name = app.config['DEFAULT_SSO_ROLE']
        assert u1.username == 'wanted'
        assert u1.name == 'My Name'
        assert u1.email == 'user@user.com'
        u1_id = u1.id
        assert u1_id is not None

    with describe('Same nameid does not create a new user but updates attrs'):
        u1_new = UserSamlProvider.get_or_create_user(
            'nameid_user1', prov1, 'new_username', 'New name', 'user@user.de'
        )
        assert u1_new.username == 'wanted'
        assert u1_new.name == 'New name'
        assert u1_new.email == 'user@user.de'
        assert u1_new.id == u1_id

    with describe('New nameid does create a new user'):
        u2 = UserSamlProvider.get_or_create_user(
            'nameid_user2', prov1, 'wanted', 'name', 'email@emai.com'
        )
        assert u2.username == 'wanted (1)'
        u2_id = u2.id
        assert u2_id is not None
        assert u2_id != u1_id

    with describe('Same nameid different provider creates new user'):
        u3 = UserSamlProvider.get_or_create_user(
            'nameid_user1', prov2, 'wanted', 'name', 'email@emai.com'
        )
        assert u3.username == 'wanted (2)'
        assert u3.id is not None
        assert u3.id != u1_id
        assert u3.id != u2_id
