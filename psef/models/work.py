"""This module defines all work related tables.

SPDX-License-Identifier: AGPL-3.0-only
"""

import os
import enum
import typing as t
import zipfile
import tempfile
from collections import defaultdict

import sqlalchemy.sql as sql
from sqlalchemy import orm, select
from sqlalchemy.orm import undefer, selectinload
from sqlalchemy.types import JSON

import psef
import cg_timers
from cg_dt_utils import DatetimeWithTimezone
from cg_sqlalchemy_helpers import hybrid_property, hybrid_expression
from cg_sqlalchemy_helpers.types import DbColumn, ColumnProxy

from . import Base, DbColumn, db
from . import file as file_models
from . import user as user_models
from . import group as group_models
from . import _MyQuery
from . import assignment as assignment_models
from .. import auth, helpers, features
from .linter import LinterState, LinterComment, LinterInstance
from .rubric import RubricItem, WorkRubricItem
from .comment import Comment
from ..helpers import JSONType
from ..exceptions import PermissionException
from ..permissions import CoursePermission


class GradeOrigin(enum.Enum):
    """What is the origin of this grade history entry.
    """
    human = enum.auto()
    auto_test = enum.auto()


class GradeHistory(Base):
    """This object is a item in a grade history of a :class:`.Work`.

    :ivar ~.GradeHistory.changed_at: When was this grade added.
    :ivar ~.GradeHistory.is_rubric: Was this grade added as a result of a
        rubric.
    :ivar ~.GradeHistory.passed_back: Was this grade passed back to the LMS
        through LTI.
    :ivar ~.GradeHistory.work: What work does this grade belong to.
    :ivar ~.GradeHistory.user: What user added this grade.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query: t.ClassVar[_MyQuery['GradeHistory']] = Base.query
    __tablename__ = "GradeHistory"
    id = db.Column('id', db.Integer, primary_key=True)
    changed_at = db.Column(
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False,
    )
    is_rubric = db.Column('is_rubric', db.Boolean)
    grade = db.Column('grade', db.Float)
    passed_back = db.Column('passed_back', db.Boolean, default=False)

    work_id = db.Column(
        'Work_id',
        db.Integer,
        db.ForeignKey('Work.id', ondelete='CASCADE'),
        nullable=False,
    )
    user_id = db.Column(
        'User_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
    )

    grade_origin = db.Column(
        'grade_origin',
        db.Enum(GradeOrigin),
        nullable=False,
        server_default=GradeOrigin.human.name,
    )

    work = db.relationship(
        lambda: Work,
        foreign_keys=work_id,
        backref=db.backref(
            'grade_histories', lazy='select', cascade='all,delete'
        ),
        innerjoin=True,
    )

    user = db.relationship(lambda: user_models.User, foreign_keys=user_id)

    __table_args__ = (
        db.CheckConstraint(
            "grade_origin != 'human' OR \"User_id\" IS NOT NULL",
            name='grade_history_grade_origin_check',
        ),
    )

    def __to_json__(self) -> t.Mapping[str, t.Any]:
        """Converts a rubric of a work to a object that is JSON serializable.

        The resulting object will look like this:

        .. code:: python

            {
                'changed_at': str, # The date the history was added.
                'is_rubric': bool, # Was this history items added by a rubric
                                   # grade.
                'grade': float, # The new grade, -1 if the grade was deleted.
                'passed_back': bool, # Is this grade given back to LTI.
                'user': t.Optional[user_models.User], # The user that added this grade.
            }

        :returns: A object as described above.
        """
        return {
            'changed_at': self.changed_at.isoformat(),
            'is_rubric': self.is_rubric,
            'grade': self.grade,
            'passed_back': self.passed_back,
            'user': self.user,
            'origin': self.grade_origin.name,
        }


class WorkOrigin(enum.Enum):
    """What is the way the work was handed in.
    """
    uploaded_files = enum.auto()
    github = enum.auto()
    gitlab = enum.auto()


class Work(Base):
    """This object describes a single work or submission of a
    :class:`user_models.User` for an :class:`.assignment_models.Assignment`.
    """
    if t.TYPE_CHECKING:  # pragma: no cover
        query = Base.query  # type: t.ClassVar[_MyQuery['Work']]
    __tablename__ = "Work"  # type: str
    id = db.Column('id', db.Integer, primary_key=True)
    assignment_id = db.Column(
        'Assignment_id',
        db.Integer,
        db.ForeignKey('Assignment.id'),
        nullable=False,
    )
    user_id = db.Column(
        'User_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='CASCADE'),
        nullable=False,
    )
    _grade = db.Column('grade', db.Float, default=None, nullable=True)
    comment = orm.deferred(db.Column('comment', db.Unicode, default=None))
    comment_author_id = db.Column(
        'comment_author_id',
        db.Integer,
        db.ForeignKey('User.id', ondelete='SET NULL'),
        nullable=True,
    )

    orm.deferred(db.Column('comment', db.Unicode, default=None))
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        default=DatetimeWithTimezone.utcnow,
        nullable=False,
    )
    assigned_to = db.Column(
        'assigned_to', db.Integer, db.ForeignKey('User.id'), nullable=True
    )
    selected_items = db.relationship(
        lambda: WorkRubricItem, cascade='all, delete-orphan', uselist=True
    )

    assignment = db.relationship(
        lambda: assignment_models.Assignment,
        foreign_keys=assignment_id,
        lazy='joined',
        innerjoin=True,
        backref=db.backref('submissions', lazy='select', uselist=True)
    )
    comment_author = db.relationship(
        lambda: user_models.User,
        foreign_keys=comment_author_id,
        lazy='select'
    )
    user = db.relationship(
        lambda: user_models.User,
        foreign_keys=user_id,
        lazy='joined',
        innerjoin=True
    )
    assignee = db.relationship(
        lambda: user_models.User, foreign_keys=assigned_to, lazy='joined'
    )

    grade_histories: t.List['GradeHistory']

    _deleted = db.Column(
        'deleted',
        db.Boolean,
        default=False,
        server_default='false',
        nullable=False
    )
    origin = db.Column(
        'work_origin',
        db.Enum(WorkOrigin),
        nullable=False,
        server_default=WorkOrigin.uploaded_files.name,
    )
    extra_info: ColumnProxy[JSONType] = db.Column(
        'extra_info',
        JSON,
        nullable=True,
        default=None,
    )

    def _get_deleted(self) -> bool:
        """Is this submission deleted.
        """
        return self._deleted or self.assignment.deleted

    @hybrid_expression
    def _get_deleted_expr(cls: t.Type['Work']) -> 'DbColumn[bool]':
        """Get a query that checks if this submission is deleted.
        """
        # pylint: disable=no-self-argument
        return select(
            [sql.or_(cls._deleted, assignment_models.Assignment.deleted)]
        ).where(
            cls.assignment_id == assignment_models.Assignment.id,
        ).label('deleted')

    def _set_deleted(self, new_value: bool) -> None:
        self._deleted = new_value

    deleted = hybrid_property(
        _get_deleted, _set_deleted, None, _get_deleted_expr
    )

    def divide_new_work(self) -> None:
        """Divide a freshly created work.

        First we check if an old work of the same author exists, that case the
        same grader is assigned. Otherwise we take the grader that misses the
        most of work.

        :returns: Nothing
        """
        self.assigned_to = self.assignment.get_assignee_for_submission(self)

        if self.assigned_to is not None:
            self.assignment.set_graders_to_not_done(
                [self.assigned_to],
                send_mail=True,
                ignore_errors=True,
            )

    def run_linter(self) -> None:
        """Run all linters for the assignment on this work.

        All linters that have been used on the assignment will also run on this
        work.

        If the linters feature is disabled this function will simply return and
        not do anything.

        :returns: Nothing
        """
        if not features.has_feature(features.Feature.LINTERS):
            return

        for linter in self.assignment.linters:
            instance = LinterInstance(work=self, tester=linter)
            db.session.add(instance)

            if psef.linters.get_linter_by_name(linter.name).RUN_LINTER:
                db.session.flush()

                def _inner(name: str, config: str, lint_id: str) -> None:
                    lint = psef.tasks.lint_instances
                    psef.helpers.callback_after_this_request(
                        lambda: lint(name, config, [lint_id])
                    )

                _inner(
                    name=linter.name,
                    config=linter.config,
                    lint_id=instance.id,
                )
            else:
                instance.state = LinterState.done

    @property
    def grade(self) -> t.Optional[float]:
        """Get the actual current grade for this work.

        This is done by not only checking the ``grade`` field but also checking
        if rubric could be found.

        :returns: The current grade for this work.
        """
        if self._grade is None:
            if not self.selected_items:
                return None

            max_rubric_points = self.assignment.max_rubric_points
            assert max_rubric_points is not None

            selected = sum(item.points for item in self.selected_items)
            return helpers.between(
                self.assignment.min_grade,
                selected / max_rubric_points * 10,
                self.assignment.max_grade,
            )
        return self._grade

    @t.overload
    def set_grade(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self,
        new_grade: t.Optional[float],
        user: 'user_models.User',
        never_passback: bool = False,
    ) -> GradeHistory:
        ...

    @t.overload
    def set_grade(  # pylint: disable=function-redefined,missing-docstring,unused-argument,no-self-use
        self,
        *,
        never_passback: bool = False,
        grade_origin: GradeOrigin,
    ) -> GradeHistory:
        ...

    def set_grade(  # pylint: disable=function-redefined
        self,
        new_grade: t.Union[float, None, helpers.MissingType] = helpers.MISSING,
        user: t.Optional['user_models.User'] = None,
        never_passback: bool = False,
        grade_origin: GradeOrigin = GradeOrigin.human,
    ) -> GradeHistory:
        """Set the grade to the new grade.

        .. note:: This also passes back the grade to LTI if this is necessary
            (see :py:func:`passback_grade`).

        .. note:: If ``grade_origin`` is ``human`` the ``user`` is required.

        :param new_grade: The new grade to set
        :param user: The user setting the new grade.
        :param grade_origin: The way this grade was given.
        :param never_passback: Never passback the new grade.
        :returns: Nothing
        """
        assert grade_origin != GradeOrigin.human or user is not None

        if new_grade is not helpers.MISSING:
            assert isinstance(new_grade, (float, int, type(None)))
            self._grade = new_grade
        passback = self.assignment.should_passback
        grade = self.grade
        history = GradeHistory(
            is_rubric=self._grade is None and grade is not None,
            grade=-1 if grade is None else grade,
            passed_back=False,
            work=self,
            user=user,
            grade_origin=grade_origin,
        )
        self.grade_histories.append(history)

        if not never_passback and passback:
            work_id = self.id
            assignment_id = self.assignment_id
            helpers.callback_after_this_request(
                lambda: psef.tasks.passback_grades(
                    [work_id],
                    assignment_id=assignment_id,
                )
            )

        return history

    @property
    def selected_rubric_points(self) -> float:
        """The amount of points that are currently selected in the rubric for
        this work.
        """
        return sum(item.points for item in self.selected_items)

    def passback_grade(self, initial: bool = False) -> None:
        """Initiates a passback of the grade to the LTI consumer via the
        :class:`.LTIProvider`.

        :param initial: Should we do a initial LTI grade passback with no
            result so that the real grade won't show as too late.
        :returns: Nothing
        """
        if self.user.is_test_student:
            # We do not need to passback these grades, as they are not of a
            # real user.
            return
        lti_provider = self.assignment.course.lti_provider
        assert lti_provider

        lti_provider.passback_grade(self, initial)

        if not initial:
            newest_grade_history_id = db.session.query(
                t.cast(DbColumn[int], GradeHistory.id)
            ).filter_by(work_id=self.id).order_by(
                t.cast(
                    DbColumn[DatetimeWithTimezone], GradeHistory.changed_at
                ).desc(),
            ).limit(1).with_for_update()

            db.session.query(GradeHistory).filter(
                GradeHistory.id == newest_grade_history_id.as_scalar(),
            ).update({'passed_back': True}, synchronize_session='fetch')

    def select_rubric_items(
        self,
        items: t.List['WorkRubricItem'],
        user: 'user_models.User',
        override: bool = False
    ) -> None:
        """ Selects the given :class:`.RubricItem`.

        .. note:: This also passes back the grade to LTI if this is necessary.

        .. note:: This also sets the actual grade field to `None`.

        .. warning::

            You should do all input sanitation before calling this
            function. Like checking for duplicate items and correct assignment.

        :param item: The item to add.
        :param user: The user selecting the item.
        :returns: Nothing
        """
        # Sanity checks
        assert all(
            item.rubric_item.rubricrow.assignment_id == self.assignment_id
            for item in items
        )
        row_ids = [item.rubric_item.rubricrow_id for item in items]
        assert len(row_ids) == len(set(row_ids))

        if override:
            self.selected_items = []

        for item in items:
            self.selected_items.append(item)

        self.set_grade(None, user)

    def __to_json__(self) -> t.MutableMapping[str, t.Any]:
        """Returns the JSON serializable representation of this work.

        The representation is based on the permissions (:class:`.Permission`)
        of the logged in :class:`.user_models.User`. Namely the assignee,
        feedback, and grade attributes are only included if the current user
        can see them, otherwise they are set to `None`.

        The resulting object will look like this:

        .. code:: python

            {
                'id': int, # Submission id
                'user': user_models.User, # User that submitted this work.
                'created_at': str, # Submission date in ISO-8601 datetime
                                   # format.
                'grade': t.Optional[float], # Grade for this submission, or
                                            # None if the submission hasn't
                                            # been graded yet or if the
                                            # logged in user doesn't have
                                            # permission to see the grade.
                'assignee': t.Optional[user_models.User],
                                            # User assigned to grade this
                                            # submission, or None if the logged
                                            # in user doesn't have permission
                                            # to see the assignee.
                'grade_overridden': bool, # Does this submission have a
                                          # rubric grade which has been
                                          # overridden.
            }

        :returns: A dict containing JSON serializable representations of the
                  attributes of this work.
        """
        item = {
            'id': self.id,
            'user': self.user,
            'created_at': self.created_at.isoformat(),
            'origin': self.origin.name,
            'extra_info': self.extra_info,
            'grade': None,
            'grade_overridden': False,
            'assignee': None,
        }

        try:
            auth.ensure_permission(
                CoursePermission.can_see_assignee, self.assignment.course_id
            )
        except PermissionException:
            pass
        else:
            item['assignee'] = self.assignee

        try:
            auth.ensure_can_see_grade(self)
        except PermissionException:
            pass
        else:
            item['grade'] = self.grade
            item['grade_overridden'] = (
                self._grade is not None and
                self.assignment.max_rubric_points is not None
            )

        return item

    @cg_timers.timed_function(collect_in_request=True)
    def __extended_to_json__(self) -> t.Mapping[str, t.Any]:
        """Create a extended JSON serializable representation of this object.

        This object will look like this:

        .. code:: python

            {
                'comment': t.Optional[str] # General feedback comment for
                                           # this submission, or None in
                                           # the same cases as the grade.

                'comment_author': t.Optional[user_models.User] # The author of the
                                                        # comment field
                                                        # submission, or None
                                                        # if the logged in user
                                                        # doesn't have
                                                        # permission to see the
                                                        # assignee.
                **self.__to_json__()
            }

        :returns: A object as described above.
        """
        res: t.Dict[str, object] = {
            'comment': None,
            'comment_author': None,
            'assignment_id': self.assignment.id,
            'rubric_result': None,
            **self.__to_json__()
        }

        if self.assignment.rubric_rows:
            res['rubric_result'] = self.__rubric_to_json__()

        try:
            auth.ensure_can_see_user_feedback(self)
        except PermissionException:
            pass
        else:
            res['comment'] = self.comment
            if psef.current_user.has_permission(
                CoursePermission.can_see_assignee, self.assignment.course_id
            ):
                res['comment_author'] = self.comment_author

        return res

    def __rubric_to_json__(self) -> t.Mapping[str, t.Any]:
        """Converts a rubric of a work to a object that is JSON serializable.

        The resulting object will look like this:

        .. code:: python

            {
                'rubrics': t.List[RubricRow] # A list of all the rubrics for
                                             # this work.
                'selected': t.List[RubricItem] # A list of all the selected
                                               # rubric items for this work,
                                               # or an empty list if the logged
                                               # in user doesn't have
                                               # permission to see the rubric.
                'points': {
                    'max': t.Optional[float] # The maximal amount of points
                                                # for this rubric, or `None` if
                                                # logged in user doesn't have
                                                # permission to see the rubric.
                    'selected': t.Optional[float] # The amount of point that
                                                     # is selected for this
                                                     # work, or `None` if the
                                                     # logged in user doesn't
                                                     # have permission to see
                                                     # the rubric.
                }
            }

        :returns: A object as described above.

        .. todo:: Remove the points object.
        """
        res = {
            'rubrics': self.assignment.rubric_rows,
            'selected': [],
            'points': {
                'max': None,
                'selected': None,
            },
        }
        try:
            psef.auth.ensure_can_see_grade(self)
        except PermissionException:
            pass
        else:
            res['selected'] = self.selected_items
            res['points'] = {
                'max': self.assignment.max_rubric_points,
                'selected': self.selected_rubric_points,
            }

        return res

    def add_file_tree(
        self, tree: 'psef.files.ExtractFileTreeDirectory'
    ) -> None:
        """Add the given tree to as only files to the current work.

        .. warning:: All previous files will be unlinked from this assignment.

        :param tree: The file tree as described by
            :py:func:`psef.files.rename_directory_structure`
        :returns: Nothing
        """
        db.session.add(
            file_models.File.create_from_extract_directory(
                tree, None, {'work': self}
            )
        )

    def get_user_feedback(self) -> t.Iterable[str]:
        """Get all user given feedback for this work.

        :returns: An iterator producing human readable representations of the
            feedback given by a person.
        """
        comments = Comment.query.filter(
            Comment.file.has(work=self),
        ).order_by(
            Comment.file_id.asc(),
            Comment.line.asc(),
        )
        for com in comments:
            yield f'{com.file.get_path()}:{com.line + 1}:1: {com.comment}'

    def get_linter_feedback(self) -> t.Iterable[str]:
        """Get all linter feedback for this work.

        :returns: An iterator that produces the all feedback given on this work
            by linters.
        """
        linter_comments = LinterComment.query.filter(
            LinterComment.file.has(work=self)
        ).order_by(
            LinterComment.file_id.asc(),
            LinterComment.line.asc(),
        )
        for line_comm in linter_comments:
            yield (
                f'{line_comm.file.get_path()}:{line_comm.line + 1}:1: '
                f'({line_comm.linter.tester.name}'
                f' {line_comm.linter_code}) {line_comm.comment}'
            )

    def remove_selected_rubric_item(self, row_id: int) -> None:
        """Deselect selected :class:`.RubricItem` on row.

        Deselects the selected rubric item on the given row with _row_id_ (if
        there are any selected).

        :param row_id: The id of the RubricRow from which to deselect
                           rubric items
        :returns: Nothing
        """
        rubricitem = db.session.query(WorkRubricItem).join(
            RubricItem, RubricItem.id == WorkRubricItem.rubricitem_id
        ).filter(
            WorkRubricItem.work_id == self.id,
            RubricItem.rubricrow_id == row_id
        ).first()
        if rubricitem is not None:
            self.selected_items.remove(rubricitem)

    def search_file_filters(
        self,
        pathname: str,
        exclude: 'file_models.FileOwner',
    ) -> t.List[t.Any]:
        """Get the filters needed to search for a file in the this directory
        with a given name.

        :param pathname: The path of the file to search for, this may contain
            leading and trailing slashes which do not have any meaning.
        :param exclude: The fileowner to exclude from search, like described in
            :func:`get_zip`.
        :returns: The criteria needed to find the file with the given pathname.
        """
        patharr, is_dir = psef.files.split_path(pathname)

        parent: t.Optional[t.Any] = None
        for idx, pathpart in enumerate(patharr[:-1]):
            if parent is not None:
                parent = parent.c.id

            parent = db.session.query(
                t.cast(DbColumn[int], file_models.File.id)
            ).filter(
                file_models.File.name == pathpart,
                file_models.File.parent_id == parent,
                file_models.File.work_id == self.id,
                file_models.File.is_directory,
            ).subquery(f'parent_{idx}')

        if parent is not None:
            parent = parent.c.id

        return [
            file_models.File.work_id == self.id,
            file_models.File.name == patharr[-1],
            file_models.File.parent_id == parent,
            file_models.File.fileowner != exclude,
            file_models.File.is_directory == is_dir,
        ]

    def search_file(
        self,
        pathname: str,
        exclude: 'file_models.FileOwner',
    ) -> 'file_models.File':
        """Search for a file in the this directory with the given name.

        :param pathname: The path of the file to search for, this may contain
            leading and trailing slashes which do not have any meaning.
        :param exclude: The fileowner to exclude from search, like described in
            :func:`get_zip`.
        :returns: The found file.
        """

        return psef.helpers.filter_single_or_404(
            file_models.File,
            *self.search_file_filters(pathname, exclude),
        )

    def get_file_children_mapping(
        self, exclude: 'file_models.FileOwner'
    ) -> t.Mapping[t.Optional[int], t.Sequence['file_models.File']]:
        """Get a mapping that maps a file id to all its children.

        This implementation does a single query to the database and runs in
        O(n*log(n)), so it will be quite a bit quicker than using the
        `children` attribute on files if you are going to need all children or
        all files.

        The list of children is sorted on filename.

        :param exclude: The file owners to exclude
        :returns: A mapping from file id to list of all its children for this
            submission.
        """
        cache: t.Mapping[t.Optional[int], t.
                         List['file_models.File']] = defaultdict(list)
        files = file_models.File.query.filter(
            file_models.File.work == self,
            file_models.File.fileowner != exclude
        ).all()
        # We sort in Python as this increases consistency between different
        # server platforms, Python also has better defaults.
        # TODO: Investigate if sorting in the database first and sorting in
        # Python after is faster, as sorting in the database should be faster
        # overal and sorting an already sorted list in Python is really fast.
        files.sort(key=lambda el: el.name.lower())
        for f in files:
            cache[f.parent_id].append(f)

        return cache

    @staticmethod
    def limit_to_user_submissions(
        query: _MyQuery['Work'], user: 'user_models.User'
    ) -> _MyQuery['Work']:
        """Limit the given query of submissions to only submission submitted by
            the given user.

        .. note::

            This is not the same as filtering on the author field as this also
            checks for groups.

        :param query: The query to limit.
        :param user: The user to filter for.
        :returns: The filtered query.
        """
        # This query could be improved, but it seems fast enough. It now gets
        # every group of a user. This could be narrowed down probably.
        groups_of_user = group_models.Group.contains_users(
            [user]
        ).with_entities(
            t.cast(DbColumn[int], group_models.Group.virtual_user_id)
        )
        return query.filter(
            sql.or_(
                Work.user_id == user.id,
                t.cast(DbColumn[int], Work.user_id).in_(groups_of_user)
            )
        )

    def get_all_authors(self) -> t.List['user_models.User']:
        """Get all the authors of this submission.

        :returns: A list of users that were the authors of this submission.
        """
        if self.user.group:
            return list(self.user.group.members)
        else:
            return [self.user]

    def has_as_author(self, user: 'user_models.User') -> bool:
        """Check if the given user is (one of) the authors of this submission.

        :param user: The user to check for.
        :returns: ``True`` if the user is the author of this submission or a
            member of the group that is the author of this submission.
        """
        return self.user.contains_user(user)

    def create_zip(
        self,
        exclude_owner: 'file_models.FileOwner',
        create_leading_directory: bool = True
    ) -> str:
        """Create zip in `MIRROR_UPLOADS` directory.

        :param exclude_owner: Which files to exclude.
        :returns: The name of the zip file in the `MIRROR_UPLOADS` dir.
        """
        path, name = psef.files.random_file_path(True)

        with open(
            path,
            'w+b',
        ) as f, tempfile.TemporaryDirectory(
            suffix='dir',
        ) as tmpdir, zipfile.ZipFile(
            f,
            'w',
            compression=zipfile.ZIP_DEFLATED,
        ) as zipf:
            # Restore the files to tmpdir
            tree_root = psef.files.restore_directory_structure(
                self, tmpdir, exclude_owner
            )

            if create_leading_directory:
                zipf.write(tmpdir, tree_root.name)
                leading_len = len(tmpdir)
            else:
                leading_len = len(tmpdir) + len('/') + len(tree_root.name)

            for root, _dirs, files in os.walk(tmpdir):
                for file in files:
                    path = psef.files.safe_join(root, file)
                    zipf.write(path, path[leading_len:])

        return name

    @classmethod
    def create_from_tree(
        cls,
        assignment: 'assignment_models.Assignment',
        author: 'user_models.User',
        tree: psef.extract_tree.ExtractFileTree,
        *,
        created_at: t.Optional[DatetimeWithTimezone] = None,
    ) -> 'Work':
        """Create a submission from a file tree.

        .. warning::

            This function **does not** check if the author has permission to
            create a submission, so this is the responsibility of the caller!

        :param assignment: The assignment in which the submission should be
            created.
        :param author: The author of the submission.
        :param tree: The tree that are the files of the submission.
        :param created_at: At what time was this submission created, defaults
            to the current time.
        :returns: The created work.
        """
        # TODO: Check why we need to pass both user_id and user.
        self = cls(assignment=assignment, user_id=author.id, user=author)

        if created_at is None:
            self.created_at = helpers.get_request_start_time()
        else:
            self.created_at = created_at

        self.divide_new_work()

        self.add_file_tree(tree)
        db.session.add(self)
        db.session.flush()

        if self.assignment.is_lti:
            # TODO: Doing this for a LMS other than Canvas is probably not a
            # good idea as it will result in a wrong submission date.
            helpers.callback_after_this_request(
                lambda: psef.tasks.passback_grades(
                    [self.id],
                    assignment_id=assignment.id,
                    initial=True,
                )
            )

        self.run_linter()

        if self.assignment.auto_test is not None:
            self.assignment.auto_test.add_to_run(self)

        return self

    @classmethod
    def update_query_for_extended_jsonify(
        cls: t.Type['Work'], query: _MyQuery['Work']
    ) -> _MyQuery['Work']:
        """Update the given query to load all attributes needed for an extended
            jsonify eagerly.

        :param query: The query to update.
        :returns: The updated query, which now loads all attributes needed for
            an extended jsonify eagerly.
        """
        return query.options(
            selectinload(
                cls.selected_items,
            ),
            # We want to load all users directly. We do this by loading the
            # user, which might be a group. For such groups we also load all
            # users.  The users in this group will never be a group, so the
            # last `selectinload` here might be seen as strange. However,
            # during the serialization of a group we access `User.group`, which
            # checks if a user is really not a group. To prevent these last
            # queries the last `selectinload` is needed here.
            selectinload(
                cls.user,
            ).selectinload(
                user_models.User.group,
            ).selectinload(
                group_models.Group.members,
            ).selectinload(
                user_models.User.group,
            ),
            undefer(cls.comment),
            selectinload(cls.comment_author),
        )
