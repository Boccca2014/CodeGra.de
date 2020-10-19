"""This module defines the tables needed for broker settings.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t
import urllib.parse

import jwt
import requests
from typing_extensions import TypedDict
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from cg_sqlalchemy_helpers.mixins import UUIDMixin, TimestampMixin

from . import Base, db
from .. import helpers, current_app


class BrokerSetting(Base, UUIDMixin, TimestampMixin):
    """The table that stores the settings of this instance.
    """
    _url = db.Column(
        'url', db.Unicode, nullable=False, unique=True, index=True
    )
    _key = db.Column('key', db.LargeBinary, nullable=False)

    @classmethod
    def get_current(cls, commit: bool = True) -> 'BrokerSetting':
        """Get the settings for the current broker.
        """
        url = current_app.config['AUTO_TEST_BROKER_URL']
        return cls._get_or_create(url, commit=commit)

    @classmethod
    def _get_or_create(cls, broker_url: str, commit: bool) -> 'BrokerSetting':
        """Get or create a broker setting.
        """
        res = cls.query.filter(cls._url == broker_url).one_or_none()
        if res is None:
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096,
                backend=default_backend(),
            )
            res = cls(
                _url=broker_url,
                _key=key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            db.session.add(res)
            if commit:
                db.session.commit()
        return res

    @property
    def _private_key(self) -> rsa.RSAPrivateKeyWithSerialization:
        assert self._key is not None

        return serialization.load_pem_private_key(
            self._key, None, default_backend()
        )

    def _get_signed_url(self) -> str:
        return jwt.encode(
            {
                'url': current_app.config['EXTERNAL_URL'],
                'id': str(self.id),
            },
            self._private_key,
            algorithm='RS256'
        ).decode('utf8')

    def get_public_key(self) -> str:
        """Get the public key that is associated with this broker.
        """
        key = self._private_key.public_key()
        return key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode('utf8')

    def get_session(self, retries: t.Optional[int] = None) -> requests.Session:
        """Get a requests session to talk to this broker.
        """
        broker_url = self._url
        signed_url = self._get_signed_url()

        class MySession(requests.Session):
            """The session subclass used to talk to the broker.
            """
            def __init__(self) -> None:
                super().__init__()
                self.headers.update({'CG-Application-Signature': signed_url})
                if retries is not None:
                    helpers.mount_retry_adapter(self, retries=retries)

            def request(  # pylint: disable=signature-differs
                    self,
                    method: str,
                    url: t.Union[str, bytes, t.Text],
                    *args: t.Any,
                    **kwargs: t.Any,
            ) -> requests.Response:
                """Do a request to the AutoTest broker.
                """
                url = urllib.parse.urljoin(broker_url, str(url))
                kwargs.setdefault('timeout', 10)
                return super().request(method, url, *args, **kwargs)

        return MySession()

    class AsJSON(TypedDict):
        """This broker as JSON
        """
        #: The id of the broker
        id: uuid.UUID
        #: The public part of the key used for this broker
        public_key: str

    def __to_json__(self) -> AsJSON:
        return {
            'id': self.id,
            'public_key': self.get_public_key(),
        }
