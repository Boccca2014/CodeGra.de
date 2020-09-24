"""gitignore files.

For details for the matching rules, see https://git-scm.com/docs/gitignore.

This code is almost copied verbatim from dulwich.

SPDX-License-Identifier: AGPL-3.0-only
"""
import re
import abc
import copy
import enum
import typing as t
import os.path
from dataclasses import dataclass

import structlog

from . import app, helpers
from .helpers import register
from .exceptions import APICodes, APIException
from .extract_tree import (
    ExtractFileTree, ExtractFileTreeBase, ExtractFileTreeDirectory
)

logger = structlog.get_logger()

T_SF = t.TypeVar('T_SF', bound='SubmissionFilter')  # pylint: disable=invalid-name

filter_handlers: register.Register[str, t.Type['SubmissionFilter']
                                   ] = register.Register()


@enum.unique
class IgnoreHandling(enum.IntEnum):
    """Describes what to do with ignored files..

    :param keep: Nothing should be done with ignored files, simply keep them.
    :param delete: Ignored files should be deleted from the resulting
        directory.
    :param error: An exception should be raised when ignored files are found in
        the given archive.
    """

    keep: int = 1
    delete: int = 2
    error: int = 3


class ParseError(APIException):
    """The exception raised when parsing failed.
    """

    def __init__(self, msg: str) -> None:
        super().__init__(
            'Parsing the ignore file failed',
            msg,
            APICodes.PARSING_FAILED,
            400,
        )
        self.msg = msg


class DeletionType(enum.Enum):
    """What type of deletion was the file deletion.
    """
    empty_directory = enum.auto()
    denied_file = enum.auto()
    leading_directory = enum.auto()


@dataclass
class FileDeletion:
    """Class representing the deletion of a file or directory.
    """
    deletion_type: DeletionType
    deleted_file: ExtractFileTreeBase
    reason: t.Union[str, 'FileRule']

    def __post_init__(self) -> None:
        self.deleted_file = copy.deepcopy(self.deleted_file)

    def __to_json__(self) -> t.Mapping[str, t.Union[str, 'FileRule']]:
        return {
            'fullname': self.deleted_file.get_full_name(),
            'reason': self.reason,
            'deletion_type': self.deletion_type.name,
            'name': self.deleted_file.name,
        }

    def __structlog__(self) -> object:
        return self.__to_json__()


