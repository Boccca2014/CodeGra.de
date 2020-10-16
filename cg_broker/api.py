"""This module implements the API that is used by all CodeGrade instances.

.. note:: This API is not public in anyway!

SPDX-License-Identifier: AGPL-3.0-only
"""
import re
import uuid
import typing as t
import secrets
from datetime import timedelta
from functools import wraps

import jwt
import furl
import requests
import structlog
from flask import Blueprint, g, request
from flask_expects_json import expects_json

import cg_json
from cg_dt_utils import DatetimeWithTimezone
from cg_flask_helpers import EmptyResponse, callback_after_this_request
from cg_sqlalchemy_helpers import TIMESTAMP
from cg_sqlalchemy_helpers.types import DbColumn, IndexedJSONColumn

from . import BrokerFlask, app, tasks, models
from .models import db
from .exceptions import NotFoundException, PermissionException

if t.TYPE_CHECKING:  # pragma: no cover
    import cg_cache.inter_request  # pylint: disable=import-unused

logger = structlog.get_logger()

api = Blueprint("api", __name__)  # pylint: disable=invalid-name
T_CAL = t.TypeVar('T_CAL', bound=t.Callable)  # pylint: disable=invalid-name


def init_app(flask_app: BrokerFlask) -> None:
    flask_app.register_blueprint(api, url_prefix="/api/v1")


def _download_public_key(instance_url: str, broker_id: str) -> str:
    url = furl.furl(instance_url).add(
        path=[
            'api',
            'v-internal',
            'brokers',
            broker_id,
        ]
    ).tostr()
    response = requests.get(url)
    response.raise_for_status()
    return response.json()['public_key']


def _verify_public_instance_jwt(
    cache: 'cg_cache.inter_request.Backend[str]',
    signature: str,
    allowed_hosts: re.Pattern,
) -> str:
    # First get the url from the jwt without verifying, then get the
    # public key and do the verification.
    unsafe_decoded = jwt.decode(signature, verify=False)
    if allowed_hosts.match(unsafe_decoded.get('url', None)) is None:
        raise PermissionException(401)

    try:
        decoded = cache.cached_call(
            key=unsafe_decoded['url'],
            get_value=lambda: _download_public_key(
                unsafe_decoded['url'],
                unsafe_decoded['id'],
            ),
            callback=lambda public_key: jwt.decode(
                signature,
                key=public_key,
                algorithms='RS256',
                verify=True,
            )
        )
        assert decoded == unsafe_decoded
    except:  # pylint: disable=bare-except
        logger.error('Got unauthorized broker request', exc_info=True)
        raise PermissionException(401)
    else:
        return decoded['url']


def instance_route(f: T_CAL) -> T_CAL:
    """This function is a decorator that makes sure that the given fuction can
    only be used when the correct headers are included.

    This effectively adds some form of authentication to the routes.
    """

    @wraps(f)
    def __inner(*args: object, **kwargs: object) -> t.Any:
        pattern = app.config['ALLOWED_INSTANCE_URL_PATTERN']
        signature = request.headers.get('CG-Application-Signature', None)
        if signature is None:
            instance_name = request.headers['CG-Broker-Instance']
            g.cg_instance_url = instance_name

            password = request.headers['CG-Broker-Pass']
            try:
                if not secrets.compare_digest(
                    app.allowed_instances[instance_name], password
                ):
                    raise PermissionException(401)
            except (KeyError, TypeError) as exc:
                raise PermissionException(401) from exc
        else:
            g.cg_instance_url = _verify_public_instance_jwt(
                app.instance_public_key_cache, signature, pattern
            )
            # We might have changed our cache, so already commit those changes.
            db.session.commit()

        return f(*args, **kwargs)

    return t.cast(T_CAL, __inner)


