# SPDX-License-Identifier: AGPL-3.0-only
import os
import re
import sys
import copy
import json
import time
import uuid
import random
import signal
import string
import logging
import secrets
import datetime
import functools
import itertools
import contextlib
import subprocess
import collections
import multiprocessing
import multiprocessing.managers
from urllib.error import URLError
from urllib.request import urlopen

import pytest
import sqlalchemy
import flask_migrate
import sqlalchemy.orm as orm
import flask_jwt_extended as flask_jwt
from flask import _app_ctx_stack as ctx_stack
from sqlalchemy import create_engine
from werkzeug.local import LocalProxy
from sqlalchemy_utils.functions import drop_database, create_database

TESTDB = 'test_project.db'
TESTDB_PATH = "/tmp/psef/psef-{}-{}".format(TESTDB, random.random())
TEST_DATABASE_URI = 'sqlite:///' + TESTDB_PATH
LIVE_SERVER_PORT = random.randint(5001, 6001)

_DATABASE = None

FreshDatabase = collections.namedtuple(
    'FreshDatabase', ['engine', 'name', 'db_name', 'run_psql']
)

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

if True:
    import psef
    import manage
    import helpers
    import psef.auth as a
    import psef.models as m
    from helpers import create_error_template, create_user_with_perms
    from lxc_stubs import lxc_stub
    from cg_dt_utils import DatetimeWithTimezone
    from psef.permissions import CoursePermission as CPerm


def get_database_name(request):
    global _DATABASE

    if _DATABASE is None:
        _DATABASE = (request.config.getoption('--postgresql'), False)
        if _DATABASE[0] == 'GENERATE':
            with get_fresh_database(keep=True) as fresh:
                _DATABASE = (fresh.name, True)

    return _DATABASE


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--postgresql",
            action="store",
            default='GENERATE',
            help="Run the test using postresql"
        )
    except ValueError:
        pass


@pytest.fixture(scope='session')
def make_app_settings(request):
    def inner(database=None):
        auto_test_password = uuid.uuid4().hex
        settings_override = {
            'TESTING': True,
            'DEBUG': True,
            'UPLOAD_DIR': f'/tmp/psef/uploads',
            'RATELIMIT_STRATEGY': 'moving-window',
            'RATELIMIT_HEADERS_ENABLED': True,
            'CELERY_CONFIG': {
                'BROKER_URL': 'redis:///', 'BACKEND_URL': 'redis:///'
            },
            'MIRROR_UPLOAD_DIR': f'/tmp/psef/mirror_uploads',
            'MAX_FILE_SIZE': 2 ** 20,  # 1mb
            'MAX_NORMAL_UPLOAD_SIZE': 4 * 2 ** 20,  # 4 mb
            'MAX_LARGE_UPLOAD_SIZE': 100 * 2 ** 20,  # 100mb
            'LTI_CONSUMER_KEY_SECRETS': {
                'my_lti': ('Canvas', ['12345678']),
                'canvas2': ('Canvas', ['123456789']),
                'unknown_lms': ('unknown', ['12345678']),
                'blackboard_lti': ('Blackboard', ['12345678']),
                'moodle_lti': ('Moodle', ['12345678']),
                'sakai_lti': ('Sakai', ['12345678']),
                'brightspace_lti': ('BrightSpace', ['12345678']),
            },
            'LTI_SECRET_KEY': 'hunter123',
            'SECRET_KEY': 'hunter321',
            'HEALTH_KEY': 'uuyahdsdsdiufhaiwueyrriu2h3',
            'CHECKSTYLE_PROGRAM': [
                "java",
                "-Dbasedir={files}",
                "-jar",
                os.path.join(
                    os.path.dirname(__file__), '..', 'checkstyle.jar'
                ),
                "-f",
                "xml",
                "-c",
                "{config}",
                "{files}",
            ],
            'PMD_PROGRAM': [
                os.path.join(
                    os.path.dirname(__file__), '..', './pmd/bin/run.sh'
                ),
                'pmd',
                '-dir',
                '{files}',
                '-failOnViolation',
                'false',
                '-format',
                'csv',
                '-shortnames',
                '-rulesets',
                '{config}',
            ],
            'MIN_PASSWORD_SCORE': 3,
            'AUTO_TEST_PASSWORD': auto_test_password,
            'AUTO_TEST_CF_EXTRA_AMOUNT': 2,
            'AUTO_TEST_CF_SLEEP_TIME': 5.0,
            'AUTO_TEST_RUNNER_INSTANCE_PASS': auto_test_password,
            'AUTO_TEST_DISABLE_ORIGIN_CHECK': True,
            'AUTO_TEST_MAX_TIME_COMMAND': 3,
            'ADMIN_USER': None,
            'CELERY_CONFIG': {
                'CELERY_TASK_ALWAYS_EAGER': True,
                'CELERY_TASK_EAGER_PROPAGATES': True,
            },
        }
        if database is not None:
            settings_override['SQLALCHEMY_DATABASE_URI'] = database
        elif request.config.getoption('--postgresql'):
            pdb, _ = get_database_name(request)

            settings_override['SQLALCHEMY_DATABASE_URI'] = pdb
            settings_override['_USING_SQLITE'] = False
        else:
            settings_override['SQLALCHEMY_DATABASE_URI'] = TEST_DATABASE_URI
            settings_override['_USING_SQLITE'] = True

        return settings_override

    yield inner


