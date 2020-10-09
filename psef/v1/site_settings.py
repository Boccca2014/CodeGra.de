"""This module defines all API routes with for site settings.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t

import cg_request_args as rqa
from cg_json import JSONResponse

from . import api
from .. import site_settings


@api.route('/site_settings/', methods=['GET'])
@rqa.swaggerize('get_all')
def get_site_settings(
) -> t.Union[JSONResponse[site_settings.Opt.AllOptsAsJSON],
             JSONResponse[site_settings.Opt.FrontendOptsAsJSON],
             ]:
    """Get the settings for this CodeGrade instance.

    .. :quickref: Site settings; Get the site settings for this instance.
    """
    return JSONResponse.make(site_settings.Opt.get_frontend_opts())
