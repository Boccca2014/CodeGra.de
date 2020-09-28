"""
This module defines all celery tasks. It is very important that you DO NOT
change the way parameters are used or the parameters provided in existing tasks
as there may tasks left in the old queue. Instead create a new task and change
the mapping of the variables at the bottom of this file.

SPDX-License-Identifier: AGPL-3.0-only
"""
from __future__ import annotations

import os
import json
import uuid
import typing as t
import datetime
import tempfile
import itertools
from operator import itemgetter

import structlog
from flask import Flask
from celery import signals, current_task
from requests import RequestException
from sqlalchemy.orm import contains_eager
from mypy_extensions import NamedArg, DefaultNamedArg
from celery.schedules import crontab
from typing_extensions import Literal

import psef as p
import cg_celery
import cg_logger
from cg_dt_utils import DatetimeWithTimezone

logger = structlog.get_logger()

celery = cg_celery.CGCelery('psef', signals)  # pylint: disable=invalid-name


def init_app(app: Flask) -> None:
    """Setup the tasks for psef.
    """
    celery.init_flask_app(app)

    if app.config['CELERY_CONFIG'].get('broker_url') is None:
        logger.error('Celery broker not set', report_to_sentry=True)
        return
    else:  # pragma: no cover
        # We cannot really test that we setup these periodic tasks yet.
        logger.info('Setting up periodic tasks')
        celery.add_periodic_task(
            crontab(minute='*/15'),
            _run_autotest_batch_runs_1.si(),
        )
        # These times are in UTC
        celery.add_periodic_task(
            crontab(minute='0', hour='10'),
            _send_daily_notifications.si(),
        )
        celery.add_periodic_task(
            crontab(minute='0', hour='18', day_of_month='5'),
            _send_weekly_notifications.si(),
        )


@celery.task
def _lint_instances_1(
    linter_name: str,
    cfg: str,
    linter_instance_ids: t.Sequence[str],
) -> None:
    p.linters.LinterRunner(
        p.linters.get_linter_by_name(linter_name),
        cfg,
    ).run(linter_instance_ids)


@celery.task
def _send_reminder_mails_1(assignment_id: int) -> None:
    assig = p.models.Assignment.query.get(assignment_id)

    if assig is None or None in {assig.done_type, assig.reminder_email_time}:
        return

    finished = set(g.user_id for g in assig.finished_graders)

    to_mail: t.Iterable[int]

    if assig.done_type == p.models.AssignmentDoneType.assigned_only:
        to_mail = assig.get_assigned_grader_ids()
    elif assig.done_type == p.models.AssignmentDoneType.all_graders:
        to_mail = map(itemgetter(1), assig.get_all_graders(sort=False))

    with p.mail.mail.connect() as conn:
        for user_id in to_mail:
            user = p.models.User.query.get(user_id)
            if user is None or user.id in finished:
                continue

            try:
                p.mail.send_grade_reminder_email(
                    assig,
                    user,
                    conn,
                )
            # pylint: disable=broad-except
            except Exception:  # pragma: no cover
                # This happens if mail sending fails or if the user has no
                # e-mail address.
                # TODO: make this exception more specific
                logger.warning(
                    'Could not send email',
                    receiving_user_id=user_id,
                    exc_info=True,
                    report_to_sentry=True,
                )


@celery.task
def _send_done_mail_1(assignment_id: int) -> None:
    assig = p.models.Assignment.query.get(assignment_id)

    if assig is not None and assig.done_email is not None:
        p.mail.send_whopie_done_email(assig)


@celery.task
def _send_grader_status_mail_1(
    assignment_id: int,
    user_id: int,
) -> None:
    assig = p.models.Assignment.query.get(assignment_id)
    user = p.models.User.query.get(user_id)

    if assig and user:
        p.mail.send_grader_status_changed_mail(assig, user)


@celery.task
def _run_plagiarism_control_1(  # pylint: disable=too-many-branches,too-many-statements
    plagiarism_run_id: int
) -> None:
    run = p.models.PlagiarismRun.query.get(plagiarism_run_id)
    if run is None:
        logger.error('Plagiarism run was already deleted')
        return
    run.do_run()


