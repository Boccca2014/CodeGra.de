/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
// TODO: Remove the axios dependency and move the api requests to the store
import axios from 'axios';

import {
    hasAttr,
    deepCopy,
    getErrorMessage,
    getUniqueId,
    getProps,
    withOrdinalSuffix,
    safeDivide,
} from '@/utils';
import * as models from '@/models';

export const FINISHED_STATES = new Set([
    'passed',
    'done',
    'partial',
    'failed',
    'timed_out',
    'hidden',
    'skipped',
]);

export class AutoTestSuiteData {
    constructor(autoTestId, autoTestSetId, serverData = {}, actuallyFromServer) {
        this.autoTestSetId = autoTestSetId;
        this.autoTestId = autoTestId;
        this.trackingId = getUniqueId();

        this.id = null;
        this.steps = [];
        this.rubricRow = {};

        this.setFromServerData(serverData, actuallyFromServer);
    }

    setFromServerData(d, actuallyFromServer) {
        const trackingIds = this.getStepTrackingIds();

        const steps = (d.steps || []).map(step => {
            const ret = Object.assign(step, {
                trackingId: getProps(trackingIds, getUniqueId(), step.id),
                collapsed: true,
            });

            if (actuallyFromServer && step.type === 'check_points') {
                ret.data.min_points *= 100;
            }

            return ret;
        });

        Vue.set(this, 'id', d.id);
        Vue.set(this, 'steps', steps);
        Vue.set(this, 'rubricRow', d.rubric_row || {});
        Vue.set(
            this,
            'commandTimeLimit',
            getProps(d, UserConfig.autoTest.auto_test_max_command_time, 'command_time_limit'),
        );
        Vue.set(this, 'networkDisabled', getProps(d, true, 'network_disabled'));
        Vue.set(this, 'submissionInfo', getProps(d, false, 'submission_info'));
    }

    getStepTrackingIds() {
        return this.steps.reduce((acc, step) => {
            acc[step.id] = step.trackingId;
            return acc;
        }, {});
    }

    copy() {
        return new AutoTestSuiteData(this.autoTestId, this.autoTestSetId, {
            id: this.id,
            steps: deepCopy(this.steps),
            rubric_row: this.rubricRow,
            network_disabled: this.networkDisabled,
            submission_info: this.submissionInfo,
            command_time_limit: this.commandTimeLimit,
        });
    }

    isEmpty() {
        return this.steps.length === 0;
    }

    get url() {
        return `/api/v1/auto_tests/${this.autoTestId}/sets/${this.autoTestSetId}/suites/`;
    }

    // eslint-disable-next-line
    prepareStepForSaving(step) {
        const ret = {
            ...step,
            weight: Number(step.weight),
        };

        if (step.type === 'check_points') {
            ret.data = {
                ...step.data,
                min_points: step.data.min_points / 100,
            };
        }

        return ret;
    }

    save() {
        const errors = this.getErrors();

        if (errors != null) {
            const err = new Error('The category is not valid');
            err.messages = errors;
            return Promise.reject(err);
        }

        return axios
            .patch(this.url, {
                id: this.id == null ? undefined : this.id,
                steps: this.steps.map(this.prepareStepForSaving),
                rubric_row_id: this.rubricRow.id,
                command_time_limit: Number(this.commandTimeLimit),
                network_disabled: getProps(this, true, 'networkDisabled'),
                submission_info: getProps(this, false, 'submissionInfo'),
            })
            .then(
                res => {
                    this.setFromServerData(res.data, true);
                    return res;
                },
                err => {
                    const newErr = new Error('The category is not valid');
                    newErr.messages = {
                        general: [getErrorMessage(err)],
                        steps: [],
                    };
                    throw newErr;
                },
            );
    }

    delete() {
        if (this.id != null) {
            return axios.delete(`${this.url}/${this.id}`);
        } else {
            return Promise.resolve();
        }
    }

    removeItem(index) {
        this.steps.splice(index, 1);
    }

    addStep(step) {
        step.trackingId = getUniqueId();
        this.steps.push(step);
    }

