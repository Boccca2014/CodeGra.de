"""This files contains the code to make the testing of migrations work.

This file does not contain the actual migration tests. The setup of these
migration tests was largely inspired by this repository:
https://github.com/freedomofpress/securedrop
"""
import os
import re
import uuid
import tempfile
import subprocess
import configparser
from os import path
from collections import namedtuple

import pytest
import alembic
from sqlalchemy import text, create_engine
from flask_migrate import Migrate
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

import psef
import migrations
from conftest import get_fresh_database

MIGRATION_PATH = path.join(path.dirname(__file__), '..', 'migrations')

ALL_MIGRATIONS = [
    x.split('.', 1)[0].split('_', 1)[0]
    for x in os.listdir(path.join(MIGRATION_PATH, 'versions'))
    if x.endswith('.py')
]

MIGRATIONS_TEST_DIR = path.join(path.dirname(__file__), 'migrations')
ALL_MIGRATION_TESTS = [
    re.match(r'migration_([0-9a-f]+)(\.py)?', x).group(1)
    for x in os.listdir(MIGRATIONS_TEST_DIR) if (
        x not in ('__init__.py', '__pycache__') and
        (x.endswith('.py') or path.isdir(path.join(MIGRATIONS_TEST_DIR, x)))
    )
]
assert ALL_MIGRATION_TESTS

ALL_TESTED_MIGRATIONS = []


def fill_all_tested_migrations():
    for migration in ALL_MIGRATIONS:
        if migration in ALL_MIGRATION_TESTS:
            ALL_TESTED_MIGRATIONS.append(migration)
            ALL_MIGRATION_TESTS.remove(migration)
            # Make sure pytest rewrites the assertions in these test files
            mod_name = 'migrations.migration_{}'.format(migration)
            pytest.register_assert_rewrite(mod_name)


fill_all_tested_migrations()
assert not ALL_MIGRATION_TESTS, 'Found unknown migrations'
assert ALL_TESTED_MIGRATIONS

WHITESPACE_REGEX = re.compile(r'\s+')


@pytest.fixture
def migration_app(make_app_settings, fresh_database):
    app = psef.create_app(
        make_app_settings(database=fresh_database.name),
        skip_celery=True,
        skip_perm_check=True
    )
    Migrate(app, psef.models.db, compare_type=True)
    yield app


@pytest.fixture
def fresh_database():
    with get_fresh_database() as db:
        yield db


@pytest.fixture
def alembic_config(fresh_database):
    ini = configparser.ConfigParser()
    ini.read(path.join(MIGRATION_PATH, 'alembic.ini'))
    ini.set('alembic', 'script_location', path.join(MIGRATION_PATH))
    ini.set('alembic', 'sqlalchemy.url', fresh_database.name)

    with tempfile.TemporaryDirectory() as tmp_dir:
        res = path.join(tmp_dir, 'alembic.ini')
        with open(res, 'w') as f:
            ini.write(f)
        yield res


def list_migrations(alembic_config, head):
    config = AlembicConfig(alembic_config)
    script = ScriptDirectory.from_config(config)
    migrations = [
        x.revision for x in script.walk_revisions(base='base', head=head)
    ]
    migrations.reverse()
    return migrations


@pytest.fixture
def upgrade(migration_app):
    def inner(alembic_config, migration):
        with migration_app.app_context():
            config = AlembicConfig(alembic_config)
            alembic.command.upgrade(config, migration, sql=False, tag=None)

    yield inner


@pytest.fixture
def downgrade(migration_app):
    def inner(alembic_config, migration):
        with migration_app.app_context():
            config = AlembicConfig(alembic_config)
            alembic.command.downgrade(config, migration, sql=False, tag=None)

    yield inner


@pytest.mark.parametrize('migration', ALL_TESTED_MIGRATIONS)
def test_upgrade_with_data(
    alembic_config, migration, fresh_database, migration_app, upgrade
):
    migrations = list_migrations(alembic_config, migration)
    if len(migrations) == 1:
        # Degenerate case where there is no data for the first migration
        return

    # Upgrade to one migration before the target stored in `migration`
    last_migration = migrations[-2]
    upgrade(alembic_config, last_migration)

    # Dynamic module import
    mod_name = 'migrations.migration_{}'.format(migration)
    mod = __import__(mod_name, fromlist=['UpgradeTester'])
    if not mod.UpgradeTester.do_test():
        pytest.skip('This upgrade is not tested')

    # Load the test data
    setup_sql = path.join(
        MIGRATIONS_TEST_DIR, f'migration_{migration}', 'setup_upgrade.sql'
    )
    if path.isfile(setup_sql) or path.islink(setup_sql):
        fresh_database.run_psql(
            '-d', fresh_database.db_name, '--set=ON_ERROR_STOP=1',
            '--set=ECHO=queries', '-f', setup_sql
        )

    upgrade_tester = mod.UpgradeTester(db=fresh_database)
    with migration_app.app_context():
        upgrade_tester.load_data()

    # Upgrade to the target
    upgrade(alembic_config, migration)

    # Make sure it applied "cleanly" for some definition of clean
    with migration_app.app_context():
        upgrade_tester.check()


@pytest.mark.parametrize('migration', ALL_TESTED_MIGRATIONS)
def test_downgrade_with_data(
    alembic_config, migration, fresh_database, downgrade, upgrade
):
    # Upgrade to the target
    upgrade(alembic_config, migration)

    # Dynamic module import
    mod_name = 'migrations.migration_{}'.format(migration)
    mod = __import__(mod_name, fromlist=['DowngradeTester'])
    if not mod.DowngradeTester.do_test():
        pytest.skip('This upgrade is not tested')

    # Load the test data
    setup_sql = path.join(
        MIGRATIONS_TEST_DIR, f'migration_{migration}', 'setup_downgrade.sql'
    )
    if path.isfile(setup_sql) or path.islink(setup_sql):
        fresh_database.run_psql(
            '-d', fresh_database.db_name, '--set=ON_ERROR_STOP=1',
            '--set=ECHO=queries', '-f', setup_sql
        )

    # Load the test data
    downgrade_tester = mod.DowngradeTester(db=fresh_database)
    downgrade_tester.load_data()

    # Downgrade to previous migration
    downgrade(alembic_config, '-1')

    # Make sure it applied "cleanly" for some definition of clean
    downgrade_tester.check()
