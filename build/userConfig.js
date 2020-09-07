/* SPDX-License-Identifier: AGPL-3.0-only */
const fs = require('fs');
var path = require('path')
const ini = require('ini');
const execFileSync = require('child_process').execFileSync;
const moment = require('moment');

function resolve (dir) {
  return path.join(__dirname, '..', dir)
}

const minutes = amount => 60 * amount;
const hours = amount => minutes(60 * amount);
const days = amount => hours(24 * amount);

function filterKeys(obj, ...keys) {
    return keys.reduce(
        (acc, key) => {
            acc[key] = obj[key];
            return acc;
        },
        {},
    );
}

let userConfig = {};

const configIni = resolve('config.ini');
process.stderr.write(configIni + '\n');

try {
    userConfig = ini.parse(fs.readFileSync(configIni, 'utf-8'));
} catch (err) {
    process.stderr.write('Config file not found, using default values!\n' + err + '\n');
}

if (userConfig['Front-end'] === undefined) userConfig['Front-end'] = {};
if (userConfig.Features === undefined) userConfig.Features = {};
if (userConfig.AutoTest === undefined) userConfig.AutoTest = {};

const config = Object.assign({}, {
    email: 'info@CodeGra.de',
    maxLines: 2500,
    notificationPollTime: 30000,
    sentryDsn: null,
}, userConfig['Front-end']);
config.maxLines = parseInt(config.maxLines, 10);
config.notificationPollTime = parseInt(config.notificationPollTime, 10);

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
let tagMsg = '';
let version = '#' + gitCommit;
if (branch.indexOf('stable') < 0) {
    tagMsg = execFileSync('git', ['tag', '-l', '-n400', version]).toString().split('\n');
    const foundVersion = execFileSync('git', ['describe', '--abbrev=0', '--tags']).toString().trim();
    if (version.match(/^[A-Z]/)) {
        version = foundVersion;
    }
}

config.release = {
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
};

config.features = Object.assign({
    auto_test: false,
    blackboard_zip_upload: true,
    rubrics: true,
    automatic_lti_role: true,
    LTI: true,
    linters: true,
    incremental_rubric_submission: true,
    register: false,
    groups: false,
    email_students: false,
    peer_feedback: false,
    course_register: false,
}, userConfig.Features);

config.autoTest = {
    auto_test_max_command_time: 300,
};

if (Object.hasOwnProperty.call(userConfig.AutoTest, 'auto_test_max_time_command')) {
    config.autoTest.auto_test_max_command_time = Number(userConfig.AutoTest.auto_test_max_time_command);
}

const backendOpts = userConfig['Back-end'];

config.proxyBaseDomain = backendOpts ? backendOpts.proxy_base_domain : '';
config.isProduction = process.env.NODE_ENV === 'production';
config.externalUrl = backendOpts ? backendOpts.external_url : '';

const beforeTime = backendOpts ? backendOpts.login_token_before_time : null;
if (beforeTime == null) {
    // Same as in ``config.py``
    config.loginTokenBeforeTime = [days(2), minutes(30)]
} else {
    config.loginTokenBeforeTime = beforeTime.split(',').map(item => parseFloat(item.trim()))
}

const examLoginMaxLength = backendOpts ? backendOpts.exam_login_max_length : null;
if (examLoginMaxLength) {
    config.examLoginMaxLength = parseInt(examLoginMaxLength);
} else {
    config.examLoginMaxLength = hours(12);
}

if (!config.proxyBaseDomain && config.isProduction) {
    throw new Error('Production can only be used with a proxy url.');
}

module.exports = config;
