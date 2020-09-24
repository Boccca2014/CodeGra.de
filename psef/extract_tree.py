"""This file contains a common data structure for saving a directory.

SPDX-License-Identifier: AGPL-3.0-only
"""
import os
import abc
import typing as t
import dataclasses

import psef
from cg_maybe import Just, Maybe, Nothing
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
    _lookup: t.Dict[str, ExtractFileTreeBase] = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self._lookup = {}

    @property
    def only_child(self) -> Maybe[ExtractFileTreeBase]:
        if len(self._lookup) == 1:
            return Just(next(iter(self._lookup.values())))
        return Nothing

    @property
    def values(self) -> t.Iterable[ExtractFileTreeBase]:
        return self._lookup.values()

    @property
    def is_empty(self) -> bool:
        return not self._lookup

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

    def add_child(self, f: ExtractFileTreeBase) -> None:
        assert f.name not in self._lookup
        self._lookup[f.name] = f

    def lookup_direct_child(self,
                            name: str) -> t.Optional[ExtractFileTreeBase]:
        return self._lookup.get(name)

    def forget_child(self, f: ExtractFileTreeBase) -> None:
        """Remove a child as one of our children.

        .. note:: This does not delete the file.

        :param f: The file to forget.
        """
        f.forget_parent()
        self._lookup.pop(f.name)

    def __to_json__(self) -> t.Mapping[str, object]:
        return {
            'name': self.name,
            'entries': sorted(self.values, key=lambda x: x.name.lower()),
        }


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

    def insert_file(self, name: t.Sequence[str], backing_file: _File) -> None:
        base = self._find_child(name[:-1])
        base.add_child(
            ExtractFileTreeFile(
                name=name[-1], backing_file=backing_file, parent=None
            )
        )

    def insert_dir(self, name: t.Sequence[str]) -> None:
        base = self._find_child(name[:-1])
        base.add_child(ExtractFileTreeDirectory(name=name[-1], parent=None))

    def _find_child(self, name: t.Sequence[str]) -> ExtractFileTreeDirectory:
        cur: ExtractFileTreeDirectory = self
        for sub in name:
            prev = cur
            new_cur = cur.lookup_direct_child(sub)
            if new_cur is None:
                cur = ExtractFileTreeDirectory(name=sub, parent=None)
                prev.add_child(cur)
            else:
                assert isinstance(new_cur, ExtractFileTreeDirectory)
                cur = new_cur

        return cur

    def remove_leading_self(self) -> None:
        """Removing leading directories in this directory.

        This function checks if this directory contains exactly one directory,
        in this case this directory is removed and its content (of the deleted
        directory) becomes the content of this directory. The directory is
        modified in place.

        If one of the conditions don't hold a :exc:`AssertionError` is raised.
        """
        maybe_only_child = self.only_child
        assert maybe_only_child.is_just
        only_child = maybe_only_child.value
        assert isinstance(only_child, ExtractFileTreeDirectory)

        only_child.forget_parent()
        for grandchild in only_child.values:
            grandchild.parent = self

        self._lookup = {c.name: c for c in only_child.values}
