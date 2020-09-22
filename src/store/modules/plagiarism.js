/* SPDX-License-Identifier: AGPL-3.0-only */
import axios from 'axios';
import Vue from 'vue';

import { flatMap1, buildUrl } from '@/utils/typed';
import * as types from '../mutation-types';

const LIMIT_FIRST_REQUEST = 250;
const LIMIT_PER_REQUEST = 100;

const getters = {
    runs: state => state.runs,
};

const processCase = (run, serverCase) => {
    serverCase.assignments = serverCase.assignment_ids.map(assigId => {
        const assig = run.assignments[assigId];
        return Object.assign({ course: run.courses[assig.course_id] }, assig);
    });

    serverCase.canView = serverCase.can_see_details;
    if (!serverCase.canView) {
        // eslint-disable-next-line
        serverCase._rowVariant = 'warning';
    }

    return serverCase;
};

function addUsersToStore(dispatch, cases) {
    return Promise.all(
        flatMap1(cases || [], c =>
            c.users
                .filter(u => u != null)
                .map(u => dispatch('users/addOrUpdateUser', { user: u }, { root: true })),
        ),
    );
}

const actions = {
    loadRun({ state, commit, dispatch }, runId) {
        if (state.loadRunPromises[runId] == null) {
            const promise = Promise.all([
                axios.get(
                    buildUrl(['api', 'v1', 'plagiarism', runId], {
                        query: { no_course_in_assignment: true },
                    }),
                ),
                axios.get(
                    buildUrl(['api', 'v1', 'plagiarism', runId, 'cases'], {
                        query: {
                            limit: LIMIT_FIRST_REQUEST,
                            no_assignment_in_case: true,
                        },
                        addTrailingSlash: true,
                    }),
                ),
            ]).then(async ([{ data: run }, { data: cases }]) => {
                run.cases = (cases || []).map(c => processCase(run, c));
                run.has_more_cases = run.cases.length >= LIMIT_FIRST_REQUEST;
                await addUsersToStore(dispatch, run.cases);
                commit(types.SET_PLAGIARISM_RUN, run);
                return run;
            });
            commit(types.SET_PLAGIARISM_PROMISE, { runId, promise });
        }
        return state.loadRunPromises[runId];
    },

    async loadMoreCases({ state, commit, dispatch }, runId) {
        await state.loadRunPromises[runId];
        const run = state.runs[runId];
        if (run.has_more_cases) {
            const { data: cases } = await axios.get(
                buildUrl(['api', 'v1', 'plagiarism', runId, 'cases'], {
                    query: {
                        limit: LIMIT_PER_REQUEST,
                        no_assignment_in_case: true,
                        offset: state.runs[runId].cases.length,
                    },
                    addTrailingSlash: true,
                }),
            );
            const newCases = cases.map(c => processCase(run, c));
            await addUsersToStore(dispatch, newCases);
            commit(types.ADD_PLAGIARISM_CASES, {
                runId,
                newCases,
            });
        }
    },

    async refreshRun({ dispatch }, runId) {
        await dispatch('removeRun', runId);
        return dispatch('loadRun', runId);
    },

    removeRun({ commit }, runId) {
        commit(types.CLEAR_PLAGIARISM_RUN, runId);
    },

    clear({ commit }) {
        commit(types.CLEAR_PLAGIARISM_RUNS);
    },
};

const mutations = {
    [types.SET_PLAGIARISM_RUN](state, run) {
        Vue.set(state.runs, run.id, run || {});
    },

    [types.CLEAR_PLAGIARISM_RUN](state, runId) {
        Vue.set(state.runs, runId, undefined);
        Vue.set(state.loadRunPromises, runId, undefined);

        delete state.runs[runId];
        delete state.loadRunPromises[runId];
    },

    [types.ADD_PLAGIARISM_CASES](state, { runId, newCases }) {
        const run = state.runs[runId];
        run.cases = run.cases.concat(newCases);
        run.has_more_cases = newCases.length >= LIMIT_PER_REQUEST;
        Vue.set(state.runs, runId, run);
    },

    [types.SET_PLAGIARISM_PROMISE](state, { runId, promise }) {
        Vue.set(state.loadRunPromises, runId, promise);
    },

    [types.CLEAR_PLAGIARISM_RUNS](state) {
        state.runs = {};
        state.loadRunPromises = {};
    },
};

export default {
    namespaced: true,
    state: {
        runs: {},
        loadRunPromises: {},
    },
    getters,
    actions,
    mutations,
};