@celery.task
def _run_autotest_batch_runs_1() -> None:
    now = DatetimeWithTimezone.utcnow()
    # Limit the amount of runs, this way we never accidentally overload the
    # server by doing a large amount of batch run.
    max_runs = p.app.config['AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS']

    runs = p.models.AutoTestRun.query.join(
        p.models.AutoTestRun.auto_test
    ).join(p.models.Assignment).filter(
        p.models.AutoTestRun.batch_run_done.is_(False),
        p.models.Assignment.deadline < now,
    ).options(contains_eager(p.models.AutoTestRun.auto_test)).order_by(
        p.models.Assignment.deadline
    ).with_for_update().limit(max_runs).all()

    logger.info('Running batch run', run_ids=[r.id for r in runs])

    for run in runs:
        run.do_batch_run()

    p.models.db.session.commit()


@celery.task(
    autoretry_for=(RequestException, ),
    retry_backoff=True,
    retry_kwargs={'max_retries': 15}
)
def _notify_broker_of_new_job_1(
    run_id: t.Union[int, 'p.models.AutoTestRun'],
    wanted_runners: t.Optional[int] = 1
) -> None:
    if isinstance(run_id, int):
        run = p.models.AutoTestRun.query.filter_by(
            id=run_id
        ).with_for_update().one_or_none()
        if run is None:
            logger.warning('Trying to start run that does not exist')
            return
    else:
        run = run_id

    if wanted_runners is None:
        wanted_runners = run.get_amount_needed_runners()

    with p.helpers.BrokerSession() as ses:
        req = ses.put(
            '/api/v1/jobs/',
            json={
                'job_id': run.get_job_id(),
                'wanted_runners': wanted_runners,
                'metadata': run.get_broker_metadata(),
            },
        )
        req.raise_for_status()
        try:
            run.runners_requested = req.json().get(
                'wanted_runners', max(wanted_runners, 1)
            )
        except json.decoder.JSONDecodeError:
            run.runners_requested = max(wanted_runners, 1)
        p.models.db.session.commit()


@celery.task(
    autoretry_for=(RequestException, ),
    retry_backoff=True,
    retry_kwargs={'max_retries': 15}
)
def _notify_broker_kill_single_runner_1(
    run_id: int, runner_hex_id: str
) -> None:
    run = p.models.AutoTestRun.query.filter_by(
        id=run_id
    ).with_for_update().one_or_none()

    runner_id = uuid.UUID(hex=runner_hex_id)
    runner = p.models.AutoTestRunner.query.with_for_update().get(runner_id)

    if run is None:
        logger.warning('Run could not be found')
        return
    elif runner is None:
        logger.warning('Runner could not be found')
        return

    with p.helpers.BrokerSession() as ses:
        ses.delete(
            f'/api/v1/jobs/{runner.job_id}/runners/',
            json={
                'ipaddr': runner.ipaddr,
            }
        ).raise_for_status()
        run.runners_requested -= 1
        p.models.db.session.commit()


@celery.task(
    autoretry_for=(RequestException, ),
    retry_backoff=True,
    retry_kwargs={'max_retries': 15}
)
def _notify_broker_end_of_job_1(
    job_id: str, ignore_non_existing: bool = False
) -> None:
    ignore = str(ignore_non_existing).lower()
    with p.helpers.BrokerSession() as ses:
        ses.delete(f'/api/v1/jobs/{job_id}?ignore_non_existing={ignore}'
                   ).raise_for_status()


@celery.task
def _check_heartbeat_stop_test_runner_1(auto_test_runner_id: str) -> None:
    runner_id = uuid.UUID(hex=auto_test_runner_id)

    runner = p.models.AutoTestRunner.query.get(runner_id)
    if runner is None:
        logger.info('Runner not found', runner=runner)
        return
    elif runner.run is None:
        logger.info('Runner already reset', runner=runner)
        return

    interval = p.app.config['AUTO_TEST_HEARTBEAT_INTERVAL']
    max_missed = p.app.config['AUTO_TEST_HEARTBEAT_MAX_MISSED']
    max_interval = datetime.timedelta(seconds=interval * max_missed)
    needed_time = DatetimeWithTimezone.utcnow() - max_interval
    expired = runner.last_heartbeat < needed_time

    logger.info(
        'Checking heartbeat',
        last_heartbeat=runner.last_heartbeat.isoformat(),
        deadline=needed_time.isoformat(),
        max_internval=max_interval.total_seconds(),
        expired=expired,
    )

    # In this case the heartbeat received was recently, so we schedule this
    # task again.
    if not expired:
        check_heartbeat_auto_test_run(
            (runner.id.hex, ), eta=runner.last_heartbeat + max_interval
        )
        return

    run = p.models.AutoTestRun.query.filter_by(id=runner.run_id
                                               ).with_for_update().one()
    run.stop_runners([runner])
    p.models.db.session.commit()


