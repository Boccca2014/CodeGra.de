#!/bin/sh
set -o xtrace

if [ -z "$(git diff origin/master -- "$@")" ]; then
    printf 'None of %s were updated!\n' "$*" >&2
    exit 1
fi
