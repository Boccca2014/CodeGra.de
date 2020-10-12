"""This module defines all API routes with for site settings.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

import cg_request_args as rqa
from cg_json import JSONResponse

from . import api
from .. import auth, models, site_settings


@api.route('/site_settings/', methods=['GET'])
@rqa.swaggerize('get_all')
@auth.login_required
def get_site_settings(
) -> t.Union[JSONResponse[site_settings.Opt.AllOptsAsJSON],
             JSONResponse[site_settings.Opt.FrontendOptsAsJSON],
             ]:
    """Get the settings for this CodeGrade instance.

    .. :quickref: Site settings; Get the site settings for this instance.
    """
    auth.SiteSettingsPermissions().ensure_may_see()
    return JSONResponse.make(site_settings.Opt.get_all_opts())


@api.route('/site_settings/', methods=['PATCH'])
@rqa.swaggerize('patch')
@auth.login_required
def update_site_settings(
) -> t.Union[JSONResponse[site_settings.Opt.AllOptsAsJSON],
             JSONResponse[site_settings.Opt.FrontendOptsAsJSON],
             ]:
    """Get the settings for this CodeGrade instance.

    .. :quickref: Site settings; Get the site settings for this instance.
    """
    options = rqa.FixedMapping(
        rqa.RequiredArgument(
            'updates',
            rqa.List(site_settings.OPTIONS_INPUT_PARSER),
            'The items you want to update',
        )
    ).from_flask()

    auth.SiteSettingsPermissions().ensure_may_edit()

    for option in options:
        # mypy bug: https://github.com/python/mypy/issues/9580
        edit_row = models.SiteSetting.set_option(
            option, option.value
        )  # type: ignore
        models.db.session.add(edit_row)
    models.db.session.commit()

    return JSONResponse.make(site_settings.Opt.get_all_opts())
