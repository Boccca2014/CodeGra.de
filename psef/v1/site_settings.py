"""This module defines all API routes with for site settings.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

import cg_request_args as rqa
from cg_json import JSONResponse

from . import api
from .. import models, site_settings


@api.route('/site_settings/', methods=['GET'])
@rqa.swaggerize('get_all')
def get_site_settings(
) -> t.Union[JSONResponse[site_settings.Opt.AllOptsAsJSON],
             JSONResponse[site_settings.Opt.FrontendOptsAsJSON],
             ]:
    """Get the settings for this CodeGrade instance.

    .. :quickref: Site settings; Get the site settings for this instance.
    """
    return JSONResponse.make(site_settings.Opt.get_all_opts())


@api.route('/site_settings/', methods=['PATCH'])
@rqa.swaggerize('update')
def update_site_settings(
) -> t.Union[JSONResponse[site_settings.Opt.AllOptsAsJSON],
             JSONResponse[site_settings.Opt.FrontendOptsAsJSON],
             ]:
    """Get the settings for this CodeGrade instance.

    .. :quickref: Site settings; Get the site settings for this instance.
    """
    options = site_settings.OPTIONS_INPUT_PARSER.from_flask()
    for option in options:
        # mypy bug: https://github.com/python/mypy/issues/9580
        edit_row = models.SiteSetting.set_option(option, option.value)  # type: ignore
        models.db.session.add(edit_row)
    models.db.session.commit()

    return JSONResponse.make(site_settings.Opt.get_all_opts())
