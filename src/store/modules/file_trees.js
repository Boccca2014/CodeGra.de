/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import axios from 'axios';

import * as utils from '@/utils';
import { FileTree } from '@/models';
import * as types from '../mutation-types';

const getters = {
    getFileTree: state => (assignmentId, submissionId) =>
        utils.getProps(state.fileTrees, null, assignmentId, submissionId),
};

const loaders = {
    fileTrees: {},
};

const actions = {
    async loadFileTree({ commit, dispatch, state }, { assignmentId, submissionId, force }) {
        if (!force && utils.getProps(state.fileTrees, null, assignmentId, submissionId) != null) {
            return Promise.resolve();
        }

        if (force || loaders.fileTrees[submissionId] == null) {
            const loader = Promise.all([
                dispatch(
                    'submissions/loadSingleSubmission',
                    { assignmentId, submissionId },
                    { root: true },
                ),
                axios.get(`/api/v1/submissions/${submissionId}/root_file_trees/`),
            ]).then(
                ([, { data: allFileTrees }]) => {
                    delete loaders.fileTrees[submissionId];
                    const fileTree = FileTree.fromServerData(
                        allFileTrees.student,
                        allFileTrees.teacher,
                    );
                    commit(types.SET_FILETREE, {
                        assignmentId,
                        submissionId,
                        fileTree,
                    });
                },
                err => {
                    delete loaders.fileTrees[submissionId];
                    throw err;
                },
            );
            loaders.fileTrees[submissionId] = loader;
        }

        return loaders.fileTrees[submissionId];
    },

    async updateAutoTestTree(
        { commit, dispatch },
        { assignmentId, submissionId, autoTest, autoTestTree },
    ) {
        await dispatch('loadFileTree', {
            assignmentId,
            submissionId,
            force: false,
        });
        const entries = [];
        autoTest.sets.forEach(set => {
            set.suites.forEach(suite => {
                if (autoTestTree[suite.id] == null) {
                    return;
                }

                entries.push({
                    id: null,
                    name: suite.rubricRow.header,
                    entries: autoTestTree[suite.id],
                    autoTestSuiteId: suite.id,
                });
            });
        });

        commit(types.SET_AT_FILETREE, {
            assignmentId,
            submissionId,
            autoTestTree: {
                id: null,
                name: 'AutoTest generated files',
                entries,
            },
        });
    },

    deleteFileTree({ commit }, { assignmentId }) {
        commit(types.DELETE_FILETREE, { assignmentId });
    },
};

const mutations = {
    [types.SET_FILETREE](state, { assignmentId, submissionId, fileTree }) {
        const trees = utils.getProps(state.fileTrees, {}, assignmentId);
        Vue.set(trees, submissionId, fileTree);
        Vue.set(state.fileTrees, assignmentId, trees);
    },

    [types.SET_AT_FILETREE](state, { assignmentId, submissionId, autoTestTree }) {
        const trees = state.fileTrees[assignmentId];
        const oldTree = trees[submissionId];
        Vue.set(trees, submissionId, oldTree.addAutoTestTree(autoTestTree));
        Vue.set(state.fileTrees, assignmentId, trees);
    },

    [types.DELETE_FILETREE](state, { assignmentId }) {
        Vue.delete(state.fileTrees, assignmentId);
    },

    [types.DELETE_ALL_FILETREES](state) {
        Vue.set(state, 'fileTrees', {});
        loaders.fileTrees = {};
    },
};

export default {
    namespaced: true,
    state: {
        fileTrees: {},
    },

    getters,
    actions,
    mutations,
};
