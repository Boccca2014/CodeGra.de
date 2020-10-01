#!/bin/bash
set -o xtrace

make build_api_libs
git add api_libs
if [[ -n "$(git diff-index --name-only HEAD)" ]]; then
    echo "You forgot to update the API libs!"
    exit 1;
fi

# Opacity with a percentage gets changed by our css optimizer, and will always
# be 1%, so we disallow using percentages and simply require a fraction.
if grep -r 'opacity:.*%' ./src; then
    printf >&2 'Opacity should not be used with percentages'
    exit 1
fi

git fetch --all

cat >config.ini <<EOF
[Back-end]
external_url = http://localhost:1234
proxy_base_domain = test.com
redis_cache_url = redis://localhost:6379/cg_cache
EOF

pip install -r test_requirements.txt

make pylint &
PYLINT_PID="$!"

make privacy_statement
npm run lint
res2="$?"

make mypy
res3="$?"

out="$(make isort_check)"
res4=$?
if [[ "$res4" -ne 0 ]]; then
    echo "$out"
fi

make yapf_check
res5=$?

( cd docs && make html )
res6="$?"

wait "$PYLINT_PID"
res1="$?"

[[ $(( res1 + res2 + res3 + res4 + res5 + res6 )) = 0 ]]
exit_code="$?"

exit "$exit_code"
