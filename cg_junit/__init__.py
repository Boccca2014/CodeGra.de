"""This module provides utilities for parsing JUnit XML files.

SPDX-License-Identifier: AGPL-3.0-only
"""
import typing as t
import dataclasses
import xml.etree.ElementTree

from typing_extensions import Literal, TypedDict
from defusedxml.ElementTree import parse as defused_xml_parse

ET = xml.etree.ElementTree
ParseError = ET.ParseError


class MalformedXmlData(ParseError):
    """Error raised when the given data could be parsed as XML, but does not
    follow the JUnit specification.
    """

    @classmethod
    @t.overload
    def ensure(
        cls, flag: Literal[False], msg: str, *formatters: object
    ) -> t.NoReturn:
        ...

    @classmethod
    @t.overload
    def ensure(
        cls, flag: t.Union[Literal[True], bool], msg: str, *formatters: object
    ) -> None:
        ...

    @classmethod
    def ensure(  # pylint: disable=useless-return
        cls,
        flag: bool,
        msg: str,
        *formatters: object,
    ) -> None:
        """Assert the validity of a proposition, and raise a
        :class:`MalformedXmlData` if it is not valid.

        :param flag: Proposition to validate.
        :param msg: Message format string, may contain % format specifiers.
        :param formatters: Arguments to the string formatting function, i.e.
            the values to be substituted for the % format specifiers.
        :returns: Nothing.
        :raises MalformedXmlData: When the proposition is not valid.
        """
        if not flag:
            raise cls(msg % formatters)

        return None


@dataclasses.dataclass(frozen=True)
class _CGJunitCaseAttribs:
    """Attributes of a test case.

    :ivar name: Name of the test case.
    :ivar classname: Name of the class containing this test case.
    :ivar time: Time it took for the test case to run.
    """
    __slots__ = ('name', 'classname', 'time', 'weight')

    name: str
    classname: str
    time: float
    weight: float


class _CGJunitCase:
    """Test case data.

    :ivar content: XML node containing the output of the test case to be shown,
        if the case was not successful.
    :ivar attribs: Attributes of this test case.
    """
    __slots__ = (
        'content', 'attribs', 'is_error', 'is_failure', 'is_skipped',
        'is_success'
    )

    _ALLOWED_CONTENT_TAGS = {
        'error', 'failure', 'skipped', 'system-out', 'system-err'
    }

    def __init__(
        self,
        content: t.Sequence[ET.Element],
        attribs: _CGJunitCaseAttribs,
    ) -> None:
        self.content = content
        self.attribs = attribs

        found_tags = set(child.tag for child in content)
        self.is_error = 'error' in found_tags
        self.is_failure = 'failure' in found_tags
        self.is_skipped = 'skipped' in found_tags
        self.is_success = not (
            self.is_error or self.is_failure or self.is_skipped or
            any(t not in self._ALLOWED_CONTENT_TAGS for t in found_tags)
        )

    @classmethod
    def from_xml(cls, xml_el: ET.Element) -> '_CGJunitCase':
        """Parse a :class:`_CGJunitCase` from an XML tree.

        :param xml_el: The XML node to parse a test case from.
        :returns: The parsed test case.
        :raises MalformedXmlData: When the XML could not be parsed as JUnit
            compatible XML.
        """
        MalformedXmlData.ensure(
            xml_el.tag == 'testcase',
            'Unknown tag encountered, got %s, expected "testcase"', xml_el.tag
        )
        MalformedXmlData.ensure(
            all(attr in xml_el.attrib for attr in ['name', 'classname']),
            'Not all required attributes were found for this testcase'
        )

        children = list(xml_el)
        return cls(
            content=children,
            attribs=_CGJunitCaseAttribs(
                name=xml_el.attrib['name'],
                classname=xml_el.attrib['classname'],
                time=float(xml_el.attrib['time']),
                weight=float(xml_el.attrib.get('weight', 1.0))
            ),
        )