@celery.task(
    autoretry_for=(RequestException, ),
    retry_backoff=True,
    retry_kwargs={'max_retries': 15}
)
def _adjust_amount_runners_1(
    auto_test_run_id: int, *, always_update_latest_results: bool = False
) -> None:
    run = p.models.AutoTestRun.query.filter_by(
        id=auto_test_run_id
    ).with_for_update().one_or_none()

    if run is None:
        logger.warning('Run to adjust not found')
        return

    requested_amount = run.runners_requested
    needed_amount = run.get_amount_needed_runners()

    should_notify_broker = False

    with cg_logger.bound_to_logger(
        requested_amount=requested_amount, needed_amount=needed_amount
    ):
        if needed_amount == requested_amount:
            logger.info('No new runners needed')
        elif needed_amount == 0 and run.runners_requested < 2:
            # If we have requested more than 2 runners we should decrease this,
            # so do send this request to the broker.
            logger.info("We don't need any runners")
        elif needed_amount > requested_amount:
            logger.info('We need more runners')
            should_notify_broker = True
        else:
            logger.info('We have requested too many runners')
            should_notify_broker = True

        if should_notify_broker:
            _notify_broker_of_new_job_1(run, needed_amount)
        elif always_update_latest_results:
            _update_latest_results_in_broker_1(run.id)


@celery.task
def _kill_runners_and_adjust_1(
    run_id: int, runners_to_kill_hex_ids: t.List[str]
) -> None:
    for runner_hex_id in runners_to_kill_hex_ids:
        _notify_broker_kill_single_runner_1(run_id, runner_hex_id)
    _adjust_amount_runners_1(run_id)


@celery.task(
    autoretry_for=(RequestException, ),
    retry_backoff=True,
    retry_kwargs={'max_retries': 15}
)
def _update_latest_results_in_broker_1(auto_test_run_id: int) -> None:
    m = p.models  # pylint: disable=invalid-name

    run = m.AutoTestRun.query.get(auto_test_run_id)
    if run is None:
        logger.info('Run not found', run_id=auto_test_run_id)
        return

    with p.helpers.BrokerSession() as ses:
        ses.put(
            '/api/v1/jobs/',
            json={
                'job_id': run.get_job_id(),
                'metadata': {
                    'results': run.get_broker_result_metadata(),
                },
                'error_on_create': True,
            },
        ).raise_for_status()


@celery.task
def _clone_commit_as_submission_1(
    unix_timestamp: float,
    clone_data_as_dict: t.Dict[str, t.Any],
) -> None:
    """Clone a repository and create a submission from its files.

    .. warning::

        This function **does not** check if the user has permission to create a
        submission, so this should be done by the caller.

    :param unix_timestamp: The date the submission should be created at. The
        rationale for passing this is that a user might have permission to
        create a submission at this time, but not at the time of the commit (or
        vica versa). And as commit times cannot be trusted this should be
        given explicitly.
    :param clone_data_as_dict: A :class:`p.models.GitCloneData` as a
        dictionary, including private data.
    :returns: Nothing.
    """
    clone_data = p.models.GitCloneData(**clone_data_as_dict)

    webhook = p.models.WebhookBase.query.get(clone_data.webhook_id)
    if webhook is None:
        logger.warning('Could not find webhook')
        return

    assignment = p.models.Assignment.query.filter_by(
        id=webhook.assignment_id
    ).with_for_update(read=True).one()

    created_at = DatetimeWithTimezone.utcfromtimestamp(unix_timestamp)

    with webhook.written_private_key() as fname, tempfile.TemporaryDirectory(
    ) as tmpdir, p.app.file_storage.putter() as putter:
        ssh_username = webhook.ssh_username
        assert ssh_username is not None
        program = p.helpers.format_list(
            p.current_app.config['GIT_CLONE_PROGRAM'],
            clone_url=clone_data.clone_url,
            commit=clone_data.commit,
            out_dir=tmpdir,
            ssh_key=fname,
            ssh_username=ssh_username,
            git_branch=clone_data.branch,
        )

        success, output = p.helpers.call_external(program)
        logger.info(
            'Called external clone program',
            successful=success,
            command_output=output
        )
        if not success:
            return

        p.files.replace_symlinks(tmpdir)

        tree = p.extract_tree.ExtractFileTree(
            name=clone_data.repository_name.replace('/', ' - ')
        )
        for child in list(
            p.files.rename_directory_structure(
                tmpdir, putter, p.app.max_file_size
            ).values
        ):
            child.forget_parent()
            tree.add_child(child)

        logger.info('Creating submission')
        work = p.models.Work.create_from_tree(
            assignment, webhook.user, tree, created_at=created_at
        )
        work.origin = p.models.WorkOrigin[clone_data.type]
        work.extra_info = clone_data.get_extra_info()
        p.models.db.session.commit()


