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

if True:
    # Run the tests from `pytest_alembic` in this module
    from pytest_alembic.tests import (
        test_upgrade, test_single_head_revision,
        test_model_definitions_match_ddl
    )


@pytest.mark.parametrize('migration', ALL_TESTED_MIGRATIONS)
def test_upgrade_with_data(alembic_runner, migration, alembic_tests_db):
    alembic_runner.migrate_up_before(migration)

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
        alembic_tests_db.run_psql(
            '-d', alembic_tests_db.db_name, '--set=ON_ERROR_STOP=1',
            '--set=ECHO=queries', '-f', setup_sql
        )

    upgrade_tester = mod.UpgradeTester(db=alembic_tests_db)
    upgrade_tester.load_data()

    # Upgrade to the target
    alembic_runner.raw_command('upgrade', migration)

    # Make sure it applied "cleanly" for some definition of clean
    upgrade_tester.check()


@pytest.mark.parametrize('migration', ALL_TESTED_MIGRATIONS)
def test_downgrade_with_data(alembic_runner, migration, alembic_tests_db):
    # Dynamic module import
    mod_name = 'migrations.migration_{}'.format(migration)
    mod = __import__(mod_name, fromlist=['DowngradeTester'])
    if not mod.DowngradeTester.do_test():
        pytest.skip('This upgrade is not tested')

    # Upgrade to the target
    alembic_runner.raw_command('upgrade', migration)

    # Load the test data
    setup_sql = path.join(
        MIGRATIONS_TEST_DIR, f'migration_{migration}', 'setup_downgrade.sql'
    )
    if path.isfile(setup_sql) or path.islink(setup_sql):
        alembic_tests_db.run_psql(
            '-d',
            alembic_tests_db.db_name,
            '--set=ON_ERROR_STOP=1',
            '--set=ECHO=queries',
            '-f',
            setup_sql,
        )

    # Load the test data
    downgrade_tester = mod.DowngradeTester(db=alembic_tests_db)
    downgrade_tester.load_data()

    # Downgrade to previous migration
    alembic_runner.migrate_down_one()

    # Make sure it applied "cleanly" for some definition of clean
    downgrade_tester.check()