@pytest.fixture(scope='session')
def app(request, make_app_settings):
    """Session-wide test `Flask` application."""
    settings_override = make_app_settings()

    app = psef.create_app(
        settings_override, skip_celery=True, skip_perm_check=True
    )
    app.config['__S_FEATURES']['GROUPS'] = True
    app.config['FEATURES'][psef.features.Feature.GROUPS] = True

    app.config['__S_FEATURES']['AUTO_TEST'] = True
    app.config['FEATURES'][psef.features.Feature.AUTO_TEST] = True

    app.config['__S_FEATURES']['INCREMENTAL_RUBRIC_SUBMISSION'] = True
    app.config['FEATURES'][psef.features.Feature.INCREMENTAL_RUBRIC_SUBMISSION
                           ] = True

    app.config['__S_FEATURES']['COURSE_REGISTER'] = True
    app.config['FEATURES'][psef.features.Feature.COURSE_REGISTER] = True

    app.config['__S_FEATURES']['RENDER_HTML'] = True
    app.config['FEATURES'][psef.features.Feature.RENDER_HTML] = True

    app.config['__S_FEATURES']['PEER_FEEDBACK'] = True
    app.config['FEATURES'][psef.features.Feature.PEER_FEEDBACK] = True

    psef.tasks.celery.conf.update({
        'task_always_eager': False,
        'task_eager_propagates': False,
    })

    # Establish an application context before running the tests.
    with app.app_context():

        class FlaskTestClientProxy(object):
            def __init__(self, app):
                self.app = app

            def __call__(self, environ, start_response):
                if (
                    _TOKENS and _TOKENS[-1] is not None and
                    'HTTP_AUTHORIZATION' not in environ
                ):
                    environ['HTTP_AUTHORIZATION'] = f'Bearer {_TOKENS[-1]}'
                return self.app(environ, start_response)

        app.wsgi_app = FlaskTestClientProxy(app.wsgi_app)

        yield app


