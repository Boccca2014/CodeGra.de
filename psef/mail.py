"""
This module is used for all mailing related tasks.

SPDX-License-Identifier: AGPL-3.0-only
"""
import html
import typing as t

import html2text
import structlog
from flask import current_app
from flask_mail import Mail, Message
from typing_extensions import Literal

import psef
import psef.models as models
from psef.errors import APICodes, APIException

from . import auth
from .helpers import readable_join

mail = Mail()  # pylint: disable=invalid-name
logger = structlog.get_logger()


def _send_mail(
    html_body: str,
    subject: str,
    recipients: t.Optional[t.Sequence[t.Union[str, t.Tuple[str, str]]]],
    mailer: t.Optional[Mail] = None,
    *,
    message_id: str = None,
    in_reply_to: str = None,
    references: t.List[str] = None,
) -> None:
    text_maker = html2text.HTML2Text(bodywidth=78)
    text_maker.inline_links = False
    text_maker.wrap_links = False
    text_maker.ignore_tables = True
    text_maker.wrap_links = False

    def _handle_tag(
        converter: html2text.HTML2Text, tag: str, _attrs: dict, start: bool
    ) -> bool:
        if start and tag in ('tr', 'th'):
            converter.out('\n')
        return False

    text_maker.tag_callback = _handle_tag  # type: ignore[assignment]

    text_body = text_maker.handle(html_body)

    logger.info(
        'Sending email',
        subject=subject,
        html_body=html_body[:200],
        text_body=text_body,
        recipients=recipients,
    )
    if recipients:
        if mailer is None:
            mailer = mail

        extra_headers = {}

        if in_reply_to is not None:
            extra_headers['In-Reply-To'] = in_reply_to
        if references:
            extra_headers['References'] = ' '.join(references)

        message = Message(
            subject=subject,
            body=text_body,
            html=html_body,
            recipients=recipients,
            extra_headers=extra_headers,
        )
        if message_id is not None:
            message.msgId = message_id

        mailer.send(message)


def send_whopie_done_email(assig: models.Assignment) -> None:
    """Send whoepie done email for the given assignment.

    :param assig: The assignment to send the mail for.
    :returns: Nothing
    """
    html_body = current_app.config['DONE_TEMPLATE'].replace(
        '\n\n',
        '<br><br>',
    ).format(
        site_url=current_app.config['EXTERNAL_URL'],
        assig_id=assig.id,
        assig_name=html.escape(assig.name),
        course_id=assig.course_id,
    )

    recipients = psef.parsers.parse_email_list(assig.done_email)
    _send_mail(
        html_body,
        (
            f'Grading has finished for {assig.name} on '
            f'{current_app.config["EXTERNAL_URL"]}'
        ),
        recipients,
    )


def send_grader_status_changed_mail(
    assig: models.Assignment, user: models.User
) -> None:
    """Send grader status changed mail.

    :param assig: The assignment of which the status has changed.
    :param user: The user whose status has changed.
    :returns: Nothing
    """
    html_body = current_app.config['GRADER_STATUS_TEMPLATE'].replace(
        '\n\n', '<br><br>'
    ).format(
        site_url=current_app.config['EXTERNAL_URL'],
        assig_id=assig.id,
        user_name=html.escape(user.name),
        user_email=html.escape(user.email),
        assig_name=html.escape(assig.name),
        course_id=assig.course_id,
    )

    _send_mail(
        html_body,
        (
            f'Grade status toggled for {assig.name} on '
            f'{current_app.config["EXTERNAL_URL"]}'
        ),
        [user.email],
    )


def send_grade_reminder_email(
    assig: models.Assignment,
    user: models.User,
    mailer: Mail,
) -> None:
    """Remind a user to grade a given assignment.

    :param assig: The assignment that has to be graded.
    :param user: The user that should resume/start grading.
    :mailer: The mailer used to mail, this is important for performance.
    :returns: Nothing
    """
    html_body = current_app.config['REMINDER_TEMPLATE'].replace(
        '\n\n', '<br><br>'
    ).format(
        site_url=current_app.config['EXTERNAL_URL'],
        assig_id=assig.id,
        user_name=html.escape(user.name),
        user_email=html.escape(user.email),
        assig_name=html.escape(assig.name),
        course_id=assig.course_id,
    )
    _send_mail(
        html_body,
        (
            f'Grade reminder for {assig.name} on '
            f'{current_app.config["EXTERNAL_URL"]}'
        ),
        [user.email],
        mailer,
    )


def send_reset_password_email(user: models.User) -> None:
    """Send the reset password email to a user.

    :param user: The user that has requested a reset password email.
    :returns: Nothing
    """
    token = user.get_reset_token()
    html_body = current_app.config['EMAIL_TEMPLATE'].replace(
        '\n\n', '<br><br>'
    ).format(
        site_url=current_app.config["EXTERNAL_URL"],
        url=(
            f'{current_app.config["EXTERNAL_URL"]}/reset_'
            f'password/?user={user.id}&token={token}'
        ),
        user_id=user.id,
        token=token,
        user_name=html.escape(user.name),
        user_email=html.escape(user.email),
    )
    try:
        _send_mail(
            html_body, f'Reset password on {psef.app.config["EXTERNAL_URL"]}',
            [user.email]
        )
    except Exception:
        logger.bind(exc_info=True)
        raise APIException(
            'Something went wrong sending the email, '
            'please contact your site admin',
            f'Sending email to {user.id} went wrong.',
            APICodes.UNKOWN_ERROR,
            500,
        )


