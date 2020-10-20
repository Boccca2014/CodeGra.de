import io
import os
import abc
import json
import shutil
import importlib
import contextlib
import subprocess

import cg_junit

BASE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..'),
)


def mkdirp(tgt):
    """Create a directory and all its parent directories if they do not exist.
    """
    os.makedirs(tgt, exist_ok=True)
    return tgt


@contextlib.contextmanager
def temp_cwd(dir):
    old_cwd = os.getcwd()
    os.chdir(dir)
    try:
        yield
    finally:
        os.chdir(old_cwd)


@contextlib.contextmanager
def temp_env(new_env):
    old_env = { **os.environ }
    os.environ.update(new_env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)


class Tester(abc.ABC):
    def __init__(self, wrapper_src, prefix):
        # Directory to run the test in.
        self.prefix = prefix

        # Directory containing the submission to run the wrapper on.
        self.submission_dir = mkdirp(f'{prefix}/submission')
        archive = os.path.join(
            BASE_DIR,
            'test_data',
            'test_linter',
            self.submission_archive,
        )
        shutil.unpack_archive(archive, self.submission_dir)

        # Directory containing binaries.
        self.bin_dir = mkdirp(f'{prefix}/bin')

        # Stub cg-api with a program that writes its stdin to
        # {self.prefix}/cgapi.out
        self.write_executable('cg-api', f'''#!/bin/sh
cat >"{self.prefix}/cgapi.out"
''')

    def write_file(self, name, content):
        path = os.path.join(self.prefix, name)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def write_executable(self, name, content):
        path = os.path.join(self.bin_dir, name)
        with open(path, 'w') as f:
            f.write(content)
        os.chmod(path, 0o755)

    @classmethod
    def run_tests(cls, assert_similar, *args, **kwargs):
        self = cls(*args, **kwargs)
        output = self.run_test()

        assert_similar(output, self.expected_output)

    @abc.abstractmethod
    def run_test(self):
        """Test a wrapper script's install command.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def wrapper_name(self):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def submission_archive(self):
        """An archive in test_data/test_linter/
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def expected_output(self):
        """Expected results.
        """
        raise NotImplementedError

    def run_wrapper(self, *args, status=0):
        """Run the wrapper script with the given arguments.
        """
        stdout = io.StringIO()
        stderr = io.StringIO()

        env = {
            'PATH': f'{self.bin_dir}:{os.environ["PATH"]}',
            'STUDENT': self.submission_dir + os.path.sep,
            'PMD_PATH': os.path.join(BASE_DIR, 'pmd'),
            'CHECKSTYLE_PATH': BASE_DIR,
        }

        with temp_cwd(self.submission_dir), temp_env(env), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            spec = importlib.util.spec_from_file_location(
                'wrapper',
                os.path.join(
                    BASE_DIR, 'psef', 'auto_test', 'code_quality_wrappers',
                    self.wrapper_name
                )
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            ret = mod.main(args)

        if status is not None:
            try:
                assert ret == status
            except:
                print('return code:', ret)
                print('stdout:')
                print(stdout.getvalue())
                print('stderr:')
                print(stderr.getvalue())
                raise

        return ret, stdout.getvalue(), stderr.getvalue()

    def get_cgapi_output(self):
        with open(os.path.join(self.prefix, 'cgapi.out')) as f:
            output = json.loads(f.read())
        assert output['op'] == 'put_comments'
        return output['comments']
