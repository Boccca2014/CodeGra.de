"""This module defines all LTI models and connections between LTI providers and
    courses.

SPDX-License-Identifier: AGPL-3.0-only
"""
import abc
import sys
import copy
import json
import uuid
import typing as t
import secrets

import furl
import structlog
import sqlalchemy
import jwcrypto.jwk
import pylti1p3.grade
import pylti1p3.exception
import pylti1p3.names_roles
import pylti1p3.service_connector
from sqlalchemy.types import JSON
from sqlalchemy_utils import UUIDType
from typing_extensions import Final, Literal, TypedDict
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import psef
from cg_helpers import handle_none
from cg_dt_utils import DatetimeWithTimezone
from cg_typing_extensions import make_typed_dict_extender
from cg_sqlalchemy_helpers import ARRAY, hybrid_property
from cg_sqlalchemy_helpers.types import DbColumn, ColumnProxy
from cg_sqlalchemy_helpers.mixins import UUIDMixin, TimestampMixin

from . import UUID_LENGTH, Base, db
from . import user as user_models
from . import work as work_models
from . import course as course_models
from . import assignment as assignment_models
from .. import auth, signals, current_app
from ..lti import v1_3 as lti_v1_3
from ..lti.v1_3 import claims as ltiv1_3_claims
from ..registry import (
    lti_1_1_providers, lti_provider_handlers, lti_1_3_lms_capabilities
)
from ..lti.v1_3.lms_capabilities import LMSCapabilities

logger = structlog.get_logger()

# This task acks late and retries on exceptions. For the exact meaning of these
# variables see the celery documentation. But basically ``acks_late`` means
# that a task will only be removed from the queue AFTER it has finished
# processing, if the worker dies during processing it will simply restart. The
# ``max_retry`` parameter means that if the worker throws an exception during
# processing the task will also be retried, with a maximum of 10. The
# ``reject_on_worker_lost`` means that if a worker suddenly dies while
# processing the task (if the machine fails, or if the main process is killed
# with the ``KILL`` signal) the task will also be retried.
_PASSBACK_CELERY_OPTS: Final = {
    'acks_late': True,
    'max_retries': 10,
    'reject_on_worker_lost': True,
    'autoretry_for': (Exception, ),
}

if t.TYPE_CHECKING:  # pragma: no cover
    # pylint: disable=unused-import, invalid-name
    from pylti1p3.names_roles import _Member, _NamesAndRolesData

    from .work import Work

_ALL_LTI_PROVIDERS = sorted(['lti1.1', 'lti1.3'])
lti_provider_handlers.set_possible_options(_ALL_LTI_PROVIDERS)

T_LTI_PROV = t.TypeVar('T_LTI_PROV', bound='LTIProviderBase')  # pylint: disable=invalid-name


