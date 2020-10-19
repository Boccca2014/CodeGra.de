import os
import abc
import json
import uuid
import shutil
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

        # Substitute paths to the linters in the script where needed.
        with open(wrapper_src, 'r') as f:
            self.write_executable(
                self.wrapper_name,
                f.read().format(
                    PMD_PATH=os.path.join(BASE_DIR, 'pmd'),
                    CHECKSTYLE_PATH=BASE_DIR,
                ),
            )

        self.uuid = str(uuid.uuid4())

        # Stub cg-api with a program that writes its stdin to stdout wrapped
        # between two lines containing the same uuid.
        self.write_executable('cg-api', f'''#!/bin/sh
echo {self.uuid}
cat
# ensure uuid starts on new line
echo
echo {self.uuid}
''')

    def write_executable(self, name, content):
        path = os.path.join(self.bin_dir, name)
        with open(path, 'w') as f:
            f.write(content)
        os.chmod(path, 0o755)

    @classmethod
    def run_tests(cls, assert_similar, *args, **kwargs):
        self = cls(*args, **kwargs)
        proc = self.run_test()
        output = self.get_cgapi_output(proc)

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
        return self.run_shell(self.wrapper_name, *args, status=status)

    def run_shell(self, *cmd, status=0):
        env = {
            **os.environ,
            'PATH': f'{self.bin_dir}:{os.environ["PATH"]}',
            'STUDENT': self.submission_dir + os.path.sep,
        }

        proc = subprocess.run(
            " ".join(cmd),
            capture_output=True,
            cwd=self.submission_dir,
            env=env,
            shell=True,
            text=True,
        )

        if status is not None:
            try:
                assert proc.returncode == status
            except:
                print('stdout:')
                print(proc.stdout)
                print('stderr:')
                print(proc.stderr)
                raise

        return proc

    def get_cgapi_output(self, proc):
        lines = proc.stdout.splitlines()

        idcs = iter(range(len(lines)))
        start = next(i for i in idcs if lines[i] == self.uuid)
        end = next(i for i in idcs if lines[i] == self.uuid)

        output = json.loads('\n'.join(lines[start + 1 : end]))
        assert output['op'] == 'put_comments'
        return output['comments']
