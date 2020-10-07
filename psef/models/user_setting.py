"""
This module defines all models needed for persisting user settings in the
database.

SPDX-License-Identifier: AGPL-3.0-only
"""
import abc
import enum
import typing as t
import itertools

import structlog
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from typing_extensions import Literal, TypedDict
from sqlalchemy.ext.declarative import declared_attr

import psef
import cg_enum
from cg_sqlalchemy_helpers.types import ColumnProxy
from cg_sqlalchemy_helpers.mixins import IdMixin, TimestampMixin

from . import Base, User, db
from ..auth import (
    APICodes, PermissionException, NotificationPermissions, as_current_user
)
from .notification import (
    NOTIFCATION_REASON_EXPLANATION, Notification, NotificationReasons,
    NotificationReasonEnum
)

logger = structlog.get_logger()

MYPY = False


class SettingBase(TimestampMixin, IdMixin):
    """The base class for representing a new user setting.
    """

    @classmethod
    @abc.abstractmethod
    def get_setting_name(cls) -> str:
        """Get the name of this setting.

        This should be unique per table.
        """
        raise NotImplementedError

    @classmethod
    def _get_salt(cls) -> str:
        return f'setting:{cls.get_setting_name()}'

    @classmethod
    def get_settings_change_token(cls, user: User) -> str:
        """Get a token to change settings on this settings class for the given
            user.

        :param user: The user for which you want to change settings later on.
        :returns: A token that can later be given to
            :meth:`.SettingBase.verify_settings_change_token`.
        """
        return URLSafeTimedSerializer(
            psef.current_app.config['SECRET_KEY'],
            salt=cls._get_salt(),
        ).dumps(user.id)

    @classmethod
    def verify_settings_change_token(cls, token: str) -> User:
        """Verify the given token to change settings for this settings class.

        :returns: The user for which this token can change settings.
        """
        try:
            user_id: int = URLSafeTimedSerializer(
                psef.current_app.config['SECRET_KEY'],
                salt=cls._get_salt(),
            ).loads(
                token,
                max_age=round(psef.current_app.config['SETTING_TOKEN_TIME']),
            )
        except SignatureExpired as exc:
            logger.warning(
                'Expired signature encountered', token=token, exc_info=True
            )
            raise PermissionException(
                (
                    'The given token has expired, this probably means the'
                    ' email from which you clicked on the unsubscribe link was'
                    ' a couple of days old.'
                ), f'The given token {token} is not valid.',
                APICodes.INVALID_CREDENTIALS, 403
            ) from exc
        except BadSignature as exc:
            logger.warning(
                'Invalid setting change token encountered',
                token=token,
                exc_info=True,
            )
            raise PermissionException(
                'The given token is not valid',
                f'The given token {token} is not valid.',
                APICodes.INVALID_CREDENTIALS, 403
            ) from exc

        return psef.helpers.get_or_404(User, user_id)

    if t.TYPE_CHECKING and MYPY:  # pragma: no cover
        user_id: ColumnProxy[int]
        user: ColumnProxy[User]
    else:

        @declared_attr
        def user_id(cls):  # pylint: disable=missing-function-docstring,no-self-argument
            return db.Column(
                'user_id',
                db.Integer,
                db.ForeignKey('User.id', ondelete='CASCADE'),
                nullable=False,
            )

        @declared_attr
        def user(cls):  # pylint: disable=missing-function-docstring,no-self-argument
            return db.relationship(
                User,
                foreign_keys=cls.user_id,
                innerjoin=True,
            )


class EmailNotificationTypes(enum.Enum):
    """The possible options for preferences for sending email notifications.
    """
    direct = 1
    daily = 2
    weekly = 3
    off = 4

    @classmethod
    def ordered_options(cls) -> t.List['EmailNotificationTypes']:
        """Get the options of this enum sorted.
        """
        return sorted(cls.__members__.values())

    def previous_option(self) -> t.Optional['EnabledEmailNotificationTypes']:
        """Get the previous value.

        >>> EmailNotificationTypes.off.previous_option()
        <EmailNotificationTypes.weekly: 3>
        >>> EmailNotificationTypes.weekly.previous_option()
        <EmailNotificationTypes.daily: 2>
        >>> EmailNotificationTypes.daily.previous_option()
        <EmailNotificationTypes.direct: 1>
        >>> EmailNotificationTypes.direct.previous_option() is None
        True
        """
        opts = self.ordered_options()
        idx = opts.index(self)
        if idx > 0:
            return t.cast(EnabledEmailNotificationTypes, opts[idx - 1])
        return None

    def __lt__(self, other: 'EmailNotificationTypes') -> bool:
        return self.value < other.value

    def __to_json__(self) -> str:
        return self.name


EnabledEmailNotificationTypes = Literal[EmailNotificationTypes.  # pylint: disable=invalid-name
                                        direct, EmailNotificationTypes.
                                        daily, EmailNotificationTypes.weekly]


class NotificationSettingOptionJSON(TypedDict):
    """The JSON serialization schema for a single notification setting option.
    """
    reason: NotificationReasons
    explanation: str
    value: EmailNotificationTypes


class NotificationSettingJSON(TypedDict):
    """The JSON serialization schema for :class:`.NotificationsSetting`.
    """
    options: t.List[NotificationSettingOptionJSON]
    possible_values: t.List[EmailNotificationTypes]


