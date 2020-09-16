"""
This module contains all the linters that are integrated in the service.

Integrated linters are ran by the :class:`LinterRunner` and thus implement run
method.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import abc
import csv
import json
import uuid
import typing as t
import tempfile
import subprocess
import xml.etree.ElementTree as ET
from io import StringIO

import structlog
from defusedxml.ElementTree import fromstring as defused_xml_fromstring

from . import app, files, models
from .models import db
from .helpers import register, format_list, maybe_wrap_in_list
from .exceptions import ValidationException

logger = structlog.get_logger()

T_LINTER = t.TypeVar('T_LINTER', bound='Linter')  # pylint: disable=invalid-name
_NICE_LEVEL = 10

ProcessCompletedCallback = t.Callable[[subprocess.CompletedProcess], None]


def init_app(_: t.Any) -> None:
    pass


_linter_handlers: register.Register[str, t.Type['Linter']] = register.Register(
)


def _read_config_file(config_cat: str, config_name: str) -> str:
    with open(
        os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            'resources',
            config_cat,
            config_name,
        ), 'r'
    ) as f:
        return f.read()


def _run_command(cmd: t.List[str]) -> subprocess.CompletedProcess:
    def preexec_fn() -> None:  # pragma: no cover
        try:
            os.nice(_NICE_LEVEL)
        except:  # pylint: disable=bare-except
            pass

    # The check for success is something we really don't want here.
    return subprocess.run(  # pylint: disable=subprocess-run-check
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=preexec_fn,
    )


class LinterCrash(Exception):
    """The exception to use that a linter has crashed.

    This is a semi-controlled crash, so it should be used when the linter
    process itself returned some unexpected code or invalid output. It should
    not be used for programming errors within CodeGrade code processing the
    output of the linter.
    """

    def __init__(self, error_summary: t.Optional[str] = None) -> None:
        super().__init__()
        self.error_summary = error_summary


class Linter(abc.ABC):
    """The base class for a linter.

    Every linter should inherit from this class as they are discovered by
    reflecting on subclasses from this class. They should override the ``run``
    method, and they may override the ``DEFAULT_OPTIONS`` variable. If
    ``RUN_LINTER`` is set to ``False`` we never actually run the linter, but
    only create a :py:class:`.models.AssignmentLinter` for this assignment and
    a :py:class:`.models.LinterInstance` for each submission.

    .. note::

        If a linter doesn't override ``DEFAULT_OPTIONS`` the user will not have
        the ability to define a custom configuration for the linter in the
        frontend.
    """
    DEFAULT_OPTIONS: t.ClassVar[t.Mapping[str, str]] = {}
    RUN_LINTER: t.ClassVar[bool] = True

    def __init__(self, cfg: str) -> None:
        self.config = cfg

    # pylint: disable=unused-argument
    @classmethod
    def validate_config(cls: t.Type[T_LINTER], config: str) -> None:
        """Verify if the config is correct.

        This method should never return something but raise a
        :class:`.ValidationException` instead.

        :param config: The config to validate.
        """
        return None

    @abc.abstractmethod
    def run(
        self,
        tempdir: str,
        emit: t.Callable[[str, int, str, str], None],
        process_completed: ProcessCompletedCallback,
    ) -> None:  # pragma: no cover
        """Run the linter on the code in `tempdir`.

        :param tempdir: The temp directory that should contain the code to
            run the linter on.
        :param emit: A callback to emit a line of feedback, where the first
            argument is the filename, the second is the line number, the third
            is the code of the linter error, and the fourth and last is the
            message of the linter.
        :param process_completed: The callback that should be called, directly,
            after the process has been completed.
        """
        raise NotImplementedError('A subclass should implement this function!')


@_linter_handlers.register('Pylint')
class Pylint(Linter):
    """The pylint checker.

    This checks python modules for many common errors. It only works on proper
    modules and will display an error on the first line of every file if the
    given code was not a proper module.
    """
    DEFAULT_OPTIONS: t.ClassVar[t.Mapping[str, str]] = {
        'Empty config file': ''
    }

    def run(
        self,
        tempdir: str,
        emit: t.Callable[[str, int, str, str], None],
        process_completed: ProcessCompletedCallback,
    ) -> None:
        """Run the pylinter.

        Arguments are the same as for :py:meth:`Linter.run`.
        """
        with tempfile.NamedTemporaryFile('w') as cfg:
            cfg.write(self.config)
            cfg.flush()

            out = _run_command(
                [
                    part.format(config=cfg.name, files=tempdir)
                    for part in app.config['PYLINT_PROGRAM']
                ]
            )
            process_completed(out)

        if out.returncode == 32:
            raise LinterCrash
        if out.returncode == 1:
            raise LinterCrash(
                error_summary=(
                    'The submission is not a valid python module, it probably'
                    ' lacks an `__init__` file.'
                ),
            )

        for err in json.loads(out.stdout):
            try:
                emit(
                    err['path'],
                    int(err['line']),
                    err['message-id'],
                    err['message'],
                )
            except (KeyError, ValueError):  # pragma: no cover
                pass


@_linter_handlers.register('Flake8')
class Flake8(Linter):
    """Run the Flake8 linter.

    This linter checks for errors in python code and checks the pep8 python
    coding standard. All "noqa"s are disabled when running.
    """
    DEFAULT_OPTIONS: t.ClassVar[t.Mapping[str, str]] = {
        'Empty config file': ''
    }

    def run(
        self,
        tempdir: str,
        emit: t.Callable[[str, int, str, str], None],
        process_completed: ProcessCompletedCallback,
    ) -> None:
        # This is not guessable
        sep = uuid.uuid4()
        fmt = '%(path)s{0}%(row)d{0}%(code)s{0}%(text)s'.format(sep)

        with tempfile.NamedTemporaryFile('w') as cfg:
            cfg.write(self.config)
            cfg.flush()
            out = _run_command(
                [
                    part.format(config=cfg.name, files=tempdir, line_fmt=fmt)
                    for part in app.config['FLAKE8_PROGRAM']
                ]
            )
            process_completed(out)

        if out.returncode != 0:
            raise LinterCrash

        for line in out.stdout.split('\n'):
            args = line.split(str(sep))
            try:
                emit(args[0], int(args[1]), *args[2:])
            except (IndexError, ValueError):
                pass


@_linter_handlers.register('MixedWhitespace')
class MixedWhitespace(Linter):
    """Run the MixedWhitespace linter.

    This linter checks if a file contains mixed indentation on the same line.
    It doesn't catch different types of indentation being used in a file but on
    different lines. Instead of adding a comment in the sidebar, the mixed
    whitespace will be highlighted in the code.
    """
    RUN_LINTER: t.ClassVar[bool] = False

    def run(
        self,
        tempdir: str,
        emit: t.Callable[[str, int, str, str], None],
        process_completed: ProcessCompletedCallback,
    ) -> None:  # pragma: no cover
        # This method should never be called as ``RUN_LINTER`` is set to
        # ``false..
        assert False


@_linter_handlers.register('Checkstyle')
class Checkstyle(Linter):
    """Run the Checkstyle linter.

    This checks java source files for common errors. It is configured by a xml
    file. It is not possible to upload your own checkers, neither is it
    possible to supply some properties such as `basedir` and `file`.
    """
    DEFAULT_OPTIONS = {
        'Google style': _read_config_file('checkstyle', 'google.xml'),
        'Sun style': _read_config_file('checkstyle', 'sun.xml'),
    }

    @classmethod
    def _validate_module(cls: t.Type['Checkstyle'], mod: ET.Element) -> None:
        name = mod.attrib.get('name')
        if name is not None:
            if '.' in name:
                raise ValidationException(
                    (
                        'The given config is not valid: invalid module used,'
                        ' only default checkstyle modules are supported'
                    ), (
                        'Invalid module used, only default checkstyle '
                        'modules are supported'
                    )
                )
            for sub_el in mod:
                validate_func = cls._get_validate_func(sub_el.tag)
                if validate_func is not None:
                    validate_func(sub_el)

    @staticmethod
    def _validate_property(prop: ET.Element) -> None:
        attrib = prop.attrib
        if attrib['name'] in {
            'basedir', 'cacheFile', 'haltOnException', 'file'
        }:
            raise ValidationException(
                (
                    'The given config is not valid: invalid property'
                    f' "{attrib["name"]}" found'
                ),
                f'Invalid property "{attrib["name"]}" found',
            )
        if list(prop):
            raise ValidationException(
                (
                    'The given config is not valid: a property cannot have'
                    ' children'
                ),
                'A property cannot have children',
            )

    @classmethod
    def _get_validate_func(cls: t.Type['Checkstyle'], name: str
                           ) -> t.Optional[t.Callable[[ET.Element], None]]:
        return {
            'property': cls._validate_property,
            'module': cls._validate_module,
            'message': lambda _: None,
        }.get(name)

    @classmethod
    def validate_config(cls: t.Type['Checkstyle'], config: str) -> None:
        """Check if the given config is valid for checkstyle.

        This also does some extra checks to make sure some invalid properties
        are not present.

        :param config: The config to check.
        """
        try:
            xml_config: ET.Element = defused_xml_fromstring(config)
            assert xml_config is not None
        except BaseException as exc:
            raise ValidationException(
                'The given xml config could not be parsed.',
                f'The config {config} could not be parsed as xml.'
            ) from exc
        if xml_config.tag != 'module' or xml_config.attrib.get(
            'name'
        ) != 'Checker':
            raise ValidationException(
                (
                    'The given config is not valid: the given top module of the'
                    ' config should be Checker.'
                ),
                'The given top module of the config should be Checker.'
            )
        for sub_el in xml_config:
            validate_func = cls._get_validate_func(sub_el.tag)
            if validate_func is None:
                raise ValidationException(
                    (
                        'The given config is not valid: unknown tag'
                        f' "{sub_el.tag}" encountered'
                    ),
                    f'Unknown tag "{sub_el.tag}" encountered'
                )
            validate_func(sub_el)

    def run(
        self,
        tempdir: str,
        emit: t.Callable[[str, int, str, str], None],
        process_completed: ProcessCompletedCallback,
    ) -> None:
        """Run checkstyle

        Arguments are the same as for :py:meth:`Linter.run`.
        """
        tempdir = os.path.dirname(tempdir)

        with tempfile.NamedTemporaryFile('w') as cfg:
            module: ET.Element = defused_xml_fromstring(self.config)
            assert module is not None
            assert module.attrib.get('name') == 'Checker'
            module.append(
                module.__class__(
                    'property', {
                        'name': 'basedir',
                        'value': '${basedir}'
                    }
                )
            )
            cfg.write(
                """<?xml version="1.0"?>
