"""
This module defines all classes and function needed for the plagiarism checking
infrastructure.

The actual providers are located in the :mod:`psef.plagiarism_providers`
module.

SPDX-License-Identifier: AGPL-3.0-only
"""
import abc
import csv
import enum
import typing as t
import dataclasses

import structlog

from . import files, errors, models, helpers, plagiarism_providers

logger = structlog.get_logger()


def init_app(app: t.Any) -> None:
    """Initialize providers for the given flask app.

    :param: The flask app to initialize for.
    :returns: Nothing
    """
    plagiarism_providers.init_app(app)


@enum.unique
class OptionTypes(enum.IntEnum):
    """Describes the type of the option

    :param multiselect: An option that should be one or more values from the
        ``possible_options`` list. It should be passed back as an array of
        values, not indices!.
    :param singleselect: The same as ``multiselect``, only it can be one value
        and it should be passed back as that value, not an array.
    :param numbervalue: An option that should be a number.
    :param strvalue: An option that should be a string.
    """
    multiselect: int = 1
    singleselect: int = 2
    numbervalue: int = 3
    strvalue: int = 4


@dataclasses.dataclass(frozen=True)
class Option:
    """Represents a single option for a plagiarism provider.

    :param name: The name of the option.
    :param title: The title of the option.
    :param description: The description of the options.
    :param type: The type of this option.
    :param mandatory: If this is ``True`` the plagiarism provider can only
        function when this option is supplied.
    :param possible_options: Possible values for this option. This value has to
        be a non empty sequence if the ``type`` is ``multiselect`` or
        ``singleselect``.
    """
    name: str
    title: str
    description: str
    type: OptionTypes
    mandatory: bool
    possible_options: t.Optional[t.Sequence[str]]
    placeholder: t.Optional[str] = None

    def __to_json__(self) -> t.Mapping[str, object]:
        res: t.Dict[str, object] = dataclasses.asdict(self)

        if self.type not in (
            OptionTypes.multiselect,
            OptionTypes.singleselect,
        ):
            del res['possible_options']

        res['type'] = self.type.name

        return res


def process_output_csv(
    lookup_map: t.Mapping[str, int],
    old_submissions: t.Container[int],
    file_tree_lookup: t.Mapping[int, files.FileTree[int]],
    csvfile: str,
    delimiter: str = ';',
) -> t.List[models.PlagiarismCase]:
    """Process the outputted csv file into plagiarism cases with matches.

    Each line of the csvfile should have the following items separated by
    ``delimiter``:

    1. The top level directory of the first submission;
    2. The top level directory of the second submission;
    3. The amount that submission 1 matched with submission 2;
    4. The amount that submission 2 matched with submission 1;
    5. The relative path of first file that matched;
    6. The start position were the match for the first file begins;
    7. The end position were the match for the first file ends;
    8. The relative path of second file that matched;
    9. The start position were the match for the second file begins;
    10. The end position were the match for the second file ends;

    Fields 5-10 can occur any number of times, but have to occur at least once.

    :param lookup_map: A dictionary that should map the name of each toplevel
        directory to a submission id.
    :param old_submissions: Some sort of set that contains the ids of all
        submissions that are old. If a match between two of those submissions
        is found this match in not inserted into the database.
    :param file_tree_lookup: A lookup that maps submission ids to their file
        trees.
    :param csvfile: The location of the csv file that follow the above format.
    :param delimiter: The delimiter used for this csv file.
    """
    res = []
    seen: t.Dict[t.Tuple[int, int], models.PlagiarismCase] = {}

    with open(csvfile, newline='') as f:
        for dir1, dir2, match1, match2, *matches in csv.reader(
            f,
            delimiter=delimiter,
        ):
            sub1_id = lookup_map[dir1]
            sub2_id = lookup_map[dir2]

            if sub1_id in old_submissions and sub2_id in old_submissions:
                continue

            if sub1_id == sub2_id:
                logger.warning(
                    'Found plagiarism within a submission',
                    submission_id=sub1_id
                )
                continue

            tup = t.cast(t.Tuple[int, int], tuple(sorted((sub1_id, sub2_id))))
            if tup in seen:
                logger.warning(
                    'Duplicate plagiarism case in csv file',
                    submission1_id=sub1_id,
                    submission2_id=sub2_id,
                )
                new_case = seen[tup]
            else:
                match_max = max(float(match1), float(match2))
                match_avg = (float(match1) + float(match2)) / 2
                new_case = models.PlagiarismCase(
                    work1_id=sub1_id,
                    work2_id=sub2_id,
                    match_avg=match_avg,
                    match_max=match_max,
                )
                seen[tup] = new_case

            for match in zip(*[iter(matches)] * 6):
                fname1, fstart1, fend1, fname2, fstart2, fend2 = match
                f_id1 = files.search_path_in_filetree(
                    file_tree_lookup[sub1_id],
                    fname1,
                )
                f_id2 = files.search_path_in_filetree(
                    file_tree_lookup[sub2_id],
                    fname2,
                )
                new_case.matches.append(
                    models.PlagiarismMatch(
                        file1_id=f_id1,
                        file2_id=f_id2,
                        file1_start=fstart1,
                        file1_end=fend1,
                        file2_start=fstart2,
                        file2_end=fend2,
                    )
                )
            res.append(new_case)

    return res