@api.route('/jobs/', methods=['POST', 'PUT'])
@expects_json({
    'type': 'object',
    'properties': {
        'job_id': {'type': 'string'}, 'wanted_runners': {'type': 'integer'},
        'metadata': {'type': 'object'}, 'error_on_create': {'type': 'boolean'}
    },
    'required': ['job_id'],
})
@instance_route
def register_job() -> cg_json.JSONResponse:
    """Register a new job.

    If needed a runner will be started for this job.
    """
    remote_job_id = g.data['job_id']
    cg_url = g.cg_instance_url
    job = None

    if request.method == 'PUT':
        job = db.session.query(models.Job).filter_by(
            remote_id=remote_job_id,
            cg_url=cg_url,
        ).with_for_update().one_or_none()

    will_create = job is None
    if will_create and g.data.get('error_on_create', False):
        raise NotFoundException

    if job is None:
        job = models.Job(
            remote_id=remote_job_id,
            cg_url=cg_url,
        )
        db.session.add(job)

    job.update_metadata(g.data.get('metadata', {}))
    if 'wanted_runners' in g.data or will_create:
        job.wanted_runners = g.data.get('wanted_runners', 1)
        active_runners = models.Runner.get_all_active_runners().filter_by(
            job_id=job.id
        ).with_for_update().all()

        too_many = len(active_runners) - job.wanted_runners
        logger.info(
            'Job was updated',
            wanted_runners=job.wanted_runners,
            amount_active=len(active_runners),
            too_many=too_many,
            metadata=job.job_metadata,
        )

        before_assigned = set(models.RunnerState.get_before_assigned_states())
        for runner in active_runners:
            if too_many <= 0:
                break

            if runner.state in before_assigned:
                runner.make_unassigned()
                too_many -= 1

        db.session.flush()
        job_id = job.id
        callback_after_this_request(
            lambda: tasks.maybe_start_runners_for_job.delay(job_id)
        )

    db.session.commit()

    return cg_json.jsonify(job)


@api.route('/jobs/<job_id>/runners/', methods=['DELETE'])
@expects_json({
    'type': 'object',
    'properties': {'ipaddr': {'type': 'string'}, },
    'required': ['ipaddr'],
})
@instance_route
def remove_runner_of_job(job_id: str) -> EmptyResponse:
    """Remove (kill) a runner of the given job.

    The runner is given by its ip in the data of the DELETE request.
    """
    job = db.session.query(
        models.Job
    ).filter_by(remote_id=job_id).with_for_update().one_or_none()
    if job is None:
        raise NotFoundException

    runner = db.session.query(models.Runner).filter(
        models.Runner.ipaddr == g.data['ipaddr'],
        models.Runner.job == job,
    ).with_for_update().one_or_none()
    if runner is None:
        raise NotFoundException

    runner.job_id = None
    db.session.commit()

    tasks.kill_runner(runner.id.hex)
    return EmptyResponse.make()


@api.route('/jobs/<job_id>', methods=['DELETE'])
@instance_route
def delete_job(job_id: str) -> EmptyResponse:
    """Delete the given job.

    If this job had any runners associated with it these will be stopped and
    cleaned.
    """
    job = db.session.query(
        models.Job
    ).filter_by(remote_id=job_id).with_for_update().one_or_none()
    if job is None:
        if request.args.get('ignore_non_existing') == 'true':
            return EmptyResponse.make()

        # Make sure job will never be able to run
        job = models.Job(
            cg_url=g.cg_instance_url,
            remote_id=job_id,
            state=models.JobState.finished,
        )
        db.session.add(job)
        db.session.commit()
        return EmptyResponse.make()
    elif job.state == models.JobState.finished:
        logger.info('Job already cleaned')
        return EmptyResponse.make()

    runners = db.session.query(models.Runner).filter_by(
        job_id=job.id,
    ).with_for_update().all()
    job.state = models.JobState.finished
    job.wanted_runners = 0
    before_assigned = set(models.RunnerState.get_before_assigned_states())
    for runner in runners:
        if runner.state in before_assigned:
            runner.make_unassigned()

    db.session.commit()

    tasks.cleanup_runners_of_job.delay(job.id)

    return EmptyResponse.make()


