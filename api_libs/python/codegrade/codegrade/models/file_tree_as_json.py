from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from typing import Any, Dict, List, Optional, cast

from ..utils import maybe_to_dict
from .file_tree_as_json_file import FileTree_AsJSONFile
from .types import File


@dataclass
class FileTreeAsJSON(FileTree_AsJSONFile):
    """  """

    entries: "Optional[List[FileTreeAsJSON]]" = None

    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()

        if self.entries is None:
            entries = None
        else:
            entries = []
            for entries_item_data in self.entries:
                entries_item = maybe_to_dict(entries_item_data)

                entries.append(entries_item)

        if self.entries is not None:
            res["entries"] = entries

        return res

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> FileTreeAsJSON:
        base = FileTree_AsJSONFile.from_dict(d).to_dict()
        entries = []
        for entries_item_data in d.get("entries") or []:
            entries_item = FileTreeAsJSON.from_dict(entries_item_data)

            entries.append(entries_item)

        return FileTreeAsJSON(**base, entries=entries, raw_data=d,)
