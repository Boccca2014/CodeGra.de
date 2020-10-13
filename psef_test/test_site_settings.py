import helpers
from psef import site_settings


def test_get_all_settings(
    test_client, describe, logged_in, admin_user, session
):
    with describe('setup'):
        user = helpers.create_user_with_role(session, 'Teacher', [])

    with describe('cannot get settings as normal user'):
        test_client.req('get', '/api/v1/site_settings/', 401)
        with logged_in(user):
            test_client.req('get', '/api/v1/site_settings/', 403)

    with describe('can get settings as admin user'), logged_in(admin_user):
        setting = test_client.req(
            'get',
            '/api/v1/site_settings/',
            200,
            result={
                setting.name: object
                for setting in site_settings.Opt._ALL_OPTS
            }
        )

        for name, value in setting.items():
            print(name)
            getattr(site_settings.Opt, name).parser.try_parse(value)


def test_set_setting(test_client, describe, logged_in, admin_user, session):
    with describe('setup'):
        user = helpers.create_user_with_role(session, 'Teacher', [])
        orig = site_settings.Opt.MIN_PASSWORD_SCORE.value
        assert orig not in (1, 2)

        def make_data(name, value):
            return {'updates': [{'name': name, 'value': value}]}

    with describe('cannot set settings as normal user'):
        test_client.req('patch', '/api/v1/site_settings/', 401)
        with logged_in(user):
            test_client.req(
                'patch', '/api/v1/site_settings/', 403, data={'updates': []}
            )

    with describe('can set settings as admin user'), logged_in(admin_user):
        test_client.req(
            'patch',
            '/api/v1/site_settings/',
            200,
            data=make_data('MIN_PASSWORD_SCORE', 2),
            result={'__allow_extra__': True, 'MIN_PASSWORD_SCORE': 2},
        )
        assert site_settings.Opt.MIN_PASSWORD_SCORE.value == 2

        # Can mutate it
        test_client.req(
            'patch',
            '/api/v1/site_settings/',
            200,
            data=make_data('MIN_PASSWORD_SCORE', 1),
            result={'__allow_extra__': True, 'MIN_PASSWORD_SCORE': 1},
        )
        assert site_settings.Opt.MIN_PASSWORD_SCORE.value == 1

    with describe('Can reset back to original value'), logged_in(admin_user):
        test_client.req(
            'patch',
            '/api/v1/site_settings/',
            200,
            data=make_data('MIN_PASSWORD_SCORE', None),
            result={'__allow_extra__': True, 'MIN_PASSWORD_SCORE': orig},
        )
        assert site_settings.Opt.MIN_PASSWORD_SCORE.value == orig
