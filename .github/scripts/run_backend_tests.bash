#!/bin/bash
set -o xtrace
export PYTHONPATH="$PWD"
export GITHUB_ACTIONS=true
sudo chown -R "$USER":"$(id -gn)" /tmp/

cat >config.ini <<EOF
[Back-end]
external_url = http://localhost:1234

redis_cache_url = redis://localhost:6379/cg_cache
EOF

pip install -r test_requirements.txt

rm package.json
rm npm-shrinkwrap.json

sudo chown -R "$USER":"$(id -gn "$USER")" ~/.config
sudo npm install -g eslint@6.8.0 \
     eslint-plugin-standard@4.0.1 \
     eslint-plugin-node@11.0.0 \
     eslint-plugin-promise@4.2.1 \
     eslint-plugin-import@2.19.1 \
     eslint-module-utils@2.4.1 \
     eslint-import-resolver-node@0.3.2 \
     eslint-config-standard@14.1.0

sudo npm list
sudo chown -R "$USER":"$(id -gn "$USER")" "$(npm root -g)"
sudo chown -R "$USER":"$(id -gn "$USER")" ~/.config

# export BASE_DATABASE_URI='postgresql://postgres:postgres@localhost:5432/ci_test_'
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_USERNAME=postgres
export PGPASSWORD=postgres

if [[ "$RUN_AT_ONLY" = "yes" ]]; then
    timeout -k 1200 1200 \
            pytest --cov psef --cov cg_signals --cov cg_cache --cov cg_enum \
            --cov-append -x \
            --postgresql="GENERATE" \
            --cov-report term-missing \
            "$(pwd)/psef_test/test_auto_test.py" \
            -vvvv
    exit "$?"
else
    rm "$(pwd)/psef_test/test_auto_test.py"
fi

pytest --cov cg_worker_pool \
       --cov cg_threading_utils \
       --cov cg_signals \
       --cov cg_cache \
       --cov cg_helpers \
       --cov cg_enum \
       --cov cg_sqlalchemy_helpers \
       --cov cg_maybe \
       --cov cg_object_storage \
       --cov cg_junit \
       --cov cg_request_args \
       --cov-report term-missing \
       "$(pwd)/cg_worker_pool/tests/" \
       "$(pwd)/cg_threading_utils/tests/" \
       "$(pwd)/cg_signals/tests/" \
       "$(pwd)/cg_cache/tests/" \
       "$(pwd)/cg_helpers/tests/" \
       "$(pwd)/cg_enum/tests/" \
       "$(pwd)/cg_maybe/tests/" \
       "$(pwd)/cg_object_storage/tests/" \
       "$(pwd)/cg_junit/tests/" \
       "$(pwd)/cg_request_args/tests/" \
       -vvvv
res1="$?"
if [[ "$res1" -ne 0 ]]; then
    exit "$res1";
fi

timeout -k 900 900 \
        pytest \
        --cov psef \
        --cov cg_signals \
        --cov cg_cache \
        --cov cg_enum \
        --cov cg_sqlalchemy_helpers \
        --cov cg_register \
        --cov cg_object_storage \
       --cov cg_request_args \
        --cov-append \
        -x \
        --postgresql="GENERATE" \
        --cov-report term-missing \
        "$(pwd)/psef_test/" \
        -n 4 \
        -vvvv
res2="$?"
if [[ "$res2" -ne 0 ]]; then
    exit "$res2";
fi

make doctest
res3="$?"

[[ $(( res1 + res2 + res3 )) = 0 ]]
exit "$?"