@pytest.fixture
def test_client(app, session, assert_similar):
    client = app.test_client()

    def req(
        method,
        url,
        status_code,
        result=None,
        query=None,
        data=None,
        real_data=None,
        include_response=False,
        allow_extra=False,
        expected_warning=None,
        **kwargs
    ):
        setattr(ctx_stack.top, 'jwt_user', None)
        if real_data is None:
            data = json.dumps(data) if data is not None else None
            if data:
                kwargs['content_type'] = 'application/json'
        else:
            data = real_data
        rv = getattr(client, method)(
            url,
            query_string=query,
            data=data,
            **kwargs,
        )
        assert rv.status_code == status_code

        if status_code == 204:
            assert rv.get_data(as_text=True) == ''
            assert result is None
            res = None
        else:
            val = json.loads(rv.get_data(as_text=True))
            res = copy.deepcopy(val)

        if result is not None:
            assert_similar(val, result)

        if expected_warning is not None:
            if expected_warning is False:
                assert 'Warning' not in rv.headers
            else:
                assert re.search(expected_warning, rv.headers['Warning'])

        session.expire_all()

        if include_response:
            return res, rv
        return res

    client.req = req
    psef.limiter._LIMITER.reset()
    yield client


@pytest.fixture
def error_template():
    yield create_error_template()


@pytest.fixture(params=[True, False])
def boolean(request):
    yield request.param


_TOKENS = []


@pytest.fixture(autouse=True)
def clear_logged_in_user():
    setattr(ctx_stack.top, 'jwt_user', None)
    yield


@pytest.fixture
def assert_similar():
    def checker(vals, tree, cur_path):
        is_list = isinstance(tree, list)
        i = 0
        allowed_extra = False
        not_allowed_extra = set()

        for k, value in enumerate(tree) if is_list else tree.items():
            if isinstance(value, LocalProxy):
                value = value._get_current_object()

            if k == '__allow_extra__' and value:
                allowed_extra = True
                if not isinstance(value, bool):
                    not_allowed_extra = set(value)
                continue
            elif not is_list and k[0] == '?' and k[-1] == '?':
                k = k[1:-1]
                if k not in vals:
                    continue
            i += 1
            assert is_list or k in vals

            if isinstance(value, psef.models.Base):
                import cg_json
                value = cg_json.JSONResponse.dump_to_object(value)
            elif isinstance(value, datetime.datetime):
                value = value.isoformat()

            if isinstance(value, type):
                assert isinstance(vals[k], value), (
                    "Wrong type for key '{}', expected '{}', got '{}'"
                ).format('.'.join(cur_path + [str(k)]), value, vals[k])
            elif isinstance(value, list) or isinstance(value, dict):
                if isinstance(vals, dict):
                    assert k in vals
                else:
                    assert 0 <= k < len(vals)
                checker(vals[k], value, cur_path + [str(k)])
            elif isinstance(value, re.Pattern):
                assert value.search(vals[k]), (
                    "Wrong value for key '{}', expected something to match"
                    " with '{}', got '{}'"
                ).format(
                    '.'.join(cur_path + [str(k)]), value.pattern, vals[k]
                )
            elif callable(value):
                assert value(vals[k]), (
                    'The function {} did not return true for {} at the path {}'
                ).format(value, vals[k], '.'.join(cur_path + [str(k)]))
            else:
                assert vals[k] == value, (
                    "Wrong value for key '{}', expected '{} (type={})', got '{}'"
                ).format(
                    '.'.join(cur_path + [str(k)]), value, type(value), vals[k]
                )

        if is_list:
            assert len(
                vals
            ) == i, 'Length of lists is not equal at {}: {} vs {}'.format(
                '.'.join(cur_path), len(vals), i
            )
        elif not allowed_extra:
            assert len(vals) == i, (
                'Difference in keys: {}, (server data: {}, expected: {})'
            ).format(set(vals) ^ set(tree), vals, tree)
        else:
            gotten_disallowed_keys = (set(vals.keys()) & not_allowed_extra)
            assert not gotten_disallowed_keys, (
                'Got disallowed keys: {}'
            ).format(gotten_disallowed_keys)

    yield lambda val, result: checker({'top': val}, {'top': result}, [])


