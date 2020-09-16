"""This module defines the capabilities of each LMS connected with LTI 1.3

You should never create your own LMSCapabilities instances outside of this
file, but instead you should get them using the ``lti_1_3_lms_capabilities``
registery.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import dataclasses

from typing_extensions import Protocol

from ...registry import lti_1_3_lms_capabilities


class LMSCapabilities(Protocol):
    """This class defines the capabilities of an LMS connected using LTI 1.3.

    An important note about naming in this class: most of the attribute names
    are not really intuitive. For example: *supporting* ``set_deadline`` means
    that we probably don't get the deadline from the LMS. This has two main
    reasons: 1) legacy: these strange names mirror the names used in our LTI
    1.1 classes, and 2) it describes what you can do inside CodeGrade with the
    LMS, maybe it is in the future possible to sync back the deadline to the
    LMS, and in this case the name ``set_deadline`` makes way more sense.
    """

    @property
    def lms(self) -> str:
        """The name of the LMS.
        """
        ...

    @property
    def set_deadline(self) -> bool:
        """Is it possible for users to set the deadline of a CodeGrade
        assignment within CodeGrade?

        This should be ``True`` if the LMS does **not** pass the deadline in
        the LTI launch, and ``False`` otherwise.
        """
        ...

    @property
    def set_state(self) -> bool:
        """Should the state of the assignment be set within CodeGrade and not
        be copied from the LMS?

        If ``False`` users are not allowed to change to state of the assignment
        within CodeGrade (they can always set the state to done).
        """
        ...

    @property
    def test_student_name(self) -> t.Optional[str]:
        """If there is a test student in the lms this its full name.
        """
        ...

    @property
    def cookie_post_message(self) -> t.Optional[str]:
        """The name of the iframe ``postMessage`` we can send to the LMS to
        notify that we want to set cookies in a full window.

        This property is ugly, and shows that these capabilities are not really
        a very good abstraction: Only Canvas supports this, and it is not that
        likely that other LMSes will support this in the exact same way as
        Canvas does now. If set to ``None`` this LMS doesn't have any post
        message that will allow us to send cookies (this is currently the case
        for all LMSes except ``Canvas``).
        """
        ...

    @property
    def supported_custom_replacement_groups(self
                                            ) -> t.Sequence[t.Sequence[str]]:
        """A list of replacements groups (or namespaces) supported by this LMS.

        Some LMSes support more replacement variables than others, however we
        don't want to send replacement variables to an LMS we know it will
        never support. This property contains a list of custom replacement
        groups supported by this LMS.

        .. example::

            We have a replacement variable called
            ``'$com.custom_lms.User.name'``, this variable will be included
            (parsed and returned as wanted config), if the
            ``supported_custom_replacement_groups`` contains ``['$com']``.  It
            will also be included if it contains ``['$com', 'custom_lms']``.
            However, it will not be included if it only contains
            ``['$com.custom_lms']`` or ``['$com', 'other_lms']``.
        """
        ...

    @property
    def use_id_in_urls(self) -> bool:
        """Should we use the :attr:`psef.models.LTI1p3Provider.id` in the url.

        Some LMSes do not provide both the ``iss`` and the ``client_id`` in all
        launches. This means that finding the correct
        :class:`psef.models.LTI1p3Provider` is not always correct (especially
        as the ``iss`` often gets used multiple times). For some LMSes
        therefore it is a better idea to simply include the id of the provider
        in the launch url, and verify with the given information that the
        provider could theoretically be the correct one (i.e. all given
        information matches with the information in the LTI provider that
        belongs to the ``id``).

        This really is a workaround, so if we know for sure that all needed
        information is present in each launch (including the ``oidc`` part) you
        should set this to ``False``.
        """
        ...

    @property
    def actual_deep_linking_required(self) -> bool:
        """Does this LMS require actual deep linking, where the user inputs a
        name and deadline.
        """
        ...

    @property
    def auth_audience_required(self) -> bool:
        """Is it required to set a separate OAuth2 Audience for this LMS before
        we can finalize it.
        """
        ...

    def __to_json__(self) -> t.Mapping[str, t.Union[str, bool]]:
        ...

@dataclasses.dataclass(frozen=True)
class _LMSCapabilities:
    lms: str

    set_deadline: bool

    set_state: bool

    test_student_name: t.Optional[str]

    cookie_post_message: t.Optional[str]

    supported_custom_replacement_groups: t.Sequence[t.Sequence[str]]

    use_id_in_urls: bool

    actual_deep_linking_required: bool

    auth_audience_required: bool

    def __post_init__(self) -> None:
        lti_1_3_lms_capabilities.register(self.lms)(self)

    def __to_json__(self) -> t.Mapping[str, t.Union[str, bool]]:
        return dataclasses.asdict(self)


_LMSCapabilities(
    lms='Canvas',
    set_deadline=False,
    set_state=False,
    test_student_name='Test Student',
    cookie_post_message='requestFullWindowLaunch',
    supported_custom_replacement_groups=[['$Canvas'], ['$com', 'instructure']],
    use_id_in_urls=False,
    actual_deep_linking_required=False,
    auth_audience_required=False,
)

_LMSCapabilities(
    lms='Blackboard',
    set_deadline=False,
    set_state=True,
    test_student_name=None,
    cookie_post_message=None,
    supported_custom_replacement_groups=[],
    use_id_in_urls=True,
    actual_deep_linking_required=False,
    auth_audience_required=False,
)

_LMSCapabilities(
    lms='Moodle',
    set_deadline=True,
    set_state=True,
    test_student_name=None,
    cookie_post_message=None,
    supported_custom_replacement_groups=[],
    use_id_in_urls=True,
    actual_deep_linking_required=False,
    auth_audience_required=False,
)

_LMSCapabilities(
    lms='Brightspace',
    set_deadline=False,
    set_state=False,
    test_student_name=None,
    cookie_post_message=None,
    supported_custom_replacement_groups=[],
    use_id_in_urls=False,
    actual_deep_linking_required=True,
    auth_audience_required=True,
)

lti_1_3_lms_capabilities.freeze()
