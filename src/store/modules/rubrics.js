// SPDX-License-Identifier: AGPL-3.0-only
import Vue from 'vue';
import axios from 'axios';

import { NONEXISTENT } from '@/constants';
import { Rubric, RubricResult } from '@/models/rubric';
import * as types from '../mutation-types';
import { AssignmentsStore } from './assignments';

const getters = {
    rubrics: state => state.rubrics,
    results: state => state.results,
};

const loaders = {
    rubrics: {},
    results: {},
};

const actions = {
    async loadRubric({ commit, state }, { assignmentId, force }) {
        if (state.rubrics[assignmentId] && !force) {
            return Promise.resolve(state.rubrics[assignmentId]);
        }

        if (!Object.hasOwnProperty.call(loaders.rubrics, assignmentId)) {
            loaders.rubrics[assignmentId] = axios
                .get(`/api/v1/assignments/${assignmentId}/rubrics/`)
                .then(
                    response => {
                        delete loaders.rubrics[assignmentId];
                        commit(types.SET_RUBRIC, {
                            assignmentId,
                            rubric: response.data,
                        });
                        return response;
                    },
                    err => {
                        delete loaders.rubrics[assignmentId];
                        commit(types.SET_RUBRIC, { assignmentId, rubric: NONEXISTENT });
                        throw err;
                    },
                );
        }

        return loaders.rubrics[assignmentId];
    },

    copyRubric({ commit }, { assignmentId, otherAssignmentId }) {
        return axios
            .post(`/api/v1/assignments/${assignmentId}/rubric`, {
                old_assignment_id: otherAssignmentId,
            })
            .then(response => {
                commit(types.SET_RUBRIC, {
                    assignmentId,
                    rubric: response.data,
                });
                return response;
            });
    },

    updateRubric({ commit }, { assignmentId, rubric, maxPoints }) {
        return axios
            .put(`/api/v1/assignments/${assignmentId}/rubrics/`, {
                rows: rubric.rows,
                max_points: maxPoints,
            })
            .then(async response => {
                commit(types.SET_RUBRIC, {
                    assignmentId,
                    rubric: rubric.updateFromServerData(response.data),
                });
                await AssignmentsStore.updateAssignment({
                    assignmentId,
                    assignmentProps: {
                        fixed_max_rubric_points: maxPoints,
                    },
                });
                return response;
            });
    },

    deleteRubric({ commit }, { assignmentId }) {
        return axios.delete(`/api/v1/assignments/${assignmentId}/rubrics/`).then(response => {
            response.onAfterSuccess = () =>
                commit(types.SET_RUBRIC, { assignmentId, rubric: NONEXISTENT });
            return response;
        });
    },

    clearRubric({ commit, state }, { assignmentId }) {
        if (Object.hasOwnProperty.call(state.rubrics, assignmentId)) {
            commit(types.CLEAR_RUBRIC, { assignmentId });
        }
    },

    loadResult({ commit, state, dispatch }, { assignmentId, submissionId, force }) {
        if (state.results[submissionId] && !force) {
            return Promise.resolve();
        }

        if (!Object.hasOwnProperty.call(loaders.results, submissionId)) {
            loaders.results[submissionId] = Promise.all([
                axios.get(`/api/v1/submissions/${submissionId}/rubrics/`),
                dispatch(
                    'submissions/loadSingleSubmission',
                    { assignmentId, submissionId },
                    { root: true },
                ),
            ]).then(
                ([response]) => {
                    delete loaders.results[submissionId];
                    commit(types.SET_RUBRIC_RESULT, {
                        submissionId,
                        result: response.data,
                    });
                    return response;
                },
                err => {
                    delete loaders.results[submissionId];
                    commit(types.SET_RUBRIC_RESULT, {
                        submissionId,
                        result: NONEXISTENT,
                    });
                    throw err;
                },
            );
        }

        return loaders.results[submissionId];
    },

    clearResult({ commit, state }, { submissionId, submissionIds }) {
        let ids = submissionIds;
        if (submissionIds == null) {
            ids = [submissionId];
        }
        ids.forEach(id => {
            if (Object.hasOwnProperty.call(state.results, id)) {
                commit(types.CLEAR_RUBRIC_RESULT, { submissionId: id });
            }
        });
    },

    async updateRubricResult({ commit, state, dispatch }, { assignmentId, submissionId, result }) {
        await Promise.all([
            dispatch(
                'submissions/loadSingleSubmission',
                { assignmentId, submissionId },
                { root: true },
            ),
            dispatch('loadRubric', { assignmentId }),
        ]);

        const rubric = state.rubrics[assignmentId];
        result.validate().throwOnError();

        const selected = Object.assign({}, result.selected);
        rubric.rows.forEach(row => {
            if (row.locked) {
                delete selected[row.id];
            }
        });

        return axios
            .patch(`/api/v1/submissions/${submissionId}/rubricitems/?copy_locked_items`, {
                items: Object.entries(selected).map(([rowId, item]) => ({
                    row_id: Number(rowId),
                    item_id: item.id,
                    multiplier: item.multiplier,
                })),
            })
            .then(response => {
                commit(types.SET_RUBRIC_RESULT, {
                    submissionId,
                    result: response.data.rubric_result,
                });
                return response;
            });
    },
};

export const mutations = {
    [types.SET_RUBRIC](state, { assignmentId, rubric }) {
        let rubricModel = rubric;
        if (rubricModel !== NONEXISTENT && !(rubric instanceof Rubric)) {
            rubricModel = Rubric.fromServerData(rubric);
        }
        Vue.set(state.rubrics, assignmentId, rubricModel);
    },

    [types.CLEAR_RUBRIC](state, { assignmentId }) {
        Vue.delete(state.rubrics, assignmentId);
    },

    [types.CLEAR_RUBRICS](state) {
        Vue.set(state, 'rubrics', {});
    },

    [types.SET_RUBRIC_RESULT](state, { submissionId, result }) {
        let resultModel = result;
        if (result !== NONEXISTENT && !(result instanceof RubricResult)) {
            resultModel = RubricResult.fromServerData(submissionId, result);
        }
        Vue.set(state.results, submissionId, resultModel);
    },

    [types.CLEAR_RUBRIC_RESULT](state, { submissionId }) {
        Vue.delete(state.results, submissionId);
    },

    [types.CLEAR_RUBRIC_RESULTS](state) {
        Vue.set(state, 'results', {});
    },
};

export default {
    namespaced: true,
    state: {
        rubrics: {},
        results: {},
    },
    getters,
    actions,
    mutations,
};
