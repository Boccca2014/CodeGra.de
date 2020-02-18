"""This module implements the CodeGrade broker.

The broker keeps track of all jobs which need to be executed in a sandboxed
environment. Instances can submit jobs and the broker starts them using the
configured platform (e.g. AWS).

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import typing as t
import subprocess
from datetime import timedelta
from configparser import ConfigParser

import flask
from mypy_extensions import TypedDict

import cg_logger

if t.TYPE_CHECKING:
    from . import models

BrokerConfig = TypedDict(  # pylint: disable=invalid-name
    'BrokerConfig', {
        'DEBUG': bool,
        'SQLALCHEMY_TRACK_MODIFICATIONS': bool,
        'SQLALCHEMY_DATABASE_URI': str,
        'AUTO_TEST_TYPE': 'models.RunnerType',
        'AWS_INSTANCE_TYPE': str,
        'AWS_TAG_VALUE': str,
        'MAX_AMOUNT_OF_RUNNERS': int,
        'MAX_AMOUNT_OF_RUNNERS_PER_JOB': int,
        'CELERY_CONFIG': t.Dict,
        'RUNNER_MAX_TIME_ALIVE': int,
        'SECRET_KEY': str,
        'ADMIN_PASSWORD': str,
        'START_TIMEOUT_TIME': int,
        '_TRANSIP_USERNAME': str,
        '_TRANSIP_PRIVATE_KEY_FILE': str,
        'OLD_JOB_AGE': int,
        'SLOW_STARTING_AGE': int,
        'HEALTH_KEY': t.Optional[str],
        'RUNNER_CONFIG_DIR': str,
        'VERSION': str,
    }
)


class BrokerFlask(flask.Flask):
    """The flask class used by the broker.

    This class parses the configuration file used by the broker.
    """
    config: BrokerConfig  # type: ignore

    def __init__(self, name: str) -> None:
        super().__init__(name)

        def make_parser(case_sensitive: bool) -> ConfigParser:
            delimiters = ('=', )
            if case_sensitive:
                parser = ConfigParser(delimiters=delimiters)
                parser.optionxform = str  # type: ignore
            else:
                parser = ConfigParser(os.environ, delimiters=delimiters)

            config_file = os.getenv("BROKER_CONFIG_FILE", "broker_config.ini")
            parser.read(config_file)
            for req_cat in ['Testers', 'General', 'Instances']:
                if req_cat not in parser:
                    parser[req_cat] = {}
            return parser

        _parser = make_parser(False)

        self.heartbeat_interval = _parser['Testers'].getint(
            'INTERVAL', fallback=15
        )
        self.heartbeat_max_missed = _parser['Testers'].getint(
            'MAX_MISSED', fallback=5
        )
        self.auto_test_max_duration = timedelta(
            minutes=int(_parser['Testers'].get('MAX_DURATION', str(24 * 60)))
        )

        self.config['DEBUG'] = _parser['General'].getboolean(
            'DEBUG', fallback=False
        )
        self.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.config['SQLALCHEMY_DATABASE_URI'] = _parser['General'].get(
            'SQLALCHEMY_DATABASE_URI', 'postgresql:///codegrade_broker_dev'
        )

        if self.debug:
            self.config['AUTO_TEST_TYPE'] = models.RunnerType.dev_runner
        else:
            self.config['AUTO_TEST_TYPE'] = models.RunnerType[
                _parser['General'].get('RUNNER_TYPE', 'aws')]

        self.config['AWS_INSTANCE_TYPE'] = _parser['General'].get(
            'AWS_INSTANCE_TYPE', 't3.medium'
        )
        self.config['AWS_TAG_VALUE'] = _parser['General'].get(
            'AWS_TAG_VALUE', 'normal'
        )

        self.config['START_TIMEOUT_TIME'] = _parser['General'].getint(
            'START_TIMEOUT_TIME', fallback=9
        )

        self.config['OLD_JOB_AGE'] = _parser['General'].getint(
            'OLD_JOB_AGE', fallback=90
        )
        self.config['SLOW_STARTING_AGE'] = _parser['General'].getint(
            'SLOW_STARTING_AGE', fallback=1
        )

        self.config['MAX_AMOUNT_OF_RUNNERS'] = _parser['General'].getint(
            'MAX_AMOUNT_OF_RUNNERS', fallback=1
        )

        self.config['MAX_AMOUNT_OF_RUNNERS_PER_JOB'
                    ] = _parser['General'].getint(
                        'MAX_AMOUNT_OF_RUNNERS', fallback=1
                    )

        self.config['RUNNER_MAX_TIME_ALIVE'] = _parser['General'].getint(
            'RUNNER_MAX_TIME_ALIVE', fallback=60
        )

        self.config['_TRANSIP_USERNAME'] = _parser['General'].get(
            'TRANSIP_USERNAME', ''
        )
        self.config['_TRANSIP_PRIVATE_KEY_FILE'] = _parser['General'].get(
            'TRANSIP_PRIVATE_KEY_FILE', ''
        )

        self.config['SECRET_KEY'] = _parser['General']['SECRET_KEY']
        self.config['ADMIN_PASSWORD'] = _parser['General']['ADMIN_PASSWORD']

        self.config['HEALTH_KEY'] = _parser['General'].get('HEALTH_KEY', None)

        self.config['RUNNER_CONFIG_DIR'] = _parser['General'].get(
            'RUNNER_CONFIG_DIR', ''
        )

        try:
            self.config['VERSION'] = subprocess.check_output([
                'git', 'rev-parse', 'HEAD'
            ]).decode('utf-8').strip()
        except subprocess.SubprocessError:
            self.config['VERSION'] = 'unknown'

        # Convert parser to case sensitve
        _parser = make_parser(True)
        self.config['CELERY_CONFIG'] = dict(_parser['Celery'])

        self.allowed_instances: t.Dict[str, str] = dict(
            _parser['Instances'].items()
        )


if t.TYPE_CHECKING:
    app: 'BrokerFlask'
else:
    from flask import current_app as app


def create_app() -> flask.Flask:
    """Create a broker flask app.
    """
    # pylint: disable=redefined-outer-name, import-outside-toplevel
    from . import api, exceptions, models, tasks, admin_panel
    import cg_timers

    app = BrokerFlask(__name__)
    cg_logger.init_app(app, set_user=False)
    models.init_app(app)
    api.init_app(app)
    tasks.init_app(app)
    exceptions.init_app(app)
    admin_panel.init_app(app)
    cg_timers.init_app(app)

    if app.debug:
        tasks.add_1.delay(1, 2)

    return app
