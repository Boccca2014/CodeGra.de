"""This file defines all celery tasks for the broker.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import random
import datetime

import structlog
from celery import signals
from sqlalchemy.sql.expression import and_
from sqlalchemy.sql.expression import func as sql_func

from cg_celery import CGCelery
from cg_logger import bound_to_logger
from cg_dt_utils import DatetimeWithTimezone
from cg_flask_helpers import callback_after_this_request

from . import BrokerFlask, app, utils, models
from .models import db

celery = CGCelery(__name__, signals)  # pylint: disable=invalid-name
logger = structlog.get_logger()


def init_app(flask_app: BrokerFlask) -> None:
    celery.init_flask_app(flask_app)


@celery.task(acks_late=True, max_retries=10, reject_on_worker_lost=True)
def maybe_kill_unneeded_runner(runner_hex_id: str) -> None:
    """Maybe kill the given runner if it is still unassigned.

    :param runner_hex_id: The hex id of the runner to maybe kill.
    """
    # One interesting thing to consider here is how to deal with the
    # minimum amount of extra runners setting here. You could say that if
    # killing this runner brings us under this setting we shouldn't kill
    # the runner. However, that might mean that runners will live for very
    # long, and that might have unforeseen complications. So we do want to
    # kill runners after some time, but that might mean we kill every
    # extra runner at the same time, which would mean that for a minute or
    # so we do not have enough runners at all. To prevent that we have a
    # random element to when runners are killed.

    # TODO: If a runner goes from unassigned, to assigned, to unassigned we
    # might kill it too soon. As we start a job to kill it for the first time
    # it is unassigned, and this job might be executed while it is unassigned
    # for the second time.
    runner_id = uuid.UUID(hex=runner_hex_id)
    runner = db.session.query(
        models.Runner
    ).filter_by(id=runner_id).with_for_update().one_or_none()

    with bound_to_logger(runner=runner):
        if runner is None:
            logger.warning('Runner was deleted')
            return

        should_run_date = runner.created_at + datetime.timedelta(
            minutes=(
                app.config['RUNNER_MAX_TIME_ALIVE'] + random.randint(0, 15)
            )
        )
        if runner.state not in models.RunnerState.get_before_running_states():
            logger.info('Runner is running', runner_state=runner.state)
            return
        elif utils.maybe_delay_current_task(should_run_date):
            return
        elif runner.job_id is not None:
            logger.info('Runner is needed', job_of_runner=runner.job_id)
            return

        logger.info('Runner is still not doing anything')
        runner.kill(maybe_start_new=True, shutdown_only=False)


@celery.task
def maybe_start_more_runners() -> None:
    """Start more runners for jobs that still need runners.

    This assigns all unassigned runners if possible, and if needed it also
    starts new runners.
    """
    # We might change the amount of unassigned runners during this task, so
    # maybe we need to start more.
    callback_after_this_request(start_needed_unassigned_runners.delay)

    # Do not use count so we can lock all these runners, this makes sure we
    # will not create new runners while we are counting.
    active_jobs = {
        job.id: job
        for job in db.session.query(models.Job).filter(
            models.Job.state != models.JobState.finished
        ).with_for_update()
    }

    unassigned_runners = models.Runner.get_all_active_runners().filter_by(
        job_id=None
    ).with_for_update().all()

    jobs_needed_runners = db.session.query(
        models.Job.id,
        models.Job.wanted_runners - sql_func.count(models.Runner.id),
    ).filter(
        models.Job.id.in_(list(active_jobs.keys())),
    ).join(
        models.Runner,
        and_(
            models.Runner.job_id == models.Job.id,
            models.Runner.state.in_(models.RunnerState.get_active_states())
        ),
        isouter=True
    ).having(
        models.Job.wanted_runners > sql_func.count(models.Runner.id),
    ).group_by(models.Job.id).all()

    with bound_to_logger(
        jobs_needed_runners=jobs_needed_runners,
        all_unassigned_runners=unassigned_runners,
    ):
        if jobs_needed_runners:
            startable = models.Runner.get_amount_of_startable_runners()

            logger.info('More runners are needed')

            for job_id, _ in jobs_needed_runners:
                # This never raises a key error as only jobs in this dictionary
                # are selected.
                job = active_jobs[job_id]
                startable -= job.add_runners_to_job(
                    unassigned_runners, startable
                )
            db.session.commit()
        elif unassigned_runners:
            logger.error('More runners than jobs active')
        else:
            logger.info('No new runners needed')


@celery.task
def start_needed_unassigned_runners() -> None:
    """Start extra runners if the mimimum_amount_extra_runners option is set
    and there are less runners than its value.
    """
    wanted_amount = models.Setting.get(
        models.PossibleSetting.minimum_amount_extra_runners
    )
    if wanted_amount < 1:
        return

    unassigned_runners = models.Runner.get_before_active_unassigned_runners(
    ).with_for_update().all()
    to_start = wanted_amount - len(unassigned_runners)

    if to_start > 0:
        start_unassigned_runner(amount=to_start)


@celery.task
def start_unassigned_runner(amount: int = 1) -> None:
    """Unconditionally start an unassigned runner.

    A unassigned runner is a runner which is not linked to one job.
    """
    to_start = []
    for _ in range(amount):
        if not models.Runner.can_start_more_runners():
            break

        runner = models.Runner.create_of_type(app.config['AUTO_TEST_TYPE'])
        db.session.add(runner)
        db.session.flush()
        to_start.append(runner)

    db.session.commit()

    for runner in to_start:
        start_runner.delay(runner.id.hex)


@celery.task
def maybe_start_runners_for_job(job_id: int) -> None:
    """Maybe start a runner assigned to the given ``job_id``.

    The runner is only started when the job doesn't already have a runner and
    there are not too many runners active.
    """
    job = db.session.query(
        models.Job
    ).filter_by(id=job_id).with_for_update().one_or_none()

    if job is None:
        logger.warning('Job to start runner for not found', job_id=job_id)
        return

    unassigned_runners = models.Runner.get_before_active_unassigned_runners(
    ).with_for_update().all()

    startable = models.Runner.get_amount_of_startable_runners()

    job.add_runners_to_job(unassigned_runners, startable)
    db.session.commit()


@celery.task
def kill_runner(runner_hex_id: str, shutdown_only: bool = False) -> None:
    """Kill the runner with the given ``runner_hex_id``.
    """
    runner_id = uuid.UUID(hex=runner_hex_id)
    runner = db.session.query(
        models.Runner
    ).filter_by(id=runner_id).with_for_update().one_or_none()
    if runner is None:
        logger.warning('Runner not found')
        return
    elif not runner.should_clean:
        logger.info('Runner already cleaned up')
        return

    runner.kill(maybe_start_new=True, shutdown_only=shutdown_only)


@celery.task
def _kill_slow_starter(runner_hex_id: str) -> None:
    runner_id = uuid.UUID(hex=runner_hex_id)
    runner = db.session.query(
        models.Runner
    ).filter_by(id=runner_id).with_for_update().one_or_none()

    if runner is None:
        logger.info('Cannot find runner')
        return
    elif runner.state not in models.RunnerState.get_before_started_states():
        logger.info(
            'Runner already started', runner=runner, state=runner.state
        )
        return

    should_run_date = runner.created_at + datetime.timedelta(
        minutes=app.config['START_TIMEOUT_TIME']
    )
    if utils.maybe_delay_current_task(should_run_date):
        return

    logger.info('Killing runner', runner=runner, state_of_runner=runner.state)

    if runner.job_id is not None:
        # For some strange reason the runner still had a job. In this case we
        # should make a new runner for that job after we killed this runner.
        job_id = runner.job_id
        callback_after_this_request(
            lambda: maybe_start_runners_for_job.delay(job_id)
        )
    else:
        callback_after_this_request(maybe_start_more_runners)

    runner.kill(maybe_start_new=False, shutdown_only=False)


@celery.task
def _check_slow_starter(runner_hex_id: str) -> None:
    runner_id = uuid.UUID(hex=runner_hex_id)
    runner = db.session.query(
        models.Runner
    ).filter_by(id=runner_id).with_for_update().one_or_none()

    if runner is None:
        logger.info('Cannot find runner')
        return
    elif runner.state not in models.RunnerState.get_before_started_states():
        logger.info(
            'Runner already started', runner=runner, state=runner.state
        )
        return

    min_age = app.config['START_TIMEOUT_TIME'] / 3
    should_run_date = runner.created_at + datetime.timedelta(minutes=min_age)

    if utils.maybe_delay_current_task(should_run_date):
        return

    # If we cannot start more runners we have to kill this old slow starting
    # runner.
    should_kill_runner = not models.Runner.can_start_more_runners()

    new_runner = models.Runner.create_of_type(app.config['AUTO_TEST_TYPE'])
    db.session.add(new_runner)

    if runner.job_id is not None:
        new_runner.job_id = runner.job_id
        runner.make_unassigned()

    if should_kill_runner:
        logger.info('Many runners active, so killing this non starting one')
        runner.kill(maybe_start_new=False, shutdown_only=False)

    db.session.commit()
    start_runner.delay(new_runner.id.hex)


@celery.task
def start_runner(runner_hex_id: str) -> None:
    """Start the given runner.

    :param runner_hex_id: The hex id of the runner in string format.
    :returns: Nothing.
    """
    runner_id = uuid.UUID(hex=runner_hex_id)
    runner = db.session.query(
        models.Runner
    ).filter_by(id=runner_id).with_for_update().one_or_none()

    if runner is None:
        logger.info('Cannot find runner')
        return
    elif runner.state != models.RunnerState.not_running:
        logger.info(
            'Runner not in not_running state',
            runner=runner,
            state=runner.state
        )
        return

    maybe_kill_unneeded_runner.apply_async(
        (runner.id.hex, ),
        eta=DatetimeWithTimezone.utcnow() +
        datetime.timedelta(minutes=app.config['RUNNER_MAX_TIME_ALIVE'])
    )

    runner.state = models.RunnerState.creating

    try:
        runner.start_runner()
    except:
        logger.error('Failed to start runner', exc_info=True)
        # The kill method commits
        runner.kill(maybe_start_new=True, shutdown_only=False)
        raise
    else:
        db.session.commit()
        _check_slow_starter.delay(runner.id.hex)
        _kill_slow_starter.delay(runner.id.hex)


@celery.task
def cleanup_runners_of_job(job_id: int) -> None:
    """Cleanup the runners of the given job.
    """
    runners = db.session.query(
        models.Runner
    ).filter_by(job_id=job_id).with_for_update().all()

    to_clean = []
    for runner in runners:
        if runner.should_clean:
            runner.state = models.RunnerState.cleaning
            to_clean.append(runner)
        else:
            logger.info('Runner already cleaned up')

    db.session.commit()

    for runner in to_clean:
        runner.kill(maybe_start_new=True, shutdown_only=False)


@celery.task
def add_1(first: int, second: int) -> int:  # pragma: no cover
    """This function is used for testing if celery works. What it actually does
    is completely irrelevant.
    """
    return first + second
