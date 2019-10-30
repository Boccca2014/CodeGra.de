/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import axios from 'axios';

import { deepCopy, getProps } from '@/utils';
import { AutoTestSuiteData, AutoTestRun, FINISHED_STATES } from '@/models/auto_test';
import * as types from '../mutation-types';

const getters = {
    tests: state => state.tests,
    results: state => state.results,
};

const loaders = {
    tests: {},
    results: {},
    runs: {},
    resultsByUser: {},
};

function getRun(autoTest, runId) {
    if (runId != null) {
        return autoTest.runs.find(r => r.id === runId);
    } else {
        return getProps(autoTest, null, 'runs', 0);
    }
}

const actions = {
    createAutoTest({ commit, dispatch }, assignmentId) {
        return axios
            .post('/api/v1/auto_tests/', {
                assignment_id: assignmentId,
            })
            .then(({ data }) =>
                Promise.all([
                    dispatch(
                        'courses/updateAssignment',
                        {
                            assignmentId,
                            assignmentProps: { auto_test_id: data.id },
                        },
                        { root: true },
                    ),
                    commit(types.SET_AUTO_TEST, data),
                ]),
            );
    },

    deleteAutoTest({ commit, dispatch, state }, autoTestId) {
        if (state.tests[autoTestId] == null) {
            return Promise.resolve();
        }

        const assignmentId = state.tests[autoTestId].assignment_id;

        return axios.delete(`/api/v1/auto_tests/${autoTestId}`).then(() =>
            Promise.all([
                dispatch(
                    'courses/updateAssignment',
                    {
                        assignmentId,
                        assignmentProps: { auto_test_id: null },
                    },
                    { root: true },
                ),
                dispatch('submissions/forceLoadSubmissions', assignmentId, { root: true }),
                commit(types.DELETE_AUTO_TEST, autoTestId),
            ]),
        );
    },

    updateAutoTest({ commit }, { autoTestId, autoTestProps }) {
        return axios.patch(`/api/v1/auto_tests/${autoTestId}`, autoTestProps).then(() => {
            commit(types.UPDATE_AUTO_TEST, {
                autoTestId,
                autoTestProps,
            });
        });
    },

    loadAutoTest({ commit, state }, { autoTestId }) {
        if (state.tests[autoTestId] != null) {
            return Promise.resolve();
        }

        if (loaders.tests[autoTestId] == null) {
            loaders.tests[autoTestId] = axios
                .get(`/api/v1/auto_tests/${autoTestId}?latest_only`)
                .then(
                    ({ data }) => {
                        delete loaders.tests[autoTestId];
                        commit(types.SET_AUTO_TEST, data);
                    },
                    err => {
                        delete loaders.tests[autoTestId];
                        throw err;
                    },
                );
        }

        return loaders.tests[autoTestId];
    },

    async createAutoTestRun({ commit, dispatch, state }, { autoTestId }) {
        await dispatch('loadAutoTest', { autoTestId });
        const autoTest = state.tests[autoTestId];

        return axios.post(`/api/v1/auto_tests/${autoTestId}/runs/`).then(({ data }) =>
            dispatch('submissions/forceLoadSubmissions', autoTest.assignment_id, {
                root: true,
            }).then(() => commit(types.UPDATE_AUTO_TEST_RUNS, { autoTest, run: data })),
        );
    },

    async loadAutoTestRun({ commit, dispatch, state }, { autoTestId, force, autoTestRunId }) {
        await dispatch('loadAutoTest', { autoTestId });
        const autoTest = state.tests[autoTestId];
        const oldRun = getRun(autoTest, autoTestRunId);

        if (oldRun == null) {
            throw new Error('AutoTest has not been run yet.');
        } else if (oldRun.finished && !force) {
            return Promise.resolve();
        }

        const runId = oldRun.id;
        if (loaders.runs[runId] == null) {
            loaders.runs[runId] = axios
                .get(`/api/v1/auto_tests/${autoTestId}/runs/${runId}?latest_only`)
                .then(
                    ({ data }) => {
                        delete loaders.runs[runId];

                        const oldResultMap = oldRun.results.reduce((accum, item) => {
                            accum[item.id] = item;
                            return accum;
                        }, {});

                        // Reload all submissions whose AutoTest is finished now,
                        // but wasn't finished on the previous request.
                        data.results.forEach(r => {
                            const oldResult = oldResultMap[r.id];
                            if (oldResult && !oldResult.finished && FINISHED_STATES.has(r.state)) {
                                dispatch(
                                    'submissions/loadSingleSubmission',
                                    {
                                        assignmentId: autoTest.assignment_id,
                                        submissionId: r.work_id,
                                        force: true,
                                    },
                                    {
                                        root: true,
                                    },
                                );
                            }
                        });
                        commit(types.UPDATE_AUTO_TEST_RUNS, { autoTest, run: data });
                    },
                    err => {
                        delete loaders.runs[runId];
                        throw err;
                    },
                );
        }

        return loaders.runs[runId];
    },

    async createAutoTestSet({ commit, dispatch, state }, { autoTestId }) {
        await dispatch('loadAutoTest', { autoTestId });
        const autoTest = state.tests[autoTestId];

        return axios.post(`/api/v1/auto_tests/${autoTestId}/sets/`).then(({ data }) =>
            commit(types.UPDATE_AUTO_TEST, {
                autoTestId,
                autoTestProps: {
                    sets: [...autoTest.sets, data],
                },
            }),
        );
    },

    async deleteAutoTestSet({ commit, dispatch, state }, { autoTestId, setId }) {
        await dispatch('loadAutoTest', { autoTestId });
        const autoTest = state.tests[autoTestId];

        return axios.delete(`/api/v1/auto_tests/${autoTestId}/sets/${setId}`).then(() =>
            commit(types.UPDATE_AUTO_TEST, {
                autoTestId,
                autoTestProps: {
                    sets: autoTest.sets.filter(set => set.id !== setId),
                },
            }),
        );
    },

    updateAutoTestSet({ commit }, { autoTestId, autoTestSet, setProps }) {
        return axios
            .patch(`/api/v1/auto_tests/${autoTestId}/sets/${autoTestSet.id}`, setProps)
            .then(() =>
                commit(types.UPDATE_AUTO_TEST_SET, {
                    autoTestSet,
                    setProps,
                }),
            );
    },

    createAutoTestSuite({ commit }, { autoTestId, autoTestSet }) {
        const suites = [...autoTestSet.suites, new AutoTestSuiteData(autoTestId, autoTestSet.id)];

        return commit(types.UPDATE_AUTO_TEST_SET, {
            autoTestSet,
            setProps: { suites },
        });
    },

    async deleteAutoTestSuite({ commit, dispatch, state }, { autoTestSuite }) {
        await dispatch('loadAutoTest', { autoTestId: autoTestSuite.autoTestId });
        const autoTest = state.tests[autoTestSuite.autoTestId];

        const autoTestSet = autoTest.sets.find(s => s.id === autoTestSuite.autoTestSetId);

        return commit(types.UPDATE_AUTO_TEST_SET, {
            autoTestSet,
            setProps: {
                suites: autoTestSet.suites.filter(s => s.id !== autoTestSuite.id),
            },
        });
    },

    updateAutoTestSuite({ commit }, { autoTestSet, index, suite }) {
        const suites = [...autoTestSet.suites];
        suites[index] = suite;

        return commit(types.UPDATE_AUTO_TEST_SET, {
            autoTestSet,
            setProps: { suites },
        });
    },

    loadAutoTestRunByUser({ commit, state }, { autoTestId, userId, autoTestRunId }) {
        if (userId in loaders.resultsByUser) {
            return loaders.resultsByUser[userId];
        }

        let promise;
        function finish() {
            promise = null;
            delete loaders.resultsByUser[userId];
        }

        promise = axios
            .get(`/api/v1/auto_tests/${autoTestId}/runs/${autoTestRunId}/users/${userId}/results/`)
            .then(result => {
                const autoTest = state.tests[autoTestId];

                if (autoTest) {
                    commit(types.SET_AUTO_TEST_RESULTS_BY_USER, {
                        autoTest,
                        autoTestRunId,
                        userId,
                        results: getProps(result, [], 'data'),
                    });
                }
                finish();
            }, finish);

        loaders.resultsByUser[userId] = promise;
        return promise;
    },

    async loadAutoTestResult(
        { commit, dispatch, state },
        {
            autoTestId, submissionId, force, autoTestRunId,
        },
    ) {
        await dispatch('loadAutoTest', { autoTestId });
        const autoTest = state.tests[autoTestId];
        let run = getRun(autoTest, autoTestRunId);

        if (run == null) {
            throw new Error('AutoTest has not been run yet.');
        }

        let result = run.findResultBySubId(submissionId);
        if (result == null) {
            await dispatch('loadAutoTestRun', {
                autoTestId,
                force: true,
                autoTestRunId,
            });
            run = getRun(autoTest, autoTestRunId);
            result = run.findResultBySubId(submissionId);
        }

        if (result == null && run != null) {
            const submission = await dispatch(
                'submissions/loadSingleSubmission',
                {
                    submissionId,
                    assignmentId: autoTest.assignment_id,
                },
                { root: true },
            );
            await dispatch('loadAutoTestRunByUser', {
                autoTestId,
                autoTestRunId: run.id,
                userId: submission && submission.user.id,
            });

            run = getRun(autoTest, autoTestRunId);
            result = run.findResultBySubId(submissionId);
        }

        if (result == null) {
            throw new Error('AutoTest result not found!');
        }
        const resultId = result.id;
        result = state.results[resultId];

        // Always reload when force is true.
        if (result && result.finished && result.isFinal && !force) {
            return Promise.resolve();
        }

        if (loaders.results[resultId] == null) {
            loaders.results[resultId] = axios
                .get(`/api/v1/auto_tests/${autoTestId}/runs/${run.id}/results/${resultId}`)
                .then(
                    ({ data }) => {
                        delete loaders.results[resultId];
                        commit(types.UPDATE_AUTO_TEST_RESULT, { autoTest, result: data });
                    },
                    err => {
                        delete loaders.results[resultId];
                        throw err;
                    },
                );
        }

        return loaders.results[resultId];
    },

    async deleteAutoTestResults({ commit, dispatch, state }, { autoTestId, runId }) {
        await dispatch('loadAutoTest', { autoTestId });
        const autoTest = state.tests[autoTestId];

        if (autoTest.runs.length === 0) {
            return Promise.resolve();
        }

        const run = autoTest.runs[0];

        const c = () => {
            commit(types.UPDATE_AUTO_TEST, {
                autoTestId,
                autoTestProps: {
                    runs: [],
                },
            });
            return dispatch('submissions/forceLoadSubmissions', autoTest.assignment_id, {
                root: true,
            });
        };

        return axios
            .delete(`/api/v1/auto_tests/${autoTestId}/runs/${runId}`)
            .then(() =>
                run.results.forEach(r =>
                    dispatch(
                        'rubrics/clearResult',
                        { submissionId: r.submissionId },
                        { root: true },
                    ),
                ),
            )
            .then(
                () => c(),
                err => {
                    switch (getProps(err, null, 'response', 'status')) {
                        case 404:
                            c();
                            throw new Error(
                                'AutoTest results were already deleted. Please reload the page.',
                            );
                        default:
                            throw err;
                    }
                },
            );
    },

    createFixtures({ commit }, { autoTestId, fixtures, delay }) {
        return axios.patch(`/api/v1/auto_tests/${autoTestId}`, fixtures).then(async res => {
            await Promise.resolve([
                commit(types.UPDATE_AUTO_TEST, {
                    autoTestId,
                    autoTestProps: { fixtures: res.data.fixtures },
                }),
                new Promise(resolve => {
                    setTimeout(resolve, delay == null ? 500 : delay);
                }),
            ]);
            return res;
        });
    },

    async toggleFixture({ commit, dispatch, state }, { autoTestId, fixture }) {
        await dispatch('loadAutoTest', { autoTestId });
        const autoTest = state.tests[autoTestId];

        const hidden = !fixture.hidden;
        const method = fixture.hidden ? 'delete' : 'post';

        return axios[method](`/api/v1/auto_tests/${autoTestId}/fixtures/${fixture.id}/hide`).then(
            () => {
                const fixtures = deepCopy(autoTest.fixtures);
                fixtures.find(f => f.id === fixture.id).hidden = hidden;

                commit(types.UPDATE_AUTO_TEST, {
                    autoTestId,
                    autoTestProps: { fixtures },
                });
            },
        );
    },
};

