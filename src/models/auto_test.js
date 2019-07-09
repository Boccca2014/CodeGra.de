/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
// TODO: Remove the axios dependency and move the api requests to the store
import axios from 'axios';

import { deepCopy, getErrorMessage, getUniqueId, getProps, withOrdinalSuffix } from '@/utils';

export class AutoTestSuiteData {
    constructor(autoTestId, autoTestSetId, serverData = {}) {
        this.autoTestSetId = autoTestSetId;
        this.autoTestId = autoTestId;
        this.trackingId = getUniqueId();

        this.id = null;
        this.steps = [];
        this.rubricRow = {};

        this.setFromServerData(serverData);
    }

    setFromServerData(d) {
        const trackingIds = this.getStepTrackingIds();

        const steps = (d.steps || []).map(step =>
            Object.assign(step, {
                trackingId: getProps(trackingIds, getUniqueId(), step.id),
                collapsed: true,
            }),
        );

        Vue.set(this, 'id', d.id);
        Vue.set(this, 'steps', steps);
        Vue.set(this, 'rubricRow', d.rubric_row || {});
        Vue.set(
            this,
            'commandTimeLimit',
            getProps(
                d,
                UserConfig.features.autoTest.auto_test_max_command_time,
                'command_time_limit',
            ),
        );
        Vue.set(this, 'networkDisabled', getProps(d, true, 'network_disabled'));
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
            command_time_limit: this.commandTimeLimit,
        });
    }

    isEmpty() {
        return this.steps.length === 0;
    }

    get url() {
        return `/api/v1/auto_tests/${this.autoTestId}/sets/${this.autoTestSetId}/suites/`;
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
                steps: this.steps.map(step => ({
                    ...step,
                    weight: Number(step.weight),
                })),
                rubric_row_id: this.rubricRow.id,
                command_time_limit: Number(this.commandTimeLimit),
                network_disabled: getProps(this, true, 'networkDisabled'),
            })
            .then(
                res => {
                    this.setFromServerData(res.data);
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
                        errs.push(`The name of the ${name} is emtpy.`);
                    }
                    if (Number(input.weight) <= 0) {
                        errs.push(`The weight of the ${name} should be a number greater than 0.`);
                    }
                });
            }
        } else if (step.type === 'check_points') {
            let weightBefore = 0;
            for (let i = 0; i < this.steps.length > 0; ++i) {
                if (this.steps[i] === step) {
                    break;
                }
                weightBefore += Number(this.steps[i].weight);
            }
            if (step.data.min_points <= 0 || step.data.min_points > weightBefore) {
                errs.push(
                    `The minimal amount of points should be achievable (at most
                    ${weightBefore}) and greater than 0.`,
                );
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

        this.update(result, autoTest);
    }

    update(result, autoTest) {
        this.state = result.state;
        this.startedAt = result.started_at;
        this.pointsAchieved = result.points_achieved;

        this.updateStepResults(result.step_results, autoTest);
    }

    updateExtended(result, autoTest) {
        this.update(result, autoTest);
        this.setupStdout = result.setup_stdout;
        this.setupStderr = result.setup_stderr;
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
                    s.startedAt = step.startedAt;
                });
            }
            return acc;
        }, {});

        const setResults = {};
        const suiteResults = {};

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
                };

                suiteResult.stepResults = suite.steps.map(step => {
                    suiteResult.possible += step.weight;

                    let stepResult = stepResults[step.id];

                    if (stepResult == null) {
                        stepResult = {
                            state: 'not_started',
                            log: null,
                        };
                    }

                    stepResult.finished = this.isFinishedState(stepResult.state);

                    if (step.type === 'check_points' && stepResult.state === 'failed') {
                        suiteFailed = true;
                    } else {
                        suiteResult.achieved += getProps(stepResult, 0, 'achieved_points');
                    }

                    stepResults[step.id] = stepResult;
                    return stepResult;
                });

                suiteResult.finished = suiteResult.stepResults.every(s => s.finished);
                suiteResults[suite.id] = suiteResult;

                if (testFailed || setFailed || suiteFailed) {
                    suiteResult.finished = true;
                    suiteResult.stepResults.forEach(s => {
                        if (s.state === 'not_started') {
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

            setResult.finished =
                setResult.suiteResults.every(s => s && s.finished) &&
                Object.values(setResults).every(prevSet => prevSet.finished);

            if (setResult.finished && totalAchieved < set.stop_points) {
                setFailed = true;
            }

            setResults[set.id] = setResult;
        });

        Vue.set(this, 'stepResults', stepResults);
        Vue.set(this, 'suiteResults', suiteResults);
        Vue.set(this, 'setResults', setResults);
        Vue.set(this, 'finished', Object.values(setResults).every(s => s.finished));
    }

    // eslint-disable-next-line
    isFinishedState(state) {
        return ['passed', 'failed', 'timed_out'].indexOf(state) !== -1;
    }
}

export class AutoTestRun {
    constructor(run, autoTest) {
        this.id = run.id;
        this.startedAt = run.started_at;
        this.update(run, autoTest);
    }

    update(run, autoTest) {
        this.state = run.state;
        this.finished = ['done', 'crashed', 'timed_out'].indexOf(run.state) !== -1;
        this.setupStdout = run.setup_stdout;
        this.setupStderr = run.setup_stderr;

        if (run.results) {
            this.updateResults(run.results, autoTest);
        }
    }

    updateResults(results, autoTest) {
        if (this.results) {
            this.results.forEach((r, i) => {
                r.update(results[i], autoTest);
            });
        } else {
            this.results = results.map(r => new AutoTestResult(r, autoTest));
        }
    }
}
