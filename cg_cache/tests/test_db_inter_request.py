import os
import time
import uuid
import subprocess
from datetime import timedelta

import pytest
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.ext.declarative

import cg_cache.inter_request as c


@pytest.fixture(params=[timedelta(seconds=1)])
def db_ttl(request):
    yield request.param


@pytest.fixture
def db_engine():
    db_name = f'cache_test_db_{uuid.uuid4().hex}'

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

        engine = sqlalchemy.create_engine(db_string)
        yield engine
    finally:
        engine.dispose()
        run_psql('-c', f'drop database "{db_name}"')


@pytest.fixture
def db_base():
    Base = sqlalchemy.ext.declarative.declarative_base()
    yield Base


@pytest.fixture
def db_session(db_engine):
    Session = sqlalchemy.orm.sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def db_table(db_base, db_engine):
    table = c.DBBackend.make_cache_table(db_base, 'cache')
    db_base.metadata.create_all(db_engine)
    yield table


@pytest.fixture
def db_cache(db_ttl, db_session, db_table):
    cache = c.DBBackend('ns', db_ttl, lambda: db_session, lambda: db_table)
    yield cache


@pytest.mark.parametrize('value', [5, 'abc', ['d'], {'a': 5, 'c': [1, 2, 3]}])
def test_db_set(db_cache, db_session, db_table, value):
    db_cache.set('test', value)

    stored = db_session.query(db_table).filter_by(key='test').one().value
    assert stored == value

    assert db_cache.get('test') == value


def test_db_ttl(db_cache, db_session, db_table, db_ttl):
    db_cache.set('test', 'should expire')
    time.sleep(db_ttl.total_seconds())
    # NOW() returns start time of the current transaction
    db_session.commit()

    with pytest.raises(KeyError):
        db_cache.get('test')


def test_db_clear(db_cache, db_session, db_table):
    for i in range(10):
        db_cache.set(f'test{i}', 'to be removed')
    db_session.commit()
    assert db_session.query(db_table).count() == 10

    for i in range(10):
        assert db_session.query(db_table).count() == 10 - i
        db_cache.clear(f'test{i}')
    assert db_session.query(db_table).count() == 0

    # Sessions are not committed
    db_session.rollback()
    assert db_session.query(db_table).count() == 10