def send_digest_notification_email(
    notifications: t.List[models.Notification],
    send_type: Literal[models.EmailNotificationTypes.daily, models.
                       EmailNotificationTypes.weekly],
) -> None:
    """Send digest email for the given notifications.

    :param notifictions: The notifications to send the digest email for. All
        notifications should have the same receiver and the list should not be
        empty.
    :param send_type: What kind of digest email is this.
    """
    assert notifications
    receiver = notifications[0].receiver
    assert all(n.receiver == receiver for n in notifications)

    settings_token = models.NotificationsSetting.get_settings_change_token(
        receiver
    )

    reasons = readable_join(
        sorted(
            set(
                expl for n in notifications
                for _, expl in n.reasons_with_explanation
            )
        )
    )
    with auth.as_current_user(receiver):
        subject = current_app.jinja_mail_env.from_string(
            current_app.config['DIGEST_NOTIFICATION_SUBJECT']
        ).render(
            site_url=current_app.config["EXTERNAL_URL"],
            notifications=notifications,
            send_type=send_type,
        )

        html_body = current_app.jinja_mail_env.get_template(
            'digest.j2'
        ).render(
            site_url=current_app.config["EXTERNAL_URL"],
            notifications=notifications,
            subject=subject,
            send_type=send_type,
            receiver=receiver,
            reasons=reasons,
            settings_token=settings_token,
        )

    _send_mail(
        html_body,
        subject,
        [(receiver.name, receiver.email)],
    )


def send_direct_notification_email(notification: models.Notification) -> None:
    """Send a direct notification email for the given notification.

    :param notification: The notification for which we should send an e-mail.
    """
    comment = notification.comment_reply

    references = [r.message_id for r in comment.references]
    first_reply = comment.comment_base.first_reply
    in_reply_to_message_id = None

    if first_reply is not None and first_reply.id != comment.id:
        in_reply_to_message_id = first_reply.message_id
        references.append(in_reply_to_message_id)
    references.reverse()

    settings_token = models.NotificationsSetting.get_settings_change_token(
        notification.receiver
    )

    with auth.as_current_user(notification.receiver):
        subject = current_app.jinja_mail_env.from_string(
            current_app.config['DIRECT_NOTIFICATION_SUBJECT']
        ).render(
            site_url=current_app.config["EXTERNAL_URL"],
            notification=notification,
            settings_token=settings_token,
        )

        html_body = current_app.jinja_mail_env.get_template(
            'notification.j2'
        ).render(
            site_url=current_app.config["EXTERNAL_URL"],
            notification=notification,
            subject=subject,
            settings_token=settings_token,
            reasons=readable_join(
                [expl for _, expl in notification.reasons_with_explanation]
            ),
        )

    _send_mail(
        html_body,
        subject,
        [(notification.receiver.name, notification.receiver.email)],
        message_id=comment.message_id,
        in_reply_to=in_reply_to_message_id,
        references=references,
    )


def send_student_mail(
    mailer: Mail,
    sender: models.User,
    receiver: models.User,
    subject: str,
    text_body: str,
) -> None:
    """Send the given student an email as the given sender.

    This sends an email to ``receiver`` and sets the ``Reply-To`` header of the
    mail to the given ``sender``.

    :param mailer: The mailer with which you want to send the email.
    :param sender: The user which should be placed in the ``Reply-To`` header.
    :param receiver: The user to which we should send the email.
    :param subject: The subject of the email.
    :param text_body: The plain text body of the email to send.
    :returns: Nothing.
    """
    logger.info(
        'Sending email to student',
        subject=subject,
        text_body=text_body,
        recipient=sender,
    )

    message = Message(
        sender=(sender.name, current_app.config['MAIL_DEFAULT_SENDER'][1]),
        subject=subject,
        body=text_body,
        recipients=[(receiver.name, receiver.email)],
        reply_to=(sender.name, sender.email),
    )

    mailer.send(message)


def send_login_link_mail(
    mailer: Mail, link: models.AssignmentLoginLink, mail_idx: int
) -> None:
    """Send a login link email with a given ``mailer``.

    :param mailer: The mailer to use to send the login link.
    :param link: The link for which you want to send the email.
    :param mail_idx: How many emails were already sent to the user about this
        link? This is used to change the body of the mail.

    :param returns: Nothing.
    """
    receiver = link.user
    subject = current_app.jinja_mail_env.from_string(
        current_app.config['EXAM_LOGIN_SUBJECT']
    ).render(
        site_url=current_app.config["EXTERNAL_URL"], link=link
    )

    html_body = current_app.jinja_mail_env.get_template(
        'exam_login.j2'
    ).render(
        site_url=current_app.config["EXTERNAL_URL"],
        subject=subject,
        link=link,
        mail_idx=mail_idx,
    )
    refereneces = [link.get_message_id(i) for i in range(mail_idx)]
    in_reply_to = refereneces[-1] if refereneces else None

    _send_mail(
        html_body,
        subject,
        [(receiver.name, receiver.email)],
        mailer=mailer,
        message_id=link.get_message_id(mail_idx),
        in_reply_to=in_reply_to,
        references=refereneces,
    )


def init_app(app: t.Any) -> None:
    mail.init_app(app)