class LTIProviderBase(Base, TimestampMixin):
    """This class defines a connection between CodeGrade and an LMS.

    This class not implement the logic for the handling for the LTI messages,
    but instead provides a place were to store data about the LMS and the
    handshake with CodeGrade.
    """
    __tablename__ = 'LTIProvider'
    _SIGNALS_SETUP = False

    id = db.Column(
        'id',
        db.String(UUID_LENGTH),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    key = db.Column('key', db.Unicode, unique=False, nullable=False)

    _intended_use = db.Column(
        'intended_use',
        db.Unicode,
        nullable=False,
        default='',
        server_default='',
    )

    # This is only really available for LTI1.3, however we need to define it
    # here to be able to create a unique constraint.
    if not t.TYPE_CHECKING:
        client_id = db.Column('client_id', db.Unicode)

    # The foreign key needs to be defined here for sqlalchemy, but the relation
    # is defined in the ``LTI1p3Provider`` model.
    _updates_lti1p1_id = db.Column(
        'updates_lti1p1_id',
        db.String(UUID_LENGTH),
        db.ForeignKey(id),
        nullable=True,
    )

    _lti_provider_version = db.Column(
        'lti_provider_version',
        db.Enum(*_ALL_LTI_PROVIDERS, name='ltiproviderversion'),
        nullable=False,
        server_default='lti1.1'
    )

    _finalized = db.Column(
        'finalized',
        db.Boolean,
        nullable=False,
        default=False,
        server_default='true'
    )

    _edit_secret = db.Column(
        'edit_secret',
        UUIDType,
        default=uuid.uuid4,
        server_default=sqlalchemy.func.uuid_generate_v4(),
        nullable=False
    )

    __mapper_args__ = {
        'polymorphic_on': _lti_provider_version,
        'polymorphic_identity': 'non_existing',
    }

    __table_args__ = (db.UniqueConstraint('client_id', key), )

    def find_user(self, lti_user_id: str) -> t.Optional['user_models.User']:
        """Find the user with the given ``lti_user_id`` in this provider.

        .. note::

            A ``lti_user_id`` is not globally unique!

        :param lti_user_id: The id to search for.
        :returns: A user that has the given lti user id for the connected LMS,
            ``None`` if no user could be found.
        """
        user_link = db.session.query(UserLTIProvider).filter(
            UserLTIProvider.lti_user_id == lti_user_id,
            UserLTIProvider.lti_provider_id == self.id,
        ).first()
        if user_link is None:
            return None

        return user_link.user

    @property
    def is_finalized(self) -> bool:
        """Is this provider finalized and ready for use.
        """
        return self._finalized

    @property
    def edit_secret(self) -> uuid.UUID:
        """The secret which you can use to edit this provider.
        """
        return self._edit_secret

    @property
    def member_sourcedid_required(self) -> bool:
        """Is it required to have an entry in the
        :class:`.assignment_models.AssignmentResult` table for a user before a
        submission can be made?

        This should be ``True`` if this data is required for a grade passback.
        """
        raise NotImplementedError

    @classmethod
    def _signal_assignment_pre_check(
        cls, assig: 'assignment_models.Assignment'
    ) -> bool:
        if not assig.is_lti:
            return False
        elif not isinstance(assig.course.lti_provider, cls):
            return False
        return True

    @classmethod
    def _get_self_from_assignment_id(
        cls: t.Type[T_LTI_PROV],
        assignment_id: t.Optional[int],
        *,
        lock: bool = True
    ) -> t.Union[t.Tuple[None, None], t.Tuple['assignment_models.Assignment', t
                                              .Optional[T_LTI_PROV]]]:
        if assignment_id is None:
            return None, None

        query = assignment_models.Assignment.query.filter(
            assignment_models.Assignment.id == assignment_id,
            assignment_models.Assignment.is_visible,
        )
        if lock:
            query = query.with_for_update(
                read=True, of=assignment_models.Assignment
            )

        assig = query.one_or_none()

        if assig is None:
            logger.info('Assignment not found', assignment_id=assignment_id)
            return None, None
        elif not assig.is_lti:
            logger.info("Assignment isn't a LTI assignment", assignment=assig)
            return None, None

        return assig, cls._get_self_from_course(assig.course)

    @classmethod
    @t.overload
    def _get_self_from_course(
        cls,
        course: None,
    ) -> None:
        ...

    @classmethod
    @t.overload
    def _get_self_from_course(
        cls: t.Type[T_LTI_PROV],
        course: 'course_models.Course',
    ) -> t.Optional[T_LTI_PROV]:
        ...

    @classmethod
    def _get_self_from_course(
        cls: t.Type[T_LTI_PROV],
        course: t.Optional['course_models.Course'],
    ) -> t.Optional[T_LTI_PROV]:
        if course is None:
            logger.info('Course not found')
            return None
        elif course.lti_provider is None:
            logger.info('Course is not an LTI course', course=course)
            return None

        possible_self = course.lti_provider

        if not isinstance(possible_self, cls):
            logger.info(
                'Course does not belong to this LTI Provider',
                course=course,
                lti_provider_cls=cls.__name__,
            )
            return None
        return possible_self

    @property
    @abc.abstractmethod
    def lms_name(self) -> str:
        """The name of the LMS for this LTIProvider.

        :getter: Get the LMS name.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def supports_setting_state(self) -> bool:
        """May users change the available at of the assignment within CodeGrade.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def supports_setting_deadline(self) -> bool:
        """May users change the deadline of the assignment within CodeGrade.

        .. seealso::

            attribute :meth:`psef.lti.v1_3.lms_capabilities.LMSCapabilities.set_deadline`.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def supports_max_points(self) -> bool:
        """May users set the ``Assignment._max_grade`` property?

        This effectively means if the LMS supports bonus points (i.e. a higher
        amount of points than the grade scale).
        """
        raise NotImplementedError

    def __structlog__(self) -> t.Mapping[str, str]:
        return {
            'type': self.__class__.__name__,
            'id': self.id,
        }

    @staticmethod
    def _update_history_sub(sub: 'work_models.Work'
                            ) -> t.Optional['work_models.GradeHistory']:
        newest_grade_history = db.session.query(
            work_models.GradeHistory,
        ).filter_by(work=sub).order_by(
            t.cast(
                DbColumn[DatetimeWithTimezone],
                work_models.GradeHistory.changed_at,
            ).desc(),
        ).limit(1).with_for_update().one_or_none()

        if newest_grade_history is None:
            logger.info('Could not find grade history item')
        else:
            newest_grade_history.passed_back = True

        return newest_grade_history

    class BaseAsJSON(TypedDict):
        id: str  #: The id of this LTI provider.
        lms: str  #: The LMS that is connected as this LTI provider.
        #: The time this LTI provider was created.
        created_at: DatetimeWithTimezone
        #: Who will use this LTI provider.
        intended_use: str

    def __base_to_json__(self) -> BaseAsJSON:
        return {
            'id': str(self.id),
            'lms': self.lms_name,
            'created_at': self.created_at,
            'intended_use': self._intended_use,
        }

    AsJSON = t.Union['psef.models.LTI1p1Provider.AsJSON',
                     'psef.models.LTI1p3Provider.AsJSON']

    @abc.abstractmethod
    def __to_json__(self) -> AsJSON:
        ...


@lti_provider_handlers.register_table
class LTI1p1Provider(LTIProviderBase):
    """This class represents a connection between an LMS and CodeGrade using
        the LTI 1.1 protocol.

    .. seealso: module :mod:`psef.lti.v1_1` for the implementation of the LTI
        1.1 launches.
    """
    __mapper_args__ = {'polymorphic_identity': 'lti1.1'}

    upgraded_to_lti1p3 = db.relationship(
        lambda: LTI1p3Provider,
        back_populates='_updates_lti1p1',
        cascade='all,delete',
        uselist=False,
        lazy='select',
    )

    _lti_provider = db.Column(
        'lms_1p1_name',
        db.Enum(lti_1_1_providers, name='lti1p1lmsnames'),
    )

    _lms_secrets = db.Column(
        'lms_1p1_secret',
        ARRAY(db.Unicode, as_tuple=True, dimensions=1),
        nullable=True,
    )

    def __init__(self, lms: str, intended_use: str) -> None:
        key = '_'.join(
            [
                *intended_use.lower().strip().split(),
                secrets.token_hex(6),
            ]
        )
        super().__init__(
            key=key,
            _lms_secrets=(secrets.token_hex(32), ),
            _intended_use=intended_use,
            _finalized=False,
            _lti_provider=lti_1_1_providers[lms],
        )

    def finalize(self) -> None:
        """Finalize this LTI provider.
        """
        assert self._lti_provider is not None
        self._finalized = True

    def find_course(self,
                    lti_course_id: str) -> t.Optional['CourseLTIProvider']:
        """Find a course with the given ``lti_course_id`` in this LTI
        connection.

        :param lti_course_id: The course that was present in the LTI launch.

        :returns: The connection object between the course and this LTI
                  provider if the course was found. If it was not found
                  ``None`` is returned.
        """
        return CourseLTIProvider.query.filter(
            CourseLTIProvider.lti_course_id == lti_course_id,
            CourseLTIProvider.lti_provider == self,
            ~CourseLTIProvider.old_connection,
        ).one_or_none()

    @property
    def member_sourcedid_required(self) -> bool:
        """We do need sourcedids to passback grades in the LTI 1.1 protocol.
        """
        return True

    @property
    def lms_name(self) -> str:
        """The name of the lms connected to this provider.
        """
        assert self._lti_provider is not None
        return self._lti_provider.get_lms_name()

    class BaseAsJSON(LTIProviderBase.BaseAsJSON, TypedDict):
        #: The LTI version used.
        version: Literal['lti1.1']

    BaseAsJSON.__cg_extends__ = LTIProviderBase.BaseAsJSON  # type: ignore

    class FinalizedAsJSON(BaseAsJSON, TypedDict):
        #: This is a already finalized provider and thus is actively being
        #: used.
        finalized: Literal[True]

    FinalizedAsJSON.__cg_extends__ = BaseAsJSON  # type: ignore

    class NonFinalizedAsJSON(BaseAsJSON, TypedDict):
        #: This is a non finalized provider, so it cannot yet be used for
        #: launches.
        finalized: Literal[False]
        #: If you have the permission to edit this provider this will be a key
        #: with which you can do that.
        edit_secret: t.Optional[uuid.UUID]
        #: The consumer key used to connect the provider to an LMS.
        lms_consumer_key: str
        #: The shared secret used to connect the provider to an LMS.
        lms_consumer_secret: str

    NonFinalizedAsJSON.__cg_extends__ = BaseAsJSON  # type: ignore

    AsJSON = t.Union[FinalizedAsJSON, NonFinalizedAsJSON]

    def __to_json__(self) -> AsJSON:
        base = make_typed_dict_extender(
            super().__base_to_json__(),
            self.BaseAsJSON,
        )(version='lti1.1')

        if self.is_finalized:
            return make_typed_dict_extender(base, self.FinalizedAsJSON)(
                finalized=True,
            )
        else:
            edit_secret = None
            if auth.LTIProviderPermissions(self).ensure_may_edit.as_bool():
                edit_secret = self.edit_secret

            return make_typed_dict_extender(base, self.NonFinalizedAsJSON)(
                finalized=False,
                edit_secret=edit_secret,
                lms_consumer_secret=self.secrets[-1],
                lms_consumer_key=self.key,
            )

    @property
    def secrets(self) -> t.Sequence[str]:
        """The shared secrets connected to this provider.
        """
        assert self._lms_secrets is not None
        return self._lms_secrets

    # The next methods all are handlers for signals we setup in `setup_signals`
    # at the end of the class

    @classmethod
    def _create_submission_in_lms(
        cls, work_assignment_id: t.Tuple[int, int]
    ) -> None:
        work_id, assignment_id = work_assignment_id

        _, self = cls._get_self_from_assignment_id(assignment_id)
        submission = work_models.Work.query.get(work_id)

        if self is not None and submission is not None:
            logger.info(
                'Creating submission in lms',
                submission=submission,
                lti_provider=self,
            )
            # pylint: disable=protected-access
            self._passback_grade(submission, initial=True)
            db.session.commit()

    @classmethod
    def _passback_grades(
        cls, work_assignment_ids: t.Tuple[t.List[int], int]
    ) -> None:
        submission_ids, assignment_id = work_assignment_ids

        assig, self = cls._get_self_from_assignment_id(assignment_id)

        if (
            self is None or assig is None or not assig.should_passback or
            not submission_ids
        ):
            return

        subs = assig.get_all_latest_submissions().filter(
            t.cast(DbColumn[int], work_models.Work.id).in_(submission_ids)
        ).all()

        logger.info(
            'Passback grades',
            gotten_submission=subs,
            wanted_submission=submission_ids,
            difference=set(s.id for s in subs) ^ set(submission_ids),
        )

        # pylint: disable=protected-access
        for sub in subs:
            self._passback_grade(sub, initial=False)
            self._update_history_sub(sub)

        db.session.commit()

    @classmethod
    def _delete_submission(cls, work_assignment_id: t.Tuple[int, int]) -> None:
        work_id, assignment_id = work_assignment_id

        assignment, self = cls._get_self_from_assignment_id(assignment_id)

        if self is None or assignment is None:
            return

        # TODO: This has a bug: if a user has a group submission, that is
        # already deleted, and now his/her latest personal submission is
        # deleted, this personal submission is not found, as we think the
        # deleted group submission (which we ignore) is the latest submission.

        # TODO: Another possible bug is that if a user has two submissions, and
        # the latest is already deleted, and now we delete the new latest this
        # is also not registered as the latest submission.  In other words:
        # this code works for common cases, but is hopelessly broken for all
        # other cases :(
        sub = assignment.get_all_latest_submissions(
            include_deleted=True
        ).filter(work_models.Work.id == work_id).one_or_none()

        if sub is None:
            logger.info('Could not find submission', work_id=work_id)
            return

        logger.info('Deleting grade for submission', work_id=sub.id)
        # pylint: disable=protected-access
        self._passback_grade(sub, initial=False)

    # End of all signal handlers.

    def _passback_grade(self, sub: 'Work', *, initial: bool) -> None:
        """Passback the grade for a given submission to this lti provider.

        :param sub: The submission to passback.
        :param initial: If true no grade will be send, this is to make sure the
            ``created_at`` date is correct in the LMS. Not all providers
            actually do a passback when this is set to ``True``.
        :returns: Nothing.
        """
        service_url = sub.assignment.lti_grade_service_data
        assert isinstance(
            service_url, str
        ), f'Service url has unexpected value: {service_url}'

        assig_results = sub.assignment.assignment_results
        for user in sub.get_all_authors():
            if user.is_test_student or user.id not in assig_results:  # pragma: no cover
                # We actually cover this line, but python optimizes it out:
                # https://github.com/nedbat/coveragepy/issues/198
                continue
            sourcedid = assig_results[user.id].sourcedid
            if sourcedid is None:  # pragma: no cover
                continue

            # Work around for https://github.com/python/mypy/issues/2608
            _sourcedid = sourcedid
            _service_url = service_url

            # We bind these values as kwargs so pylint doesn't complain about
            # using names bound in a loop in a closure (as python ) will reuse
            # the same name for every iteration, so:
            #
            # ```
            # cbs = []
            # for i in range(9): cbs.append(lambda: print(i))
            # [cb() for cb in cbs()]
            # ```
            #
            # Will print '9' nine times.
            def try_passback(
                secret: str,
                *,
                _sid: str = _sourcedid,
                _surl: str = _service_url
            ) -> None:
                self.lti_class.passback_grade(
                    key=self.key,
                    secret=secret,
                    grade=None if sub.deleted else sub.grade,
                    initial=initial,
                    service_url=_surl,
                    sourcedid=_sid,
                    lti_points_possible=sub.assignment.lti_points_possible,
                    submission=sub,
                    host=current_app.config['EXTERNAL_URL'],
                )

            # The newest secret should be placed last in this list
            psef.helpers.try_for_every(reversed(self.secrets), try_passback)

    @property
    def lti_class(self) -> t.Type['psef.lti.v1_1.LTI']:
        """The name of the LTI class to be used for this LTIProvider.

        :getter: Get the LTI class name.
        :setter: Impossible as this is fixed during startup of CodeGrade.
        """
        assert self._lti_provider is not None
        return self._lti_provider

    def supports_setting_deadline(self) -> bool:
        """Only some LMSes pass the deadline in LTI launches.
        """
        return not self.lti_class.supports_deadline()

    def supports_setting_state(self) -> bool:
        """We cannot set the state of the assignment when the LMS
            manages the state.
        """
        return not self.lti_class.supports_state_management()

    def supports_max_points(self) -> bool:
        """Only some LMSes support bonus points using the LTI 1.1 standard.
        """
        return self.lti_class.supports_max_points()

    @classmethod
    def setup_signals(cls) -> None:
        """Setup the signals used by the LTI 1.1 providers.
        """
        if cls._SIGNALS_SETUP:  # pragma: no cover
            return
        cls._SIGNALS_SETUP = True

        pre_checker = cls._signal_assignment_pre_check

        signals.WORK_DELETED.connect_celery(
            pre_check=lambda wd: (
                wd.was_latest and wd.new_latest is not None and
                pre_checker(wd.assignment)
            ),
            converter=(
                lambda wd: (
                    # This stupid check is needed for mypy
                    [wd.new_latest.id] if wd.new_latest else [],
                    wd.assignment_id
                )
            ),
            task_args=_PASSBACK_CELERY_OPTS,
        )(cls._passback_grades)

        signals.WORK_DELETED.connect_celery(
            converter=lambda wd: (
                wd.deleted_work.id,
                wd.deleted_work.assignment_id,
            ),
            pre_check=lambda wd: (
                wd.was_latest and wd.new_latest is None and
                pre_checker(wd.assignment)
            ),
        )(cls._delete_submission)

        signals.GRADE_UPDATED.connect_celery(
            pre_check=lambda work: pre_checker(work.assignment),
            converter=lambda work: (
                [work.id],
                work.assignment_id,
            ),
            task_args=_PASSBACK_CELERY_OPTS,
        )(cls._passback_grades)

        signals.ASSIGNMENT_STATE_CHANGED.connect_celery(
            pre_check=pre_checker,
            converter=lambda a: (
                [w.id for w in a.get_all_latest_submissions()],
                a.id,
            ),
            task_args=_PASSBACK_CELERY_OPTS,
        )(cls._passback_grades)

        signals.WORK_CREATED.connect_celery(
            pre_check=lambda work: pre_checker(work.assignment),
            converter=lambda work: (work.id, work.assignment_id),
            task_args=_PASSBACK_CELERY_OPTS,
        )(cls._create_submission_in_lms)


LTI1p1Provider.setup_signals()


@lti_provider_handlers.register_table
class LTI1p3Provider(LTIProviderBase):
    """This class represents a connection between an LMS and CodeGrade using
        the LTI 1.3 protocol.

    .. seealso: module :mod:`psef.lti.v1_3` for the implementation of the LTI
        1.3 launches.
    """
    __mapper_args__ = {'polymorphic_identity': 'lti1.3'}

    if t.TYPE_CHECKING:  # pragma: no cover
        client_id = db.Column('client_id', db.Unicode)

    @property
    def lms_capabilities(self) -> LMSCapabilities:
        """The capabilities of the lms connect to this provider.
        """
        return lti_1_3_lms_capabilities[self.lms_name]

    def get_launch_url(self, goto_latest_sub: bool) -> furl.furl:
        """Get the launch url for this provider.

        :param goto_latest_sub: Get the url that navigates a user to the latest
            submission.
        :returns: The launch url for this provider.
        """
        base_url = furl.furl(current_app.config['EXTERNAL_URL'])

        to_add = ['api', 'v1', 'lti1.3']
        if goto_latest_sub:
            to_add.append('launch_to_latest_submission')
        else:
            to_add.append('launch')

        if self.lms_capabilities.use_id_in_urls:
            to_add.append(str(self.id))

        return base_url.add(path=to_add)

    _lms_name = db.Column(
        'lms_name',
        db.Enum(*lti_1_3_lms_capabilities.keys(), name='lti1p3lmsnames'),
    )
    _auth_login_url = db.Column('auth_login_url', db.Unicode)
    _auth_token_url = db.Column('auth_token_url', db.Unicode)
    _auth_audience = db.Column('auth_audience', db.Unicode)
    _key_set_url = db.Column('key_set_url', db.Unicode)

    _crypto_key = db.Column('crypto_key', db.LargeBinary)

    _updates_lti1p1 = db.relationship(
        LTI1p1Provider,
        foreign_keys=LTIProviderBase._updates_lti1p1_id,
        remote_side=[LTIProviderBase.id],
        back_populates='upgraded_to_lti1p3',
        uselist=False,
    )

    @property
    def updates_lti1p1(self) -> t.Optional[LTI1p1Provider]:
        """The LTI 1.1 provider this provider updates.

        This allows us to reuse users from that provider, so we will not create
        duplicate users.
        """
        return self._updates_lti1p1

    @property
    def member_sourcedid_required(self) -> bool:
        """Passback works using user ids, so no sourcedids required.
        """
        return False

    @property
    def lms_name(self) -> str:
        """The name of the lms of this provider.
        """
        assert self._lms_name is not None
        return self._lms_name

    @property
    def key_set_url(self) -> t.Optional[str]:
        """The location where you can find the public key of the LMS.
        """
        return self._key_set_url

    @property
    def auth_audience(self) -> t.Optional[str]:
        """The OAuth2 Audience for this provider.
        """
        return handle_none(self._auth_audience, self._auth_token_url)

    @property
    def auth_token_url(self) -> t.Optional[str]:
        """The url where you can get an access token.
        """
        return self._auth_token_url

    def update_registration(
        self,
        iss: t.Optional[str],
        auth_login_url: t.Optional[str],
        auth_token_url: t.Optional[str],
        client_id: t.Optional[str],
        key_set_url: t.Optional[str],
        auth_audience: t.Optional[str],
        finalize: t.Optional[bool],
    ) -> None:
        """Update this lti provider.

        :param auth_login_url: The new auth login url, pass ``None`` to keep
            the old one.
        :param auth_token_url: The new auth token url, pass ``None`` to keep
            the old one.
        :param client_id: The new client id, pass ``None`` to keep the old one.
        :param key_set_url: The new key set url, pass ``None`` to keep the old
            one.
        :param auth_audience: The new OAuth2 Audience this is not required for
            all LMSes. Pass ``None`` to keep the old value.
        :param finalize: Pass ``True`` to seal this provider, and make it ready
            for use.

        :returns: Nothing.
        """
        assert not self._finalized

        if iss is not None:
            self.key = iss
        if client_id is not None:
            self.client_id = client_id
        if auth_login_url is not None:
            self._auth_login_url = auth_login_url
        if auth_token_url is not None:
            self._auth_token_url = auth_token_url
        if key_set_url is not None:
            self._key_set_url = key_set_url
        if auth_audience is not None:
            self._auth_audience = auth_audience

        if finalize is True:
            all_opts = [
                self.client_id, self._auth_login_url, self._auth_token_url,
                self._key_set_url
            ]
            if self.lms_capabilities.auth_audience_required:
                all_opts.append(self._auth_audience)

            if any(opt is None for opt in all_opts):
                raise psef.errors.APIException(
                    (
                        'Cannot finalize registration as not all required'
                        ' options are set'
                    ), 'Some of the required options are not yet set',
                    psef.errors.APICodes.INVALID_STATE, 400
                )
            self._finalized = True

    @classmethod
    def create_and_generate_keys(
        cls,
        iss: str,
        lms_capabilities: LMSCapabilities,
        intended_use: str,
    ) -> 'LTI1p3Provider':
        """Create a new LTI1p3 provider with the given ``iss``.

        :param iss: The iss of the new provider.
        :param lms_capabilities: The capabilities of the new provider.
        :param intended_use: A string describing who will be using this
            provider, this is only for human consumption.
        :returns: The non finalized created provider.
        """
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend(),
        )
        lms_name = lms_capabilities.lms
        assert lms_name in lti_1_3_lms_capabilities

        return cls(
            key=iss,
            _finalized=False,
            _lms_name=lms_name,
            _intended_use=intended_use,
            _crypto_key=key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    def find_course(
        self, lti_course_id: str, deployment_id: str, old_lti_course_id: str
    ) -> t.Optional['CourseLTIProvider']:
        """Find a course in this LTI connection.

        This method will also upgrade an existing LTI 1.1 course to a LTI 1.3
        course if possible. In this case the database will be mutated.

        :param lti_course_id: The course id that was present in the LTI 1.3
            launch.
        :param deployment_id: The deployment id that was present in the LTI 1.3
            launch.
        :param old_lti_course_id: The old LTI 1.1 course id that we should use
            to find old LTI 1.1 courses. This is only used if this provider
            updates a LTI 1.1 provider.

        :returns: The connection object between the course and this LTI
                  provider if a course was found. If it was not found ``None``
                  is returned.
        """
        res = CourseLTIProvider.query.filter(
            CourseLTIProvider.deployment_id == deployment_id,
            CourseLTIProvider.lti_course_id == lti_course_id,
            CourseLTIProvider.lti_provider == self,
            ~CourseLTIProvider.old_connection,
        ).one_or_none()

        if res is None and self.updates_lti1p1 is not None:
            old_conn = self.updates_lti1p1.find_course(
                lti_course_id=old_lti_course_id
            )
            if old_conn is not None:
                old_conn.old_connection = True
                res = CourseLTIProvider.create_and_add(
                    course=old_conn.course,
                    lti_provider=self,
                    lti_context_id=lti_course_id,
                    deployment_id=deployment_id,
                )
                db.session.flush()

        return res

    def find_assignment(
        self,
        course: 'course_models.Course',
        resource_id: t.Optional[str],
        old_resource_id: t.Optional[str],
    ) -> t.Optional['assignment_models.Assignment']:
        """Find an assignment in this LTI connection.

        This method will also upgrade an existing LTI 1.1 assignment to a LTI
        1.3 assignment if possible. In this case the database will be mutated.

        :param course: The course in which we should find the assignment.
        :param resource_id: The assignment id that was present in the LTI 1.3
            launch.
        :param old_resource_id: The old LTI 1.1 assignment id that we should
            use to find old LTI 1.1 assignments. This is only used if this
            provider updates a LTI 1.1 provider.

        :returns: The found assignment or ``None`` if no assignment could be
                  found.
        """
        if resource_id is None:
            return None

        def find(lti_assid_id: t.Optional[str]
                 ) -> t.Optional['assignment_models.Assignment']:
            return course.get_assignments().filter(
                assignment_models.Assignment.lti_assignment_id == lti_assid_id,
                assignment_models.Assignment.lti_assignment_id.isnot(None),
                assignment_models.Assignment.is_lti,
            ).with_for_update(
                read=True, of=assignment_models.Assignment
            ).one_or_none()

        found_assig = find(resource_id)

        if found_assig is None and self.updates_lti1p1 is not None:
            if db.session.query(
                CourseLTIProvider.query.filter(
                    CourseLTIProvider.course == course,
                    CourseLTIProvider.lti_provider == self.updates_lti1p1,
                    CourseLTIProvider.old_connection,
                ).exists()
            ).scalar():
                found_assig = find(old_resource_id)

        if found_assig is not None:
            # Make sure we always upgrade this assignment to the latest lti 1.3
            # resource id.
            found_assig.lti_assignment_id = resource_id

        return found_assig

    @property
    def _private_key(self) -> rsa.RSAPrivateKeyWithSerialization:
        assert self._crypto_key is not None

        return serialization.load_pem_private_key(
            self._crypto_key, None, default_backend()
        )

    def get_public_key(self) -> str:
        """Get the public key that is associated with this LTIProvider.
        """
        key = self._private_key.public_key()
        return key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode('utf8')

    def get_public_jwk(self) -> t.Mapping[str, str]:
        """Get the public part of key used to communicate with the LMS
            represented as jwk.
        """
        pub_key = self.get_public_key().encode('utf8')
        jwk = jwcrypto.jwk.JWK.from_pem(pub_key)
        assert not jwk.has_private

        # For Canvas, and maybe others too, we need to set the `alg` and `use`
        # field of the jwk, however the python library doesn't export this. We
        # now that for now this is always 'RS256' and 'sig'. This assertion is
        # simply to make sure we don't accidentally start creating these keys
        # differently without noticing.
        assert jwk.key_type == 'RSA'
        return {
            **json.loads(jwk.export_public()),
            'alg': 'RS256',
            'use': 'sig',
        }

    @hybrid_property
    def iss(self) -> str:
        """Get the ``iss`` of this lms.

        .. warning::

            DO NOT rely on this being unique, it is not! The tuple of the
            ``iss``, ``client_id`` is unique for each provider, but please
            simply use the id of this provider.
        """
        return self.key

    def get_registration(self) -> 'lti_v1_3.CGRegistration':
        """Get a registration object for this provider.
        """
        return lti_v1_3.CGRegistration(self)

    def get_service_connector(self) -> lti_v1_3.CGServiceConnector:
        """Get the connector to talk to the LMS with.
        """
        return lti_v1_3.CGServiceConnector(self)

    def supports_max_points(self) -> bool:
        """All LTI 1.3 providers support bonus points."""
        return True

    # The next methods all are handlers for signals we setup in `setup_signals`
    # at the end of the class

    @classmethod
    def _delete_submission(cls, work_id: int) -> None:
        work = work_models.Work.query.get(work_id)
        assig, self = cls._get_self_from_assignment_id(
            None if work is None else work.assignment_id
        )
        now = DatetimeWithTimezone.utcnow()

        if self is None or assig is None or work is None:
            return

        if not work.deleted:
            logger.info('Work was not deleted', work=work)
            return

        group_of_user = work.user.group
        for author in work.get_all_authors():
            # pylint: disable=protected-access
            latest_sub = assig.get_latest_submission_for_user(
                author, group_of_user=group_of_user
            ).one_or_none()

            if latest_sub is None:
                self._passback_grade(
                    user=author, assignment=assig, timestamp=now
                )
            else:
                self._passback_grade(
                    sub=latest_sub, assignment=assig, timestamp=now
                )

        db.session.commit()

    @classmethod
    def _passback_new_user(
        cls, user_course_id_tsp: t.Tuple[int, int, str]
    ) -> None:
        user_id, course_id, timestamp = user_course_id_tsp

        course = course_models.Course.query.get(course_id)
        user = user_models.User.query.get(user_id)
        self = cls._get_self_from_course(course)

        if (
            course is None or self is None or user is None or
            not user.is_enrolled(course)
        ):
            return

        for assig in course.get_assignments().filter(
            assignment_models.Assignment.is_lti,
            assignment_models.Assignment.is_visible,
        ):
            # pylint: disable=protected-access
            self._passback_grade(
                user=user,
                assignment=assig,
                # The user might already have a submission by the time this
                # passback is done, however this passback should be ignored in
                # that case as the timestamp should be older.
                timestamp=DatetimeWithTimezone.fromisoformat(timestamp),
            )

    @classmethod
    def _passback_submission(
        cls, work_assignment_id: t.Tuple[int, int]
    ) -> None:
        work_id, assignment_id = work_assignment_id
        assig, self = cls._get_self_from_assignment_id(assignment_id)
        now = DatetimeWithTimezone.utcnow()

        if self is None or assig is None:
            logger.info(
                'Could not find self or assignment',
                found_self=self,
                found_assignment=assig
            )
            return

        work = assig.get_all_latest_submissions().filter(
            work_models.Work.id == work_id
        ).one_or_none()
        if work is None:
            logger.info(
                'Submission is not the latest',
                assignment=assig,
                work_id=work_id
            )
            return

        # pylint: disable=protected-access
        self._passback_grade(
            sub=work,
            assignment=assig,
            timestamp=now,
        )
        db.session.commit()

    @classmethod
    def _passback_grades(cls, assignment_id: int) -> None:
        assig, self = cls._get_self_from_assignment_id(assignment_id)
        now = DatetimeWithTimezone.utcnow()

        if self is None or assig is None or not assig.should_passback:
            return

        subs = assig.get_all_latest_submissions().all()
        logger.info('Passback grades', gotten_submission=subs)
        found_user_ids = set(a.id for s in subs for a in s.get_all_authors())

        # pylint: disable=protected-access
        for sub in subs:
            self._passback_grade(sub=sub, assignment=assig, timestamp=now)

        for user, _ in assig.course.get_all_users_in_course(
            include_test_students=False
        ).filter(user_models.User.id.notin_(found_user_ids)):
            self._passback_grade(user=user, assignment=assig, timestamp=now)

        db.session.commit()

    @t.overload
    def _passback_grade(
        self,
        *,
        assignment: 'assignment_models.Assignment',
        user: 'user_models.User',
        timestamp: DatetimeWithTimezone,
    ) -> None:
        ...

    @t.overload
    def _passback_grade(
        self,
        *,
        assignment: 'assignment_models.Assignment',
        sub: 'Work',
        timestamp: DatetimeWithTimezone,
    ) -> t.Optional['work_models.GradeHistory']:
        ...

    def _passback_grade(
        self,
        *,
        assignment: 'assignment_models.Assignment',
        sub: t.Optional['Work'] = None,
        user: t.Optional['user_models.User'] = None,
        timestamp: DatetimeWithTimezone,
    ) -> t.Optional['work_models.GradeHistory']:
        assert (sub is None) ^ (user is None)

        if sub is not None and sub.deleted:
            logger.info('Submission is deleted, not passing back', work=sub)
            return None
        logger.info('Passing back submission', work=sub)

        grade = lti_v1_3.CGGrade(assignment, timestamp, self)

        if sub is None:
            grade.set_grading_progress('NotReady')
            grade.set_activity_progress('Initialized')
        elif assignment.should_passback and sub.grade is not None:
            grade.set_score_given(sub.grade)
            grade.set_grading_progress('FullyGraded')
            grade.set_activity_progress('Completed')
            grade.set_extra_claims(
                {
                    'https://canvas.instructure.com/lti/submission':
                        {
                            'submission_type': 'basic_lti_launch',
                            'submission_data':
                                str(self.get_launch_url(goto_latest_sub=True)),
                        }
                }
            )
            logger.info(
                'Setting extra claims', extra_claims=grade.get_extra_claims()
            )

        else:
            grade.set_grading_progress('Pending')
            # This is not really the case. Submitted means that a user is still
            # able to make more submissions, but if a user does not have the
            # permission to submit again this is not the case. In this case we
            # should use 'Completed'.
            grade.set_activity_progress('Submitted')

        service_connector = self.get_service_connector()
        grades_service = psef.lti.v1_3.CGAssignmentsGradesService(
            service_connector, assignment
        )

        if sub is None:
            # This is assured by the mypy overloads
            assert user is not None
            authors = [user]
        else:
            authors = sub.get_all_authors()

        author_lookup = dict(
            db.session.query(
                t.cast(DbColumn[int], UserLTIProvider.user_id),
                t.cast(DbColumn[str], UserLTIProvider.lti_user_id),
            ).filter(
                UserLTIProvider.lti_provider == self,
                UserLTIProvider.user_id.in_([a.id for a in authors]),
            ).all()
        )

        passed_back_once = False

        for author in authors:
            lti_user_id = author_lookup.get(author.id)
            if lti_user_id is None:
                logger.info(
                    'Author does not have an LTI user id',
                    author=author,
                    lti_provider=self,
                )
                continue

            grade.set_user_id(lti_user_id)
            try:
                # The ``grade`` is mutable, and we also mutate it in the
                # loop. The call ``put_grade`` shouldn't mutate ``grade`` and
                # it shouldn't keep a reference after the call, so not copying
                # should be safe. The advantage of copying is that in testing
                # it is easier with a copy to see for whom a grade was passed
                # back, furthermore it is also nice and defensive for if the
                # library ever changes its implementation.
                res = grades_service.put_grade(copy.copy(grade))
            except pylti1p3.exception.LtiException:
                logger.info(
                    'Passing back grade failed',
                    exc_info=True,
                    report_to_sentry=True,
                )
            else:
                logger.info(
                    'Successfully passed back grade',
                    work=sub,
                    passback_result=res
                )
                passed_back_once = True

        if (
            sub is not None and passed_back_once and
            grade.get_score_given() is not None
        ):
            return self._update_history_sub(sub)
        return None

    @classmethod
    def _retrieve_users_in_course(cls, course_id: int) -> None:
        course = course_models.Course.query.get(course_id)
        self = cls._get_self_from_course(course)

        if course is None or self is None:
            return
        course_lti_provider = course.course_lti_provider
        assert course_lti_provider is not None

        service_connector = self.get_service_connector()
        members = course_lti_provider.get_members(service_connector)
        logger.info('Got members', found_members=members)

        for member in members:
            logger.info('Got member', member=member)
            status = member.get('status', 'Active')
            if status not in {'Active', 'Inactive'}:  # pragma: no cover
                logger.info(
                    'Got unsupported status', member=member, status=status
                )
                continue

            # This is NOT a typo, the claim is really called 'message' and it
            # contains an array of messages. However, for some strange reason
            # some LMS (looking at you Blackboard) don't send an array, but
            # send a single object. So we wrap it in a list if this is the
            # case.
            messages = member.get('message', [])

            get_claim_data = psef.lti.v1_3.CGCustomClaims.get_custom_claim_data
            custom_claim = None
            for message in psef.helpers.maybe_wrap_in_list(messages):
                try:
                    custom_claim = get_claim_data(
                        t.cast(dict, message.get(ltiv1_3_claims.CUSTOM, {})),
                        base_data=member
                    )
                except:  # pylint: disable=bare-except
                    logger.info(
                        'Could not parse message',
                        exc_info=True,
                        message=message
                    )
                else:
                    break

            logger.info(
                'Adding member to course',
                member=member,
                custom_claim=custom_claim,
            )
            try:
                user, _ = UserLTIProvider.get_or_create_user(
                    lti_user_id=member['user_id'],
                    lti_provider=self,
                    wanted_username=psef.helpers.on_not_none(
                        custom_claim, lambda claim: claim.username
                    ),
                    email=lti_v1_3.get_email_for_user(member, self),
                    full_name=member['name'],
                    old_lti_user_id=member.get('lti11_legacy_user_id'),
                )
            except:  # pylint: disable=bare-except
                logger.info('Could not add new user', exc_info=True)
            else:
                course_lti_provider.maybe_add_user_to_course(
                    user,
                    member['roles'],
                )

        db.session.commit()

    # End of all signal handlers.

    def supports_setting_deadline(self) -> bool:
        """Does this lms supports setting deadline.

        .. seealso::

            class :class:`psef.lti.v1_3.lms_capabilities.LMSCapabilities`.
        """
        return self.lms_capabilities.set_deadline

    def supports_setting_state(self) -> bool:
        """Does the LMS support the available at.
        """
        return self.lms_capabilities.set_state

    @property
    def _custom_fields(self) -> t.Mapping[str, str]:
        return psef.lti.v1_3.CGCustomClaims.get_variable_claims_config(
            self.lms_capabilities
        )

    def get_json_config(self) -> t.Mapping[str, object]:
        """Get the config used by this lti provider for setup.
        """

        def get_url(*to_add: str) -> str:
            return furl.furl(current_app.config["EXTERNAL_URL"]
                             ).add(path=to_add).tostr()

        target_link_uri = self.get_launch_url(False).tostr()
        icon_url = get_url('/static/favicon/android-chrome-512x512.png')
        placement = {
            'text': 'Add CodeGrade assignment',
            'enabled': True,
            'placement': 'assignment_selection',
            'message_type': 'LtiDeepLinkingRequest',
            'target_link_uri': target_link_uri,
            'icon_url': icon_url,
        }
        return {
            'title': 'CodeGrade',
            'description': 'Deliver engaging feedback on code.',
            'oidc_initiation_url': get_url('api', 'v1', 'lti1.3', 'login'),
            'target_link_uri': target_link_uri,
            'scopes': psef.lti.v1_3.NEEDED_SCOPES,
            'extensions':
                [
                    {
                        'domain': get_url(),
                        'tool_id': str(self.id),
                        'platform': self.iss,
                        'privacy_level': 'public',
                        'settings':
                            {
                                'text': 'CodeGrade',
                                'icon_url': icon_url,
                                'placements': [placement],
                            }
                    }
                ],
            'public_jwk_url':
                get_url(
                    'api', 'v1', 'lti1.3', 'providers', str(self.id), 'jwks'
                ),
            'custom_fields': self._custom_fields,
        }

    class BaseAsJSON(LTIProviderBase.BaseAsJSON, TypedDict):
        #: The capabilities of this LMS
        capabilities: LMSCapabilities
        #: The LTI version used.
        version: Literal['lti1.3']
        #: The iss configured for this provider.
        iss: str

    BaseAsJSON.__cg_extends__ = LTIProviderBase.BaseAsJSON  # type: ignore

    class FinalizedAsJSON(BaseAsJSON, TypedDict):
        #: This is a finalized provider.
        finalized: Literal[True]

    FinalizedAsJSON.__cg_extends__ = BaseAsJSON  # type: ignore

    class NonFinalizedAsJSON(BaseAsJSON, TypedDict):
        #: This is a non finalized provider.
        finalized: Literal[False]
        #: The auth login url, if already configured.
        auth_login_url: t.Optional[str]
        #: The auth token url, if already configured.
        auth_token_url: t.Optional[str]
        #: The client id, if already configured.
        client_id: t.Optional[str]
        #: The url where we can download the keyset of the LMS, if already
        #: configured.
        key_set_url: t.Optional[str]
        #: The auth audience, if already configured.
        auth_audience: t.Optional[str]
        #: Custom fields that the LMS should provide when launching.
        custom_fields: t.Mapping[str, str]
        #: The public JWK for this provider, this should be provided to the
        #: LMS.
        public_jwk: t.Mapping[str, str]
        #: The public key for this provider, this should be provided to the
        #: LMS.
        public_key: str
        #: If you have the permission to edit this provider this will be a key
        #: with which you can do that.
        edit_secret: t.Optional[uuid.UUID]

    NonFinalizedAsJSON.__cg_extends__ = BaseAsJSON  # type: ignore

    AsJSON = t.Union[FinalizedAsJSON, NonFinalizedAsJSON]

    def __to_json__(self) -> AsJSON:
        base = make_typed_dict_extender(
            super().__base_to_json__(),
            self.BaseAsJSON,
        )(
            version='lti1.3',
            capabilities=self.lms_capabilities,
            iss=self.iss,
        )

        if self._finalized:
            return make_typed_dict_extender(
                base,
                LTI1p3Provider.FinalizedAsJSON,
            )(finalized=True)
        else:
            if auth.LTIProviderPermissions(self).ensure_may_edit.as_bool():
                edit_secret: t.Optional[uuid.UUID] = self.edit_secret
            else:
                edit_secret = None

            return make_typed_dict_extender(
                base,
                LTI1p3Provider.NonFinalizedAsJSON,
            )(
                finalized=False,
                edit_secret=edit_secret,
                auth_login_url=self._auth_login_url,
                auth_token_url=self._auth_token_url,
                client_id=self.client_id,
                key_set_url=self._key_set_url,
                auth_audience=self._auth_audience,
                custom_fields=self._custom_fields,
                public_jwk=self.get_public_jwk(),
                public_key=self.get_public_key(),
            )

    @classmethod
    def setup_signals(cls) -> None:
        """Setup the signals used by the LTI 1.3 providers.
        """
        if cls._SIGNALS_SETUP:  # pragma: no cover
            return
        cls._SIGNALS_SETUP = True

        pre_checker = cls._signal_assignment_pre_check

        signals.ASSIGNMENT_STATE_CHANGED.connect_celery(
            pre_check=pre_checker,
            converter=lambda a: a.id,
            task_args=_PASSBACK_CELERY_OPTS,
        )(cls._passback_grades)

        signals.WORK_DELETED.connect_celery(
            pre_check=lambda wd: (
                wd.was_latest and pre_checker(wd.deleted_work.assignment)
            ),  # yapf: disable
            converter=lambda wd: wd.deleted_work.id,
            task_args=_PASSBACK_CELERY_OPTS
        )(cls._delete_submission)

        signals.WORK_CREATED.connect_celery(
            pre_check=lambda work: pre_checker(work.assignment),
            converter=lambda work: (work.id, work.assignment_id),
            task_args=_PASSBACK_CELERY_OPTS,
        )(cls._passback_submission)

        signals.GRADE_UPDATED.connect_celery(
            pre_check=lambda work: pre_checker(work.assignment),
            converter=lambda work: (work.id, work.assignment_id),
            task_args=_PASSBACK_CELERY_OPTS,
        )(cls._passback_submission)

        signals.USER_ADDED_TO_COURSE.connect_celery(
            converter=lambda uc: (
                uc.user.id,
                uc.course_role.course_id,
                DatetimeWithTimezone.utcnow().isoformat(),
            ),
            pre_check=lambda uc: uc.course_role.course.is_lti,
            task_args=_PASSBACK_CELERY_OPTS,
            prevent_recursion=True,
        )(cls._passback_new_user)

        signals.USER_ADDED_TO_COURSE.connect_celery(
            converter=lambda uc: uc.course_role.course_id,
            pre_check=lambda uc: uc.course_role.course.is_lti,
            task_args=_PASSBACK_CELERY_OPTS,
            prevent_recursion=True,
        )(cls._retrieve_users_in_course)

        signals.ASSIGNMENT_CREATED.connect_celery(
            converter=lambda a: a.course_id,
            pre_check=pre_checker,
            task_args=_PASSBACK_CELERY_OPTS,
        )(cls._retrieve_users_in_course)


LTI1p3Provider.setup_signals()
lti_provider_handlers.freeze()

# Begin of classes that provide connections between other classes and the LTI
# classes.


class UserLTIProvider(Base, TimestampMixin):
    """This class connects a :class:`.user_models.User` to a
        :class:`.LTIProviderBase`.

    This class makes sure that it is possible to have two users with the same
    lti user id, but from different LMSes. Each user can be linked to at most
    one LTIProvider, and eacher ``lti_user_id`` has to be unique within the
    LMS.
    """
    __tablename__ = 'user_lti-provider'

    user_id = db.Column(
        'user_id', db.Integer, db.ForeignKey('User.id'), nullable=False
    )
    lti_provider_id = db.Column(
        'lti_provider_id',
        db.String(UUID_LENGTH),
        db.ForeignKey(LTIProviderBase.id),
        nullable=False
    )
    #: The id of the user given to us by the LMS. Not globally unique!
    lti_user_id = db.Column(
        'lti_user_id', db.Unicode, nullable=False, index=True
    )

    __table_args__ = (
        # A user can only be connected once to an LTI Provider
        db.PrimaryKeyConstraint(user_id, lti_provider_id),
        # LTI user ids should be unique for a single LTI provider, however they
        # are NOT (!) globally unique between LMSes.
        db.UniqueConstraint(lti_provider_id, lti_user_id),
    )

    lti_provider = db.relationship(
        LTIProviderBase,
        lazy='joined',
        foreign_keys=lti_provider_id,
    )

    user = db.relationship(
        lambda: user_models.User,
        lazy='joined',
        foreign_keys=user_id,
    )

    def __init__(
        self, user: 'user_models.User', lti_provider: LTIProviderBase,
        lti_user_id: str
    ) -> None:
        super().__init__()
        self.user_id = user.id
        self.user = user
        self.lti_provider = lti_provider
        self.lti_user_id = lti_user_id

    @classmethod
    def user_is_linked(cls, user: 'user_models.User') -> bool:
        """Is the given user known in any LTIProvider
        """
        return db.session.query(
            cls.query.filter(cls.user_id == user.id).exists()
        ).scalar()

    @classmethod
    def _create_user(
        cls,
        lti_user_id: str,
        lti_provider: LTIProviderBase,
        wanted_username: t.Optional[str],
        full_name: str,
        email: str,
    ) -> t.Tuple['user_models.User', t.Optional[str]]:
        logger.info(
            'Creating new user for lti user id',
            lti_user_id=lti_user_id,
            wanted_username=wanted_username
        )
        if wanted_username is None:
            raise psef.errors.APIException(
                (
                    'Cannot create new user as a username was not provided in'
                    ' the LTI launch. This probably occurred because the LTI'
                    ' provider was not configured correctly.'
                ), 'The LTI launch did not include a username',
                psef.errors.APICodes.MISSING_REQUIRED_PARAM, 400
            )

        # New LTI user id is found and no user is logged in or the current
        # user has a different LTI user id. A new user is created and
        # logged in.

        username = user_models.User.find_possible_username(wanted_username)

        user = user_models.User(
            name=full_name,
            email=email,
            active=True,
            password=None,
            username=username,
        )
        db.session.add(user)
        db.session.add(
            cls(
                user=user,
                lti_provider=lti_provider,
                lti_user_id=lti_user_id,
            )
        )
        db.session.flush()

        token = user.make_access_token()
        return user, token

    @classmethod
    def _maybe_migrate_lti1p1_user(
        cls, lti_1p3_user_id: str, lti_1p1_user_id: str,
        lti_provider: LTI1p3Provider
    ) -> t.Optional['user_models.User']:
        provider = lti_provider.updates_lti1p1
        if provider is None:
            return None

        lti_user = provider.find_user(lti_1p1_user_id)
        if lti_user is not None:
            db.session.add(
                cls(
                    user=lti_user,
                    lti_provider=lti_provider,
                    lti_user_id=lti_1p3_user_id,
                )
            )
            db.session.flush()

        return lti_user

    @t.overload
    @classmethod
    def get_or_create_user(
        cls,
        lti_user_id: str,
        lti_provider: LTI1p1Provider,
        wanted_username: t.Optional[str],
        full_name: str,
        email: str,
    ) -> t.Tuple['user_models.User', t.Optional[str]]:
        ...

    @t.overload
    @classmethod
    def get_or_create_user(
        cls,
        lti_user_id: str,
        lti_provider: LTI1p3Provider,
        wanted_username: t.Optional[str],
        full_name: str,
        email: str,
        *,
        old_lti_user_id: t.Optional[str],
    ) -> t.Tuple['user_models.User', t.Optional[str]]:
        ...

    @classmethod
    def get_or_create_user(
        cls,
        lti_user_id: str,
        lti_provider: LTIProviderBase,
        wanted_username: t.Optional[str],
        full_name: str,
        email: str,
        *,
        old_lti_user_id: t.Optional[str] = None,
    ) -> t.Tuple['user_models.User', t.Optional[str]]:
        """Get or create a new user for the given LTI Provider

        :param lti_user_id: The user id that we received from the LMS.
        :param lti_provider: The provider of the lauchn.
        :param wanted_username: The username the user wants if it is created.
        :param full_name: The full name of the launching user.
        :param email: The email of the user that does this launch.
        :returns: A tuple containing, in this order: the found or created user,
            optionally an access token to login the new user (this is only
            returned if the current user is not the resulting user).
        """
        current_user = psef.current_user
        is_logged_in = (
            auth.user_active(current_user) and
            # Never connect the global admin user to an LTI course
            not current_user.is_global_admin_user
        )
        token = None
        user = None

        lti_user = lti_provider.find_user(lti_user_id=lti_user_id)

        if lti_user is None and isinstance(lti_provider, LTI1p3Provider):
            lti_user = cls._maybe_migrate_lti1p1_user(
                lti_1p3_user_id=lti_user_id,
                # According to the spec the lti 1.1 user id should **not** be
                # specified if it is the same as the lti 1.3 user id.
                lti_1p1_user_id=handle_none(old_lti_user_id, lti_user_id),
                lti_provider=lti_provider,
            )

        if is_logged_in and lti_user is not None and current_user == lti_user:
            logger.info('Currently logged in user is user doing launch')
            # The currently logged in user is now using LTI
            user = current_user
        elif lti_user is not None:
            if is_logged_in:
                logger.warning(
                    'Found different LTI user than logged in user',
                    lti_user=lti_user
                )
            # LTI users are used before the current logged user.
            token = lti_user.make_access_token()
            user = lti_user
        elif is_logged_in and not cls.user_is_linked(current_user):
            # TODO show some sort of screen if this linking is wanted
            logger.info(
                'Found no LTI user, linking current user',
                lti_user_id=lti_user_id
            )
            db.session.add(
                cls(
                    user=current_user,
                    lti_provider=lti_provider,
                    lti_user_id=lti_user_id,
                )
            )
            user = current_user
        else:
            user, token = cls._create_user(
                lti_user_id, lti_provider, wanted_username, full_name, email
            )

        return user, token


class CourseLTIProvider(UUIDMixin, TimestampMixin, Base):
    """This models connects a :class:`.course_models.Course` to a
        :class:`.LTIProviderBase`.

    This class also makes sure that only course is created inside CodeGrade for
    each course inside the LMS, and it makes sure that courses from one LMS are
    not used as courses for another one. Please see the `__table_args__` unique
    constraints for more info.
    """
    course_id = db.Column(
        'course_id',
        db.Integer,
        db.ForeignKey('Course.id'),
        nullable=False,
    )

    lti_provider_id = db.Column(
        'lti_provider_id',
        db.String(UUID_LENGTH),
        db.ForeignKey(LTIProviderBase.id),
        nullable=False,
    )

    lti_course_id = db.Column(
        'lti_course_id',
        db.Unicode,
        nullable=False,
    )

    old_connection = db.Column(
        'old_connection',
        db.Boolean,
        default=False,
        server_default='false',
        nullable=False,
    )

    # For LTI1.1: the deployment_id is always the same as `lti_course_id`.
    deployment_id = db.Column(
        'deployment_id',
        db.Unicode,
        nullable=False,
    )

    last_names_roles_poll = db.Column(
        'last_names_roles_poll', db.TIMESTAMP(timezone=True), nullable=True
    )

    names_roles_claim: ColumnProxy[t.Optional['_NamesAndRolesData']
                                   ] = db.Column(
                                       'names_roles_claim',
                                       JSON,
                                       nullable=True
                                   )

    lti_provider = db.relationship(
        LTIProviderBase,
        lazy='joined',
        foreign_keys=lti_provider_id,
    )

    course = db.relationship(
        lambda: course_models.Course,
        lazy='joined',
        foreign_keys=course_id,
    )

    __table_args__ = (
        # For LTI1.1: the deployment_id is always the same as `lti_course_id`.

        # For LTI1.3: A lti_course_id (context_id in LTI terminology) is
        # locally (so for a single lti_provider (platform)) unique for a
        # deployment_id.
        db.UniqueConstraint(lti_provider_id, deployment_id, lti_course_id),
    )

    def __init__(
        self,
        lti_course_id: str,
        course: 'course_models.Course',
        lti_provider: LTIProviderBase,
        deployment_id: str,
    ) -> None:
        super().__init__(
            lti_course_id=lti_course_id,
            course=course,
            lti_provider=lti_provider,
            deployment_id=deployment_id,
            old_connection=False,
        )

    def can_poll_names_again(self) -> bool:
        """Check if we may poll the names again from the LMS.

        This method checks if the last poll was long enough ago to poll the
        names again.

        :returns: ``True`` if we can poll again.
        """
        if self.last_names_roles_poll is None:
            return True

        return (
            DatetimeWithTimezone.utcnow() - self.last_names_roles_poll
        ).total_seconds() > current_app.config['LTI1.3_MIN_POLL_INTERVAL']

    def get_members(
        self,
        service_connector: pylti1p3.service_connector.ServiceConnector,
        force: bool = False
    ) -> t.Sequence['_Member']:
        """Poll the LMS for the members in this course.

        :param service_connector: The connection to the LMS which we will use
            the poll the members.
        :param force: Always poll, even if
            :func:`CourseLTIProvider.can_poll_names_again` returns ``False``.

        :returns: The members as retrieved from the LMS.
        """
        if not force and not self.can_poll_names_again():
            logger.info(
                'Not polling again as last poll was a short while ago',
                last_names_roles_poll=self.last_names_roles_poll,
            )
            return []

        assert isinstance(self.names_roles_claim, dict)
        claim = copy.copy(self.names_roles_claim)
        rlid = self.course.get_assignments().filter(
            assignment_models.Assignment.lti_assignment_id.isnot(None),
            assignment_models.Assignment.is_visible,
        ).order_by(
            assignment_models.Assignment.created_at.desc(),
        ).with_entities(
            assignment_models.Assignment.lti_assignment_id,
        ).limit(1).scalar()

        mem_url_claim: Final = 'context_memberships_url'
        if rlid is not None and isinstance(claim[mem_url_claim], str):
            claim[mem_url_claim] = furl.furl(claim[mem_url_claim]).add(
                {'rlid': rlid}
            )
        else:  # pragma: no cover
            logger.warning(
                'No rlid found or claim is missing url',
                claim=claim,
                rlid=rlid,
                report_to_sentry=True,
            )
            return []

        res = pylti1p3.names_roles.NamesRolesProvisioningService(
            service_connector, claim
        ).get_members()
        self.last_names_roles_poll = DatetimeWithTimezone.utcnow()
        return res

    @classmethod
    def create_and_add(
        cls,
        *,
        course: 'course_models.Course',
        lti_provider: LTIProviderBase,
        lti_context_id: str,
        deployment_id: str,
    ) -> 'CourseLTIProvider':
        """Create a :class:`CourseLTIProvider` and add it to the current session.

        :param course: The course which has to be connected to the
            ``lti_provider``.
        :param lti_provder: The LTI provider in which this course is defined.
        :param lti_context_id: The LTI id of the course.
        :param deployment_id: The deployment id of the course. This is only
            defined for LTI1.3.
        :returns: The created object.
        """
        course_lti_provider = cls(
            lti_course_id=lti_context_id,
            course=course,
            lti_provider=lti_provider,
            deployment_id=deployment_id,
        )
        db.session.add(course_lti_provider)
        return course_lti_provider

    def maybe_add_user_to_course(
        self, user: 'user_models.User', roles_claim: t.List[str]
    ) -> t.Optional[str]:
        """Maybe add the given user to the course.

        This method adds the given user to the course, determining its role
        based on the given ``roles_claim``, if the user is not already enrolled
        in the course.

        .. todo::

            Move this method to the LTI 1.3 implementation, as this only makes
            sense when you have an LTI 1.3 roles claim.

        :param user: The user to possibly enrol in the course connected to this
            ``CourseLTIProvider``.
        :param roles_claim: The LTI1p3 roles claim that we should use to
            determine the role of the given user.
        """
        if user.is_enrolled(self.course):
            return None

        roles = psef.lti.v1_3.roles.ContextRole[str].parse_roles(roles_claim)
        logger.info(
            'Finding role for user',
            roles_claim=roles_claim,
            parsed_context_roles=roles,
        )
        if roles:
            user.enroll_in_course(
                course_role=psef.models.CourseRole.get_by_name(
                    self.course,
                    roles[0].codegrade_role_name,
                ).one()
            )
            return None

        unmapped_roles = psef.lti.v1_3.roles.ContextRole[
            None].get_unmapped_roles(roles_claim)

        if unmapped_roles:
            logger.info(
                'No mapped LTI roles found, searching for unmapped roles',
                unmapped_roles=unmapped_roles,
            )

            base = 'Unmapped LTI Role ({})'
            for unmapped_role in unmapped_roles:
                role = psef.models.CourseRole.get_by_name(
                    self.course, base.format(unmapped_role.stripped_name)
                ).one_or_none()
                if role:
                    user.enroll_in_course(course_role=role)
                    return None

            new_role_name = base.format(unmapped_roles[0].stripped_name)
        else:
            base = 'New LTI Role'
            for idx in range(sys.maxsize):
                if not db.session.query(
                    psef.models.CourseRole.get_by_name(
                        self.course, base.format(idx=idx), include_hidden=True
                    ).exists()
                ).scalar():
                    break
                base = 'New LTI Role ({idx})'
            new_role_name = base.format(idx=idx)

        logger.info('Creating new role', new_role_name=new_role_name)
        role = psef.models.CourseRole(
            course=self.course, name=new_role_name, hidden=False
        )
        db.session.add(role)
        db.session.flush()

        user.enroll_in_course(course_role=role)
        return role.name
