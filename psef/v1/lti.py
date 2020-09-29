"""This module implements all lti routes.

.. warning::

    Most of the routes in this modules should not be considered public. Only
    routes in this module explicitly stating that they are part of the public
    API should be considered stable and public.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t
import urllib
import urllib.parse
from datetime import timedelta

import jwt
import flask
import werkzeug
import structlog
import pylti1p3.exception
from mypy_extensions import TypedDict
from typing_extensions import Literal
from pylti1p3.deep_link import DeepLink

from psef import app
from cg_json import JSONResponse, jsonify
from cg_helpers import assert_never
from cg_dt_utils import DatetimeWithTimezone

from . import api
from .. import (
    auth, errors, models, helpers, parsers, features, registry, exceptions
)
from ..lti import LTIVersion
from ..lti import v1_1 as lti_v1_1
from ..lti import v1_3 as lti_v1_3
from ..models import db
from ..lti.abstract import LTILaunchData

logger = structlog.get_logger()


def _maybe_get_provider(provider_id: t.Optional[str]
                        ) -> t.Optional[models.LTI1p3Provider]:
    if provider_id is None:
        return None
    else:
        return helpers.get_or_404(models.LTI1p3Provider, provider_id)


def _convert_boolean(value: t.Union[bool, str, None], default: bool) -> bool:
    """Convert possible string value to boolean.

    >>> cv = _convert_boolean
    >>> s = object()
    >>> cv('true', s)
    True
    >>> cv('false', s)
    False
    >>> cv(True, s)
    True
    >>> cv('not a bool', s) is s
    True
    >>> cv(None, s) is s
    True
    """
    if isinstance(value, bool):
        return value
    elif isinstance(value, str) and value.lower() in {'true', 'false'}:
        return value.lower() == 'true'
    return default


def _make_blob_and_redirect(
    params: t.Mapping[str, object],
    version: LTIVersion,
    goto_latest_submission: bool,
) -> werkzeug.wrappers.Response:
    data = {
        'params': {
            'data': params,
            'version': version.__to_json__(),
        },
        'exp': DatetimeWithTimezone.utcnow() + timedelta(minutes=5)
    }
    blob = models.BlobStorage(
        data=jwt.encode(
            data,
            app.config['LTI_SECRET_KEY'],
            algorithm='HS512',
        )
    )
    db.session.add(blob)
    db.session.commit()

    return flask.redirect(
        (
            '{host}/lti_launch/?inLTI=true&blob_id={blob_id}'
            '&redirect={redirect}&goto_latest_submission={goto_latest}'
        ).format(
            host=app.config['EXTERNAL_URL'],
            blob_id=blob.id,
            redirect=urllib.parse.quote(
                flask.request.args.get('codegrade_redirect', ''),
            ),
            goto_latest=goto_latest_submission,
        ),
        code=303,
    )


@api.route('/lti/launch/1', methods=['POST'])
@features.feature_required(features.Feature.LTI)
def launch_lti() -> t.Any:
    """Do a LTI launch.
    """
    try:
        params = lti_v1_1.LTI.create_from_request(flask.request).launch_params
    except exceptions.APIException as exc:
        return _make_blob_and_redirect(
            {
                'type': 'exception',
                'exception_message': exc.message,
                'original_exception': JSONResponse.dump_to_object(exc),
            },
            version=LTIVersion.v1_1,
            goto_latest_submission=False,
        )

    return _make_blob_and_redirect(
        params, LTIVersion.v1_1, goto_latest_submission=False
    )


@api.route('/lti/', methods=['GET'])
def get_lti_config() -> werkzeug.wrappers.Response:
    """Get a LTI config xml for this CodeGrade instance

    .. :quickref: LTI; Get the configuration for a LTI 1.1 provider.

    This route is part of the public API.

    :qparam str lms: The name of the LMS to get the config for. This is
        required.

    :returns: An xml that can be used as a config for the specified LMS.
    """
    helpers.ensure_keys_in_dict(flask.request.args, [('lms', str)])
    lms: str = flask.request.args.get('lms', '')
    cls = registry.lti_1_1_providers.get(lms)
    if cls is None:
        raise errors.APIException(
            f'The given LMS "{lms}" was not found',
            f'The LMS "{lms}" is not yet supported by CodeGrade',
            errors.APICodes.OBJECT_NOT_FOUND, 404
        )

    if cls.supports_lti_common_cartridge():
        res = flask.make_response(cls.generate_xml())
        res.headers['Content-Type'] = 'application/xml; charset=utf-8'
        return res
    else:
        raise errors.APIException(
            f'{lms} does not support Common Cartridge configuration',
            f'The LMS "{lms}" does not support Common Cartridge configuration',
            errors.APICodes.INVALID_PARAM, 400
        )


class LTIDeeplinkResult(TypedDict):
    """The result of a LTI launch when an actual deep link is required.

    :ivar type: Always ``"deep_link"``.
    :ivar deep_link_blob_id: The id of the blob that stores the deep link
        information.
    :ivar auth_token: The authentication token you can use to finish the LTI
        deep link later on.
    """
    type: Literal['deep_link']
    deep_link_blob_id: str
    auth_token: str


class _LTILaunchResult(TypedDict):
    data: t.Union[LTILaunchData, LTIDeeplinkResult]
    version: LTIVersion


def _get_second_phase_lti_launch_data(blob_id: str) -> _LTILaunchResult:
    blob = helpers.filter_single_or_404(
        models.BlobStorage,
        models.BlobStorage.id == uuid.UUID(blob_id),
        with_for_update=True,
        also_error=lambda b: b.age > timedelta(minutes=5),
    )

    try:
        launch_params = jwt.decode(
            blob.data,
            app.config['LTI_SECRET_KEY'],
            algorithms=['HS512'],
        )['params']
    except jwt.PyJWTError as exc:
        logger.warning(
            'Invalid JWT token encountered',
            blob_id=str(blob.id),
            exc_info=True,
        )
        raise errors.APIException(
            (
                'Decoding given JWT token failed, LTI is probably '
                'not configured correctly. Please contact your site admin.'
            ),
            'The decoding of jwt failed.',
            errors.APICodes.INVALID_PARAM,
            400,
        ) from exc
    else:
        db.session.delete(blob)

    version = LTIVersion[launch_params.get('version', LTIVersion.v1_1)]
    data = launch_params['data']
    result: t.Union[LTILaunchData, LTIDeeplinkResult]

    if data.get('type') == 'exception':
        if version is LTIVersion.v1_1:
            code = exceptions.APICodes.LTI1_1_ERROR
        elif version is LTIVersion.v1_3:
            code = exceptions.APICodes.LTI1_3_ERROR
        else:  # pragma: no cover
            assert_never(version, LTIVersion)

        raise exceptions.APIException(
            data.get('exception_message'),
            'An error occured when processing the LTI1.3 launch',
            code,
            400,
            original_exception=data.get('original_exception'),
        )
    elif version == LTIVersion.v1_1:
        inst = lti_v1_1.LTI.create_from_launch_params(data)
        result = inst.do_second_step_of_lti_launch()
    elif version == LTIVersion.v1_3:
        lti_provider = helpers.get_or_404(
            models.LTI1p3Provider, data['lti_provider_id']
        )
        launch_message = lti_v1_3.FlaskMessageLaunch.from_message_data(
            launch_data=data['launch_data'], lti_provider=lti_provider
        )

        if launch_message.is_deep_link_launch():
            deep_link_settings = launch_message.get_deep_link_settings()

            auth_token = str(uuid.uuid4())
            blob = models.BlobStorage(
                json={
                    'type': 'deep_link_settings',
                    'deep_link_settings': deep_link_settings,
                    'deployment_id': launch_message.deployment_id,
                    'auth_token': auth_token,
                    'lti_provider_id': str(lti_provider.id),
                },
            )
            db.session.add(blob)
            db.session.flush()
            result = {
                'type': 'deep_link',
                'deep_link_blob_id': str(blob.id),
                'auth_token': auth_token,
            }
        else:
            result = launch_message.do_second_step_of_lti_launch()
    else:
        assert False

    return {
        'version': version,
        'data': result,
    }


@api.route('/lti/launch/2', methods=['POST'])
@features.feature_required(features.Feature.LTI)
def second_phase_lti_launch(
) -> helpers.JSONResponse[t.Union[_LTILaunchResult, t.Dict[str, t.Any]]]:
    """Do the second part of an LTI launch.

    :>json string blob_id: The id of the blob which you got from the lti launch
        redirect.

    :returns: A _LTILaunch instance.
    :raises APIException: If the given Jwt token is not valid. (INVALID_PARAM)
    """
    with helpers.get_from_map_transaction(
        helpers.get_json_dict_from_request()
    ) as [get, _]:
        blob_id = get('blob_id', str)

    res = _get_second_phase_lti_launch_data(blob_id)
    db.session.commit()

    if helpers.extended_requested():
        return jsonify(res)

    return jsonify(t.cast(dict, res['data']))


@api.route('/lti1.3/login/<lti_provider_id>', methods=['GET', 'POST', 'HEAD'])
@api.route('/lti1.3/login', methods=['GET', 'POST', 'HEAD'])
def do_oidc_login(
    lti_provider_id: t.Optional[str] = None
) -> werkzeug.wrappers.Response:
    """Do an LTI 1.3 OIDC login.

    :param lti_provider_id: The id of the provider doing the launch, not
        required for LMSes that pass all required information.
    """
    req = helpers.maybe_unwrap_proxy(flask.request, flask.Request)
    if req.method == 'GET':
        target = req.args.get('target_link_uri')
    else:
        target = req.form.get('target_link_uri')
    assert target is not None

    try:
        provider = _maybe_get_provider(lti_provider_id)
        oidc = lti_v1_3.FlaskOIDCLogin.from_request(lti_provider=provider)
        red = oidc.get_redirect_object(target)
    except exceptions.APIException as exc:
        logger.info('Login request went wrong', exc_info=True)
        message = exc.message

        if exc.api_code == exceptions.APICodes.OBJECT_NOT_FOUND:
            message = (
                'This LMS was not found as a LTIProvider for CodeGrade, this'
                ' is probably caused by a wrong setup.'
            )

        return _make_blob_and_redirect(
            {
                'type': 'exception',
                'exception_message': message,
                'original_exception': JSONResponse.dump_to_object(exc),
            },
            version=LTIVersion.v1_3,
            goto_latest_submission=False,
        )
    except pylti1p3.exception.OIDCException as exc:
        logger.info('Login request went wrong', exc_info=True)
        return _make_blob_and_redirect(
            {
                'type': 'exception',
                'exception_message': exc.args[0],
            },
            version=LTIVersion.v1_3,
            goto_latest_submission=False,
        )
    logger.info(
        'Redirecting after oidc',
        target=target,
        get_args=req.args,
        post_args=req.form,
        redirect=red,
    )
    return red.do_redirect()


@api.route('/lti1.3/providers/<lti_provider_id>/jwks', methods=['GET'])
@api.route('/lti1.3/jwks/<lti_provider_id>', methods=['GET'])
def get_lti_provider_jwks(
    lti_provider_id: str
) -> helpers.JSONResponse[t.Mapping[str, t.List[t.Mapping[str, str]]]]:
    """Get the JWKS of a given provider.

    .. :quickref: LTI; Get the public key of a provider in JWKS format.

    The ``/api/v1/lti1.3/providers/<lti_provider_id>/jwks`` route is part of
    the public API. The ``/api/v1/lti1.3/jwks/<lti_provider_id>`` is not and
    **will** be removed in a future version.

    :param lti_provider_id: The id of the provider from which you want to get
        the JWKS.
    """
    lti_provider = helpers.filter_single_or_404(
        models.LTI1p3Provider, models.LTI1p3Provider.id == lti_provider_id
    )
    return jsonify({'keys': [lti_provider.get_public_jwk()]})


@api.route('/lti1.3/launch/<lti_provider_id>', methods=['POST'])
@api.route('/lti1.3/launch', methods=['POST'])
def handle_lti_advantage_launch(lti_provider_id: t.Optional[str] = None
                                ) -> t.Union[str, werkzeug.wrappers.Response]:
    """Do a LTI 1.3 launch to the submission page.

    :param lti_provider_id: The id of the provider doing the launch, not
        required for LMSes that pass all required information.
    """

    return _handle_lti_advantage_launch(lti_provider_id, goto_latest_sub=False)


@api.route(
    '/lti1.3/launch_to_latest_submission/<lti_provider_id>', methods=['POST']
)
@api.route('/lti1.3/launch_to_latest_submission', methods=['POST'])
def handle_lti_advantage_launch_to_latest_sub(
    lti_provider_id: t.Optional[str] = None
) -> t.Union[str, werkzeug.wrappers.Response]:
    """Do a LTI 1.3 launch to the latest submission

    :param lti_provider_id: The id of the provider doing the launch, not
        required for LMSes that pass all required information.
    """
    return _handle_lti_advantage_launch(lti_provider_id, goto_latest_sub=True)


def _handle_lti_advantage_launch(
    lti_provider_id: t.Optional[str], goto_latest_sub: bool
) -> t.Union[str, werkzeug.wrappers.Response]:
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'

    try:
        provider = _maybe_get_provider(lti_provider_id)
        message_launch = lti_v1_3.FlaskMessageLaunch.from_request(
            lti_provider=provider,
        ).validate()
    except exceptions.APIException as exc:
        logger.info('An error occurred during the LTI launch', exc_info=True)
        return _make_blob_and_redirect(
            {
                'type': 'exception',
                'exception_message': exc.message,
                'original_exception': JSONResponse.dump_to_object(exc),
            },
            version=LTIVersion.v1_3,
            goto_latest_submission=False,
        )
    except pylti1p3.exception.LtiException as exc:
        logger.info('Incorrect LTI launch encountered', exc_info=True)
        return _make_blob_and_redirect(
            {
                'type': 'exception',
                'exception_message': exc.args[0],
            },
            version=LTIVersion.v1_3,
            goto_latest_submission=False,
        )

    plat_red_url = flask.request.args.get('platform_redirect_url')
    full_win_launch = flask.request.args.get('full_win_launch_requested')
    if full_win_launch == '1' and plat_red_url:
        return flask.redirect(plat_red_url)

    provider = message_launch.get_lti_provider()
    if (
        message_launch.is_deep_link_launch() and
        not provider.lms_capabilities.actual_deep_linking_required
    ):
        deep_link = message_launch.get_deep_link()
        dp_resource = lti_v1_3.CGDeepLinkResource.make(message_launch)
        form = deep_link.output_response_form([dp_resource])
        return f'<!DOCTYPE html>\n<html><body>{form}</body></html>'

    return _make_blob_and_redirect(
        {
            'launch_data': message_launch.get_launch_data(),
            'lti_provider_id': message_launch.get_lti_provider().id,
            'request_args': dict(flask.request.args),
        },
        version=LTIVersion.v1_3,
        goto_latest_submission=goto_latest_sub,
    )


@api.route('/lti1.3/providers/<lti_provider_id>/config', methods=['GET'])
def get_lti1_3_config(lti_provider_id: str) -> helpers.JSONResponse[object]:
    """Get the LTI 1.3 config in such a way that it can be used by the LMS
    connected to this provider.

    :param lti_provider_id: The id of the provider you want to get the
        configuration for.

    :returns: An opaque object that is useful only for the LMS.
    """
    lti_provider = helpers.filter_single_or_404(
        models.LTI1p3Provider, models.LTI1p3Provider.id == lti_provider_id
    )
    return jsonify(lti_provider.get_json_config())


@api.route('/lti1.3/providers/', methods=['GET'])
@auth.login_required
def list_lti1p3_provider(
) -> helpers.JSONResponse[t.List[models.LTI1p3Provider]]:
    """List all known LTI 1.3 providers for this instance.

    .. :quickref: LTI; List all known LTI 1.3 providers.

    This route is part of the public API.

    :returns: A list of all known LTI 1.3 providers.
    """
    providers = [
        prov for prov in models.LTI1p3Provider.query.order_by(
            models.LTI1p3Provider.created_at.asc(),
        ) if auth.LTIProviderPermissions(prov).ensure_may_see.as_bool()
    ]
    return jsonify(providers)


@api.route('/lti/providers/', methods=['GET'])
@auth.login_required
def list_lti_providers(
) -> helpers.JSONResponse[t.Sequence[models.LTIProviderBase]]:
    """List all known LTI providers for this instance.

    .. :quickref: LTI; List all known LTI providers.

    This route is part of the public API.

    :returns: A list of all known LTI providers.
    """
    providers = [
        prov for prov in models.LTIProviderBase.query.order_by(
            models.LTIProviderBase.created_at.asc(),
        ) if auth.LTIProviderPermissions(prov).ensure_may_see.as_bool()
    ]
    return jsonify(providers)


def _create_lti1p3_provider(intended_use: str) -> models.LTI1p3Provider:
    with helpers.get_from_request_transaction() as [get, _]:
        iss = get('iss', str)
        caps = get(
            'lms',
            registry.lti_1_3_lms_capabilities,
            transform=lambda x: x[1],
        )

    if iss == '':
        raise exceptions.APIException(
            'The "iss" must be non empty', f'The iss={iss} was empty',
            exceptions.APICodes.INVALID_PARAM, 400
        )

    return models.LTI1p3Provider.create_and_generate_keys(
        iss=iss,
        lms_capabilities=caps,
        intended_use=intended_use,
    )


def _create_lti1p1_provider(intended_use: str) -> models.LTI1p1Provider:
    with helpers.get_from_request_transaction() as [get, _]:
        lms = get(
            'lms',
            registry.lti_1_1_providers,
            transform=lambda x: x[0],
        )

    return models.LTI1p1Provider(
        lms=lms,
        intended_use=intended_use,
    )


@api.route('/lti1.3/providers/', methods=['POST'])
@api.route('/lti/providers/', methods=['POST'])
@auth.login_required
def create_lti_provider() -> helpers.JSONResponse[models.LTIProviderBase]:
    """Create a new LTI 1.3 provider.

    .. :quickref: LTI; Create a new LTI 1.3 provider.

    This route is part of the public API.

    :<json str iss: The iss of the new provider.
    :<json str lms: The LMS of the new provider, this should be known LMS.
    :<json str indented_use: The intended use of the provider. Like which
        organization will be using the provider, this can be any string.

    :returns: The just created provider.
    """
    with helpers.get_from_request_transaction() as [get, opt_get]:
        lti_version = opt_get('lti_version', str, 'lti1.3')
        intended_use = get('intended_use', str)

    if not intended_use:
        raise exceptions.APIException(
            'The "intended_use" must be non empty',
            f'The intended_use={intended_use} was empty',
            exceptions.APICodes.INVALID_PARAM, 400
        )

    lti_provider: models.LTIProviderBase
    if lti_version == 'lti1.3':
        lti_provider = _create_lti1p3_provider(intended_use)
    elif lti_version == 'lti1.1':
        lti_provider = _create_lti1p1_provider(intended_use)
    else:
        assert False

    auth.LTIProviderPermissions(lti_provider).ensure_may_add()
    db.session.add(lti_provider)
    db.session.commit()

    return jsonify(lti_provider)


@api.route('/lti/providers/<lti_provider_id>', methods=['GET'])
def get_lti_provider(lti_provider_id: str
                     ) -> helpers.JSONResponse[models.LTIProviderBase]:
    """Get a LTI 1.3 provider.

    .. :quickref: LTI; Get a LTI 1.3 provider by id.

    This route is part of the public API.

    :param lti_provider_id: The id of the provider you want to get.

    :returns: The requested LTI 1.3 provider.
    """
    lti_provider: models.LTIProviderBase = helpers.filter_single_or_404(
        # We may only provide concrete classes when a type is expected.
        models.LTIProviderBase,  # type: ignore[misc]
        models.LTIProviderBase.id == lti_provider_id,
    )
    secret = flask.request.args.get('secret')
    auth.LTIProviderPermissions(lti_provider, secret=secret).ensure_may_see()
    return jsonify(lti_provider)


@api.route('/lti1.3/providers/<lti_provider_id>', methods=['GET'])
def get_lti1p3_provider(lti_provider_id: str
                        ) -> helpers.JSONResponse[models.LTI1p3Provider]:
    """Get a LTI 1.3 provider.

    .. :quickref: LTI; Get a LTI 1.3 provider by id.

    This route is part of the public API.

    :param lti_provider_id: The id of the provider you want to get.

    :returns: The requested LTI 1.3 provider.
    """
    lti_provider = helpers.filter_single_or_404(
        models.LTI1p3Provider, models.LTI1p3Provider.id == lti_provider_id
    )
    secret = flask.request.args.get('secret')
    auth.LTIProviderPermissions(lti_provider, secret=secret).ensure_may_see()
    return jsonify(lti_provider)


@api.route('/lti1.1/providers/<lti_provider_id>/finalize', methods=['POST'])
def finalize_lti1p1_provider(lti_provider_id: str
                             ) -> helpers.JSONResponse[models.LTI1p1Provider]:
    """Finalize the given LTI 1.1 provider.

    .. :quickref: LTI; Finalize a LTI 1.1 provider.

    This route is part of the public api.

    :param lti_provider_id: The id of the provider you want to finalize.
    """
    lti_provider = helpers.filter_single_or_404(
        models.LTI1p1Provider,
        models.LTI1p1Provider.id == lti_provider_id,
    )
    secret = flask.request.args.get('secret')
    auth.LTIProviderPermissions(lti_provider, secret=secret).ensure_may_edit()

    lti_provider.finalize()
    db.session.commit()
    return jsonify(lti_provider)


@api.route('/lti1.3/providers/<lti_provider_id>', methods=['PATCH'])
def update_lti1p3_provider(lti_provider_id: str
                           ) -> helpers.JSONResponse[models.LTI1p3Provider]:
    """Update the given LTI 1.3 provider.

    .. :quickref: LTI; Update the information of an LTI 1.3 provider.

    This route is part of the public API.

    :param lti_provider_id: The id of the provider you want to update.

    :<json str client_id: The new client id.
    :<json str auth_token_url: The new authentication token url.
    :<json str auth_login_url: The new authentication login url.
    :<json str key_set_url: The new key set url.
    :<json str auth_audience: The new OAuth2 audience.
    :<json bool finalize: Should this provider be finalized.

    All input JSON is optional, when not provided that attribute will not be
    updated.

    :returns: The updated LTI 1.3 provider.
    """
    lti_provider = helpers.filter_single_or_404(
        models.LTI1p3Provider, models.LTI1p3Provider.id == lti_provider_id
    )
    secret = flask.request.args.get('secret')
    auth.LTIProviderPermissions(lti_provider, secret=secret).ensure_may_edit()

    with helpers.get_from_request_transaction() as [_, opt_get]:
        iss = opt_get('iss', str, None)
        client_id = opt_get('client_id', str, None)
        auth_token_url = opt_get('auth_token_url', str, None)
        auth_login_url = opt_get('auth_login_url', str, None)
        key_set_url = opt_get('key_set_url', str, None)
        auth_audience = opt_get('auth_audience', str, None)
        finalize = opt_get('finalize', bool, None)

    lti_provider.update_registration(
        iss=iss,
        client_id=client_id,
        auth_token_url=auth_token_url,
        auth_login_url=auth_login_url,
        key_set_url=key_set_url,
        auth_audience=auth_audience,
        finalize=finalize,
    )

    db.session.commit()

    return jsonify(lti_provider)


@api.route('/lti1.3/deep_link/<uuid:deep_link_blob_id>', methods=['POST'])
def deep_link_lti_assignment(deep_link_blob_id: uuid.UUID
                             ) -> helpers.JSONResponse[t.Mapping[str, str]]:
    """Create a deeplink response for the given blob.

    :<json name: The name of the new assignment.
    :<json deadline: The deadline of the new assignment, formatted as an
        ISO8601 datetime string.
    :<json auth_token: The authentication token received after the initial LTI
        launch.

    :>json url: The url you should use to post the given ``jwt`` to.
    :>json jwt: The JWT that should be posted to the outputted ``url``.
    """
    blob = helpers.filter_single_or_404(
        models.BlobStorage,
        models.BlobStorage.id == deep_link_blob_id,
        with_for_update=True,
    )
    db.session.delete(blob)
    blob_json = blob.as_json()
    assert isinstance(blob_json, dict)
    assert blob_json['type'] == 'deep_link_settings'

    # We need a bit longer expiration here compared to other uses of the blob
    # storage in this module as users need to have the time to actually input
    # the needed data.
    if blob.age > timedelta(days=1):
        # Really delete the blob in this case too.
        db.session.commit()
        raise errors.APIException(
            'This deep linking session has expired, please reload',
            f'The deep linking session with blob {blob.id} has expired',
            errors.APICodes.OBJECT_EXPIRED, 400
        )

    provider = helpers.get_or_404(
        models.LTI1p3Provider, blob_json['lti_provider_id']
    )

    with helpers.get_from_request_transaction() as [get, _]:
        auth_token = get('auth_token', str)
        name = get('name', str)
        deadline_str = get('deadline', str)

    if auth_token != blob_json['auth_token']:
        raise exceptions.PermissionException(
            'You did not provide the correct token to deep link an assignment',
            f'The provided token {auth_token} is not correct',
            exceptions.APICodes.INCORRECT_PERMISSION, 403
        )

    deadline = parsers.parse_datetime(deadline_str)

    dp_resource = lti_v1_3.CGDeepLinkResource.make(
        lti_provider=provider, deadline=deadline
    ).set_title(name)
    deep_link_settings = t.cast(t.Any, blob_json['deep_link_settings'])
    deep_link = DeepLink(
        lti_v1_3.CGRegistration(provider),
        t.cast(str, blob_json['deployment_id']),
        deep_link_settings,
    )
    db.session.commit()
    return JSONResponse.make(
        {
            'url': deep_link_settings['deep_link_return_url'],
            'jwt': deep_link.get_response_jwt([dp_resource]),
        }
    )
