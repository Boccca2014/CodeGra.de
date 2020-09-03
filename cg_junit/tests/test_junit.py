import os

import pytest

from cg_junit import CGJunit, ParseError, MalformedXmlData


def fixture(name):
    return f'{os.path.dirname(__file__)}/../../test_data/{name}'


def parse_fixture(name):
    return CGJunit.parse_file(fixture(name))


@pytest.mark.parametrize(
    'junit_xml',
    [
        'test_junit_xml/valid.xml',
        'test_junit_xml/valid_many_errors.xml',
        'test_junit_xml/valid_system_out.xml',
    ],
)
def test_parse_valid_xml(junit_xml):
    parse_fixture(junit_xml)


def test_valid_xml_unknown_state():
    res = parse_fixture('test_junit_xml/valid_unknown_state.xml')

    assert res.total_errors == 0
    assert res.total_failures == 0
    assert res.total_skipped == 0
    assert res.total_success == 0
    assert res.total_tests == 1


def test_valid_with_weight():
    res = parse_fixture('test_junit_xml/valid_with_weight.xml')

    assert res.total_errors == 0 + 0
    assert res.total_failures == 1 + 0
    assert res.total_skipped == 0 + 0
    assert res.total_success == 4 + 9
    assert res.total_tests == 5 + 9


def test_valid_xml_without_skipped_attr():
    res = parse_fixture('test_junit_xml/valid_no_skipped.xml')

    assert res.total_skipped == 0
    assert all(suite.skipped == 0 for suite in res.suites)
    assert all(
        not case.is_skipped for suite in res.suites for case in suite.cases
    )


def test_valid_xml_no_toplevel_testsuites():
    res = parse_fixture('test_junit_xml/valid_no_testsuites_tag.xml')

    assert len(res.suites) == 1


@pytest.mark.parametrize(
    'junit_xml',
    [
        'test_junit_xml/invalid_missing_name_attr.xml',
        'test_junit_xml/invalid_missing_failures_attr.xml',
        'test_junit_xml/invalid_missing_errors_attr.xml',
        'test_junit_xml/invalid_missing_name_attr.xml',
    ],
)
def test_invalid_xml_missing_suite_attrs(junit_xml):
    with pytest.raises(MalformedXmlData) as err:
        parse_fixture(junit_xml)

    assert 'Did not find all required attributes' in str(err.value)


@pytest.mark.parametrize(
    'junit_xml',
    [
        'test_junit_xml/invalid_missing_case_name_attr.xml',
        'test_junit_xml/invalid_missing_case_classname_attr.xml',
    ],
)
def test_invalid_xml_missing_case_attrs(junit_xml):
    with pytest.raises(MalformedXmlData) as err:
        parse_fixture(junit_xml)

    assert 'Not all required attributes were found' in str(err.value)


@pytest.mark.parametrize(
    'junit_xml',
    [
        'test_junit_xml/invalid_top_level_tag.xml',
        'test_junit_xml/invalid_valid_xml_but_not_junit.xml',
    ],
)
def test_invalid_xml_invalid_toplevel_tag(junit_xml):
    with pytest.raises(MalformedXmlData) as err:
        parse_fixture(junit_xml)

    assert 'Unknown root tag' in str(err.value)


def test_invalid_xml_mismatch_number_of_failures():
    with pytest.raises(MalformedXmlData) as err:
        parse_fixture('test_junit_xml/invalid_mismatch_failures.xml')

    assert 'Got a different amount of failed cases' in str(err.value)


def test_invalid_xml_mismatch_number_of_errors():
    with pytest.raises(MalformedXmlData) as err:
        parse_fixture('test_junit_xml/invalid_mismatch_errors.xml')

    assert 'Got a different amount of error cases' in str(err.value)


def test_invalid_xml_mismatch_number_of_skipped():
    with pytest.raises(MalformedXmlData) as err:
        parse_fixture('test_junit_xml/invalid_mismatch_skipped.xml')

    assert 'Got a different amount of skipped cases' in str(err.value)


@pytest.mark.parametrize(
    'junit_xml',
    [
        'test_submissions/hello.py',
        'test_junit_xml/invalid_xml.xml',
    ],
)
def test_parse_not_xml(junit_xml):
    with pytest.raises(ParseError):
        parse_fixture(junit_xml)


def test_parse_nonexisting_file():
    with pytest.raises(FileNotFoundError):
        parse_fixture('NONEXISTING_FILE')