@pytest.fixture(autouse=True)
def logged_in():
    @contextlib.contextmanager
    def _login(user, yield_token=False):
        setattr(ctx_stack.top, 'jwt_user', None)
        if isinstance(user, str) and user == 'NOT_LOGGED_IN':
            _TOKENS.append(None)
            res = None
        else:
            _TOKENS.append(
                helpers.to_db_object(user, m.User).make_access_token()
            )
            res = user

        yield _TOKENS[-1] if yield_token else res

        _TOKENS.pop(-1)
        setattr(ctx_stack.top, 'jwt_user', None)

    yield _login
    _TOKENS.clear()

    _TOKENS.clear()


@pytest.fixture
def named_user(session, request):
    if request.param == 'NOT_LOGGED_IN':
        return 'NOT_LOGGED_IN'
    return LocalProxy(session.query(m.User).filter_by(name=request.param).one)


@pytest.fixture
def student_user(session):
    return LocalProxy(session.query(m.User).filter_by(name="Student1").one)


@pytest.fixture
def user_with_perms(session, request, course_name):
    course = session.query(m.Course).filter_by(name=course_name).one()
    yield create_user_with_perms(session, request.param, course)


@pytest.fixture
def teacher_user(session):
    return LocalProxy(session.query(m.User).filter_by(name="Robin").one)


@pytest.fixture
def ta_user(session):
    return LocalProxy(
        session.query(m.User).filter_by(name="Thomas Schaper").one
    )


@pytest.fixture
def admin_user(session):
    return LocalProxy(session.query(m.User).filter_by(name="admin").one)


@pytest.fixture
def pse_course(session):
    return session.query(m.Course
                         ).filter_by(name="Project Software Engineering").one()


@pytest.fixture
def prog_course(session):
    yield m.Course.query.filter_by(name='Programmeertalen').one()


@pytest.fixture
def inprog_course(session):
    yield m.Course.query.filter_by(name='Inleiding Programmeren').one()


@pytest.fixture
def bs_course(session):
    return session.query(m.Course).filter_by(name="Besturingssystemen").one()


@pytest.fixture
def prolog_course(session):
    return session.query(
        m.Course
    ).filter_by(name="Introductie Logisch programmeren").one()


@pytest.fixture(scope='session', autouse=True)
def _db(app, request):
    """Session-wide test database."""
    if os.path.exists(TESTDB_PATH):
        os.unlink(TESTDB_PATH)

    if not request.config.getoption('--postgresql'):
        psef.models.db.create_all()
    else:
        db_name, generated = get_database_name(request)
        if generated:
            psef.models.db.create_all()

    manage.app = app
    manage.seed_force(psef.models.db)
    manage.test_data(psef.models.db)

    assert psef.models.Permission.query.all()
    psef.permissions.database_permissions_sanity_check(app)

    try:
        yield psef.models.db
    finally:
        if request.config.getoption('--postgresql'):
            db_name, generated = get_database_name(request)
            if generated:
                orm.session.close_all_sessions()
                psef.models.db.engine.dispose()
                drop_database(db_name)
        else:
            os.unlink(TESTDB_PATH)


@pytest.fixture(params=[False])
def fresh_db(request):
    yield request.param


@contextlib.contextmanager
def get_fresh_database(keep=False):
    db_name = f'migration_test_db_{uuid.uuid4()}'.replace('-', '')

    host = os.getenv('POSTGRES_HOST')
    password = os.getenv('PGPASSWORD')
    port = os.getenv('POSTGRES_PORT')
    username = os.getenv('POSTGRES_USERNAME')
    assert bool(host) == bool(port) == bool(username) == bool(password)
    psql_host_info = bool(host)

    def run_psql(*args):
        base = ['psql']
        if psql_host_info:
            base.extend(['-h', host, '-p', port, '-U', username])

        return subprocess.check_call(
            [*base, *args],
            stderr=subprocess.STDOUT,
            text=True,
        )

    run_psql('-c', f'create database "{db_name}"')
    try:
        run_psql(db_name, '-c', 'create extension "uuid-ossp"')
        run_psql(db_name, '-c', 'create extension "citext"')
        if psql_host_info:
            db_string = f'postgresql://{username}:{password}@{host}:{port}/{db_name}'
        else:
            db_string = f'postgresql:///{db_name}'

        engine = create_engine(db_string)
        yield FreshDatabase(
            engine=engine, name=db_string, db_name=db_name, run_psql=run_psql
        )
    finally:
        engine.dispose()
        if not keep:
            run_psql('-c', f'drop database "{db_name}"')


