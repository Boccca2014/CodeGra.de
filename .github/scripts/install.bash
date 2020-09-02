#!/bin/bash
set -e

skip="${1}"

if [[ "$skip" = skip_pip ]]; then
    pip install mistune &
else
    grep -lr --null microsoft /etc/apt/sources.list.d/ | xargs -0 sudo rm

    (
        sudo apt-get update &&
        sudo apt-get install -y lxc lxc-dev lxcfs libvirt0 libssl-dev postgresql-client libxmlsec1-dev &&
        python -m pip install --upgrade pip &&
        pip install 'celery[redis]' coveralls pytest-cov codecov &&
        pip install -r requirements.txt;
    ) &
fi

(
    wget https://github.com/pmd/pmd/releases/download/pmd_releases%2F6.18.0/pmd-bin-6.18.0.zip -O pmd.zip &&
    unzip pmd.zip &&
    mv pmd-bin-6.* pmd;
) &

wget https://github.com/checkstyle/checkstyle/releases/download/checkstyle-8.25/checkstyle-8.25-all.jar \
     -O ./checkstyle.jar &

if ! [[ "$skip" = skip_npm ]]; then
    npm ci
fi

wait
exit "$?"
