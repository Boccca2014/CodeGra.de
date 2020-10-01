#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# mypy: ignore-errors

import os
import sys
import json
import uuid
import shutil
import getpass
import datetime

import alembic_autogenerate_enums
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from sqlalchemy_utils import PasswordType

import psef
import cg_dt_utils
import psef.models as m


def render_item(type_, col, autogen_context):
    autogen_context.imports.add("import sqlalchemy_utils")
    if type_ == "type" and isinstance(col, PasswordType):
        return "sqlalchemy_utils.PasswordType"
    else:
        return False


app = psef.create_app(
    skip_celery=True,
    skip_perm_check=True,
    skip_secret_key_check=True,
)

migrate = Migrate(
    app, psef.models.db, render_item=render_item, compare_type=True
)
manager = Manager(app)

manager.add_command('db', MigrateCommand)


@manager.command
def seed():
    if not app.config['DEBUG']:
        print(
            'Seeding the database is NOT safe if there is data in'
            ' the database, please use seed_force to seed anyway',
            file=sys.stderr
        )
        return 1
    return seed_force()


@manager.command
def seed_force(db=None):
    db = psef.models.db if db is None else db

    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/seed_data/permissions.json',
        'r'
    ) as perms:
        perms = json.load(perms)
        for name, perm_data in perms.items():
            if perm_data['course_permission']:
                perm = psef.permissions.CoursePermission.get_by_name(name)
            else:
                perm = psef.permissions.GlobalPermission.get_by_name(name)

            old_perm = m.Permission.query.filter_by(value=perm).first()

            if old_perm is not None:
                old_perm.default_value = perm.value.default_value
                assert old_perm.course_permission == isinstance(
                    perm, psef.permissions.CoursePermission
                )
            else:
                db.session.add(
                    m.Permission(
                        _Permission__name=perm.name,
                        default_value=perm.value.default_value,
                        course_permission=isinstance(
                            perm, psef.permissions.CoursePermission
                        )
                    )
                )

    # Flush to make sure all new perms are in the db.
    db.session.flush()

    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/seed_data/roles.json',
        'r'
    ) as c:
        cs = json.load(c)
        for name, c in cs.items():
            perms = m.Permission.get_all_permissions(
                psef.permissions.GlobalPermission
            )
            r_perms = {}
            perms_set = set(c['permissions'])
            for perm in perms:
                if (perm.default_value ^ (perm.value.name in perms_set)):
                    r_perms[perm.value] = perm

            r = m.Role.query.filter_by(name=name).with_for_update().first()
            if r is None:
                db.session.add(m.Role(name=name, _permissions=r_perms))
            else:
                r._permissions = r_perms

    db.session.commit()


@manager.command
def create_user():
    db = psef.models.db

    name = input('Name of new user: ').strip('\n')
    username = input('Username of new user: ').strip('\n')
    prompt = 'Password of new user: '
    password = (
        getpass.getpass(prompt) if sys.stdin.isatty() else input(prompt)
    ).strip('\n')
    role = input('Role of new user: ').strip('\n')
    email = input('Email of new user: ').strip('\n')

    user = psef.models.User(
        username=username,
        password=password,
        role=psef.models.Role.query.filter_by(name=role).one(),
        name=name,
        email=email,
    )
    db.session.add(user)
    db.session.commit()


@manager.command
def delete_lti_provider():
    db = psef.models.db
    prov_id = input('id: ').strip()
    prov = psef.models.LTI1p3Provider.query.get(prov_id)
    db.session.delete(prov)
    db.session.commit()


@manager.command
def update_lti_provider():
    db = psef.models.db
    prov_id = input('id: ').strip()
    to_update = input('to update: ').strip()
    new_value = input('new value: ').strip()
    prov = psef.models.LTI1p3Provider.query.filter_by(id=prov_id).update({
        to_update: new_value,
    })
    db.session.commit()


@manager.command
def create_lti_provider():
    db = psef.models.db
    iss = input('ISS: ').strip()
    prov = psef.models.LTI1p3Provider.create_and_generate_keys(iss)
    db.session.add(prov)
    db.session.commit()
    print(prov.id)


