import psef
import cg_request_args.swagger

app = psef.create_app()
app.config['SERVER_NAME'] = '$inst.codegra.de'
with app.app_context():
    cg_request_args.swagger.collect_swagger()
