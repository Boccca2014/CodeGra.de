/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import axios from 'axios';
import jwtDecode from 'jwt-decode';

import * as utils from '@/utils';
import * as types from '../mutation-types';

const UNLOADED_SNIPPETS = {};
let snippetsLastReloaded;

function setUser(user) {
    utils.withSentry(Sentry => {
        Sentry.setUser(user);
    });
}

const getters = {
    loggedIn: state => state.id !== 0,
    id: state => state.id,
    snippets: state => state.snippets,
    name: state => state.name,
    username: state => state.username,
    canSeeHidden: state => state.canSeeHidden,
    permissions: state => state.permissions || {},
    findSnippetsByPrefix(state) {
        let values = [];
        if (state && state.snippets !== UNLOADED_SNIPPETS) {
            values = Object.values(state.snippets).sort((a, b) => a.key.localeCompare(b.key));
        }

        return prefix => values.filter(({ key }) => key.startsWith(prefix));
    },
    dangerousJwtToken: state => state.jwtToken,
    jwtClaims: (state, otherGetters) => {
        const jwt = otherGetters.dangerousJwtToken;
        if (!jwt) {
            return {};
        }
        return utils.getProps(jwtDecode(jwt), {}, 'user_claims') || {};
    },
};

const actions = {
    login({ commit, dispatch }, response) {
        commit(types.LOGIN, response.data);
        return dispatch(
            'users/addOrUpdateUser',
            {
                user: response.data.user,
            },
            {
                root: true,
            },
        );
    },

    addSnippet({ commit }, snippet) {
        commit(types.NEW_SNIPPET, snippet);
    },

    updateSnippet({ commit }, snippet) {
        commit(types.UPDATE_SNIPPET, snippet);
    },

    deleteSnippet({ commit }, snippet) {
        commit(types.REMOVE_SNIPPET, snippet);
    },

    refreshSnippets({ commit }) {
        return new Promise(resolve => {
            axios.get('/api/v1/snippets/').then(({ data }) => {
                const snips = {};
                for (let i = 0, len = data.length; i < len; i += 1) {
                    snips[data[i].key] = data[i];
                }
                commit(types.SNIPPETS, snips);
                snippetsLastReloaded = Date.now();
                resolve();
            });
        });
    },

    maybeRefreshSnippets({ commit, state }) {
        if (!state || state.snippets === UNLOADED_SNIPPETS) {
            return actions.refreshSnippets({ commit });
        }

        const diff = (Date.now() - snippetsLastReloaded) / (60 * 1000);

        if (diff > 5 && Math.random() < ((diff - 5) / (60 * 24)) ** 2) {
            return actions.refreshSnippets({ commit });
        }

        return null;
    },

    logout({ commit }) {
        commit(types.LOGOUT);
        return Promise.all([
            commit(`submissions/${types.CLEAR_SUBMISSIONS}`, null, { root: true }),
            commit(`code/${types.CLEAR_CODE_CACHE}`, null, { root: true }),
            commit(`plagiarism/${types.CLEAR_PLAGIARISM_RUNS}`, null, {
                root: true,
            }),
            commit(`rubrics/${types.CLEAR_RUBRIC_RESULTS}`, null, { root: true }),
            commit(`rubrics/${types.CLEAR_RUBRICS}`, null, { root: true }),
            commit(`autotest/${types.CLEAR_AUTO_TESTS}`, null, { root: true }),
            commit(`users/${types.CLEAR_USERS}`, null, { root: true }),
            commit(`fileTrees/${types.DELETE_ALL_FILETREES}`, null, { root: true }),
            commit('feedback/commitDeleteAllFeedback', null, { root: true }),
            commit('notification/commitClearNotifications', null, { root: true }),
            commit('peer_feedback/commitClearConnections', null, { root: true }),
        ]);
    },

    verifyLogin({ commit, state, dispatch }) {
        return new Promise((resolve, reject) => {
            axios
                .get('/api/v1/login?type=extended&with_permissions')
                .then(async response => {
                    // We are already logged in. Update state to logged in state
                    commit(types.LOGIN, {
                        access_token: state.jwtToken,
                        user: response.data,
                    });
                    await dispatch(
                        'users/addOrUpdateUser',
                        {
                            user: response.data,
                        },
                        {
                            root: true,
                        },
                    );
                    resolve(response);
                })
                .catch(() => {
                    dispatch('logout').then(reject, reject);
                });
        });
    },

    updateUserInfo({ commit, dispatch }, { name, email, oldPw, newPw }) {
        return axios
            .patch('/api/v1/login', {
                name,
                email,
                old_password: oldPw,
                new_password: newPw,
            })
            .then(async response => {
                commit(types.UPDATE_USER_INFO, { name, email });
                await dispatch(
                    'users/addOrUpdateUser',
                    {
                        user: response.data,
                    },
                    {
                        root: true,
                    },
                );
                return response;
            });
    },

    updateAccessToken({ dispatch, commit }, newToken) {
        return dispatch('logout')
            .then(() => commit(types.SET_ACCESS_TOKEN, newToken))
            .then(() => dispatch('verifyLogin'));
    },
};

const mutations = {
    [types.LOGIN](state, data) {
        state.jwtToken = data.access_token;

        const userdata = data.user;
        state.id = userdata.id;
        state.email = userdata.email;
        state.name = userdata.name;
        state.canSeeHidden = userdata.hidden;
        state.username = userdata.username;
        state.permissions = userdata.permissions;
        setUser({
            id: state.id,
            username: state.username,
        });
    },

    [types.SNIPPETS](state, snippets) {
        state.snippets = snippets;
    },

    [types.LOGOUT](state) {
        state.id = 0;
        state.name = '';
        state.email = '';
        state.snippets = UNLOADED_SNIPPETS;
        state.canSeeHidden = false;
        state.jwtToken = null;
        state.username = null;
        state.permissions = null;
        setUser(null);
    },

    [types.NEW_SNIPPET](state, { id, key, value }) {
        Vue.prototype.$set(state.snippets, key, { id, key, value });
    },

    [types.UPDATE_SNIPPET](state, { id, key, value }) {
        const oldKey = Object.entries(state.snippets).find(([, snippet]) => snippet.id === id)[0];
        delete state.snippets[oldKey];
        Vue.prototype.$set(state.snippets, key, { id, key, value });
    },

    [types.REMOVE_SNIPPET](state, { key }) {
        const newSnippets = Object.assign({}, state.snippets);
        delete newSnippets[key];
        state.snippets = newSnippets;
    },

    [types.UPDATE_USER_INFO](state, { name, email }) {
        state.name = name;
        state.email = email;
    },

    [types.SET_ACCESS_TOKEN](state, accessToken) {
        state.jwtToken = accessToken;
    },

    [types.CLEAR_CACHE](state) {
        state.snippets = UNLOADED_SNIPPETS;
    },
};

export default {
    namespaced: true,
    state: {
        jwtToken: null,
        id: 0,
        email: '',
        name: '',
        snippets: UNLOADED_SNIPPETS,
        permissions: null,
        canSeeHidden: false,
        username: '',
    },
    getters,
    actions,
    mutations,
};
