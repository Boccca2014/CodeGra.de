const execFileSync = require('child_process').execFileSync;

const gitCommitLong = execFileSync('git', ['rev-parse', 'HEAD']).toString().trim();
module.exports = gitCommitLong;
