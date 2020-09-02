"""This module defines all API routes with the main directory "sso_providers".

The APIs are used to create/get SSO Providers.

SPDX-License-Identifier: AGPL-3.0-only
"""
import json
import uuid
import typing as t

import flask
import structlog
from sqlalchemy.orm import undefer

from cg_json import JSONResponse

from . import api
from .. import auth, models, helpers, exceptions, current_app
from ..models import db
from ..permissions import GlobalPermission as GPerm

logger = structlog.get_logger()


@api.route('/sso_providers/', methods=['GET'])
def get_all_sso_providers() -> JSONResponse[t.Sequence[models.Saml2Provider]]:
    """Get all SSO Providers.

    .. :quickref: SSO Provider; Get all SSO Providers for this instance.
    """
    return JSONResponse.make(
        models.Saml2Provider.query.order_by(
            models.Saml2Provider.created_at.asc()
        ).all()
    )


@api.route('/sso_providers/<uuid:provider_id>/default_logo', methods=['GET'])
def get_default_logo(provider_id: uuid.UUID) -> flask.Response:
    """Get the default logo of the given provider.

    .. :quickref: SSO Provider; Get the default logo of a provider.

    :param provider_id: The id of the provider from which you want to get the
        logo.
    """
    provider = helpers.get_or_404(
        models.Saml2Provider, provider_id, options=[undefer('logo')]
    )
    return flask.Response(
        provider.logo, headers={'Content-Type': 'application/octet-stream'}
    )


@api.route('/sso_providers/', methods=['POST'])
@auth.permission_required(GPerm.can_manage_sso_providers)
def create_sso_providers() -> JSONResponse[models.Saml2Provider]:
    """Register a new SSO Provider in this instance.

    .. :quickref: SSO Provider; Create a new SSO Providers in this instance.

    Users will be able to login using the registered provider.

    The request should contain two files. One named ``json`` containing the
    json data explained below and one named ``logo`` containing the backup
    logo.

    :>json metadata_url: The url where we can download the metadata for the IdP
        connected to this provider.
    :>json name: If no name can be found in the metadata this name will be
        displayed to users when choosing login methods.
    :>json description: If no description can be found in the metadata this
        description will be displayed to users when choosing login methods.

    :returns: The just created provider.
    """
    json_files = helpers.get_files_from_request(
        max_size=current_app.max_single_file_size, keys=['json']
    )
    data = helpers.ensure_json_dict(json.load(json_files[0]))

    with helpers.get_from_map_transaction(data) as [get, _]:
        metadata_url = get('metadata_url', str)
        name = get('name', str)
        description = get('description', str)

    logo = helpers.get_files_from_request(
        max_size=current_app.max_single_file_size, keys=['logo']
    )[0]

    prov = models.Saml2Provider(
        metadata_url=metadata_url,
        name=name,
        description=description,
        logo=logo,
    )
    db.session.add(prov)
    db.session.flush()
    try:
        prov.check_metadata_url()
    except:
        logger.error(
            'Error parsing given metadata url',
            exc_info=True,
            report_to_sentry=True,
        )
        raise exceptions.APIException(
            'Could not parse the metadata in the given metadata url',
            'The metadata could not be parsed',
            exceptions.APICodes.INVALID_PARAM, 400
        )
    db.session.commit()

    return JSONResponse.make(prov)
