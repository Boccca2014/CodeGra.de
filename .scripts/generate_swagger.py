import json

import yaml

import psef
from cg_request_args.open_api import OpenAPISchema

app = psef.create_app()
app.config['SERVER_NAME'] = '$inst.codegra.de'
with app.app_context():
    res = OpenAPISchema({'psef': psef}).collect_for_current_app()

    with open('swagger.yaml', 'w') as f:
        yaml.dump(res, f)

    with open('swagger.json', 'w') as f:
        json.dump(res, f)