@pytest.fixture
def db(_db, fresh_db, monkeypatch, app):
    if fresh_db:
        with get_fresh_database(keep=True) as fresh:
            monkeypatch.setitem(
                app.config, 'SQLALCHEMY_DATABASE_URI', fresh.name
            )

            yield psef.models.db
    else:
        yield _db


@pytest.fixture(autouse=True)
def session(app, db, fresh_db, monkeypatch):
    """Creates a new database session for a test."""
    connection = db.engine.connect()
    if not fresh_db:
        transaction = connection.begin()

    options = dict(bind=connection, binds={}, autoflush=False)
    session = db.create_scoped_session(options=options)

    old_uri = app.config['SQLALCHEMY_DATABASE_URI']

    if not fresh_db:
        session.begin_nested()

        # then each time that SAVEPOINT ends, reopen it
        @sqlalchemy.event.listens_for(session, 'after_transaction_end')
        def restart_savepoint(session, transaction):
            if transaction.nested and not transaction._parent.nested:
                # ensure that state is expired the way
                # session.commit() at the top level normally does
                # (optional step)
                session.expire_all()

                session.begin_nested()

    if fresh_db:
        with app.app_context():
            from flask_migrate import Migrate
            from flask_migrate import upgrade as db_upgrade
            logging.disable(logging.ERROR)
            Migrate(app, db)
            db_upgrade()
            logging.disable(logging.NOTSET)
        manage.seed_force(psef.models.db)
        manage.test_data(psef.models.db)

    try:
        psef.models.validator._update_session(session)
        with monkeypatch.context() as context:
            context.setattr(psef.models.db, 'session', session)
            if not fresh_db:
                context.setattr(session, 'remove', lambda: None)
            yield session
    finally:
        if not fresh_db:
            sqlalchemy.event.remove(
                session, 'after_transaction_end', restart_savepoint
            )
            transaction.rollback()

        try:
            session.remove()
            connection.close()
        except:
            import traceback
            traceback.print_exc(file=sys.stderr)
            raise

        if fresh_db:
            db.engine.dispose()
            db.drop_all()
            drop_database(old_uri)


@pytest.fixture(autouse=True)
def monkeypatch_celery(app, monkeypatch):
    monkeypatch.setattr(psef.tasks.celery.conf, 'task_always_eager', True)
    monkeypatch.setattr(psef.tasks.celery.conf, 'task_eager_propagates', True)
    yield


@pytest.fixture(params=['Programmeertalen'])
def course_name(request):
    yield request.param


@pytest.fixture
def course(session, course_name):
    yield LocalProxy(session.query(m.Course).filter_by(name=course_name).first)


@pytest.fixture
def describe():
    class Describe:
        def __init__(self):
            self._hooks = []

        def add_hook(self, hook):
            self._hooks.append(hook)

        @contextlib.contextmanager
        def __call__(self, name):
            print()
            sep = '+={}=+'.format('=' * len(name))
            print(sep)
            print('|', name, '|')
            print(sep)
            print()
            sys.stdout.flush()
            yield
            for hook in self._hooks:
                hook()

    yield Describe()


@pytest.fixture(params=[False])
def state_is_hidden(request):
    yield request.param


@pytest.fixture(params=[False])
def with_works(request):
    yield request.param


