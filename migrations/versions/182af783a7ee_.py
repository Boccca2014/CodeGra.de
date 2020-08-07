"""Add timezone information to proxy dates

Revision ID: 182af783a7ee
Revises: 1cdea6bbcaa6
Create Date: 2020-03-03 14:51:52.411675

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlalchemy_utils

# revision identifiers, used by Alembic.
revision = '182af783a7ee'
down_revision = '1cdea6bbcaa6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('AutoTestResult_auto_test_runner_id_fkey', 'AutoTestResult', type_='foreignkey')
    op.create_foreign_key(None, 'AutoTestResult', 'AutoTestRunner', ['auto_test_runner_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('AutoTestSet_auto_test_id_fkey', 'AutoTestSet', type_='foreignkey')
    op.create_foreign_key(None, 'AutoTestSet', 'AutoTest', ['auto_test_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('AutoTestSuite_auto_test_set_id_fkey', 'AutoTestSuite', type_='foreignkey')
    op.create_foreign_key(None, 'AutoTestSuite', 'AutoTestSet', ['auto_test_set_id'], ['id'], ondelete='CASCADE')
    op.alter_column('proxy', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.TIMESTAMP(timezone=True),
               existing_nullable=False)
    op.alter_column('proxy', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.TIMESTAMP(timezone=True),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('proxy', 'updated_at',
               existing_type=sa.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=False)
    op.alter_column('proxy', 'created_at',
               existing_type=sa.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=False)
    op.drop_constraint(None, 'AutoTestSuite', type_='foreignkey')
    op.create_foreign_key('AutoTestSuite_auto_test_set_id_fkey', 'AutoTestSuite', 'AutoTestSet', ['auto_test_set_id'], ['id'])
    op.drop_constraint(None, 'AutoTestSet', type_='foreignkey')
    op.create_foreign_key('AutoTestSet_auto_test_id_fkey', 'AutoTestSet', 'AutoTest', ['auto_test_id'], ['id'])
    op.drop_constraint(None, 'AutoTestResult', type_='foreignkey')
    op.create_foreign_key('AutoTestResult_auto_test_runner_id_fkey', 'AutoTestResult', 'AutoTestRunner', ['auto_test_runner_id'], ['id'])
    # ### end Alembic commands ###