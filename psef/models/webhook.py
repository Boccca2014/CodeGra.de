"""This module defines all webhook related tables.

SPDX-License-Identifier: AGPL-3.0-only
"""
import hmac
import json
import typing as t
import secrets
import tempfile
import contextlib
import dataclasses

import flask
import structlog
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import psef
from cg_dt_utils import DatetimeWithTimezone
from cg_sqlalchemy_helpers.mixins import UUIDMixin, TimestampMixin

from . import Base, User, db
from . import assignment as assignment_models
from .. import auth, exceptions
from ..registry import webhook_handlers
from ..exceptions import APICodes, APIException

T = t.TypeVar('T', bound=t.Type['WebhookBase'])

_ALL_WEBHOOK_TYPES = sorted(['git'])
webhook_handlers.set_possible_options(_ALL_WEBHOOK_TYPES)
logger = structlog.get_logger()


class WebhookBase(Base, UUIDMixin, TimestampMixin):
    """This table represents a webhook.

    At the moment only webhook (GitHub + GitLab) are supported.
    """
    secret = db.Column(
        'secret',
        db.Unicode,
        nullable=False,
        default=secrets.token_hex,
    )
    assignment_id = db.Column(
        'assignment_id',
        db.Integer,
        db.ForeignKey('assignment_models.Assignment.id'),
        nullable=False,
    )
    user_id = db.Column(
        'user_id',
        db.Integer,
        db.ForeignKey('User.id'),
        nullable=False,
    )

    assignment = db.relationship(
        lambda: assignment_models.Assignment,
        foreign_keys=assignment_id,
        lazy='joined',
        innerjoin=True,
    )

    user = db.relationship(
        User,
        foreign_keys=user_id,
        lazy='joined',
        innerjoin=True,
    )

    webhook_type = db.Column(
        'webhook_type',
        db.Enum(*_ALL_WEBHOOK_TYPES, name='webhooktype'),
        nullable=False
    )

    _ssh_key = db.Column('ssh_key', db.LargeBinary, nullable=False)
    _ssh_username = db.Column('ssh_username', db.Unicode, nullable=False)

    __mapper_args__ = {
        'polymorphic_on': webhook_type,
        'polymorphic_identity': 'non_existing'
    }

    __table_args__ = (
        db.UniqueConstraint(
            'assignment_id',
            'user_id',
            'webhook_type',
            name='_webhook_assig_user_type_uc'
        ),
    )

    def __init__(self, assignment_id: int, user_id: int) -> None:
        super().__init__()
        self.assignment_id = assignment_id
        self.user_id = user_id
        self._ssh_username = psef.app.config['SITE_EMAIL']

        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend(),
        )
        self._ssh_key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

    @property
    def _ssh_private_key(self) -> rsa.RSAPrivateKeyWithSerialization:
        assert self._ssh_key is not None
        return serialization.load_pem_private_key(
            self._ssh_key, None, default_backend()
        )

    @property
    def ssh_username(self) -> t.Optional[str]:
        """Get the ssh username of this webhook.
        """
        return self._ssh_username

    def get_ssh_public_key(self) -> str:
        """Get the public key that is associated with this webhook.
        """
        key = self._ssh_private_key.public_key()
        return '{public} {host}'.format(
            public=key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH,
            ).decode('utf8'),
            host=self.ssh_username,
        )

    @contextlib.contextmanager
    def written_private_key(self) -> t.Generator[str, None, None]:
        """Get the private key written to a file.

        :yields: This context manager yields the name of the temporary file
            where the private key is written to.
        """
        key = self._ssh_private_key

        with tempfile.NamedTemporaryFile() as tmpfile:
            tmpfile.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            tmpfile.flush()
            tmpfile.seek(0, 0)
            yield tmpfile.name

    def handle_request(self, request: flask.Request) -> None:
        raise NotImplementedError

    def __to_json__(self) -> t.Dict[str, object]:
        assert self.id is not None

        return {
            'id': str(self.id),
            'public_key': self.get_ssh_public_key(),
            'assignment_id': self.assignment_id,
            'user_id': self.user_id,
            'secret': self.secret,
            'default_branch': 'master',
        }


@dataclasses.dataclass
class _PartialGitCloneData:
    type: str
    url: str
    commit: str
    ref: str
    sender_username: str
    sender_name: str
    webhook_id: str
    clone_url: str
    repository_name: str
    event: str


@dataclasses.dataclass
class GitCloneData(_PartialGitCloneData):
    """

    .. warning::

        This data is also used in the front-end, so be careful what fields you
        add (or prefix them with ``private_``), and make sure you don't change
        the keys without considering backwards compatibility.
    """
    branch: str

    @classmethod
    def from_partial(
        cls, partial: _PartialGitCloneData, branch: str
    ) -> 'GitCloneData':
        """Create a ``GitCloneData`` object from a partial clone data and a
            branch.
        """
        data_dict = dataclasses.asdict(partial)
        data_dict['branch'] = branch
        return cls(**data_dict)

    def get_extra_info(self) -> t.Dict[str, str]:
        """Convert this clone data to the ``extra_data`` of a work by stripping
            all private information.
        """
        return {
            key: value
            for key, value in dataclasses.asdict(self).items()
            if not key.startswith('private_')
        }


