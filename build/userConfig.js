/* SPDX-License-Identifier: AGPL-3.0-only */
const fs = require('fs');
var path = require('path')
const execFileSync = require('child_process').execFileSync;
const moment = require('moment');

const branch = execFileSync('git', ['rev-parse', '--abbrev-ref', 'HEAD']).toString().trim();
const gitCommit = execFileSync('git', ['rev-parse', '--short', 'HEAD']).toString().trim();
const gitCommitLong = execFileSync('git', ['rev-parse', 'HEAD']).toString().trim();
let inCorrectPart = false;
let done = false;
let skip = false;

// If the version doesn't start with a capital and the branch is not the stable
// branch show the commit hash. We heavily prefer a false negative (we should
// show the commit hash but show the version instead) over a false positive (we
// show a commit hash instead of a version) as this would mean we would show a
// commit hash on a production server which looks bad.
let tagMsg = [];
let version = '#' + gitCommit;
if (branch.indexOf('stable') >= 0) {
    const tag = execFileSync('git', ['describe', '--abbrev=0', '--tags']).toString().trim();
    tagMsg = execFileSync('git', ['tag', '-l', '-n400', tag]).toString().split('\n');
    if (tag.match(/^[A-Z]/)) {
        version = tag;
    }
}


const config = {
    release: {
        version,
        commit: gitCommit,
        commitHash: gitCommitLong,
        date: process.env.CG_FORCE_BUILD_DATE || moment.utc().toISOString(),
        message: tagMsg.reduce((res, cur) => {
            if (done || skip) {
                skip = false;
            } else if (inCorrectPart && /^ *$/.test(cur)) {
                done = true;
            } else if (inCorrectPart) {
                res.push(cur);
            } else if (/^ *\*\*Released\*\*/.test(cur)) {
                inCorrectPart = true;
                skip = true;
            }
            return res;
        }, []).join(' '),
    },
};

// config.proxyBaseDomain = backendOpts ? backendOpts.proxy_base_domain : '';
config.isProduction = process.env.NODE_ENV === 'production';
// config.externalUrl = backendOpts ? backendOpts.external_url : '';

module.exports = config;