@pytest.fixture(params=['new'])
def assignment(course_name, state_is_hidden, session, request, with_works):
    course = m.Course.query.filter_by(name=course_name).one()
    state = (
        m.AssignmentStateEnum.hidden
        if state_is_hidden else m.AssignmentStateEnum.open
    )
    assig = m.Assignment(
        name='TEST COURSE',
        state=state,
        course=course,
        deadline=DatetimeWithTimezone.utcnow() +
        datetime.timedelta(days=1 if request.param == 'new' else -1),
        is_lti=False,
    )
    session.add(assig)
    session.commit()

    if with_works:
        names = ['Student1', 'Student2', 'Student3', 'Œlµo']
        if with_works != 'single':
            names += names
        for uname in names:
            user = m.User.query.filter_by(name=uname).one()
            work = m.Work(assignment=assig, user=user)
            session.add(work)
        session.commit()

    yield assig


@pytest.fixture
def filename(request):
    yield request.param


@pytest.fixture
def stub_function(stub_function_class, session, monkeypatch):
    class inner_stub_function:
        def __init__(self, mk):
            self.mk = mk

        def __call__(self, *args, **kwargs):
            return self.stub(*args, **kwargs)

        def stub(self, module, name, *args, **kwargs):
            stub = stub_function_class(*args, **kwargs)
            self.mk.setattr(module, name, stub)
            return stub

        @contextlib.contextmanager
        def temp_stubs(self):
            with self.mk.context() as ctx:
                yield type(self)(ctx)

    yield inner_stub_function(monkeypatch)


@pytest.fixture
def watch_signal(stub_function_class, session):
    undos = []
    idx = 0

    def make_watcher(signal, *, flush_db=False, clear_all_but=False):
        nonlocal idx
        idx += 1

        def maybe_flush():
            if flush_db:
                session.flush()

        class Watcher(stub_function_class):
            __name__ = f'signal_watcher_{idx}'

            @property
            def send_amount(self):
                return len(self.args)

            @property
            def signal_arg(self):
                # This property only makes sense if the signal was send exactly
                # once
                assert self.was_send_once
                all_args = self.all_args
                assert len(all_args[0]) == 1
                return all_args[0][0]

            @property
            def was_send_once(self):
                return self.was_send_n_times(1)

            @property
            def was_not_send(self):
                return len(self.args) == 0

            def was_send_n_times(self, n):
                return self.called_amount == n

        watcher = Watcher(maybe_flush)

        if clear_all_but is not False:
            assert all(signal.is_connected(f) for f in clear_all_but)
            undos.append(signal.disable_all_but(clear_all_but))
        signal.connect_immediate(watcher)
        if clear_all_but is False:
            undos.append(lambda: signal.disconnect(watcher))

        return watcher

    yield make_watcher

    for undo in undos:
        undo()


@pytest.fixture
def make_function_spy(monkeypatch, stub_function_class):
    def make_spy(module, name, *, pass_self=False):
        orig = getattr(module, name)
        spy = stub_function_class(orig, with_args=True, pass_self=pass_self)
        monkeypatch.setattr(module, name, spy)
        return spy

    yield make_spy


@pytest.fixture
def stub_function_class(describe):
    class StubFunction:
        def __init__(
            self, ret_func=lambda: None, with_args=False, pass_self=False
        ):
            self.args = []
            self.kwargs = []
            self.rets = []
            self.ret_func = ret_func
            self.with_args = with_args
            self.call_dates = []
            self.pass_self = pass_self
            describe.add_hook(self.reset)

        def __call__(self, *args, **kwargs):
            return self.make_callable(self.ret_func)(*args, **kwargs)

        def set_impl(self, fn):
            self.ret_func = fn

        @property
        def all_args(self):
            def merge(args, kwargs):
                res = {idx: val for idx, val in enumerate(args)}
                res.update(kwargs)
                return res

            return [merge(a, k) for a, k in zip(self.args, self.kwargs)]

        def __get__(self, obj, typ=None):
            if self.pass_self:
                func = self.ret_func.__get__(obj, typ)
                return self.make_callable(func)
            return self.__call__

        def make_callable(self, func):
            def inner(*args, **kwargs):
                self.args.append(args)
                self.kwargs.append(kwargs)
                self.call_dates.append(DatetimeWithTimezone.utcnow())

                if self.with_args:
                    self.rets.append(func(*args, **kwargs))
                else:
                    self.rets.append(func())

                return self.rets[-1]

            return inner

        @property
        def called(self):
            return self.called_amount > 0

        @property
        def called_amount(self):
            assert len(self.args) == len(self.kwargs)
            return len(self.args)

        def reset(self):
            self.args = []
            self.kwargs = []
            self.rets = []
            self.call_dates = []

    yield StubFunction


