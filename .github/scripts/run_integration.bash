#!/bin/bash

set -o xtrace

# Make sure none of the tests are run as the only one.
if grep -r '\.only(' ./cypress; then
    printf >&2 'Cypress tests contain a .only()\n'
    exit 1
fi

make privacy_statement

DBNAME="ci_test"
export SQLALCHEMY_DATABASE_URI="postgresql://postgres:postgres@localhost:5432/${DBNAME}"

cat >config.ini <<EOF
[Back-end]
sqlalchemy_database_uri = $SQLALCHEMY_DATABASE_URI
DEBUG = true
external_url = http://localhost:8080
mirror_upload_dir = /tmp/psef/mirror_uploads
upload_dir = /tmp/psef/uploads

redis_cache_url = redis://localhost:6379/cg_cache

[Celery]
broker_url = redis://localhost:6379

[Features]
register = true
auto_test = true
course_register = true
groups = true
render_html = true
email_students = true
peer_feedback = true

EOF

npm run start_integration &

wget https://github.com/CodeGra-de/jplag/releases/download/v2.14.2-SNAPSHOT/jplag-2.14.2-SNAPSHOT-jar-with-dependencies.jar -O jplag.jar
export PYTHONPATH="$PYTHONPATH:${PWD}"
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -c "create database $DBNAME;" || exit 1
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres "$DBNAME" -c "create extension \"citext\";" || exit 1
PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres "$DBNAME" -c "create extension \"uuid-ossp\";" || exit 1
./manage.py db upgrade
./manage.py test_data

celery worker --app=runcelery:celery -E > /dev/null &
python run.py > /dev/null &

./node_modules/wait-on/bin/wait-on http://localhost:8080/api/v1/about -l

curl http://localhost:8080/
while ! ( curl http://localhost:8080/app.js | head -c 100 | grep '{' ); do
    sleep 1;
done

sleep 30

while ! ( curl http://localhost:8080/app.js | head -c 100 | grep '{' ); do
    sleep 1;
done

FILES=$(python - <<PYTHON
import os
import sys
base='cypress/integration/tests/'

def sort_key(test):
    if test == 'plagiarism.spec.js':
        return sys.maxsize
    elif test == 'submissions.spec.js':
        return sys.maxsize - 1

    return os.path.getsize(base + test)

tests = [base + test for test in sorted(os.listdir(base), key=sort_key)]
print(','.join(tests[$RUNNER_NUM::$RUNNER_AMOUNT]))
PYTHON
     )


PATH="$PATH:$(npm bin)"
export PATH
NO_COLOR=1 xvfb-run --server-args="-screen 0 1600x1024x24" --auto-servernum cypress run --spec "$FILES"
res="$?"

exit "$res"
