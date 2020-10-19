import os
import re
import sys
import typing as t
import tempfile
import dataclasses

import pytest

TEST_DIR = os.path.dirname(__file__)
BASE_DIR = os.path.join(TEST_DIR, '..')

WRAPPER_DIR = os.path.join(
    BASE_DIR, 'psef', 'auto_test', 'code_quality_wrappers'
)


@pytest.fixture
def prefix():
    with tempfile.TemporaryDirectory() as prefix:
        yield prefix


def get_wrapper_tests():
    wrapper_test_dir = os.path.join(TEST_DIR, 'code_quality_wrappers')
    all_tests = []

    for wrapper in os.listdir(wrapper_test_dir):
        wrapper_dir = os.path.join(wrapper_test_dir, wrapper)

        if not os.path.isdir(wrapper_dir) or wrapper == '__pycache__':
            continue

        mod = __import__(
            f'code_quality_wrappers.{wrapper}',
            fromlist=['wrapper_testers'],
        )

        all_tests.extend(
            (wrapper, tester)
            for tester in mod.wrapper_testers
        )

    assert all_tests
    return all_tests


@pytest.mark.parametrize('wrapper, tester', get_wrapper_tests())
def test_wrapper_script(assert_similar, prefix, wrapper, tester):
    wrapper_src = os.path.join(WRAPPER_DIR, wrapper)

    tester.run_tests(
        wrapper_src=wrapper_src,
        prefix=prefix,
        assert_similar=assert_similar,
    )