@celery.task
def _delete_mirror_file_at_time_1(name: str, deletion_time: str) -> None:
    if current_task.maybe_delay_task(
        DatetimeWithTimezone.fromisoformat(deletion_time)
    ):
        return

    found = p.app.mirror_file_storage.get(name)
    found.if_just(lambda f: f.delete())


@celery.task
def _delete_file_at_time_1(
    filename: str, in_mirror_dir: bool, deletion_time: str
) -> None:  # pragma: no cover
    # This tasks only still exists as it might be scheduled before the
    # update. It should be removed in version M.3.
    if current_task.maybe_delay_task(
        DatetimeWithTimezone.fromisoformat(deletion_time)
    ):
        return

    if in_mirror_dir:
        root = p.app.config['MIRROR_UPLOAD_DIR']
    else:  # pragma: no cover
        # The case outside of the mirror_upload_dir is not yet used
        root = p.app.config['UPLOAD_DIR']

    filename = p.files.safe_join(root, filename)
    if os.path.isfile(filename):
        # There is a race condition here (file is removed in this small space),
        # but we don't care as it is removed in that case
        try:
            os.unlink(filename)
        except FileNotFoundError:  # pragma: no cover
            pass


@celery.task
def _add_1(first: int, second: int) -> int:  # pragma: no cover
    """This function is used for testing if celery works. What it actually does
    is completely irrelevant.
    """
    return first + second


@celery.task
def _send_direct_notification_emails_1(
    notification_ids: t.List[int],
) -> None:
    notifications = p.models.db.session.query(p.models.Notification).filter(
        p.models.Notification.id.in_(notification_ids),
        p.models.Notification.email_sent_at.is_(None),
    ).with_for_update().all()

    should_send = p.models.NotificationsSetting.get_should_send_for_users(
        [n.receiver_id for n in notifications]
    )

    for notification in notifications:
        with cg_logger.bound_to_logger(notification=notification):
            if not should_send(
                notification, p.models.EmailNotificationTypes.direct
            ):
                logger.info('Should not send notification')
                continue

            now = DatetimeWithTimezone.utcnow()
            try:
                p.mail.send_direct_notification_email(notification)
            # pylint: disable=broad-except
            except Exception:  # pragma: no cover
                # This happens if mail sending fails or if the user has no
                # e-mail address.
                # TODO: make this exception more specific
                logger.warning(
                    'Could not send notification email',
                    receiving_user_id=notification.receiver_id,
                    exc_info=True,
                    report_to_sentry=True,
                )
            else:
                notification.email_sent_at = now

    p.models.db.session.commit()