class SubmissionFilter:
    """Class representing the base submission filter.

    This filters a submission, and checks if the resulting submission is valid.
    """
    CGIGNORE_VERSION: t.ClassVar[int]

    @abc.abstractmethod
    def file_allowed(self, f: ExtractFileTreeBase) -> t.Optional[FileDeletion]:
        """Check if the given file adheres to this validator.

        :param f: The file to check.
        :returns: If the submission is valid.
        """
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def parse(cls: t.Type[T_SF], data: 'helpers.JSONType') -> T_SF:
        """Parse given data as submission filter

        :param data: The data to parse.
        :returns: An instance of this filter.
        :raises ParseError: When parsing failed for whatever reason.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def export(self) -> 'helpers.JSONType':
        """Export the this submission filter.

        :returns: The exported filter in such a way that when the return value
            of this function is given to :meth:`.SubmissionFilter.parse` it
            should produce the exact same filter.
        """
        raise NotImplementedError

    def _remove_leading_directories(
        self, tree: ExtractFileTree
    ) -> t.Tuple[ExtractFileTree, t.List[FileDeletion]]:
        """Remove leading directories from a given tree.

        :param tree: The tree to remove the directories from.
        :returns: The modified tree, and a list of files that were deleted.
        """
        # pylint: disable=no-self-use
        changes = []

        def is_dir(f: ExtractFileTreeBase) -> bool:
            return f.is_dir

        if tree.only_child.map(is_dir).or_default(False):
            tree = copy.deepcopy(tree)

        while tree.only_child.map(is_dir).or_default(False):
            changes.append(
                FileDeletion(
                    deletion_type=DeletionType.leading_directory,
                    deleted_file=tree,
                    reason='Leading directory',
                )
            )
            tree.remove_leading_self()

        return tree, changes

    def _delete_file(self, cur: ExtractFileTreeBase) -> t.List[FileDeletion]:
        if cur.is_dir:
            tree = t.cast(ExtractFileTreeDirectory, cur)
            res: t.List[FileDeletion] = []

            # Copy is needed here as we modify values by doing a `.delete` call
            # on one of the children.
            for child in list(tree.values):
                res.extend(self._delete_file(child))

            if tree.is_empty:
                deleted_tree = self.file_allowed(tree)
                if deleted_tree is not None:
                    res.append(deleted_tree)
                    tree.delete()

            return res
        else:
            deleted_file = self.file_allowed(cur)
            if deleted_file is None:
                return []
            cur.delete()
            return [deleted_file]

    def process_submission(
        self, tree: ExtractFileTree, handle_ignore: 'IgnoreHandling'
    ) -> t.Tuple['ExtractFileTree', t.List[FileDeletion], t.
                 List[t.Mapping[str, str]]]:
        """Process a submission with the given filter.

        This method will apply the filter, respecting the given
        ``handle_ignore``, deleting files from the given tree (in-place!).

        :param tree: The tree to check.
        :param handle_ignore: The way files that files that are ignored should
            be handled. There is not difference between ``error`` and
            ``delete``.
        :returns: A tuple, first containing the tree (however, the tree given
            is modified in-place!), a list of files and directories that are
            deleted, and finally a list of missing files.
        """
        total_changes = []

        tree, removed_top_dirs = self._remove_leading_directories(tree)
        total_changes.extend(removed_top_dirs)

        if handle_ignore != IgnoreHandling.keep:
            # Copy is needed here as we modify values by doing a `.delete` call
            # on one of the children.
            for child in list(tree.values):
                total_changes.extend(self._delete_file(child))

            tree, removed_top_dirs = self._remove_leading_directories(tree)
            total_changes.extend(removed_top_dirs)

        logger.info(
            'Processed submission with submission filter',
            changes=total_changes,
            resulting_tree=tree,
        )
        return tree, total_changes, self.get_missing_files(tree)

    @property
    def can_override_ignore_filter(self) -> bool:
        """Is it possible for users to override this ignore filter.
        """
        # pylint: disable=no-self-use
        return True

    def get_missing_files(self, tree: ExtractFileTree
                          ) -> t.List[t.Mapping[str, str]]:
        """Get all missing files for the given submission.

        :param tree: The tree to check for.
        :returns: A list of files, or file patterns, that are missing from the
            given tree.
        """
        # pylint: disable=no-self-use,unused-argument
        return []


@filter_handlers.register('EmptySubmissionFilter')
class EmptySubmissionFilter(SubmissionFilter):
    """A :class:`.SubmissionFilter` that does nothing.

    This filter allows all files, and all submissions are seen as valid.
    """
    CGIGNORE_VERSION = -1

    @classmethod
    def parse(cls, data: 'helpers.JSONType') -> 'EmptySubmissionFilter':
        return cls()

    def export(self) -> 'helpers.JSONType':
        return ''

    def file_allowed(self, f: ExtractFileTreeBase) -> t.Optional[FileDeletion]:
        return None


class Pattern:
    """A single ignore pattern."""

    def __init__(self, pattern: str, orig_line: str) -> None:
        self.pattern = pattern
        self.original_line = orig_line
        if pattern[0:1] == '!':
            self.is_exclude = False
            pattern = pattern[1:]
        else:
            if pattern[0:1] == '\\':
                pattern = pattern[1:]
            self.is_exclude = True
        flags = 0
        self._re = re.compile(self.translate(pattern), flags)

    def match(self, path: str) -> bool:
        """Try to match a path against this ignore pattern.

        :param path: Path to match (relative to ignore location)
        :return: boolean
        """
        return bool(self._re.match(path))

    @staticmethod
    def _translate_segment(segment: str) -> str:
        """Translate the given gitignore segment to regex segment.

        :param segment: The segment to translate.
        :returns: A valid regex string.
        """
        if segment == "*":
            return '[^/]+'

        res = []
        i, segment_length = 0, len(segment)
        while i < segment_length:
            char = segment[i:i + 1]
            i = i + 1
            if char == '*':
                res.append('[^/]*')
            elif char == '?':
                res.append('.')
            elif char == '[':
                j = i
                if j < segment_length and segment[j:j + 1] == '!':
                    j = j + 1
                if j < segment_length and segment[j:j + 1] == ']':
                    j = j + 1
                while j < segment_length and segment[j:j + 1] != ']':
                    j = j + 1
                if j >= segment_length:
                    res.append('\\[')
                else:
                    stuff = segment[i:j].replace('\\', '\\\\')
                    i = j + 1
                    if stuff.startswith('!'):
                        stuff = '^' + stuff[1:]
                    res.append('[' + stuff + ']')
            else:
                res.append(re.escape(char))

        return ''.join(res)

    @classmethod
    def translate(cls, pat: str) -> str:
        """Translate a shell PATTERN to a regular expression.

        There is no way to quote meta-characters.

        Originally copied from fnmatch in Python 2.7, but modified for Dulwich
        to cope with features in Git ignore patterns.
        """

        res = '(?ms)'

        if '/' not in pat[:-1]:
            # If there's no slash, this is a filename-based match
            res += '(.*/)?'

        if pat.startswith('**/'):
            # Leading **/
            pat = pat[2:]
            res += '(.*/)?'

        if pat.startswith('/'):
            pat = pat[1:]

        for i, segment in enumerate(pat.split('/')):
            if segment == '**':
                res += '(/.*)?'
            else:
                res += (
                    (re.escape('/') if i > 0 else '') +
                    cls._translate_segment(segment)
                )

        if not pat.endswith('/'):
            res += '/?'

        return res + r'\Z'


class IgnoreFilter:
    """A ignore filter. This filter consists of multiple :class:`.Filter`.
    """

    def __init__(self, patterns: t.Iterable[str]) -> None:
        self.original_input = patterns

        self._patterns: t.List[Pattern] = []
        for pattern, orig_line in self.read_ignore_patterns(patterns):
            self.append_pattern(pattern, orig_line)

    def append_pattern(self, pattern: str, orig_line: str) -> None:
        """Add a pattern to the set."""
        self._patterns.append(Pattern(pattern, orig_line))

    def find_matching(self, path: str) -> t.Iterable[Pattern]:
        """Yield all matching patterns for path.

        :param path: Path to match
        :return: Iterator over iterators
        """
        for pattern in self._patterns:
            if pattern.match(path):
                yield pattern

    @staticmethod
    def read_ignore_patterns(f: t.Iterable[str]
                             ) -> t.Iterable[t.Tuple[str, str]]:
        """Read a git ignore file.

        :param f: Iterable to read from
        :return: List of patterns
        """

        for line in f:
            line = line.rstrip('\r\n')
            original_line = line

            # Ignore blank lines, they're used for readability.
            if not line:
                continue

            if line.startswith('#'):
                # Comment
                continue

            # Trailing spaces are ignored unless they are quoted with a backslash.
            while line.endswith(' ') and not line.endswith('\\ '):
                line = line[:-1]
            line = line.replace('\\ ', ' ')

            yield line, original_line


@filter_handlers.register('IgnoreFilterManager')
class IgnoreFilterManager(SubmissionFilter):
    """Ignore file manager."""

    CGIGNORE_VERSION = 1

    def __init__(
        self,
        global_filters: t.Union[str, t.Sequence[str]],
    ) -> None:
        super().__init__()

        if isinstance(global_filters, str):
            global_filters = global_filters.split('\n')
        self._filter = IgnoreFilter(global_filters)

    @classmethod
    def parse(cls, data: 'helpers.JSONType') -> 'IgnoreFilterManager':
        if not isinstance(data, str):
            raise ParseError('CGIgnore version 1 should be given as a string.')
        return cls(data)

    def export(self) -> 'helpers.JSONType':
        return '\n'.join(self._filter.original_input)

    def find_matching(self, path: str) -> t.List[Pattern]:
        """Find matching patterns for path.

        Stops after the first ignore file with matches.

        :param path: Path to check
        :return: Iterator over Pattern instances
        """
        assert not os.path.isabs(path), f'File "{path}" is an absolute path'

        parts = path.split('/')

        for i in range(len(parts) + 1):
            relpath = '/'.join(parts[:i])

            if i < len(parts):
                # Paths leading up to the final part are all directories,
                # so need a trailing slash.
                relpath += '/'
            matches = list(self._filter.find_matching(relpath))
            if matches:
                return matches
        return []

    def is_ignored(self, path: str
                   ) -> t.Union[t.Tuple[bool, str], t.Tuple[None, None]]:
        """Check whether a path is explicitly included or excluded in ignores.

        :param path: Path to check
        :return: None if the file is not mentioned, True if it is included,
            False if it is explicitly excluded.
        """
        matches = self.find_matching(path)
        if matches:
            return matches[-1].is_exclude, matches[-1].original_line

        return None, None

    def file_allowed(self, f: ExtractFileTreeBase) -> t.Optional[FileDeletion]:
        """Check if the given file adheres to this validator.

        :param f: The file to check.
        :returns: If the submission is valid.
        """
        ignored, rule = self._check_file_allowed(f)
        if not ignored:
            return None
        assert rule is not None
        return FileDeletion(
            deletion_type=DeletionType.denied_file,
            deleted_file=f,
            reason=rule,
        )

    def _check_file_allowed(
        self, f: ExtractFileTreeBase
    ) -> t.Union[t.Tuple[bool, str], t.Tuple[None, None]]:
        return self.is_ignored(f.get_full_name())


T_SV = t.TypeVar('T_SV', bound='SubmissionValidator')  # pylint: disable=invalid-name


@dataclass
class FileRule:
    """A FileRule allows, disallows or requires a certain file or directory.
    """

    class Filename:
        """A filename is something with a ``name`` and ``dir_names``
        """
        _split_regex = re.compile(r'(?<!\\)/')

        def __init__(self, filename: str):
            parts = self.split_into_parts(filename)
            assert parts
            escaped_name = parts.pop(-1)
            self.name = self._remove_escape_chars(escaped_name)
            self.dir_names = [p for p in parts if p]
            self.from_root = filename.startswith('/')

            _, indices = FileRule.count_chars('*', escaped_name)
            assert len(indices) < 2
            self.wildcard_index = indices[0] if indices else None

        @staticmethod
        def _remove_escape_chars(filename: str) -> str:
            """Remove backslashes escaping from a filename.

            >>> FileRule.Filename._remove_escape_chars('hello\\\\*.py')
            'hello*.py'
            >>> FileRule.Filename._remove_escape_chars('hello*.py')
            'hello*.py'
            >>> FileRule.Filename._remove_escape_chars('hello\\\\\\\\.py')
            'hello\\\\.py'
            >>> len(FileRule.Filename._remove_escape_chars('hello\\\\\\\\.py'))
            9
            """
            if '\\' not in filename:
                return filename

            res = []
            next_literal = False
            for char in filename:
                if next_literal:
                    res.append(char)
                    next_literal = False
                elif char == '\\':
                    next_literal = True
                else:
                    res.append(char)
            return ''.join(res)

        @classmethod
        def split_into_parts(cls, filename: str) -> t.List[str]:
            """Split a file into directory parts, respecting escaping.

            :param filename: The filename to split.
            :returns: A list of file parts.
            """
            return re.split(cls._split_regex, filename)

        def __str__(self) -> str:
            """Convert a filename to a string.

            >>> str(FileRule.Filename('/hello'))
            '/hello'
            >>> str(FileRule.Filename('hello/abc/d.e'))
            'hello/abc/d.e'
            >>> str(FileRule.Filename('/hello/'))
            '/hello/'
            >>> str(FileRule.Filename('hello'))
            'hello'
            >>> str(FileRule.Filename('hello/abc/'))
            'hello/abc/'
            """
            begin = '/' if self.from_root else ''
            if self.dir_names:
                return '{}{}/{}'.format(
                    begin, '/'.join(self.dir_names), self.name
                )
            else:
                return f'{begin}{self.name}'

        def matches(self, f: ExtractFileTreeBase) -> bool:
            """Check if a file matches this filename pattern.

            :param f: The file you want to check.
            :returns: ``True`` if this patterns matches the given file,
                ``False`` otherwise.
            """
            name_list = f.get_name_list()
            if self.name:
                if not self.__filename_matches(name_list[-1]):
                    return False
                name_list = name_list[:-1]
            res = self.__dir_matches(name_list)
            return res

        def __filename_matches(self, f_name: str) -> bool:
            if self.wildcard_index is None:
                return self.name == f_name
            else:
                before = self.name[:self.wildcard_index]
                after = self.name[self.wildcard_index + 1:]

                if before:
                    if not f_name.startswith(before):
                        return False
                    f_name = f_name[len(before):]

                if after and not f_name.endswith(after):
                    return False

                return True

        def __dir_matches(self, f_names: t.Sequence[str]) -> bool:
            if self.from_root:
                return f_names[:len(self.dir_names)] == self.dir_names
            elif not self.dir_names:
                return True
            else:
                return helpers.is_sublist(self.dir_names, f_names)

    class RuleType(enum.Enum):
        """A rule type specifies if a file is allowed, required, or disallowed.
        """
        allow = enum.auto()
        deny = enum.auto()
        require = enum.auto()

        def __str__(self) -> str:
            return self.name.title()

    class FileType(enum.Enum):
        """Is the file a file or a directory.
        """
        file = enum.auto()
        directory = enum.auto()

        def __str__(self) -> str:
            return self.name.title()

    @property
    def is_dir_rule(self) -> bool:
        """Is this a directory rule
        """
        return not self.filename.name

    rule_type: RuleType
    file_type: FileType
    filename: Filename

    @staticmethod
    def count_chars(needle: str, filename: str) -> t.Tuple[int, t.List[int]]:
        """Count the amount the needle occurs in the filename, with escaping.

        >>> FileRule.count_chars('*', '/hello.py/\\\\**')[0]
        1
        >>> FileRule.count_chars('*', '/hello.py/\\\\*')[0]
        0
        >>> FileRule.count_chars('*', '*/hello*.py/\\\\*')[0]
        2

        :param needle: A string with a length of 1, which should be searched.
        :param filename: The filename which should be searched for the needle.
        :returns: A tuple, the first element is the amount of times needle was
            found, and the second element are the indices where needle was
            found.
        """
        indices = []
        assert len(needle) == 1
        skip_next = False
        res = 0

        for i, char in enumerate(filename):
            if skip_next:
                skip_next = False
            elif char == '\\':
                skip_next = True
            elif char == needle:
                indices.append(i)
                res += 1

        return res, indices

    def __to_json__(self) -> t.Mapping[str, str]:
        return {
            'file_type': self.file_type.name,
            'name': str(self.filename),
            'rule_type': self.rule_type.name,
        }

    @classmethod
    def parse(cls, data: 'helpers.JSONType') -> 'FileRule':
        """Parse a file rule.

        :param data: The rule that should be parsed
        :returns: The parsed ``FileRule``.
        """
        if not isinstance(data, dict):
            raise ParseError('A rule should be given as a map.')

        try:
            rule_type = cls.RuleType[data.get('rule_type')]  # type: ignore
        except KeyError as exc:
            raise ParseError(
                f'The given rule type ("{data.get("rule_type")}") is not'
                ' valid.'
            ) from exc

        if data.get('file_type') not in {'file', 'directory'}:
            raise ParseError(
                f'Unknown file type, got "{data.get("file_type")}"'
                f'  but only "file" or "directory" is allowed.'
            )
        file_type = cls.FileType[t.cast(str, data.get('file_type'))]
        filename = data.get('name')

        if not filename or not isinstance(filename, str):
            raise ParseError(
                'The filename of a rule should be a non empty string, but got:'
                f' "{filename}"'
            )

        star_amount, star_indices = cls.count_chars('*', filename)
        if file_type == cls.FileType.directory and star_amount > 0:
            raise ParseError(
                f'Directories cannot contain wildcards, but "{filename}"'
                f' filename {star_amount}'
                f' wildcard{"s" if star_amount > 1 else ""}.'
            )
        elif star_amount > 1:
            raise ParseError(
                f'Files can only contain one wildcard but "{filename}"'
                f' contains {star_amount} wildcards.'
            )
        elif (
            file_type == cls.FileType.file and star_amount > 0 and
            cls.count_chars('/', filename[star_indices[0] + 1:])[0] > 0
        ):
            raise ParseError(
                'Files can only contain a wildcard for the name of the file,'
                f' not for preceding directories, however "{filename}"'
                ' contains a wildcard in the directory name.'
            )

        f = cls.Filename(filename)
        if f.name == '' and file_type == cls.FileType.file:
            raise ParseError(
                f'Filenames should not end with a "/", but "{filename}" ends'
                ' with a "/" , you can escape the slash by placing a "\\"'
                ' before the slash.'
            )
        elif f.name != '' and file_type == cls.FileType.directory:
            raise ParseError(
                f'Directory names should end with a "/", but "{filename}" ends'
                ' with "{f.name}".'
            )

        return cls(
            rule_type=rule_type,
            file_type=file_type,
            filename=f,
        )

    def __str__(self) -> str:
        return f'{self.rule_type} {self.file_type} {self.filename}'

    def matches(self, f: ExtractFileTreeBase) -> bool:
        """Check if a file matches this rule.

        :param f: The file that should be checked.
        :returns: A boolean indicating if the given file matches this rule.
        """
        return self.filename.matches(f)


@dataclass(eq=False)
class _OptionNameValue:
    required: bool
    default: bool


class Options:
    """All options that can be set.
    """

    @enum.unique
    class OptionName(enum.Enum):
        """Enum representing the name of each option.
        """
        delete_empty_directories = _OptionNameValue(
            required=False, default=False
        )
        remove_leading_directories = _OptionNameValue(
            required=False, default=True
        )
        allow_override = _OptionNameValue(required=False, default=False)

    def __init__(self) -> None:
        self._opts: t.Dict[Options.OptionName, bool] = {}

    def parse_option(self, rule: 'helpers.JSONType') -> None:
        """Parse a option

        """
        if not isinstance(rule, dict):
            raise ParseError('An option should be given as a map.')

        val = rule.get('value')
        if not isinstance(val, bool):
            raise ParseError(
                'The "value" key was not found or was not a boolean in:'
                f' "{rule}".',
            )

        option_name = rule.get('key')
        for option in self.OptionName:
            if option.name == option_name:
                if option in self._opts:
                    raise ParseError(
                        f'Option "{option_name}" was specified multiple times.'
                    )
                self._opts[option] = val
                break
        else:
            raise ParseError(
                f'Option "{option_name}" is not a valid option,'
                ' expected one of {}.'.format(
                    ', '.join(o.name for o in self.OptionName)
                )
            )

    def get(self, option: 'Options.OptionName') -> bool:
        """Get an option returning its default value when it is not set.

        :param option: The option to get.
        :returns: The value it has been set to or its default value.
        """
        if option in self._opts:
            return self._opts[option]
        return option.value.default


@filter_handlers.register('SubmissionValidator')
class SubmissionValidator(SubmissionFilter):
    """Validate a submission using a config file.
    """

    CGIGNORE_VERSION = 2

    class Policy(enum.Enum):
        """The default policy used by this validator.
        """
        deny_all_files = enum.auto()
        allow_all_files = enum.auto()

    @classmethod
    def parse(cls, data: 'helpers.JSONType') -> 'SubmissionValidator':
        """Parse and validate the given data as a config for the validator.

        :param data: The data of the config file.
        :returns: A submission validator with policy, options, and rules as
            described in the given data.
        :raises ParseError: When the given data is not valid.
        """
        if not isinstance(data, dict):
            raise ParseError(
                'The submission validator should be a dictionary.'
            )
        opts = Options()
        rules: t.List[FileRule] = []

        required_keys = ['policy', 'rules', 'options']
        if any(key not in data.keys() for key in required_keys):
            raise ParseError(
                'Not all required keys are found in the given config, all of'
                f' "{", ".join(required_keys)}" are required, but only'
                f' "{", ".join(data.keys())}" were found.'
            )

        given_policy = data['policy']
        given_options = data['options']
        given_rules = data['rules']

        if given_policy == 'allow_all_files':
            policy = cls.Policy.allow_all_files
        elif given_policy == 'deny_all_files':
            policy = cls.Policy.deny_all_files
        else:
            raise ParseError(
                f'The policy "{given_policy}" is not known, only the'
                ' policies "{}" are known.'.format(
                    ', '.join(p.name for p in cls.Policy)
                )
            )

        if policy == cls.Policy.deny_all_files and not given_rules:
            raise ParseError(
                f'When the policy is set to "{policy.name}" it is required to'
                ' have rules that allow or require some files.'
            )

        if (
            not isinstance(given_options, list) or
            not isinstance(given_rules, list)
        ):
            raise ParseError(
                'The rules and options should be given as a list.'
            )

        for given_opt in given_options:
            opts.parse_option(given_opt)

        for given_rule in given_rules:
            rules.append(FileRule.parse(given_rule))

        disallow_rule = (
            FileRule.RuleType.allow
            if policy == cls.Policy.allow_all_files else FileRule.RuleType.deny
        )
        for rule in rules:
            if rule.rule_type == disallow_rule:
                raise ParseError(
                    f'The policy is set to "{policy.name}", so it is not'
                    f' possible to have a rule "{rule}" as it is only possible'
                    f' to {str(rule.rule_type).lower()} files when the policy'
                    f' is not "{policy.name}".'
                )

        return cls(policy, opts, rules, data=data)

    def export(self) -> 'helpers.JSONType':
        return self._data

    def __init__(
        self,
        policy: Policy,
        options: Options,
        rules: t.List[FileRule],
        data: 'helpers.JSONType',
    ) -> None:
        super().__init__()
        self.policy = policy
        self.options = options
        self.rules = rules
        self._data = data

    def file_allowed(self, f: ExtractFileTreeBase) -> t.Optional[FileDeletion]:
        """Check if the given file adheres to this validator.

        :param f: The file to check.
        :returns: If the submission is valid.
        """
        if (
            isinstance(f, ExtractFileTreeDirectory) and f.is_empty and
            self.options.get(Options.OptionName.delete_empty_directories)
        ):
            return FileDeletion(
                deletion_type=DeletionType.empty_directory,
                deleted_file=f,
                reason='Empty directory'
            )

        if self.policy == self.Policy.deny_all_files:
            if not any(rule.matches(f) for rule in self.rules):
                return FileDeletion(
                    deletion_type=DeletionType.denied_file,
                    deleted_file=f,
                    reason='Default policy, no rule matches',
                )
        elif self.policy == self.Policy.allow_all_files:
            for rule in self.rules:
                if rule.rule_type == rule.RuleType.require and rule.matches(f):
                    return None
            for rule in self.rules:
                if rule.rule_type == rule.RuleType.deny and rule.matches(f):
                    return FileDeletion(
                        deletion_type=DeletionType.denied_file,
                        deleted_file=f,
                        reason=rule,
                    )
        return None

    def _remove_leading_directories(
        self, tree: ExtractFileTree
    ) -> t.Tuple[ExtractFileTree, t.List[FileDeletion]]:
        if not self.options.get(Options.OptionName.remove_leading_directories):
            return tree, []
        return super()._remove_leading_directories(tree)

    def get_missing_files(self, tree: ExtractFileTree
                          ) -> t.List[t.Mapping[str, str]]:
        required_files = [
            r for r in self.rules if r.rule_type == FileRule.RuleType.require
        ]
        found: t.Set[int] = set()

        stop = False
        for f in tree.get_all_children():
            for idx, required_file in enumerate(required_files):
                if not required_file.matches(f):
                    continue
                # Directory rules are only satisfied when there is a file
                # or subdirectory in the directory. So if we match a directory
                # rule we should only remove it if we are a child in this
                # directory. We check if we are a child in this directory
                # by checking if our parent also matches the rule.
                if required_file.is_dir_rule and (
                    f.parent is None or not required_file.matches(f.parent)
                ):
                    continue
                # Directories can never satisfy a file rule. Their children
                # can, and may do so in their own iteration of the outer loop.
                if not required_file.is_dir_rule and f.is_dir:
                    continue

                found.add(idx)

                if len(found) == len(required_files):
                    stop = True
                    break

            if stop:
                break

        logger.info(
            'Found missing files', reqiured_files=required_files, found=found
        )
        return [
            r.__to_json__() for idx, r in enumerate(required_files)
            if idx not in found
        ]

    @property
    def can_override_ignore_filter(self) -> bool:
        return self.options.get(Options.OptionName.allow_override)