@manager.command
def test_data(db=None):
    db = psef.models.db if db is None else db

    if not app.config['DEBUG']:
        print('You can not add test data in production mode', file=sys.stderr)
        return 1
    if not os.path.isdir(app.config['UPLOAD_DIR']):
        os.mkdir(app.config['UPLOAD_DIR'])

    seed()
    db.session.commit()
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/test_data/courses.json',
        'r'
    ) as c:
        cs = json.load(c)
        for c in cs:
            if m.Course.query.filter_by(name=c['name']).first() is None:
                db.session.add(m.Course.create_and_add(name=c['name']))
    db.session.commit()
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/test_data/assignments.json',
        'r'
    ) as c:
        cs = json.load(c)
        for c in cs:
            assig = m.Assignment.query.filter_by(name=c['name']).first()
            if assig is None:
                db.session.add(
                    m.Assignment(
                        name=c['name'],
                        deadline=cg_dt_utils.now() +
                        datetime.timedelta(days=c['deadline']),
                        state=c['state'],
                        description=c['description'],
                        course=m.Course.query.filter_by(name=c['course']
                                                        ).first(),
                        is_lti=False,
                    )
                )
            else:
                assig.description = c['description']
                assig.state = c['state']
                assig.course = m.Course.query.filter_by(name=c['course']
                                                        ).first()
    db.session.commit()
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/test_data/users.json',
        'r'
    ) as c:
        cs = json.load(c)
        for c in cs:
            u = m.User.query.filter_by(name=c['name']).first()
            courses = {
                m.Course.query.filter_by(name=name).first(): role
                for name, role in c['courses'].items()
            }
            perms = {
                course.id:
                m.CourseRole.query.filter_by(name=name,
                                             course_id=course.id).first()
                for course, name in courses.items()
            }
            username = c['name'].split(' ')[0].lower()
            if u is not None:
                u.name = c['name']
                u.courses = perms
                u.email = c['name'].replace(' ', '_').lower() + '@example.com'
                u.password = c['name']
                u.username = username
                u.role = m.Role.query.filter_by(name=c['role']).first()
            else:
                u = m.User(
                    name=c['name'],
                    courses=perms,
                    email=c['name'].replace(' ', '_').lower() + '@example.com',
                    password=c['name'],
                    username=username,
                    role=m.Role.query.filter_by(name=c['role']).first()
                )
                db.session.add(u)
                for course, role in courses.items():
                    if role == 'Student':
                        for assig in course.assignments:
                            work = m.Work(assignment=assig, user=u)
                            f = m.File(
                                work=work,
                                name='Top stub dir ({})'.format(u.name),
                                is_directory=True,
                                backing_file=None,
                                parent=None,
                            )
                            path = __file__
                            with app.file_storage.putter() as p:
                                backing_file = p.from_file(path, move=False)
                            f.children = [
                                m.File(
                                    work=work,
                                    name='manage.py',
                                    is_directory=False,
                                    backing_file=backing_file,
                                    parent=f,
                                )
                            ]
                            db.session.add(f)
                            db.session.add(work)
    db.session.commit()
    with open(
        f'{os.path.dirname(os.path.abspath(__file__))}/test_data/rubrics.json',
        'r'
    ) as c:
        cs = json.load(c)
        for c in cs:
            for row in c['rows']:
                assignment = m.Assignment.query.filter_by(
                    name=c['assignment']
                ).first()
                if assignment is not None:
                    rubric_row = m.RubricRow.query.filter_by(
                        header=row['header'],
                        description=row['description'],
                        assignment_id=assignment.id,
                    ).first()
                    if rubric_row is None:
                        rubric_row = m.RubricRow(
                            header=row['header'],
                            description=row['description'],
                            assignment=assignment,
                            rubric_row_type='normal',
                        )
                        db.session.add(rubric_row)
                    for item in row['items']:
                        if not db.session.query(
                            m.RubricItem.query.filter_by(
                                rubricrow_id=rubric_row.id,
                                **item,
                            ).exists()
                        ).scalar():
                            rubric_item = m.RubricItem(
                                description=item['description'] * 5,
                                header=item['header'],
                                points=item['points'],
                                rubricrow=rubric_row
                            )
                            db.session.add(rubric_item)
    db.session.commit()


if __name__ == '__main__':
    manager.run()