def _send_delayed_notification_emails(
    digest_type: Literal[p.models.EmailNotificationTypes.daily, p.models.
                         EmailNotificationTypes.weekly]
) -> None:
    now = DatetimeWithTimezone.utcnow()
    if digest_type == p.models.EmailNotificationTypes.daily:
        max_age = now - datetime.timedelta(days=1, hours=2)
    else:
        assert digest_type == p.models.EmailNotificationTypes.weekly
        max_age = now - datetime.timedelta(days=7, hours=2)

    notifications = p.models.db.session.query(p.models.Notification).filter(
        p.models.Notification.email_sent_at.is_(None),
        p.models.Notification.created_at > max_age,
    ).order_by(p.models.Notification.receiver_id).with_for_update().all()

    should_send = p.models.NotificationsSetting.get_should_send_for_users(
        list(set(n.receiver_id for n in notifications))
    )

    notifications_to_send = []

    now = DatetimeWithTimezone.utcnow()
    for notification in notifications:
        with cg_logger.bound_to_logger(
            notification=notification.__structlog__()
        ):
            if not should_send(notification, digest_type):
                logger.info('Should not send notification')
                continue
            logger.info('Should send notification')
            notification.email_sent_at = now
            notifications_to_send.append(notification)
    p.models.db.session.commit()

    for user, user_notifications in itertools.groupby(
        notifications_to_send, lambda n: n.receiver
    ):
        try:
            p.mail.send_digest_notification_email(
                list(user_notifications), digest_type
            )
        # pylint: disable=broad-except
        except Exception:  # pragma: no cover
            logger.warning(
                'Could not send digest email',
                receiving_user_id=user.id,
                exc_info=True,
                report_to_sentry=True,
            )


@celery.task
def _send_daily_notifications() -> None:
    _send_delayed_notification_emails(p.models.EmailNotificationTypes.daily)


@celery.task
def _send_weekly_notifications() -> None:
    _send_delayed_notification_emails(p.models.EmailNotificationTypes.weekly)


@celery.task
def _send_email_as_user_1(
    receiver_ids: t.List[int], subject: str, body: str,
    task_result_hex_id: str, sender_id: int
) -> None:
    task_result_id = uuid.UUID(hex=task_result_hex_id)
    task_result = p.models.TaskResult.query.with_for_update(
    ).get(task_result_id)

    if task_result is None:
        logger.error('Could not find task result')
        return

    def __task() -> None:
        receivers = p.helpers.get_in_or_error(
            p.models.User,
            p.models.User.id,
            receiver_ids,
            same_order_as_given=True,
        )
        sender = p.models.User.query.get(sender_id)
        if sender is None:  # pragma: no cover
            raise Exception('Wanted sender was not found')

        failed_receivers = []

        with p.mail.mail.connect() as mailer:
            for receiver in receivers:
                with cg_logger.bound_to_logger(receiver=receiver):
                    try:
                        p.mail.send_student_mail(
                            mailer,
                            sender=sender,
                            receiver=receiver,
                            subject=subject,
                            text_body=body
                        )
                    except:  # pylint: disable=bare-except
                        logger.info(
                            'Failed emailing to student',
                            exc_info=True,
                            report_to_sentry=True,
                        )
                        failed_receivers.append(receiver)

        if failed_receivers:
            raise p.exceptions.APIException(
                'Failed to email {every} user'.format(
                    every='every'
                    if len(receivers) != len(failed_receivers) else 'any'
                ),
                'Failed to mail some users',
                p.exceptions.APICodes.MAILING_FAILED,
                400,
                all_users=receivers,
                failed_users=failed_receivers,
            )

    if task_result.as_task(__task):
        p.models.db.session.commit()


@celery.task
def _maybe_open_assignment_at_1(assignment_id: int) -> None:
    assignment = p.models.Assignment.query.filter(
        p.models.Assignment.id == assignment_id,
    ).with_for_update(of=p.models.Assignment).one_or_none()

    if assignment is None or assignment.available_at is None:
        logger.error(
            'Could not find assignment with available_at',
            assignment=assignment,
            assignment_id=assignment_id
        )
        return
    if not assignment.state.is_hidden:
        logger.info('State already set to not hidden')
        return

    if current_task.maybe_delay_task(assignment.available_at):
        return

    assignment.state = p.models.AssignmentStateEnum.open
    p.models.db.session.commit()


