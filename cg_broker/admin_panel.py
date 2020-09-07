"""This module implements the admin panel of our broker.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid
import typing as t
import secrets
import datetime

import structlog
from flask import (
    Blueprint, abort, flash, request, session, url_for, redirect,
    make_response, render_template
)
from flask_login import (
    UserMixin, LoginManager, login_user, logout_user, current_user,
    login_required
)
from sqlalchemy.orm import selectinload
from werkzeug.wrappers import Response

from cg_dt_utils import DatetimeWithTimezone

from . import BrokerFlask, app, tasks, models
from .models import db

logger = structlog.get_logger()

login_manager = LoginManager()  # pylint: disable=invalid-name

admin = Blueprint("admin", __name__)  # pylint: disable=invalid-name


def init_app(flask_app: BrokerFlask) -> None:
    """Add the admin panel blueprint to the given ``flask_app``.
    """
    flask_app.register_blueprint(admin, url_prefix="/admin/")
    login_manager.init_app(flask_app)


@login_manager.unauthorized_handler
def unauthorized_request() -> Response:
    """This function is called if a unauthorized user requests a route which is
    protected.
    """
    logger.warning(
        'User tried to access restricted page without password',
        requested_url=request.url
    )
    return redirect(url_for('.login', next_url=request.url))


admin.add_app_template_global(lambda: current_user, 'current_user')


@admin.add_app_template_global
def utcnow() -> DatetimeWithTimezone:
    """Get current date.
    """
    return DatetimeWithTimezone.utcnow()


@admin.app_template_filter('datetime')
def _format_datetime(date: datetime.datetime) -> str:
    return date.strftime('%Y-%m-%d %T')


@admin.app_template_filter('nested_get')
def _nested_get(
    mapping: t.Optional[t.Dict[str, object]], default: object, *keys: str
) -> object:
    res: t.Optional[t.Dict] = mapping

    key_list = list(reversed(keys))
    while key_list and isinstance(res, dict):
        res = res.get(key_list.pop(), None)

    return default if res is None else res


@admin.app_template_filter('age')
def _get_age_datetime(
    date: t.Union[DatetimeWithTimezone, str], add_m: bool = False
) -> t.Union[float, str]:
    if isinstance(date, str):
        date = DatetimeWithTimezone.fromisoformat(date)
    res = int(
        round((DatetimeWithTimezone.utcnow() - date).total_seconds() / 60)
    )
    if add_m:
        return f'{res}m'
    return res


@admin.add_app_template_global
def csrf_token() -> str:
    """Get the csrf_token of this session, and generate one if it is not
    available.
    """
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(64)
    return session['_csrf_token']


@admin.before_request
def csrf_protect() -> None:
    """Protect the current route by checking if the ``_csrf_token`` is correct.
    """
    if request.method in {'POST', 'DELETE'}:
        token = session.pop('_csrf_token', None)
        got = request.form.get('_csrf_token')
        if token is None or token != got:
            logger.error('CSRF was not correct', got=got, expected=token)
            abort(403)


class AdminUser(UserMixin):  # type: ignore
    """The only valid user of the admin panel: the admin user!
    """

    @staticmethod
    def get_id() -> str:
        return '1'


@login_manager.user_loader
def load_user(user_id: str) -> t.Optional[UserMixin]:
    """Load the user with the given ``user_id``.
    """
    admin_user = AdminUser()
    if user_id == admin_user.get_id():
        return admin_user
    return None


@admin.route('/logout', methods=['POST'])
def logout() -> Response:
    """Logout the current user by clearing the session.
    """
    logout_user()
    flash('You were logged out successfully')
    return redirect(url_for('.login'))


@admin.route('/login', methods=['GET', 'POST'])
def login() -> Response:
    """Login to the admin panel, or get the admin panel page.
    """
    if request.method == 'GET':
        return make_response(render_template('login.j2', runners=[]))
    elif request.method == 'POST':
        next_url = request.args.get('next', url_for('.show_all_runners'))
        if secrets.compare_digest(
            request.form['password'], app.config['ADMIN_PASSWORD']
        ):
            login_user(AdminUser())
            return redirect(next_url)
        else:
            flash('Password is wrong!')
            logger.error(
                'User tried to login to broker admin panel with wrong password'
            )
            return redirect(
                url_for('.login', next=request.args.get('next', None))
            )
    else:
        raise RuntimeError


@admin.route('/runners/', methods=['GET'])
@login_required
def show_all_runners() -> str:
    """Get all runners in a nice (?) layout.
    """
    finished_runners = db.session.query(models.Runner).filter(
        models.Runner.state.notin_(models.RunnerState.get_active_states())
    ).order_by(models.Runner.created_at.desc()).options(
        selectinload(models.Runner.job)
    ).limit(50).all()

    active_runners = db.session.query(models.Runner).filter(
        models.Runner.state.in_(models.RunnerState.get_active_states())
    ).order_by(models.Runner.created_at.asc()).options(
        selectinload(models.Runner.job)
    ).all()

    return render_template(
        'runners.j2',
        active_runners=active_runners,
        finished_runners=finished_runners
    )


@admin.route('/jobs/', methods=['GET'])
@login_required
def show_all_jobs() -> str:
    """Get all jobs in a nice (?) layout.
    """
    finished_jobs = db.session.query(models.Job).filter(
        models.Job.state.in_(models.JobState.get_finished_states())
    ).order_by(models.Job.created_at.desc()).limit(50).all()

    active_jobs = db.session.query(models.Job).filter(
        models.Job.state.notin_(models.JobState.get_finished_states())
    ).order_by(models.Job.created_at.asc()).all()

    return render_template(
        'jobs.j2', active_jobs=active_jobs, finished_jobs=finished_jobs
    )


@admin.route('/runners/<runner_hex_id>/stop', methods=['POST'])
@login_required
def stop_runner(runner_hex_id: str) -> Response:
    """Stop the given runner.

    .. note::

        The runner will not be stopped immediately, as this is done in a celery
        task.
    """
    runner_id = uuid.UUID(hex=runner_hex_id)
    runner = db.session.query(models.Runner).get(runner_id)
    shutdown = request.args.get('shutdown', 'false') == 'true'
    assert runner is not None

    tasks.kill_runner.delay(runner.id.hex, shutdown)
    flash('Stopping runner')

    return redirect(url_for('.show_all_runners'))


@admin.route('/runners/', methods=['POST'])
@login_required
def create_runner() -> Response:
    """Create a new unsigned runner.
    """
    if not models.Runner.can_start_more_runners():
        flash('We cannot create more runners, as the maximum is reached')
    else:
        try:
            amount = int(request.form.get('amount') or '1')
        except (KeyError, ValueError):
            flash('Amount is not a number')
        else:
            flash(f'Starting {amount} runners')
            tasks.start_unassigned_runner.delay(amount)

    return redirect(url_for('.show_all_runners'))


@admin.route('/settings/', methods=['GET'])
@login_required
def show_settings() -> str:
    """Display the settings and their values.
    """
    lookup = {
        setting.setting: setting.value
        for setting in models.Setting.query.all()
    }
    all_settings = [(item, lookup.get(item, item.value.default_value))
                    for item in models.PossibleSetting]
    return render_template(
        'settings.j2',
        all_settings=all_settings,
    )


@admin.route('/settings/', methods=['POST'])
@login_required
def update_setting() -> Response:
    """Update values of settings.
    """
    setting_name = request.form['setting']
    setting_value = request.form['value']

    setting = models.PossibleSetting[setting_name]
    value = setting.value.type_convert(setting_value)
    models.Setting.set(setting, value)
    db.session.commit()

    return redirect(url_for('.show_settings'))
