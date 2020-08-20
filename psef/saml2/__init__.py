"""This module implements the Service Provider (SP) side of SAML2 for
CodeGrade.

The routes here are not suitable to be used outside of browser environments,
and can only be used in the correct order and while cookies are enabled. The
correct order is first doing a ``GET`` ``/login/<provider_id>`` route,
following all redirects, logging in using the IdP, following all redirects and
then use the ``/jwts/<token>`` route to retrieve your jwt token.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t
import xml.etree.ElementTree as ET
from datetime import timedelta

import furl
import flask
import structlog
import flask_jwt_extended as flask_jwt
from flask import request, session
from typing_extensions import Final, Literal, TypedDict
from werkzeug.wrappers import Response
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from defusedxml.ElementTree import fromstring as defused_xml_fromstring
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.constants import OneLogin_Saml2_Constants

import cg_json
from cg_helpers import maybe_wrap_in_list

from .. import PsefFlask, models, helpers, exceptions, current_app
from ..models import db
from ..helpers import readable_join

logger = structlog.get_logger()

MDUI_NAMESPACE: Final = 'urn:oasis:names:tc:SAML:metadata:ui'
_SAML_SESSION_PREFIX = '[SAML]'
_MAX_BLOB_AGE = timedelta(minutes=5)

saml = flask.Blueprint(
    name='saml',
    import_name=__name__,
)  # pylint: disable=invalid-name


def _session_key(key: str) -> str:
    return f'{_SAML_SESSION_PREFIX}_{key}'


def _make_saml_url() -> furl.furl:
    return furl.furl(current_app.config['EXTERNAL_URL']).add(
        path=['api', 'sso', 'saml2'],
    )


def _clear_session() -> None:
    for key in list(session.keys()):
        if key.startswith(_SAML_SESSION_PREFIX):
            del session[key]


def _make_error(
    title: str,
    message: str,
    auth: t.Optional[OneLogin_Saml2_Auth] = None,
) -> t.Tuple[str, int]:
    """Render the error template with the given data.

    This also logs the error to sentry.
    """
    logger.error(
        'SAML request went wrong',
        error_message=message,
        error_title=title,
        error_reason=auth and auth.get_last_error_reason(),
        report_to_sentry=True,
    )
    _clear_session()
    return (
        flask.render_template(
            'error_page.j2', error_title=title, error_message=message
        ),
        400,
    )


class SamlRequest(TypedDict, total=True):
    """The data shape the OneLogin library expects for a request.
    """
    https: Literal['on', 'off']
    http_host: str
    server_port: int
    script_name: str
    get_data: t.Mapping[str, t.Any]
    post_data: t.Mapping[str, t.Any]


class _AttributeNames:
    EMAIL: Final = 'urn:oid:0.9.2342.19200300.100.1.3'
    FULL_NAME: Final = 'urn:oid:2.5.4.3'
    DISPLAY_NAME: Final = 'urn:oid:2.16.840.1.113730.3.1.241'
    UID: Final = 'urn:oid:0.9.2342.19200300.100.1.1'


def _init_saml_auth(
    req: SamlRequest, provider: models.Saml2Provider
) -> OneLogin_Saml2_Auth:
    """Create a OneLogin Saml2 Auth object for the current request in the given
    provider.

    :param req: The request for which you want to create an auth object.
    :param provider: The provider in which this request was done.
    """
    bindings = 'urn:oasis:names:tc:SAML:2.0:bindings'
    entityId = _make_saml_url().add(path=['metadata', provider.id]).tostr()
    acs_url = _make_saml_url().add(path=['acs', provider.id]).tostr()
    strict = not current_app.config['DEBUG'] or current_app.config['TESTING']

    # yapf: disable
    settings = OneLogin_Saml2_Settings(
        settings={
            'strict': strict,
            'debug': current_app.config['DEBUG'],
            'security': {
                'authnRequestsSigned': True,
                'WantAssertionsSigned': True,
                'signMetadata': True,
                'metadataCacheDuration': timedelta(days=1).total_seconds(),
                'signatureAlgorithm': OneLogin_Saml2_Constants.RSA_SHA512,
                'digestAlgorithm': OneLogin_Saml2_Constants.SHA512,
            },
            'sp': {
                'entityId': entityId,
                'assertionConsumerService': {
                    'url': acs_url,
                    'binding': f'{bindings}:HTTP-POST',
                },
                'NameIDFormat': OneLogin_Saml2_Constants.NAMEID_PERSISTENT,
                'x509cert': provider.public_x509_cert,
                'privateKey': provider.private_key,
            },
            'idp': provider.provider_metadata,
            'contactPerson': {
                'support': {
                    'givenName': 'CodeGrade Support',
                    'emailAddress': 'support@codegrade.com',
                },
            },
            'organization': {
                'en-US': {
                    'name': 'CodeGrade',
                    'displayname': 'CodeGrade',
                    'url': current_app.config['EXTERNAL_URL'],
                },
            },
        },
    )
    # yapf: enable
    return OneLogin_Saml2_Auth(req, old_settings=settings)


def _prepare_flask_request() -> SamlRequest:
    """Convert the current (flask) request to a request object as expected by
    the OneLogin classes.
    """
    url_data = furl.furl(request.url)

    https: Literal['on', 'off'] = (
        'on' if not current_app.config['DEBUG'] or request.scheme == 'https'
        else 'off'
    )
    return {
        'https': https,
        'http_host': request.host,
        'server_port': url_data.port,
        'script_name': request.path,
        'get_data': request.args.copy(),
        # Uncomment if using ADFS as IdP, https://github.com/onelogin/python-saml/pull/144
        # 'lowercase_urlencoding': True,
        'post_data': request.form.copy(),
    }


@saml.route('/login/<uuid:provider_id>', methods=['GET'])
def do_saml_login(provider_id: uuid.UUID) -> Response:
    """Begin the SAML2 login procedure.

    :param provider_id: The id of the provider that should do the login.
    :returns: A redirection to your IdP.
    """
    provider = helpers.get_or_404(models.Saml2Provider, provider_id)
    req = _prepare_flask_request()
    auth = _init_saml_auth(req, provider)

    token = str(uuid.uuid4())
    session[_session_key('TOKEN')] = token
    return_to = furl.furl(current_app.config['EXTERNAL_URL']).add(
        path=['sso_login', token],
        args=req['get_data'],
    ).tostr()

    sso_built_url = auth.login(return_to)
    session[_session_key('AuthNRequestID')] = auth.get_last_request_id()
    return flask.redirect(sso_built_url)


@saml.route('/acs/<uuid:provider_id>', methods=['POST'])
def get_acs(provider_id: uuid.UUID) -> t.Union[t.Tuple[str, int], Response]:
    """This route is the Assertion Consumer Service (ACS) route of CodeGrade.

    The form posted to this route should contain a valid SAML ACS request for
    the given provider.

    :param provider_id: The provider that is providing the assertions.

    :returns: A redirection to the ``RelayState`` or an html page containing an
              error message.
    """
    req = _prepare_flask_request()
    provider = helpers.get_or_404(models.Saml2Provider, provider_id)
    auth = _init_saml_auth(req, provider)

    request_id = session.pop(_session_key('AuthNRequestID'), str(uuid.uuid4()))
    auth.process_response(request_id=request_id)
    errors = auth.get_errors()

    if errors or not auth.is_authenticated():
        error_title = (
            'Something went wrong during login.'
            if auth.is_authenticated() else 'Logging in was unsuccessful.'
        )

        error_message = error_title
        if current_app.config['DEBUG']:
            error_message = readable_join(
                [str(err) for err in errors]
            ) or error_title

        return _make_error(
            flask.escape(error_title),
            flask.escape(error_message),
            auth=auth,
        )

    relay_state = req['post_data'].get('RelayState')
    if relay_state is None:
        return _make_error(
            'No redirection target found',
            (
                'The login request did not contain a redirection target.'
                ' Please note that CodeGrade does not support unsolicited'
                ' login request'
            ),
        )

    redirect_target = auth.redirect_to(relay_state)
    if not redirect_target.startswith(current_app.config['EXTERNAL_URL']):
        return _make_error(
            'Wrong redirection target found', (
                'Only redirection within this domain ({}), found redirection'
                ' to {}.'
            ).format(
                flask.escape(current_app.config['EXTERNAL_URL']),
                flask.escape(redirect_target),
            )
        )

    if auth.get_nameid_format() != OneLogin_Saml2_Constants.NAMEID_PERSISTENT:
        return _make_error(
            'Incorrect nameId type',
            flask.escape(
                (
                    'Got a wrong type of name id, so we cannot log you in.'
                    ' (Got: {})'
                ).format(auth.get_nameid_format()),
            ),
            auth=auth,
        )

    attributes = auth.get_attributes()
    name_id = auth.get_nameid()
    username = attributes.get(_AttributeNames.UID)
    email = attributes.get(_AttributeNames.EMAIL)
    full_name = attributes.get(
        _AttributeNames.FULL_NAME,
        attributes.get(_AttributeNames.DISPLAY_NAME)
    )

    if not (username and email and full_name):
        missing_data = [
            name for name, value in [
                ('username', username),
                ('email', email),
                ('name', full_name),
            ] if not value
        ]
        return _make_error(
            'Not all required data found',
            'The following data is missing: {}'.format(
                readable_join(missing_data)
            ),
        )

    user = models.UserSamlProvider.get_or_create_user(
        name_id=name_id,
        saml2_provider=provider,
        username=maybe_wrap_in_list(username)[0],
        email=maybe_wrap_in_list(email)[0],
        full_name=maybe_wrap_in_list(full_name)[0],
    )

    blob = models.BlobStorage(
        json={
            'provider_id': str(provider_id),
            'user_id': user.id,
            'token': session.get(_session_key('TOKEN'), str(uuid.uuid4())),
        },
    )
    db.session.add(blob)

    db.session.commit()
    session[_session_key('DB_BLOB_ID')] = str(blob.id)

    return flask.redirect(redirect_target)


@saml.route('/jwts/<uuid:token>', methods=['POST'])
def get_jwt_from_success_full_login(
    token: uuid.UUID
) -> cg_json.JSONResponse[t.Dict[str, str]]:
    """Get a JWT token for a user after doing a successful launch.

    :param token: The token that we will use to verify that you are the correct
        owner of the SAML launch. This data will be cross referenced to stored
        data and your session.

    This method will use various pieces of information from the session from
    the requested user.

    This method can only be used once to retrieve the JWT, as the data will be
    removed after the first request.

    :returns: A mapping containing one key (``access_token``).
    """
    if not all(_session_key(k) in session for k in ['DB_BLOB_ID', 'TOKEN']):
        _clear_session()
        raise exceptions.APIException(
            'Could not find all required data in the session', (
                'This route will only work if data set in earlier phases of'
                ' the SAML login is present in the session, this was not the'
                ' case.'
            ), exceptions.APICodes.INVALID_STATE, 409
        )
    blob_id = uuid.UUID(session[_session_key('DB_BLOB_ID')])
    session_token = session[_session_key('TOKEN')]
    _clear_session()

    blob = helpers.filter_single_or_404(
        models.BlobStorage,
        models.BlobStorage.id == blob_id,
        with_for_update=True,
        also_error=lambda blob: blob.age > _MAX_BLOB_AGE,
    )
    blob_json = blob.as_json()
    assert isinstance(blob_json, dict)
    found_token = blob_json.get('token')

    if str(token) != found_token or session_token != found_token:
        raise exceptions.APIException(
            'Invalid token provided',
            'The given token does not match your session and/or the found jwt',
            exceptions.APICodes.INVALID_URL, 400
        )

    user = helpers.get_or_404(models.User, blob_json['user_id'])
    db.session.delete(blob)
    db.session.commit()

    return cg_json.JSONResponse.make(
        {
            'access_token':
                flask_jwt.create_access_token(
                    identity=user.id,
                    fresh=True,
                    expires_delta=timedelta(days=1),
                )
        }
    )


@saml.route('/metadata/<uuid:provider_id>', methods=['GET'])
def get_metadata(provider_id: uuid.UUID
                 ) -> t.Union[t.Tuple[str, int], Response]:
    """Get the metadata xml for SP connected to the given provider.

    While this URL should always return a valid XML it might be IP restricted,
    and is not part of the public API.

    :param provider_id: The id of the provider for which you want to generate
        the XML.

    :returns: The generated XML or an error page.
    """
    req = _prepare_flask_request()
    auth = _init_saml_auth(
        req, helpers.get_or_404(models.Saml2Provider, provider_id)
    )
    settings = auth.get_settings()
    metadata = settings.get_sp_metadata()

    tree: ET.Element = defused_xml_fromstring(metadata)
    NSMAP = {
        **OneLogin_Saml2_Constants.NSMAP,
        'mdui': MDUI_NAMESPACE,
    }

    def make_tag(ns: str, tagname: str) -> str:
        return '{{{}}}{}'.format(NSMAP.get(ns), tagname)

    desc = tree.find('.//md:SPSSODescriptor', NSMAP)
    assert desc is not None
    ext = desc.find('./md:Extensions'.format(), NSMAP)
    if ext is None:
        ext = desc.makeelement(make_tag('md', 'Extensions'), {})
        desc.insert(0, ext)

    uiinfo = ext.makeelement(make_tag('mdui', 'UIInfo'), {})

    for lang in ['en', *current_app.config['SSO_METADATA_EXTRA_LANGUAGES']]:
        display_name = uiinfo.makeelement(
            make_tag('mdui', 'DisplayName'), {'xml:lang': lang}
        )
        display_name.text = 'CodeGrade'
        uiinfo.append(display_name)

        description = uiinfo.makeelement(
            make_tag('mdui', 'Description'), {'xml:lang': lang}
        )
        description.text = 'Deliver engaging feedback on code.'
        uiinfo.append(description)

        info_url = uiinfo.makeelement(
            make_tag('mdui', 'InformationURL'), {'xml:lang': lang}
        )
        info_url.text = current_app.config['EXTERNAL_URL']
        uiinfo.append(info_url)

    logo = uiinfo.makeelement(
        make_tag('mdui', 'Logo'), {
            'height': '249',
            'width': '1263'
        }
    )
    logo.text = furl.furl(current_app.config['EXTERNAL_URL']
                          ).add(path='static/img/codegrade-inv.png').tostr()
    uiinfo.append(logo)

    ext.append(uiinfo)

    metadata = ET.tostring(tree)
    errors = settings.validate_metadata(metadata)

    if errors:  # pragma: no cover
        return _make_error(
            'Error generating metadata',
            flask.escape(readable_join([str(err) for err in errors])),
        )
    else:
        resp = flask.make_response(metadata, 200)
        resp.headers['Content-Type'] = 'text/xml'
        return resp


def init_app(app: PsefFlask) -> None:
    app.register_blueprint(saml, url_prefix='/api/sso/saml2/')