@celery.task
def _send_login_links_to_users_1(
    assignment_id: int, task_id_hex: str, scheduled_time: str,
    reset_token_hex: str, mail_idx: int
) -> None:
    task_id = uuid.UUID(hex=task_id_hex)
    task_result = p.models.TaskResult.query.filter(
        p.models.TaskResult.id == task_id,
        p.models.TaskResult.state == p.models.TaskResultState.not_started
    ).with_for_update(of=p.models.TaskResult).one_or_none()
    eta = DatetimeWithTimezone.fromisoformat(scheduled_time)
    if task_result is None:
        logger.error('Could not find task')
        return

    def __task() -> p.models.TaskReturnType:
        reset_token = uuid.UUID(hex=reset_token_hex)
        assignment = p.models.Assignment.query.filter(
            p.models.Assignment.id == assignment_id,
        ).with_for_update(of=p.models.Assignment).one_or_none()

        if assignment is None or assignment.deadline_expired:
            logger.error(
                'Could not find assignment or deadline expired',
                assignment_id=assignment_id,
                assignment=assignment,
            )
            return p.models.TaskResultState.skipped
        elif reset_token != assignment.send_login_links_token:
            logger.info('Tokens did not match')
            return p.models.TaskResultState.skipped

        login_link_map = {
            link.user: link
            for link in p.models.AssignmentLoginLink.query.filter(
                p.models.AssignmentLoginLink.assignment == assignment
            )
        }
        perm = p.permissions.CoursePermission.can_receive_login_links
        users = [
            user for user, _ in assignment.course.get_all_users_in_course(
                include_test_students=False,
                with_permission=perm,
            )
        ]

        for user in users:
            if user not in login_link_map:
                link = p.models.AssignmentLoginLink(
                    user_id=user.id, assignment_id=assignment.id
                )
                p.models.db.session.add(link)
                login_link_map[user] = link

        # We commit here to release the locks on all tables before we start
        # emailing.
        p.models.db.session.commit()

        with p.mail.mail.connect() as mailer:
            for user in users:
                link = login_link_map[user]
                try:
                    p.mail.send_login_link_mail(
                        mailer, link, mail_idx=mail_idx
                    )
                # pylint: disable=bare-except
                except:  # pragma: no cover
                    logger.warning(
                        'Could not send email',
                        receiving_user_id=user.id,
                        exc_info=True,
                        report_to_sentry=True,
                    )

        return p.models.TaskResultState.finished

    if task_result.as_task(__task, eta=eta):
        p.models.db.session.commit()


lint_instances = _lint_instances_1.delay  # pylint: disable=invalid-name
add = _add_1.delay  # pylint: disable=invalid-name
send_done_mail = _send_done_mail_1.delay  # pylint: disable=invalid-name
send_grader_status_mail = _send_grader_status_mail_1.delay  # pylint: disable=invalid-name
run_plagiarism_control = _run_plagiarism_control_1.delay  # pylint: disable=invalid-name
notify_broker_of_new_job = _notify_broker_of_new_job_1.delay  # pylint: disable=invalid-name
notify_broker_end_of_job = _notify_broker_end_of_job_1.delay  # pylint: disable=invalid-name
notify_broker_kill_single_runner = _notify_broker_kill_single_runner_1.delay  # pylint: disable=invalid-name
adjust_amount_runners = _adjust_amount_runners_1.delay  # pylint: disable=invalid-name
kill_runners_and_adjust = _kill_runners_and_adjust_1.delay  # pylint: disable=invalid-name
update_latest_results_in_broker = _update_latest_results_in_broker_1.delay  # pylint: disable=invalid-name
clone_commit_as_submission = _clone_commit_as_submission_1.delay  # pylint: disable=invalid-name
delete_mirror_file_at_time = _delete_mirror_file_at_time_1.delay  # pylint: disable=invalid-name
send_direct_notification_emails = _send_direct_notification_emails_1.delay  # pylint: disable=invalid-name
send_email_as_user = _send_email_as_user_1.delay  # pylint: disable=invalid-name

send_login_links_to_users: t.Callable[[
    t.Tuple[int, str, str, str, int],
    NamedArg(DatetimeWithTimezone, 'eta')
], object] = _send_login_links_to_users_1.apply_async  # pylint: disable=invalid-name

send_reminder_mails: t.Callable[
    [t.Tuple[int],
     NamedArg(t.Optional[DatetimeWithTimezone], 'eta')], t.
    Any] = _send_reminder_mails_1.apply_async  # pylint: disable=invalid-name

check_heartbeat_auto_test_run: t.Callable[
    [t.Tuple[str],
     DefaultNamedArg(t.Optional[DatetimeWithTimezone], 'eta')], t.
    Any] = _check_heartbeat_stop_test_runner_1.apply_async  # pylint: disable=invalid-name

maybe_open_assignment_at: t.Callable[[
    t.Tuple[int],
    DefaultNamedArg(t.Optional[DatetimeWithTimezone], 'eta')
], None] = _maybe_open_assignment_at_1.apply_async  # pylint: disable=invalid-name
