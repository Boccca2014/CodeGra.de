"""This module defines a models to store some binary data in the database.

Do not use these blobs for things like file storage, but only for temporary
storage of data. The only use as of writing is temporary storing of lti launch
data.

SPDX-License-Identifier: AGPL-3.0-only
"""
import json as _json
import typing as t
import datetime

import psef
import cg_cache.intra_request
from cg_sqlalchemy_helpers.mixins import UUIDMixin, TimestampMixin

from . import Base, db


class BlobStorage(Base, UUIDMixin, TimestampMixin):
    """This class represents a blob indexed by a uuid.

    :ivar data: The data that is stored in this blob.
    """
    data = db.Column('data', db.LargeBinary, nullable=False)

    @t.overload
    def __init__(self, *, data: bytes) -> None:
        ...

    @t.overload
    def __init__(self, *, json: 'psef.helpers.JSONType') -> None:
        ...

    def __init__(
        self,
        *,
        data: bytes = None,
        json: 'psef.helpers.JSONType' = None,
    ) -> None:
        if data is None:
            assert json is not None
            data = _json.dumps(json).encode('utf8')
        super().__init__(data=data)

    @property
    def age(self) -> datetime.timedelta:
        """Get the age of this blob storage.
        """
        return psef.helpers.get_request_start_time() - self.created_at

    @cg_cache.intra_request.cache_for_object_id
    def as_json(self) -> 'psef.helpers.JSONType':
        """Get the json data from this blob parsed and ready to go.

        This method caches the parsing of the json, so it will be more
        efficient than manually parsing the data of this blob multiple times.
        However, be careful when changing the ``data`` attribute of the class,
        we will not detect it and the value returned by this method will be
        incorrect.
        """
        return _json.loads(self.data.decode('utf8'))
