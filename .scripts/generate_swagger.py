import os
import sys
import json
import uuid

main_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(main_dir)
os.chdir(main_dir)

if True:
    import psef
    from cg_request_args.open_api import OpenAPISchema

app = psef.create_app(skip_all=True)
app.config['SERVER_NAME'] = '$inst.codegra.de'
with app.app_context():
    res = OpenAPISchema({'psef': psef, 'uuid': uuid}).collect_for_current_app()

    base = os.path.join(os.path.dirname(__file__), '..')

    with open(sys.argv[1], 'w') as f:
        json.dump(res, f, indent=4)