    // eslint-disable-next-line
    checkValid(step) {
        const isEmpty = val => !val.match(/[a-zA-Z0-9]/);
        const errs = [];

        if (isEmpty(step.name)) {
            errs.push('The name may not be empty.');
        }

        const program = getProps(step, null, 'data', 'program');
        if (program != null && isEmpty(program)) {
            errs.push('The program may not be empty.');
        }

        if (step.type !== 'check_points' && Number(step.weight) <= 0) {
            errs.push('The weight should be a number greater than 0.');
        }

        if (step.type === 'io_test') {
            if (step.data.inputs.length === 0) {
                errs.push('There should be at least one input output case.');
            } else {
                step.data.inputs.forEach((input, i) => {
                    const name = `${withOrdinalSuffix(i + 1)} input output case`;
                    if (isEmpty(input.name)) {
                        errs.push(`The name of the ${name} is empty.`);
                    }
                    if (Number(input.weight) <= 0) {
                        errs.push(`The weight of the ${name} should be a number greater than 0.`);
                    }
                });
            }
        } else if (step.type === 'check_points') {
            if (step.data.min_points < 0) {
                errs.push('The minimal percentage must be greater than 0.');
            } else if (step.data.max_points > 100) {
                errs.push('The mimimal percentage must be less than or equal to 100.');
            }
        } else if (step.type === 'custom_output') {
            if (!step.data.regex.match(/([^\\]|^)(\\\\)*\\f/)) {
                errs.push('The regular expression must contain at least one "\\f"');
            }
        }

        return errs;
    }

    getErrors() {
        const caseErrors = {
            general: [],
            steps: [],
            isEmpty() {
                return this.steps.length === 0 && this.general.length === 0;
            },
        };
        if (this.steps.length === 0) {
            caseErrors.general.push('You should have at least one step.');
        }

        const stepErrors = this.steps.map(s => [s, this.checkValid(s)]);
        if (stepErrors.some(([, v]) => v.length > 0)) {
            caseErrors.steps = stepErrors;
        }

        if (!this.rubricRow || !this.rubricRow.id) {
            caseErrors.general.push('You should select a rubric category for this test category.');
        }

        return caseErrors.isEmpty() ? null : caseErrors;
    }
}

export class AutoTestResult {
    constructor(result, autoTest) {
        this.id = result.id;
        this.submissionId = result.work_id;
        this.finished = false;
        this.finishedAllSets = false;
        this.autoTest = autoTest;

        this.update(result, autoTest);
    }

    get hasExtended() {
        return this.setResults != null;
    }

    update(result, autoTest) {
        this.createdAt = result.created_at;
        this.startedAt = result.started_at;
        this.pointsAchieved = result.points_achieved;

        if (hasAttr(result, 'final_result')) {
            this.isFinal = result.final_result;
        }
        if (hasAttr(result, 'setup_stdout')) {
            this.setupStdout = result.setup_stdout;
        }
        if (hasAttr(result, 'setup_stderr')) {
            this.setupStderr = result.setup_stderr;
        }
        if (hasAttr(result, 'approx_waiting_before')) {
            this.approxWaitingBefore = result.approx_waiting_before;
        }
        if (hasAttr(result, 'quality_comments')) {
            this.qualityComments = models.QualityComments.fromServerData(
                result.quality_comments,
                this,
            );
        }

        this.updateState(result.state);
        this.updateStepResults(result.step_results, autoTest);
    }

    updateState(newState) {
        switch (newState) {
            case 'passed':
                this.state = 'done';
                break;
            default:
                this.state = newState;
                break;
        }

        this.finished = FINISHED_STATES.has(this.state);
    }

