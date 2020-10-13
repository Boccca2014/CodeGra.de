"""Add site settings tables

Revision ID: a7dff76ad19f
Revises: e4830dd710d6
Create Date: 2020-10-07 19:44:09.378929

"""
import os
from configparser import ConfigParser

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

import cg_json
from cg_dt_utils import DatetimeWithTimezone

# revision identifiers, used by Alembic.
revision = 'a7dff76ad19f'
down_revision = 'e4830dd710d6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    setting_table = op.create_table(
        'site_setting',
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('name', sa.Unicode(), nullable=False),
        sa.Column(
            'value', postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.PrimaryKeyConstraint('name'),
    )
    setting_history_table = op.create_table(
        'site_setting_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('name', sa.Unicode(), nullable=False),
        sa.Column(
            'old_value',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True
        ),
        sa.Column(
            'new_value',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True
        ),
        sa.ForeignKeyConstraint(
            ['name'],
            ['site_setting.name'],
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.getenv(
        'CODEGRADE_CONFIG_FILE',
        os.path.join(cur_dir, '..', '..', 'config.ini'),
    )

    now = DatetimeWithTimezone.utcnow()

    parser = ConfigParser({k: v for k, v in os.environ.items() if k.isupper()})
    if 'Back-end' not in parser:
        parser['Back-end'] = {}
    if 'Features' not in parser:
        parser['Features'] = {}
    if 'AutoTest' not in parser:
        parser['AutoTest'] = {}
    if 'Front-end' not in parser:
        parser['Front-end'] = {}

    parser.read(config_file)
    opts = [
        ('AutoTest', 'AUTO_TEST_MAX_TIME_COMMAND', int),
        ('AutoTest', 'AUTO_TEST_HEARTBEAT_INTERVAL', int),
        ('AutoTest', 'AUTO_TEST_HEARTBEAT_MAX_MISSED', int),
        ('AutoTest', 'AUTO_TEST_MAX_JOBS_PER_RUNNER', int),
        ('AutoTest', 'AUTO_TEST_MAX_CONCURRENT_BATCH_RUNS', int),

        ('Back-end', 'EXAM_LOGIN_MAX_LENGTH', int),
        ('Back-end', 'MIN_PASSWORD_SCORE', int),
        ('Back-end', 'MAX_NUMBER_OF_FILES', int),
        ('Back-end', 'MAX_LARGE_UPLOAD_SIZE', int),
        ('Back-end', 'MAX_NORMAL_UPLOAD_SIZE', int),
        ('Back-end', 'MAX_FILE_SIZE', int),
        ('Front-end', 'maxLines', 'MAX_LINES', int),
        ('Front-end', 'notificationPollTime', 'NOTIFICATION_POLL_TIME', int),
        ('Back-end', 'RESET_TOKEN_TIME', float),
        ('Back-end', 'SETTING_TOKEN_TIME', float),
        ('Back-end', 'SITE_EMAIL', str),
        ('Back-end', 'JWT_ACCESS_TOKEN_EXPIRES', str),
        ('Back-end', 'NOTIFICATION_POLL_TIME', str),
        (
            'Back-end', 'LOGIN_TOKEN_BEFORE_TIME',
            lambda x: [int(p.strip()) for p in x.split(',') if x.strip()]
        ),
        (
            'Features', 'BLACKBOARD_ZIP_UPLOAD',
            'BLACKBOARD_ZIP_UPLOAD_ENABLED', bool
        ),
        ('Features', 'RUBRICS', 'RUBRICS_ENABLED', bool),
        ('Features', 'AUTOMATIC_LTI_ROLE', 'AUTOMATIC_LTI_ROLE_ENABLED', bool),
        ('Features', 'LTI', 'LTI_ENABLED', bool),
        ('Features', 'LINTERS', 'LINTERS_ENABLED', bool),
        (
            'Features', 'INCREMENTAL_RUBRIC_SUBMISSION',
            'INCREMENTAL_RUBRIC_SUBMISSION_ENABLED', bool
        ),
        ('Features', 'REGISTER', 'REGISTER_ENABLED', bool),
        ('Features', 'GROUPS', 'GROUPS_ENABLED', bool),
        ('Features', 'AUTO_TEST', 'AUTO_TEST_ENABLED', bool),
        ('Features', 'COURSE_REGISTER', 'COURSE_REGISTER_ENABLED', bool),
        ('Features', 'RENDER_HTML', 'RENDER_HTML_ENABLED', bool),
        ('Features', 'EMAIL_STUDENTS', 'EMAIL_STUDENTS_ENABLED', bool),
        ('Features', 'PEER_FEEDBACK', 'PEER_FEEDBACK_ENABLED', bool),
    ]

    to_insert = []
    for opt in opts:
        if len(opt) == 3:
            section, name, converter = opt
            tag = name
        else:
            assert len(opt) == 4
            section, name, tag, converter = opt

        if converter == bool:
            val = parser[section].getboolean(name, None)
        else:
            val = parser[section].get(name, None)
            if val is not None:
                val = converter(val)

        if val is not None:
            to_insert.append((tag, cg_json.JSONResponse.dump_to_object(val)))

    op.bulk_insert(
        setting_table, [{
            'name': tag,
            'value': value,
            'created_at': now,
            'updated_at': now,
        } for tag, value in to_insert]
    )

    op.bulk_insert(
        setting_history_table, [{
            'name': tag,
            'old_value': None,
            'new_value': value,
            'created_at': now,
            'updated_at': now,
        } for tag, value in to_insert]
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('site_setting_history')
    op.drop_table('site_setting')
    # ### end Alembic commands ###