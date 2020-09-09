"""This file implements a abstract LTI connector.

This tries to handle as much business logic as possible for handling LTI
messages. The high level logic for the second step of the LTI launch is handled
here.

SPDX-License-Identifier: AGPL-3.0-only
"""
import abc
import typing as t

import structlog
from mypy_extensions import TypedDict
from typing_extensions import Literal

from cg_logger import bound_to_logger

from .. import auth, models
from ..exceptions import APICodes, APIException

logger = structlog.get_logger()


class LTILaunchData(TypedDict):
    """This is the data returned to the client after a successful LTI launch.

    :ivar ~course: The course of the LTI launch. This is always included, even
        if the course already did exist.
    :ivar ~assignment: Same as ``course`` but the assignment instead.
    :ivar ~custom_lms_name: The name of the LMS in which the launch was done.
        **Deprecated**: Please use the ``lti_provider`` attribute on the course
        to get the name of the LMS.
    :ivar ~new_role_created: If a new role needed to be created to give the
        current user a role the name of the new role will be stored in this
        variable. If no role was created it the value is ``None``.
    :ivar ~access_token: If the current user needs a new token to login it will
        be stored here, otherwise ``None``.
    :ivar ~updated_email: If the email of the user was updated by this LTI
        launch the new email will be given, if no email was updated it will be
        ``None``.
    :ivar ~type: Always ``normal_result``.
    """
    course: 'models.Course'
    assignment: 'models.Assignment'
    custom_lms_name: str
    new_role_created: t.Optional[str]
    access_token: t.Optional[str]
    updated_email: t.Optional[str]
    type: Literal['normal_result']


class AbstractLTIConnector(abc.ABC):
    """This the abstract LTI connector, it provides a connection between an LMS
        and CodeGrade using LTI.
    """

    @abc.abstractmethod
    def ensure_lti_user(
        self
    ) -> t.Tuple['models.User', t.Optional[str], t.Optional[str]]:
        """Make sure the current LTI user is logged in as a CodeGrade user.

        :returns: A tuple containing the items in order: A CodeGrade user,
            optionally a new token for the user to login with, optionally the
            updated email of the user as a string, this should be ``None`` if
            the email was not updated.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_course(self) -> 'models.Course':
        """Get the current LTI course as a CodeGrade course.

        This method should create a new course with the correct information if
        no course could be found.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_assignment(
        self, user: 'models.User', course: 'models.Course'
    ) -> 'models.Assignment':
        """Get the current LTI assignment as a CodeGrade assignment.

        A new assignment should be created if no could be found.

        :param user: The user doing the launch. This is the same user as
            returned by :meth:`.AbstractLTIConnector.ensure_lti_user`.
        :param course: The :class:`.models.Course` in which to search for, or
            create, an assignment. This method should **never** return an
            assignment that is not inside the given course.

        :returns: The found or created assignment. If an assignment is created
                  it should be added to the database session.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def set_user_role(self, user: 'models.User') -> None:
        """Set the role of the given user if the user has no role.

        :param user: The user to set the role for.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def set_user_course_role(
        self, user: 'models.User', course: 'models.Course'
    ) -> t.Optional[str]:
        """Set the course role for the given course and user if there is no
            such role just yet.

        :param user: The user to set the course role for.
        :param course: The course to connect to user to.

        :returns: The name of the new role created, or ``None`` if no role was
                  created.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_lms_name(self) -> str:
        """Get the name of the LMS that does the LTI launch.
        """
        raise NotImplementedError

    def do_second_step_of_lti_launch(self) -> LTILaunchData:
        """Do the second step of the LTI launch.
        """
        with bound_to_logger() as bind_to_logger:
            user, new_token, updated_email = self.ensure_lti_user()
            auth.set_current_user(user)

            course = self.get_course()
            bind_to_logger(course=course)
            assert course.is_lti, 'Returned course is not an LTI course'

            assig = self.get_assignment(user, course)
            bind_to_logger(assignment=assig)
            assert assig.course_id == course.id, (
                'The returned assignment is not in the earlier returned course'
            )

            if assig.visibility_state.is_deleted:
                raise APIException(
                    'The launched assignment has been deleted on CodeGrade.',
                    f'The assignment "{assig.id}" has been deleted',
                    APICodes.OBJECT_NOT_FOUND, 404
                )

            self.set_user_role(user)
            new_role_created = self.set_user_course_role(user, course)

            models.db.session.commit()
            auth.AssignmentPermissions(assig).ensure_may_see()

            return LTILaunchData(
                assignment=assig,
                course=course,
                new_role_created=new_role_created,
                custom_lms_name=self.get_lms_name(),
                updated_email=updated_email,
                access_token=new_token,
                type='normal_result',
            )