@api.route('/jobs/<job_id>/runners/', methods=['POST', 'PUT'])
@expects_json({
    'type': 'object',
    'properties': {'runner_ip': {'type': 'string'}},
    'minProperties': 1,
    'required': ['runner_ip'],
})
@instance_route
def register_runner_for_job(job_id: str) -> EmptyResponse:
    """Check if the given ``runner_ip`` is allowed to be used for the given
    job (identified by ``job_id``).
    """
    runner_ip = g.data['runner_ip']
    job = db.session.query(models.Job).filter(
        models.Job.remote_id == job_id,
        models.Job.cg_url == g.cg_instance_url,
        models.Job.state.notin_(models.JobState.get_finished_states()),
    ).with_for_update().one_or_none()
    if job is None:
        logger.info('Job not found!', job_id=job_id)
        raise NotFoundException

    logger.info(
        'Searching for runner',
        runner_ipaddr=g.data['runner_ip'],
        job_id=job.id
    )

    runner = db.session.query(models.Runner).filter(
        models.Runner.state.in_(
            models.RunnerState.get_before_running_states()
        ),
        models.Runner.ipaddr == runner_ip,
    ).with_for_update().one_or_none()

    if runner is None:
        logger.warning('Runner could not be found')
        raise NotFoundException

    if not job.maybe_use_runner(runner):
        logger.info(
            'Runner cannot be used for job', job_id=job.id, runner=runner
        )
        raise NotFoundException

    # We don't mark the job as started here, as there might be a connection
    # problem back to the server (or the runner). Then the server might think
    # that the job has not yet started, but as the broker thinks that
    # everything is fine it won't assign more runners. See DEV-252 in Jira for
    # more information.
    runner.state = models.RunnerState.assigned
    db.session.commit()

    return EmptyResponse.make()


@api.route('/runners/<uuid:public_runner_id>/jobs/', methods=['POST'])
@expects_json({
    'type': 'object',
    'properties': {'url': {'type': 'string'}},
    'minProperties': 1,
    'required': ['url'],
})
def confirm_runner_for_job(public_runner_id: uuid.UUID) -> EmptyResponse:
    """Confirm the runner that does this request for connected job.
    """
    runner = db.session.query(models.Runner).filter(
        models.Runner.ipaddr == request.remote_addr,
        models.Runner.public_id == public_runner_id,
    ).with_for_update().one_or_none()
    if runner is None:
        raise NotFoundException

    runner.verify_password()

    if runner.state.is_running:
        # We might want to retry this request because of dropped packets. In
        # this case simply do nothing and return.
        return EmptyResponse.make()
    if not runner.state.is_assigned:
        raise NotFoundException

    if runner.job is None or runner.job.cg_url != g.data['url']:
        logger.info(
            'Tried to register for wrong job',
            found_url=g.data['url'],
            assigned_job=runner.job
        )
        raise NotFoundException

    runner.state = models.RunnerState.running
    runner.job.state = models.JobState.started
    db.session.commit()
    return EmptyResponse.make()


@api.route('/alive/', methods=['POST'])
def mark_runner_as_alive() -> cg_json.JSONResponse[models.Runner]:
    """Mark the given runner as alive and set its state to ``started`` if it
    isn't already. The given runner should not be assigned to a job yet.
    """
    runner = db.session.query(models.Runner).filter(
        models.Runner.ipaddr == request.remote_addr,
        models.Runner.state.in_([
            models.RunnerState.creating,
            models.RunnerState.started,
        ])
    ).with_for_update().one_or_none()
    if runner is None:
        logger.info('Could not find runner', runner_ip=request.remote_addr)
        raise NotFoundException

    runner.verify_password()

    runner.state = models.RunnerState.started
    runner.started_at = DatetimeWithTimezone.utcnow()
    db.session.commit()

    return cg_json.jsonify(runner)


