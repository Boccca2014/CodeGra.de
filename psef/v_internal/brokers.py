import uuid

import cg_json

from . import api
from .. import models, helpers


@api.route('/brokers/<uuid:broker_id>', methods=['GET'])
def get_broker(broker_id: uuid.UUID
               ) -> cg_json.JSONResponse[models.BrokerSetting]:
    broker = helpers.get_or_404(models.BrokerSetting, broker_id)
    return cg_json.JSONResponse.make(broker)