@pytest.fixture
def assignment_real_works(
    filename,
    test_client,
    logged_in,
    assignment,
):
    res = []
    for name in ['Student1', 'Student2', 'Œlµo']:
        user = m.User.query.filter_by(name=name).one()
        with logged_in(user):
            res.append(
                test_client.req(
                    'post',
                    f'/api/v1/assignments/{assignment.id}/submission',
                    201,
                    real_data={
                        'file': (
                            f'{os.path.dirname(__file__)}/../'
                            f'test_data/test_linter/{filename}',
                            os.path.basename(os.path.realpath(filename))
                        )
                    }
                )
            )

    yield assignment, res[0]


@pytest.fixture
def live_server_url():
    yield f'http://localhost:{LIVE_SERVER_PORT}'


@pytest.fixture
def live_server(app, live_server_url, db):
    p = None

    def stop():
        if p is None:
            return

        from pytest_cov.embed import cleanup
        cleanup()

        for sig in [signal.SIGTERM, signal.SIGINT]:
            os.kill(p.pid, sig)
            try:
                p.join(4)
            except:
                pass
            else:
                break
        else:
            p.terminate()
            p.join()

    def start(get_stop=False):
        nonlocal p

        def _inner():
            from pytest_cov.embed import cleanup_on_sigterm
            cleanup_on_sigterm()
            app.run(
                host='localhost',
                port=LIVE_SERVER_PORT,
                debug=False,
                use_reloader=False,
                threaded=False
            )

        p = multiprocessing.Process(target=_inner)
        p.start()
        url = live_server_url

        for _ in range(15):
            try:
                urlopen(f'{url}/api/v1/about')
            except URLError:
                time.sleep(1)
                pass
            else:
                break
        else:
            stop()
            assert False, "Server on {} could not be reached".format(url)

        if get_stop:
            return url, stop
        return url

    try:
        yield start
    finally:
        stop()


@pytest.fixture
def stubmailer(monkeypatch, describe):
    class StubMailer():
        def __init__(self):
            self.msg = None
            self.do_raise = False
            self.called = 0
            self.args = []
            self.kwargs = []
            self.times_connect_called = 0
            describe.add_hook(self.reset)

        def send(self, msg):
            self.called += 1
            self.msg = msg
            self.args.append((msg, ))
            if self.do_raise:
                raise Exception

        def reset(self):
            self.msg = None
            self.args = []
            self.called = 0
            self.times_connect_called = 0

        @property
        def was_called(self):
            return self.called > 0

        @contextlib.contextmanager
        def connect(self):
            self.times_connect_called += 1
            yield self

        @property
        def times_called(self):
            return self.called

    mailer = StubMailer()

    monkeypatch.setattr(psef.mail, 'mail', mailer)

    yield mailer


@pytest.fixture
def tomorrow():
    yield DatetimeWithTimezone.utcnow() + datetime.timedelta(days=1)


@pytest.fixture
def yesterday():
    yield DatetimeWithTimezone.utcnow() - datetime.timedelta(days=1)


@pytest.fixture
def canvas_lti1p1_provider(session):
    prov = m.LTI1p1Provider(key='canvas2')
    session.add(prov)
    session.commit()
    yield prov


@pytest.fixture
def lti1p3_provider(logged_in, admin_user, test_client):
    with logged_in(admin_user):
        prov = helpers.to_db_object(
            helpers.create_lti1p3_provider(test_client, 'Canvas'),
            m.LTI1p3Provider
        )
    yield prov