class PlagiarismProvider(metaclass=abc.ABCMeta):
    """The (abstract) base class every plagiarism provider should inherit from.

    The main functionality each implementation should provide are options and
    mapping those options to a program call (the actual plagiarism checking
    should be done in an external program). This program is called from a
    celery task and should produce log on ``stdout`` and ``stderr``, and a csv
    file that should follow the format expected by
    :func:`process_output_csv`. If the csv needs to be transformed this can be
    done using :func:`PlagiarismProvider.transform_csv` which is called just
    before the csv file is processed.
    """

    @classmethod
    def get_name(cls) -> str:
        """Get the name of this provider.
        """
        return cls.__name__

    @staticmethod
    def supports_base_code() -> bool:
        """Does this provider support base code.

        :returns: A boolean indicating if the provider supports base code.
        """
        return True

    @staticmethod
    def transform_csv(csvfile: str) -> str:
        """Transform the csv file outputed by the plagiarism checker to
            something that is readable by :func:`process_output_csv`.

        :param csvfile: The location of the old csv file.
        :returns: The location of the csv file that can be processed by
            :func:`process_output_csv`.
        """
        return csvfile

    @staticmethod
    @abc.abstractmethod
    def supports_progress() -> bool:
        """Does this provider support showing progress to the user.

        :returns: ``True`` if this provider supports progress detection.
        """
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def get_progress_from_line(prefix: str,
                               line: str) -> t.Optional[t.Tuple[int, int]]:
        """Get the progress of the plagiarism provider.

        This function is called for every line of output produced by the
        provider. This should return two values, the first value should be the
        amount of submissions processed and the second the total amount. These
        values first indicate that this many submissions have been parsed. When
        the first value is equal to the second value it means that all
        submissions have been parsed and that comparing has started.

        You should return ``None`` if the given line doesn't contain progress
        information.

        :returns: Two values or ``None`` as described above.
        """
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def get_options() -> t.Sequence[Option]:
        """Get all possible options for this provider.

        This function needs to be implemented by the provider.

        :returns: A list of possible options for this plagiarism provider.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def matches_output(self) -> str:
        """The path of the csv file that contains the matches in the correct
        format.

        This function needs to be implemented by the provider.

        :returns: The path of the result csv relative to the
            ``{ result_dir }``.
        """
        raise NotImplementedError

    @staticmethod
    def _check_multiselect(val: object, opt: Option) -> t.List[str]:
        """Check if a given value ``v`` is valid for the given multiselect.

        :param val: The object to check.
        :param opt: The multiselect to check for.
        :returns: A list of all errors.
        """
        errs = []
        if not isinstance(val, list):
            errs.append(
                f'The value for "{opt.name}" should '
                f'be a list but is a "{type(val)}"'
            )
        else:
            for item in val:
                # This is only None for things that are not selectables
                assert opt.possible_options is not None

                if item not in opt.possible_options:
                    errs.append(
                        f'The value "{item}" is not '
                        f'possible for "{opt.name}"'
                    )
        return errs

    @staticmethod
    def _check_singlevalue(
        val: object,
        opt: Option,
        typ: helpers.IsInstanceType,
    ) -> t.List[str]:
        """Check if a given value ``v`` is valid for the given singlevalue.

        :param val: The object to check.
        :param opt: The single to check for.
        :param typ: The required type for the value.
        :returns: A list of all errors.
        """
        if not isinstance(typ, tuple):
            typ = (typ, )

        if not isinstance(val, typ):
            return [
                (
                    f'The type of "{opt.name}" is not correct '
                    f'(it should be a "{" or ".join(map(str, typ))}", '
                    f'but it is a "{type(val)}").'
                )
            ]
        return []

    def set_options(self, values: helpers.JSONType) -> None:
        """Set the options for this plagiarism provider.

        :param values: The options for this run, this can still include the
            ``provider`` and ``old_assignments`` key.
        :returns: Nothing.

        :raises APIException: If the values are not the correct format, if
            mandatory options miss, if an option has an incorrect value or if
            given value was not recognized.
        """
        complete_values = helpers.ensure_json_dict(values)
        values = complete_values.copy()
        values.pop('provider', None)
        values.pop('old_assignments', None)
        values.pop('has_base_code', None)
        values.pop('has_old_submissions', None)
        seen = set()

        errs = []
        for opt in self.get_options():
            if opt.name in values:
                val = values[opt.name]
                seen.add(opt.name)
                if opt.type is OptionTypes.multiselect:
                    errs.extend(self._check_multiselect(val, opt))
                elif opt.type is OptionTypes.singleselect:
                    errs.extend(self._check_multiselect([val], opt))
                elif opt.type in {
                    OptionTypes.strvalue,
                    OptionTypes.numbervalue,
                }:
                    typ: helpers.IsInstanceType
                    if opt.type is OptionTypes.strvalue:
                        typ = str
                    else:
                        typ = (int, float)
                    errs.extend(self._check_singlevalue(
                        val,
                        opt,
                        typ,
                    ))
            elif opt.mandatory:
                errs.append(
                    f'The option "{opt.name}" is not present but is mandatory'
                )
        for missed_key in set(values.keys()) - seen:
            missed_value = values[missed_key]
            errs.append(
                f'The option "{missed_key}" with '
                f'value "{missed_value}" is unknown.'
            )

        if errs:
            raise errors.APIException(
                'The given config is not valid for this provider',
                'Some options are invalid or missing',
                errors.APICodes.INVALID_PARAM,
                400,
                invalid_options=errs
            )
        else:
            self._set_provider_values(complete_values)

    @abc.abstractmethod
    def _set_provider_values(
        self, values: t.Dict[str, helpers.JSONType]
    ) -> None:
        """Set the provided values as options.

        When this function is called you can assume that the provided values
        are valid.

        This function needs to be implemented by the provider.

        :returns: Nothing
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_program_call(self) -> t.List[str]:
        """Get a program call list that runs the checker.

        This list is used as the first argument to
        :func:`subprocess.check_output`, with ``shell=False``. It can contain
        two special entries:

        1. ``'{ restored_dir }'``: This will be replaced with the location of
        the files that need to be checked.

        2. ``'{ result_dir }'``: This will be replaced with the directory where
        the result csv needs to be placed.

        This function needs to be implemented by the provider.

        :returns: A list as that can be used with
            :func:`subprocess.check_output`.
        """
        raise NotImplementedError