<!DOCTYPE module PUBLIC
          "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN"
          "https://checkstyle.org/dtds/configuration_1_3.dtd">\n"""
            )
            cfg.write(ET.tostring(module, encoding='unicode'))
            cfg.flush()

            out = _run_command(
                format_list(
                    app.config['CHECKSTYLE_PROGRAM'],
                    config=cfg.name,
                    files=tempdir,
                )
            )
            process_completed(out)
            if out.returncode == 254:
                raise LinterCrash(
                    'The given submission could not be parsed as valid java',
                )

            output: ET.Element = defused_xml_fromstring(out.stdout)
            assert output is not None

            for file_el in output:
                if file_el.tag != 'file':  # pragma: no cover
                    continue
                filename = file_el.attrib['name']
                for error_el in file_el:
                    if error_el.tag != 'error':  # pragma: no cover
                        continue
                    attrib = error_el.attrib
                    emit(
                        filename,
                        int(attrib['line']),
                        attrib.get('severity', 'warning'),
                        attrib['message'],
                    )


@_linter_handlers.register('PMD')
class PMD(Linter):
    """Run the PMD linter.

    This checks java source files for common errors. It is configured by a xml
    file. It is not possible to upload your own rules, neither is it
    possible to use XPath rules.
    """
    DEFAULT_OPTIONS: t.ClassVar[t.Mapping[str, str]] = {
        'Maven': _read_config_file('pmd', 'maven.xml'),
    }

    @classmethod
    def validate_config(cls: t.Type['PMD'], config: str) -> None:
        """Check if the given config is valid for PMD.

        This also does some extra checks to make sure some invalid properties
        are not present.

        :param config: The config to check.
        """
        try:
            xml_config: ET.Element = defused_xml_fromstring(config)
            assert xml_config is not None
        except BaseException as exc:
            logger.warning('Error', exc_info=True)
            raise ValidationException(
                'The given xml config could not be parsed.',
                f'The config {config} could not be parsed as xml.'
            ) from exc
        stack: t.List[ET.Element] = [xml_config]

        while stack:
            cur = stack.pop()
            stack.extend(cur)
            class_el = cur.attrib.get('class')
            if class_el is None:
                continue
            if 'xpathrule' in class_el.lower().split('.'):
                raise ValidationException(
                    'XPath rules cannot be used.', (
                        'The given config is invalid as XPath rules are'
                        ' not allowed.'
                    )
                )

    def run(
        self,
        tempdir: str,
        emit: t.Callable[[str, int, str, str], None],
        process_completed: ProcessCompletedCallback,
    ) -> None:
        """Run PMD.

        Arguments are the same as for :py:meth:`Linter.run`.
        """
        tempdir = os.path.dirname(tempdir)

        with tempfile.NamedTemporaryFile('w') as cfg:
            cfg.write(self.config)
            cfg.flush()

            out = _run_command(
                [
                    part.format(config=cfg.name, files=tempdir)
                    for part in app.config['PMD_PROGRAM']
                ]
            )
            process_completed(out)
            assert out.returncode == 0
            output = csv.DictReader(StringIO(out.stdout))
            assert output is not None

            for line in output:
                filename = line['File']
                line_number = int(line['Line'])
                msg = line['Description']
                code = line['Rule set']

                emit(filename, line_number, code, msg)


@_linter_handlers.register('ESLint')
class ESLint(Linter):
    """Run the ESLint linter.
    """
    DEFAULT_OPTIONS: t.ClassVar[t.Mapping[str, str]] = {
        'Standard': _read_config_file('eslint', 'standard.json')
    }

    @classmethod
    def validate_config(cls: t.Type['ESLint'], config: str) -> None:
        """Check if the given config is valid for ESLint.

        This also does some extra checks to make sure some invalid properties
        are not present.

        >>> ESLint.validate_config('{"extends": "./a_path"}')
        Traceback (most recent call last):
        ...
        ValidationException: ...
        >>> ESLint.validate_config('{"extends": "plugin:a_path"}')
        >>> ESLint.validate_config('{"extends": "a/path')
        Traceback (most recent call last):
        ...
        ValidationException: ...
        >>> ESLint.validate_config('{"extends": "/path')
        Traceback (most recent call last):
        ...
        ValidationException: ...

        :param config: The config to check.
        """
        try:
            json_config = json.loads(config)
        except ValueError as exc:
            raise ValidationException(
                'The given json config could not be parsed.',
                f'The config {config} could not be parsed as json.'
            ) from exc

        for plugin in json_config.get('plugins', []):
            if '/' in plugin:
                raise ValidationException(
                    'Plugins cannot be paths',
                    f'The plugin {plugin} contains a slash'
                )

        for extend in maybe_wrap_in_list(json_config.get('extends', '')):
            if '.' in extend or (
                not extend.startswith('plugin:') and '/' in extend
            ):
                raise ValidationException(
                    'Base configs cannot be paths',
                    f'The base config ({extend}) as paths are not supported'
                )

    def run(
        self,
        tempdir: str,
        emit: t.Callable[[str, int, str, str], None],
        process_completed: ProcessCompletedCallback,
    ) -> None:
        """Run ESLint.

        Arguments are the same as for :py:meth:`Linter.run`.
        """
        tempdir = os.path.dirname(tempdir)
        config = json.loads(self.config)

        with tempfile.NamedTemporaryFile('w') as cfg:
            config['root'] = True
            json.dump(config, cfg)
            cfg.flush()

            out = _run_command(
                [
                    part.format(config=cfg.name, files=tempdir)
                    for part in app.config['ESLINT_PROGRAM']
                ]
            )
            process_completed(out)
            # Exit code 1 means that linting was successful but that errors
            # were found.
            if out.returncode not in {0, 1}:
                raise LinterCrash(
                    error_summary=(
                        'ESLint crashed, stdout: "{}", stderr: "{}"'
                    ).format(
                        out.stdout,
                        out.stderr,
                    )
                )
            output = json.loads(out.stdout)

            for f in output:
                filename = f['filePath']
                for message in f['messages']:
                    msg = message['message']
                    if message.get('fatal', False):
                        raise Exception(f'Encountered fatal error: {msg}')

                    line_number = int(message['line'])
                    code = message['ruleId']

                    emit(filename, line_number, code, msg)


class LinterRunner:
    """This class is used to run a :class:`Linter` with a specific config on
    sets of :class:`.models.Work`.

    .. py:attribute:: linter
        The attached :class:`Linter` that will be ran by this class.
    """

    def __init__(self, cls: t.Type[Linter], cfg: str) -> None:
        """Create a new instance of :class:`LinterRunner`

        :param Linter cls: The linter to run.
        :param str cfg: The config as as `str` to pass to the linter.
        """
        self.linter = cls(cfg)

    def run(self, linter_instance_ids: t.Sequence[str]) -> None:
        """Run this linter runner on the given works.

        .. note:: This method takes a long time to execute, please run it in a
                  thread.

        :param linter_instance_ids: A sequence of all the ids of the linter
            instances which should be run. If this linter instance has already
            run once its old comments will be removed.

        :returns: Nothing
        """
        for linter_instance_id in linter_instance_ids:
            linter_inst = db.session.query(models.LinterInstance
                                           ).get(linter_instance_id)

            # This should never happen however it is better to check here.
            if linter_inst is None or linter_inst.work.deleted:  # pragma: no cover
                continue

            compl_proc: t.Optional[subprocess.CompletedProcess] = None

            def set_proc(proc: subprocess.CompletedProcess) -> None:
                nonlocal compl_proc
                compl_proc = proc

            try:
                self.test(linter_inst, set_proc)
            # We want to catch all exceptions here as need to set our linter to
            # the crashed state.
            except LinterCrash as e:
                logger.warning(
                    'The linter crashed',
                    linter_instance_id=linter_inst.id,
                    exc_info=True,
                )
                linter_inst.state = models.LinterState.crashed
                linter_inst.error_summary = (
                    e.error_summary or
                    'The linter program exited unsuccessfully.'
                )
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    'The linter crashed unexpectedly',
                    linter_instance_id=linter_inst.id,
                    exc_info=True,
                )
                linter_inst.state = models.LinterState.crashed
            finally:
                if compl_proc is not None:
                    linter_inst.stdout = compl_proc.stdout.replace('\0', '')
                    linter_inst.stderr = compl_proc.stderr.replace('\0', '')
                db.session.commit()

    def test(
        self,
        linter_instance: models.LinterInstance,
        process_completed: ProcessCompletedCallback,
    ) -> None:
        """Test the given code (:class:`.models.Work`) and add generated
        comments.

        :param linter_instance: The linter instance that will be run. This
            linter instance is linked to a work from which all files will be
            restored and the linter will be run on those files.
        :param process_completed: The callback that should be called by the
            linter instance after the process, like pylint or java, has been
            completed.
        :returns: Nothing
        """
        temp_res: t.Dict[str, t.Dict[int, t.List[t.Tuple[str, str]]]]
        temp_res = {}
        res: t.Dict[int, t.Mapping[int, t.Sequence[t.Tuple[str, str]]]]
        res = {}

        with tempfile.TemporaryDirectory() as tmpdir:

            def __emit(f: str, line: int, code: str, msg: str) -> None:
                if f.startswith(tmpdir):
                    f = f[len(tmpdir) + 1:]
                if f not in temp_res:
                    temp_res[f] = {}
                line = line - 1
                if line not in temp_res[f]:
                    temp_res[f][line] = []
                temp_res[f][line].append((code, msg))

            tree_root = files.restore_directory_structure(
                linter_instance.work,
                tmpdir,
            )

            self.linter.run(
                files.safe_join(tmpdir, tree_root.name), __emit,
                process_completed
            )

        del tmpdir

        def __do(tree: files.FileTree[int], parent: str) -> None:
            # We can safely use os.path.join here as the contents of this path
            # will never be read.
            parent = os.path.join(parent, tree.name)
            if tree.entries is not None:  # this is dir:
                for entry in tree.entries:
                    __do(entry, parent)
            elif parent in temp_res:
                res[tree.id] = temp_res[parent]
                del temp_res[parent]

        __do(tree_root, '')

        meth = logger.warning if temp_res else logger.info
        meth('Finished adding linter comments', comments_left=temp_res)

        models.LinterComment.query.filter_by(linter_id=linter_instance.id
                                             ).delete()

        for comment in linter_instance.add_comments(res):
            db.session.add(comment)

        linter_instance.state = models.LinterState.done

        db.session.commit()


def get_all_linters(
) -> t.Dict[str, t.Dict[str, t.Union[str, t.Mapping[str, str]]]]:
    """Get an overview of all linters.

    The returned linters are all the subclasses of :class:`Linter`.

    :returns: A mapping of the name of the linter to a dictionary containing
        the description and the default options of the linter with that name

    .. testsetup::

        from psef.linters import get_all_linters, Linter

    .. doctest::

        >>> @_linter_handlers.register('MyLinter')
        ... class MyLinter(Linter): pass
        >>> MyLinter.__doc__ = "Description"
        >>> MyLinter.DEFAULT_OPTIONS = {'wow': 'sers'}
        >>> all_linters = get_all_linters()
        >>> sorted(all_linters.keys())
        ['Checkstyle', 'ESLint', 'Flake8', 'MixedWhitespace', 'MyLinter', 'PMD', 'Pylint']
        >>> linter = all_linters['MyLinter']
        >>> linter == {'desc': 'Description', 'opts': {'wow': 'sers'} }
        True
    """
    res = {}
    for name, cls in _linter_handlers.get_all():
        item: t.Dict[str, t.Union[str, t.Mapping[str, str]]]
        item = {
            'desc': cls.__doc__ or 'No linter documentation',
            'opts': cls.DEFAULT_OPTIONS,
        }
        res[name] = item
    return res


def get_linter_by_name(name: str) -> t.Type[Linter]:
    """Get the linter class associated with the given name.

    :param str name: The name of the linter wanted.
    :returns: The linter with the attribute `__name__` equal to `name`. If
        there are multiple linters with the name `name` the result can be any
        one of these linters.
    :raises KeyError: If the linter with the specified name is not found.
    """
    return _linter_handlers[name]