const mutations = {
    [types.SET_AUTO_TEST](state, autoTest) {
        autoTest.sets.forEach(set => {
            set.suites = set.suites.map(
                suite => new AutoTestSuiteData(autoTest.id, set.id, suite, true),
            );
        });

        Object.defineProperty(autoTest, 'pointsPossible', {
            get() {
                return autoTest.sets.reduce((acc1, set) => {
                    if (set.deleted) {
                        return acc1;
                    }

                    return (
                        acc1 +
                        set.suites.reduce(
                            (acc2, suite) =>
                                acc2 + suite.steps.reduce((acc3, step) => acc3 + step.weight, 0),
                            0,
                        )
                    );
                }, 0);
            },
        });

        autoTest.runs = autoTest.runs.map(run => new AutoTestRun(run, autoTest));

        Vue.set(state.tests, autoTest.id, autoTest);
    },

    [types.DELETE_AUTO_TEST](state, autoTestId) {
        state.tests[autoTestId].runs.forEach(run =>
            run.results.forEach(result => Vue.delete(state.results, result.id)),
        );

        Vue.delete(state.tests, autoTestId);
    },

    [types.UPDATE_AUTO_TEST](state, { autoTestId, autoTestProps }) {
        const autoTest = state.tests[autoTestId];

        Object.entries(autoTestProps).forEach(([k, v]) => Vue.set(autoTest, k, v));
    },

    [types.UPDATE_AUTO_TEST_RUNS](state, { autoTest, run }) {
        const runIndex = autoTest.runs.findIndex(r => r.id === run.id);
        let storeRun;

        if (runIndex === -1) {
            storeRun = new AutoTestRun(run, autoTest);
            autoTest.runs.push(storeRun);
        } else {
            storeRun = autoTest.runs[runIndex];
            storeRun.update(run, autoTest);
            Vue.set(autoTest.runs, runIndex, storeRun);
        }
    },

    [types.UPDATE_AUTO_TEST_SET](state, { autoTestSet, setProps }) {
        Object.entries(setProps).forEach(([k, v]) => Vue.set(autoTestSet, k, v));
    },

    [types.DELETE_AUTO_TEST_SUITE](state, { autoTestSuite }) {
        Vue.set(autoTestSuite, 'deleted', true);
    },

    [types.UPDATE_AUTO_TEST_RESULT](state, { result, autoTest }) {
        let storeResult;
        const run = autoTest.runs.find(r => {
            storeResult = r.findResultById(result.id);
            return storeResult != null;
        });

        if (run == null || storeResult == null) {
            return;
        }

        storeResult.updateExtended(result, autoTest);

        run.setResultById(storeResult);
        Vue.set(state.results, storeResult.id, storeResult);
    },

    [types.SET_AUTO_TEST_RESULTS_BY_USER](state, {
        results, autoTest, autoTestRunId, userId,
    }) {
        const runIndex = autoTest.runs.findIndex(r => r.id === autoTestRunId);
        if (runIndex === -1) {
            throw new Error('Could not find run');
        }
        const run = autoTest.runs[runIndex];
        run.updateResultsByUser(userId, results, autoTest);
        Vue.set(autoTest.runs, runIndex, run);
    },

    [types.CLEAR_AUTO_TESTS](state) {
        state.tests = {};
        state.results = {};
    },
};

export default {
    namespaced: true,
    state: {
        tests: {},
        results: {},
    },
    getters,
    actions,
    mutations,
};
