"""This file contains a common data structure for saving a directory.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import abc
import typing as t
import dataclasses

import psef
from cg_object_storage import File as _File
from cg_object_storage import FileSize

if t.TYPE_CHECKING and not getattr(t, 'SPHINX', False):  # pragma: no cover
    # pylint: disable=unused-import
    import psef.files


# This is a bug: https://github.com/python/mypy/issues/5374
@dataclasses.dataclass  # type: ignore
class ExtractFileTreeBase:
    """Base type for an entry in an extracted file tree.

    :ivar ~.ExtractFileTreeBase.name: The original name of this file in the
        archive that was extracted.
    """
    name: str
    parent: t.Optional['ExtractFileTreeDirectory']

    def __post_init__(self) -> None:
        self.name = psef.files.escape_logical_filename(self.name)

    def forget_parent(self) -> None:
        self.parent = None

    def delete(self) -> None:
        """Delete the this file and all its children.

        :param base_dir: The base directory where the files can be found.
        :returns: Nothing.
        """
        # pylint: disable=unused-argument
        if self.parent is not None:
            self.parent.forget_child(self)

    def get_full_name(self) -> str:
        """Get the full filename of this file including all its parents.
        """
        name = '/'.join(
            part.replace('/', '\\/') for part in self.get_name_list()
        )
        if self.is_dir:
            name += '/'
        return name

    def get_name_list(self) -> t.Sequence[str]:
        """Get the filename of this file including all its parents as a list.
        """
        if self.parent is None:
            return []
        else:
            return [*self.parent.get_name_list(), self.name]

    @abc.abstractmethod
    def get_size(self) -> FileSize:
        """Get the size of this file.

        For a normal file this is the amount of space used on disk, and for a
        directory it is the sum of the space of all its children.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def is_dir(self) -> bool:
        """Is this file a directory.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def __to_json__(self) -> t.Mapping[str, object]:
        raise NotImplementedError

    def __structlog__(self) -> t.Mapping[str, object]:
        return self.__to_json__()


@dataclasses.dataclass
class ExtractFileTreeFile(ExtractFileTreeBase):
    """Type used to represent a file in an extracted file tree.

    :ivar ~.ExtractFileTreeFile.diskname: The name of the file saved in the
        uploads directory.
    """
    backing_file: _File

    def get_size(self) -> FileSize:
        return self.backing_file.size

    def delete(self) -> None:
        super().delete()
        self.backing_file.delete()

    @property
    def is_dir(self) -> bool:
        return False

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'name': self.name,
        }


@dataclasses.dataclass
class ExtractFileTreeSpecialFile(ExtractFileTreeFile):
    """Type used to represent a special file.

    This is exactly the same as a normal file, only we allow these files to
    have __reserved__ filenames. Only construct these with hard-coded
    filenames.
    """

    def __post_init__(self) -> None:
        # These files DO NOT need to be escaped, as their names are hard-coded
        # and trusted.
        pass


@dataclasses.dataclass
class ExtractFileTreeDirectory(ExtractFileTreeBase):
    """Type used to represent a directory of an extracted file tree.

    :ivar ~.ExtractFileTreeDirectory.values: The items present in this
        directory.
    """
    values: t.List[ExtractFileTreeBase]

    def get_size(self) -> FileSize:
        return FileSize(sum(c.get_size() for c in self.values))

    def delete(self) -> None:
        super().delete()
        for val in self.values:
            val.delete()

    def get_all_children(self) -> t.Iterable['ExtractFileTreeBase']:
        """Get all the children of this directory.

        :returns: An iterable of all children, including directories.
        """
        for val in self.values:
            yield val
            if isinstance(val, ExtractFileTreeDirectory):
                yield from val.get_all_children()

    @property
    def is_dir(self) -> bool:
        return True

    def forget_child(self, f: ExtractFileTreeBase) -> None:
        """Remove a child as one of our children.

        .. note:: This does not delete the file.

        :param f: The file to forget.
        """
        f.forget_parent()
        self.values.remove(f)

    def add_child(self, f: ExtractFileTreeBase) -> None:
        """Add a directory as a child.

        :param f: The file to add.
        """
        assert f is not self
        assert f.parent is None

        f.parent = self
        self.values.append(f)

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'name': self.name,
            'entries': sorted(self.values, key=lambda x: x.name.lower()),
        }

    def fix_duplicate_filenames(self) -> None:
        """Fix duplicate filenames in this directory and all its sub
        directories.

        This will rename files when duplicates are detected by adding a ``
        ($number)`` suffix to the file.
        """
        psef.files.fix_duplicate_filenames(self.values)

        for child in self.values:
            if isinstance(child, ExtractFileTreeDirectory):
                child.fix_duplicate_filenames()


@dataclasses.dataclass
class ExtractFileTree(ExtractFileTreeDirectory):
    """Type used to represent the top of an extracted file tree.

    This is simply a directory with some utility methods.
    """

    @property
    def contains_file(self) -> bool:
        """Check if archive contains something other than directories.

        :returns: If the file tree contains actual files
        """
        return any(
            isinstance(v, ExtractFileTreeFile) for v in self.get_all_children()
        )

    def remove_leading_self(self) -> None:
        """Removing leading directories in this directory.

        This function checks if this directory contains exactly one directory,
        in this case this directory is removed and its content (of the deleted
        directory) becomes the content of this directory. The directory is
        modified in place.

        If one of the conditions don't hold a :exc:`AssertionError` is raised.
        """
        # pylint: disable=access-member-before-definition,attribute-defined-outside-init
        # Pylint is too stupid to see that this property already exists.
        assert len(self.values) == 1
        assert isinstance(self.values[0], ExtractFileTreeDirectory)
        child = self.values[0]
        child.forget_parent()
        for grandchild in child.values:
            grandchild.parent = self
        self.values = child.values
