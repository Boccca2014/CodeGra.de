import os
import re
import glob
import contextlib

import pytest
from mypy import api

base_dir = os.path.dirname(__file__)


@contextlib.contextmanager
def working_dir(new):
    old = os.getcwd()
    try:
        os.chdir(new)
        yield
    finally:
        os.chdir(old)


test_dir = os.path.join(base_dir, 'plugin_tests')


@pytest.mark.parametrize(
    'test_file', sorted(glob.glob(os.path.join(test_dir, '*.py')))
)
def test_plugin(test_file):
    mypy_cmdline = [
        '--show-traceback',
        '--no-error-summary',
        '--show-absolute-path',
        '--config-file={}'.format(
            os.path.join(base_dir, '..', '..', 'setup.cfg')
        ),
        test_file,
    ]
    with working_dir(os.path.join(base_dir, '..', '..')):
        out, err, ok = api.run(mypy_cmdline)
    assert ok
    output = []

    in_correct_file = False
    for line in (out + err).splitlines():
        if line.startswith(test_file):
            in_correct_file = True
            to_strip = test_file + ':'
            line = line[len(to_strip):].strip().replace('.py', '')
            number, typ, rest = line.split(':', 2)
            output.append((int(number), typ.strip(), [rest.strip()]))
        elif in_correct_file:
            output[-1][-1].append(line.strip())
        else:
            in_correct_file = False

    expected = []
    with open(test_file, 'r') as f:
        for idx, line in enumerate(f):
            matches = re.findall(r'(#|;) (N|E):(r?) ([^;]*)', line.strip())
            for _, e_or_n, is_regex, message in matches:
                expected.append((idx + 1, e_or_n, bool(is_regex), message))

    print(output, expected)
    assert len(output) == len(expected)
    for out, expect in zip(output, expected):
        print(out, expect)
        assert out[0] == expect[0]
        assert out[1][0] == expect[1].lower()
        if expect[2]:
            assert re.match(expect[3], ' '.join(x for x in out[2] if x))
        else:
            assert expect[3] == ' '.join(x for x in out[2] if x)