class NotificationsSetting(Base, SettingBase):
    """The class representing settings for sending notification emails.
    """

    @staticmethod
    def get_setting_name() -> str:
        return 'notification_settings'

    @classmethod
    def get_notification_setting_json_for_user(
        cls, user: User
    ) -> NotificationSettingJSON:
        """Get the notification settings for the given user as JSON.
        """
        settings = cls._get_default_values()
        settings.update(
            db.session.query(cls.reason, cls.value).filter(cls.user == user)
        )

        return {
            'options':
                [
                    {
                        'reason': reason,
                        'explanation': explanation,
                        'value': settings[reason],
                    } for reason, explanation in
                    sorted(NOTIFCATION_REASON_EXPLANATION.items())
                ],
            'possible_values': sorted(EmailNotificationTypes),
        }

    reason = db.Column(
        'reason',
        NotificationReasonEnum(),
        nullable=False,
    )
    value = db.Column(
        'value',
        db.Enum(EmailNotificationTypes, name='notification_setting_value'),
        nullable=False,
    )

    __table_args__ = (db.UniqueConstraint(
        'user_id',
        reason,
    ), )

    @staticmethod
    def _get_default_values(
    ) -> t.MutableMapping[NotificationReasons, EmailNotificationTypes]:
        return {
            NotificationReasons.author: EmailNotificationTypes.off,
            NotificationReasons.replied: EmailNotificationTypes.direct,
            NotificationReasons.assignee: EmailNotificationTypes.direct,
        }

    @classmethod
    def update_for_user(
        cls,
        user: User,
        reason: NotificationReasons,
        value: EmailNotificationTypes,
    ) -> None:
        """Update the notification type for the given reason for the given
            user.

        :param user: The user for which we should update the setting.
        :param reason: The reason for which we should update the setting.
        :param value: The value the setting should be set to.
        """
        # XXX: It would be useful to use an upsert here, but you cannot use
        # upserts with the orm
        pref = db.session.query(cls).filter(
            cls.user == user, cls.reason == reason
        ).with_for_update().one_or_none()
        if pref is None:
            pref = cls(user=User.resolve(user), reason=reason, value=value)
            db.session.add(pref)
        else:
            pref.value = value

    @classmethod
    def get_should_send_for_users(
        cls, user_ids: t.List[int]
    ) -> t.Callable[[Notification, EnabledEmailNotificationTypes], bool]:
        """Get a function that can be used to check if you should send a given
        notification.

        :param user_ids: A list of user ids, these are the users that later can
            be the receiver of the notification you pass to the returned
            closure.
        :returns: A function that when called with two arguments, the
            notification and the notification type, will return if you should
            send the notification receiver an email.
        """
        given_user_ids = set(user_ids)
        query = db.session.query(cls).filter(
            cls.user_id.in_(user_ids),
        ).order_by(cls.reason)

        lookup = {
            reason: {pref.user_id: pref
                     for pref in prefs}
            for reason, prefs in itertools.groupby(
                query,
                lambda noti: noti.reason,
            )
        }
        default_values = cls._get_default_values()

        def _should_send(
            notification: Notification,
            send_type: EnabledEmailNotificationTypes,
        ) -> bool:
            previous_val = send_type.previous_option()
            if (
                previous_val is not None and
                _should_send(notification, previous_val)
            ):
                logger.info('More specific preference known')
                return False

            default_return = False
            for reason in notification.reasons:
                pref = lookup.get(reason, {}).get(notification.receiver_id)
                if pref is None:
                    default_return |= default_values[reason] == send_type
                elif pref.value == send_type:
                    return True

            return default_return

        def should_send(
            notification: Notification,
            send_type: EnabledEmailNotificationTypes,
        ) -> bool:
            assert notification.receiver_id in given_user_ids, (
                "You didn't specify this user in the original call"
            )
            with as_current_user(notification.receiver):
                if notification.deleted:
                    logger.info('Notification is deleted')
                    return False
                elif not NotificationPermissions(notification
                                                 ).ensure_may_see.as_bool():
                    logger.info('No permission to see the notification')
                    return False

            return _should_send(notification, send_type)

        return should_send


class UIPreferenceName(cg_enum.CGEnum):
    rubric_editor_v2 = enum.auto()


class UIPreference(Base, SettingBase):
    """The class representing user preferences..
    """

    @staticmethod
    def get_setting_name() -> str:
        return 'ui_preferences'

    name = db.Column(
        'name',
        db.Enum(UIPreferenceName, name='ui_preference_name'),
        nullable=False,
    )

    value = db.Column('value', db.Boolean, nullable=False)

    __table_args__ = (db.UniqueConstraint(
        'user_id',
        name,
    ), )

    @classmethod
    def get_preferences_for_user(
        cls,
        user: User,
    ) -> t.Mapping[UIPreferenceName, t.Optional[bool]]:
        """Get the ui preference mapping for a user.

        :param user: User to get the preferences of.
        :returns: Mapping of preference name to value. The value is None if the
            user hasn't set a value yet, or a boolean to indicate their choice.
        """
        prefs: t.MutableMapping[UIPreferenceName, t.Optional[bool]]
        prefs = {p: None for p in UIPreferenceName}
        prefs.update(
            db.session.query(cls.name, cls.value).filter(cls.user == user)
        )
        return prefs

    @classmethod
    def update_for_user(
        cls,
        user: User,
        name: UIPreferenceName,
        value: bool,
    ) -> None:
        """Update the given ui preference for the given user.

        :param user: The user for which we should update the setting.
        :param name: The name of the setting that should be updated.
        :param value: The value the setting should be set to.
        """
        pref = db.session.query(cls).filter(
            cls.user == user, cls.name == name
        ).with_for_update().one_or_none()
        if pref is None:
            pref = cls(user=User.resolve(user), name=name, value=value)
            db.session.add(pref)
        else:
            pref.value = value