class _CGJunitSuite:
    """Test suite data.

    :ivar cases: The test cases contained in this suite.
    :ivar attribs: Attributes of this test suite.
    """
    __slots__ = (
        'cases', 'name', 'weight', 'tests', 'failures', 'errors', 'skipped',
        'success'
    )

    def __init__(
        self, cases: t.Sequence[_CGJunitCase], name: str, weight: float
    ) -> None:
        self.name = name
        self.cases = cases
        self.tests = sum(c.attribs.weight for c in cases)
        self.weight = weight

        self.failures = 0.0
        self.errors = 0.0
        self.skipped = 0.0
        self.success = 0.0

        for case in cases:
            weight = case.attribs.weight
            if case.is_failure:
                self.failures += weight
            elif case.is_error:
                self.errors += weight
            elif case.is_skipped:
                self.skipped += weight
            elif case.is_success:
                self.success += weight

    @classmethod
    def from_xml(cls, xml_el: ET.Element) -> '_CGJunitSuite':
        """Parse a :class:`_CGJunitSuite` from an XML tree.

        :param xml_el: The XML node to parse a test suite from.
        :returns: The parsed test suite.
        :raises MalformedXmlData: When the XML could not be parsed as JUnit
            compatible XML.
        """
        MalformedXmlData.ensure(
            xml_el.tag == 'testsuite',
            'Unknown tag encountered, got %s, expected "testsuite"', xml_el.tag
        )
        MalformedXmlData.ensure(
            all(
                attr in xml_el.attrib
                for attr in ['name', 'errors', 'failures', 'tests']
            ),
            (
                'Did not find all required attributes for this testsuite,'
                ' found: %s'
            ),
            list(xml_el.attrib.keys()),
        )
        cases = [_CGJunitCase.from_xml(child) for child in xml_el]

        MalformedXmlData.ensure(
            sum(c.is_failure for c in cases) == int(xml_el.attrib['failures']),
            (
                'Got a different amount of failed cases compared to the found'
                ' attribute'
            )
        )
        MalformedXmlData.ensure(
            sum(c.is_error for c in cases) == int(xml_el.attrib['errors']), (
                'Got a different amount of error cases compared to the found'
                ' attribute'
            )
        )
        MalformedXmlData.ensure(
            sum(c.is_skipped
                for c in cases) == int(xml_el.attrib.get('skipped', 0)),
            (
                'Got a different amount of skipped cases compared to the found'
                ' attribute'
            )
        )
        MalformedXmlData.ensure(
            len(cases) == int(xml_el.attrib['tests']), (
                'Got a different amount of skipped cases compared to the found'
                ' attribute'
            )
        )

        return cls(
            cases,
            name=xml_el.attrib['name'],
            weight=float(xml_el.attrib.get('weight', 1.0))
        )


class CGJunit:
    """Class containing the information of a test run available in a JUnit
    compatible XML file.

    :ivar suites: The test suites in this test run.
    :ivar total_failures: The total number of failed test cases in this test
        run.
    :ivar total_errors: The total number of error cases in this test run.
    :ivar total_skipped: The total number of skipped cases in this test run.
    :ivar total_success: The total number of successful cases in this test run.
    :ivar total_tests: The total number of test cases in this test run.
    """

    def __init__(self, suites: t.Sequence[_CGJunitSuite]) -> None:
        self.suites = suites
        self.total_failures = sum(s.failures * s.weight for s in suites)
        self.total_errors = sum(s.errors * s.weight for s in suites)
        self.total_skipped = sum(s.skipped * s.weight for s in suites)
        self.total_success = sum(s.success * s.weight for s in suites)
        self.total_tests = sum(
            s.tests * s.weight for s in suites
        ) - self.total_skipped

    @classmethod
    def parse_file(cls, xml_file: t.IO[bytes]) -> 'CGJunit':
        """Parse a :class:`CGJunit` from an XML bytestream.

        :param xml_file: Path to the XML file with test run data to be parsed.
        :returns: The parsed test run data.
        :raises ParseError: When the XML could not be parsed, or does not
            follow the JUnit specification.
        """
        xml_data: ET.ElementTree = defused_xml_parse(xml_file)

        root_node = xml_data.getroot()
        if root_node.tag == 'testsuites':
            return cls([_CGJunitSuite.from_xml(node) for node in root_node])
        elif root_node.tag == 'testsuite':
            return cls([_CGJunitSuite.from_xml(root_node)])

        MalformedXmlData.ensure(
            False, 'Unknown root tag encountered, found: %s', root_node.tag
        )