@api.route('/runners/<uuid:public_runner_id>/jobs/', methods=['GET'])
def get_jobs_for_runner(public_runner_id: uuid.UUID
                        ) -> cg_json.JSONResponse[t.List[t.Mapping[str, str]]]:
    """Get jobs for a runner"""
    runner = db.session.query(models.Runner).filter(
        models.Runner.ipaddr == request.remote_addr,
        models.Runner.public_id == public_runner_id,
        models.Runner.state.in_(
            models.RunnerState.get_before_running_states()
        ),
    ).with_for_update().one_or_none()
    if runner is None:
        raise NotFoundException

    runner.verify_password()

    # If an assigned runners comes asking for work again we simply assume that
    # the application backend was not successful in using the runner. So we
    # simply make it unassigned again.
    if runner.state.is_assigned and (
        runner.job is None or not runner.job.needs_more_runners
    ):
        runner.make_unassigned()

    urls: t.Iterable[str]
    if runner.state in models.RunnerState.get_before_assigned_states():
        urls = set(
            url for url, in db.session.query(models.Job.cg_url).filter(
                models.Job.state.notin_(
                    models.JobState.get_finished_states(),
                ),
                models.Job.needs_more_runners,
            )
        )
        # If assigned make sure that url is first in the list so that the
        # runner tries that first.
        if runner.job is not None:
            best_url = runner.job.cg_url
            urls = sorted(urls, key=lambda url: url == best_url, reverse=True)
    else:
        urls = [] if runner.job is None else [runner.job.cg_url]

    return cg_json.jsonify([{'url': url} for url in urls])


@api.route('/ping', methods=['GET'])
@instance_route
def get_ping() -> cg_json.JSONResponse[t.Mapping[str, str]]:
    """Do a simple ping to the broker.

    This is useful to make sure an instance is allowed to access the broker.
    """
    return cg_json.jsonify({'ping': 'pong'})


@api.route('/about', methods=['GET'])
def about() -> cg_json.JSONResponse[t.Mapping[str, object]]:
    """Get some information about the state of this broker.

    When given a valid ``health`` get parameter this will also return some
    health information.
    """
    if request.args.get('health', object()) == app.config['HEALTH_KEY']:
        now = DatetimeWithTimezone.utcnow()
        slow_created_date = now - timedelta(minutes=app.config['OLD_JOB_AGE'])
        not_started_created_date = now - timedelta(
            minutes=app.config['SLOW_STARTING_AGE']
        )
        not_started_task_date = now - timedelta(
            minutes=app.config['SLOW_STARTING_TASK_AGE']
        )
        slow_task_date = now - timedelta(minutes=app.config['SLOW_TASK_AGE'])

        def get_count(*cols: DbColumn[bool]) -> int:
            return db.session.query(models.Job).filter(
                models.Job.state.notin_(models.JobState.get_finished_states()),
                *cols,
            ).count()

        slow_jobs = get_count(models.Job.created_at < slow_created_date)

        not_starting_jobs = get_count(
            models.Job.created_at < not_started_created_date,
            models.Job.state == models.JobState.waiting_for_runner,
        )

        def as_dt(col: IndexedJSONColumn) -> DbColumn[DatetimeWithTimezone]:
            return col.as_string().cast(TIMESTAMP(timezone=True))

        not_started_task = models.Job.job_metadata['results']['not_started']
        jobs_not_starting_tasks = get_count(
            as_dt(not_started_task) < not_started_task_date
        )

        slow_task = models.Job.job_metadata['results']['running']
        jobs_with_slow_tasks = get_count(as_dt(slow_task) < slow_task_date)

        health = {
            'not_starting_jobs': not_starting_jobs,
            'slow_jobs': slow_jobs,
            'jobs_with_not_starting_tasks': jobs_not_starting_tasks,
            'jobs_with_slow_tasks': jobs_with_slow_tasks,
        }
    else:
        health = {}

    return cg_json.jsonify(
        {
            'health': health,
            'version': app.config.get('CUR_COMMIT', 'unknown'),
        },
        status_code=500 if any(health.values()) else 200,
    )