@webhook_handlers.register_table
class _GitWebhook(WebhookBase):
    __mapper_args__ = {'polymorphic_identity': 'git'}

    def handle_request(self, request: flask.Request) -> None:
        """Handle a request for this webhook.

        :param request: The request done to this webhook.
        :returns: Nothing.
        """
        if 'X-Hub-Signature' in request.headers:
            self._handle_github_request(request)
        elif 'X-Gitlab-Token' in request.headers:
            self._handle_gitlab_request(request)
        else:
            raise APIException(
                'Unknown git webhook type',
                "The webhook didn't contain a gitlab or github event header",
                APICodes.WEBHOOK_UNKNOWN_REQUEST, 400
            )

    def _is_valid_github_request(self, request: flask.Request) -> bool:
        header_signature = request.headers['X-Hub-Signature']

        sig_type, signature = header_signature.split('=', 1)
        if sig_type != 'sha1':
            logger.error(
                'Got a unknown signature type from GitHub',
                signature_type=signature
            )
            return False

        assert self.secret
        mac = hmac.new(
            key=self.secret.encode(),
            msg=request.get_data(),
            digestmod=sig_type,
        )
        if hmac.compare_digest(mac.hexdigest(), signature):
            return True

        logger.info('Got wrong signature', received_signature=signature)
        return False

    def _handle_github_request(self, request: flask.Request) -> None:
        if not self._is_valid_github_request(request):
            raise APIException(
                'Got invalid github request',
                f'The webhook request on webhook {self.id} was not valid',
                APICodes.WEBHOOK_INVALID_REQUEST, 400
            )

        if request.is_json:
            data = request.get_json()
        else:
            data = json.loads(request.form['payload'])

        repo = data.get('repository', {})
        self._handle_request(
            request,
            event=request.headers.get('X-GitHub-Event', 'unknown'),
            get_data=lambda: _PartialGitCloneData(
                type='github',
                url=repo['html_url'],
                commit=data['after'],
                repository_name=repo['full_name'],
                ref=data['ref'],
                sender_username=data['sender']['login'],
                sender_name=data['sender']['login'],
                webhook_id=str(self.id),
                clone_url=repo['ssh_url'],
                event=request.headers['X-GitHub-Event'],
            ),
        )

    def _handle_gitlab_request(self, request: flask.Request) -> None:
        got_token: str = request.headers.get('X-Gitlab-Token', '')
        assert self.secret
        if not hmac.compare_digest(self.secret, got_token):
            raise APIException(
                'Got invalid gitlab request',
                f'The webhook request on webhook {self.id} was not valid',
                APICodes.WEBHOOK_INVALID_REQUEST, 400
            )

        data = request.get_json()
        project = data.get('project', {})

        self._handle_request(
            request,
            event=data['object_kind'],
            get_data=lambda: _PartialGitCloneData(
                type='gitlab',
                url=data['repository']['homepage'],
                commit=data['checkout_sha'],
                repository_name='{namespace} / {name}'.format(**project),
                ref=data['ref'],
                sender_username=data['user_username'],
                sender_name=data['user_name'],
                webhook_id=str(self.id),
                clone_url=project['git_ssh_url'],
                event=data['object_kind'],
            ),
        )

    def _handle_request(
        self,
        request: flask.Request,
        event: str,
        get_data: t.Callable[[], _PartialGitCloneData],
    ) -> None:
        if self.user.group:
            users = self.user.group.members
        else:
            users = [self.user]

        exc = Exception()

        for user in users:
            # If one user of the group can hand-in submissions we continue,
            # otherwise we raise the last exception.
            try:
                with auth.as_current_user(user):
                    auth.ensure_can_submit_work(
                        self.assignment,
                        author=self.user,
                        for_user=user,
                    )
            except exceptions.PermissionException as e:
                logger.info('User cannot submit work', exc_info=True)
                exc = e
            else:
                break
        else:
            logger.info('No user can submit work')
            raise exc

        group_set = self.assignment.group_set
        if (
            self.user.group is None and group_set is not None and
            group_set.get_valid_group_for_user(self.user)
        ):
            raise APIException(
                'This webhook is disabled as the owner is part of a group', (
                    f'The user {self.user.id} is in a group so existing'
                    ' webhooks are disabled.'
                ), APICodes.WEBHOOK_DISABLED, 400
            )

        if event != 'push':
            logger.info('Got non push event', event_type=event)
            raise APIException(
                'Got wrong webhook event type',
                f'The webhook event {event} is not supported',
                APICodes.WEBHOOK_UNKNOWN_EVENT_TYPE, 400
            )

        target_branches = request.args.getlist('branch', str) or ['master']
        data = get_data()
        current_branch = None

        for branch in target_branches:
            if data.ref == f'refs/heads/{branch}':
                current_branch = branch
                break

        if current_branch is None:
            raise APIException(
                'Got a push to a different branch',
                f'Push was to {data.ref}, which is not monitored',
                APICodes.WEBHOOK_DIFFERENT_BRANCH, 400
            )

        psef.tasks.clone_commit_as_submission(
            unix_timestamp=DatetimeWithTimezone.utcnow().timestamp(),
            clone_data_as_dict=dataclasses.asdict(
                GitCloneData.from_partial(data, branch=current_branch)
            ),
        )


webhook_handlers.freeze()
