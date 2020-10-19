"""This module defines all routes for the internal brokers api.

SPDX-License-Identifier: AGPL-3.0-only
"""
import uuid

import cg_json

from . import api
from .. import models, helpers


@api.route('/brokers/<uuid:broker_id>', methods=['GET'])
def get_broker(broker_id: uuid.UUID
               ) -> cg_json.JSONResponse[models.BrokerSetting]:
    """Get a broker by its id.

    :param broker_id: The id of the broker to get.
    :returns: The requested broker.
    """
    broker = helpers.get_or_404(models.BrokerSetting, broker_id)
    return cg_json.JSONResponse.make(broker)
