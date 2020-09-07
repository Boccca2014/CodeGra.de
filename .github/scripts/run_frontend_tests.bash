#!/bin/bash

cat >config.ini <<EOF
[Back-end]
external_url = http://localhost:1234
proxy_base_domain = test.com
redis_cache_url = redis://localhost:6379/cg_cache
EOF

make privacy_statement

if ! npm run build; then
    exit 1
fi

npm run unit
exit "$?"
