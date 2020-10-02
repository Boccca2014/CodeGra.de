import psef.models as m


def test_get_ui_preferences(
    test_client, session, logged_in, admin_user, describe, error_template
):
    with describe('setup'):
        url = 'api/v1/settings/ui_preferences/'

    with describe('should return a maping of all preferences'
                  ), logged_in(admin_user):
        test_client.req(
            'get',
            url,
            200,
            result={p.name: (bool, type(None))
                    for p in m.UIPreferenceName},
        )

    with describe('values should be null when not set'), logged_in(admin_user):
        test_client.req(
            'get',
            url,
            200,
            result={p.name: None
                    for p in m.UIPreferenceName},
        )

    with describe('should return the value when set'), logged_in(admin_user):
        pref_name = m.UIPreferenceName.rubric_editor_v2.name
        pref = m.UIPreference(
            user_id=admin_user.id, name=pref_name, value=True
        )
        session.add(pref)
        session.commit()

        test_client.req(
            'get',
            url,
            200,
            result={
                '__allow_extra__': True,
                pref_name: True,
            },
        )

        pref = m.UIPreference.query.filter_by(
            user=admin_user, name=pref_name
        ).one()
        pref.value = False
        session.commit()

        test_client.req(
            'get',
            url,
            200,
            result={
                '__allow_extra__': True,
                pref_name: False,
            },
        )

    with describe('should error when not logged in'):
        test_client.req(
            'get',
            url,
            401,
            result=error_template,
        )


def test_update_ui_preference(
    test_client, session, logged_in, admin_user, describe, error_template
):
    with describe('setup'):
        url = 'api/v1/settings/ui_preferences/'

    with describe('should update the value'), logged_in(admin_user):
        pref_name = m.UIPreferenceName.rubric_editor_v2.name

        test_client.req(
            'patch',
            url,
            204,
            data={'name': pref_name, 'value': True},
        )

        pref = m.UIPreference.query.filter_by(
            user=admin_user, name=pref_name
        ).one()
        assert pref.value == True

        test_client.req(
            'patch',
            url,
            204,
            data={'name': pref_name, 'value': False},
        )

        pref = m.UIPreference.query.filter_by(
            user=admin_user, name=pref_name
        ).one()
        assert pref.value == False

    with describe('should error when not logged in'):
        test_client.req(
            'patch',
            url,
            401,
            result=error_template,
        )
