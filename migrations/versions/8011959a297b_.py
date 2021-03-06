"""Add AutoTest tables

Revision ID: 8011959a297b
Revises: f05ffa6bcca6
Create Date: 2019-05-02 15:22:30.939015

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8011959a297b'
down_revision = 'f05ffa6bcca6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('AutoTest',
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('base_systems', sa.JSON(), nullable=False),
    sa.Column('setup_script', sa.Unicode(), nullable=False),
    sa.Column('finalize_script', sa.Unicode(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('AutoTestFixture',
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('name', sa.Unicode(), nullable=False),
    sa.Column('filename', sa.Unicode(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('auto_test_id', sa.Integer(), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['auto_test_id'], ['AutoTest.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('AutoTestRun',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('auto_test_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['auto_test_id'], ['AutoTest.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('AutoTestSet',
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('stop_points', sa.Float(), nullable=False),
    sa.Column('auto_test_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['auto_test_id'], ['AutoTest.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('AutoTestResult',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('auto_test_run_id', sa.Integer(), nullable=False),
    sa.Column('points_achieved', sa.Float(), nullable=True),
    sa.Column('work_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['auto_test_run_id'], ['AutoTestRun.id'], ),
    sa.ForeignKeyConstraint(['work_id'], ['Work.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('AutoTestSuite',
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('rubric_row_id', sa.Integer(), nullable=False),
    sa.Column('auto_test_set_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['auto_test_set_id'], ['AutoTestSet.id'], ),
    sa.ForeignKeyConstraint(['rubric_row_id'], ['RubricRow.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('AutoTestStep',
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.Column('name', sa.Unicode(), nullable=False),
    sa.Column('weight', sa.Float(), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('auto_test_suite_id', sa.Integer(), nullable=False),
    sa.Column('test_type', sa.Enum('io_test', 'run_program', 'custom_output', 'check_points', name='autoteststeptesttype'), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['auto_test_suite_id'], ['AutoTestSuite.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('auto_test_step_result',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('auto_test_step_id', sa.Integer(), nullable=False),
    sa.Column('auto_test_result_id', sa.Integer(), nullable=True),
    sa.Column('state', sa.Enum('not_started', 'running', 'passed', 'failed', name='autoteststepresultstate'), nullable=False),
    sa.Column('log', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['auto_test_result_id'], ['AutoTestResult.id'], ),
    sa.ForeignKeyConstraint(['auto_test_step_id'], ['AutoTestStep.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('Assignment', sa.Column('auto_test_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'Assignment', 'AutoTest', ['auto_test_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'Assignment', type_='foreignkey')
    op.drop_column('Assignment', 'auto_test_id')
    op.drop_table('auto_test_step_result')
    op.drop_table('AutoTestStep')
    op.drop_table('AutoTestSuite')
    op.drop_table('AutoTestResult')
    op.drop_table('AutoTestSet')
    op.drop_table('AutoTestRun')
    op.drop_table('AutoTestFixture')
    op.drop_table('AutoTest')
    # ### end Alembic commands ###