    updateStepResults(steps, autoTest) {
        if (steps == null) {
            return;
        }

        const stepResults = steps.reduce((acc, step) => {
            acc[step.auto_test_step.id] = step;
            step.startedAt = step.started_at;

            if (step.log && step.log.steps) {
                step.log.steps.forEach(s => {
                    s.startedAt = s.started_at;
                });
            }
            return acc;
        }, {});

        const setResults = {};
        const suiteResults = {};

        const testSkipped = this.state === 'skipped';
        const testFailed = this.state === 'failed' || this.state === 'timed_out';
        let setFailed = false;
        let totalAchieved = 0;
        let totalPossible = 0;

        autoTest.sets.forEach(set => {
            if (set.deleted) return;

            const setResult = {
                achieved: totalAchieved,
                possible: totalPossible,
                finished: false,
                set,
            };

            setResult.suiteResults = set.suites.map(suite => {
                if (suite.deleted) {
                    return null;
                }

                let suiteFailed = false;

                const suiteResult = {
                    achieved: 0,
                    possible: 0,
                    finished: false,
                    suite,
                };

                suiteResult.stepResults = suite.steps.map(step => {
                    let stepResult = stepResults[step.id];

                    if (!this.isFinal && step.hidden) {
                        stepResult = {
                            state: 'hidden',
                            log: null,
                        };
                    } else {
                        suiteResult.possible += step.weight;

                        if (stepResult == null) {
                            stepResult = {
                                state: 'not_started',
                                log: null,
                            };
                        }
                    }
                    stepResult.step = step;

                    switch (step.type) {
                        case 'check_points':
                            if (stepResult.state === 'failed') {
                                suiteFailed = true;
                            }
                            break;
                        case 'custom_output':
                        case 'junit_test':
                            if (stepResult.state === 'passed') {
                                const points = stepResult.log.points;
                                if (points === 0) {
                                    stepResult.state = 'failed';
                                } else if (points < 1) {
                                    stepResult.state = 'partial';
                                }
                            }
                            break;
                        default:
                            break;
                    }

                    suiteResult.achieved += getProps(stepResult, 0, 'achieved_points');
                    stepResult.finished = FINISHED_STATES.has(stepResult.state);

                    stepResults[step.id] = stepResult;
                    return stepResult;
                });

                suiteResult.percentage =
                    100 * safeDivide(suiteResult.achieved, suiteResult.possible, 0);
                suiteResult.finished = suiteResult.stepResults.every(s => s.finished);
                suiteResults[suite.id] = suiteResult;

                if (testFailed || setFailed || suiteFailed) {
                    suiteResult.finished = true;
                    suiteResult.stepResults.forEach(s => {
                        switch (s.state) {
                            case 'not_started':
                                s.state = 'skipped';
                                break;
                            case 'running':
                                s.state = 'failed';
                                break;
                            default:
                                break;
                        }
                    });
                } else if (testSkipped) {
                    suiteResult.finished = true;
                    suiteResult.stepResults.forEach(s => {
                        if (!s.finished) {
                            s.state = 'skipped';
                        }
                    });
                }

                setResult.achieved += suiteResult.achieved;
                setResult.possible += suiteResult.possible;

                suiteResults[suite.id] = suiteResult;
                return suiteResult;
            });

            totalAchieved = setResult.achieved;
            totalPossible = setResult.possible;

            setResult.percentage = 100 * safeDivide(setResult.achieved, setResult.possible, 0);
            setResult.passed =
                setResult.percentage >= 100 * set.stop_points &&
                Object.values(setResults).every(prevSet => prevSet.passed);
            setResult.finished =
                setResult.suiteResults.every(s => s && s.finished) &&
                Object.values(setResults).every(prevSet => prevSet.finished);

            const achievedPerc = safeDivide(totalAchieved, totalPossible, 1);
            if (setResult.finished && achievedPerc < set.stop_points) {
                setFailed = true;
            }

            setResults[set.id] = setResult;
        });

        Vue.set(this, 'stepResults', stepResults);
        Vue.set(this, 'suiteResults', suiteResults);
        Vue.set(this, 'setResults', setResults);

        // Store a result per rubric row id for in the RubricViewer.
        Vue.set(
            this,
            'rubricResults',
            Object.values(suiteResults).reduce((acc, suiteResult) => {
                acc[suiteResult.suite.rubricRow.id] = suiteResult;
                return acc;
            }, {}),
        );

        this.finishedAllSets =
            this.finished && Object.values(this.setResults).every(setResult => setResult.finished);
    }
}

export class AutoTestRun {
    constructor(run, autoTest) {
        this.id = run.id;
        this.createdAt = run.created_at;
        this.results = [];
        this.resultsById = {};
        this.update(run, autoTest);
    }

    update(run, autoTest) {
        this.setupStdout = run.setup_stdout;
        this.setupStderr = run.setup_stderr;

        if (run.results) {
            this.updateResults(run.results, autoTest);
        }
    }

    makeNewResultArray(newResults, autoTest) {
        // For each passed result, check if there already is a result with the
        // same id. If it exists, it is updated and returned. Otherwise a new
        // result is created, inserted into resultsById, and returned.

        return newResults.map(newResult => {
            let result = this.resultsById[newResult.id];
            if (result == null) {
                result = new AutoTestResult(newResult, autoTest);
                Vue.set(this.resultsById, result.id, result);
            } else {
                result.update(newResult, autoTest);
            }
            return result;
        });
    }

    updateNonLatestResults(newResults, autoTest) {
        this.makeNewResultArray(newResults, autoTest);
    }

    updateResults(newResults, autoTest) {
        Vue.set(this, 'results', this.makeNewResultArray(newResults, autoTest));
    }

    findResultBySubId(submissionId) {
        let res = this.results.find(r => r.submissionId === submissionId);
        if (res == null) {
            res = Object.values(this.resultsById).find(r => r.submissionId === submissionId);
        }
        return res;
    }

    findResultById(resultId) {
        return this.resultsById[resultId];
    }

    setResultById(result) {
        const index = this.results.findIndex(res => res.id === result.id);
        if (index !== -1) {
            Vue.set(this.results, index, result);
        }
        Vue.set(this.resultsById, result.id, result);
    }
}
