/* SPDX-License-Identifier: AGPL-3.0-only */
import axios from 'axios';
import Vue from 'vue';

import { makeUser } from '@/models/user';
import { getProps } from '@/utils';

import * as types from '../mutation-types';

const getters = {
    getUser: state => userId => state.usersById[userId] || null,
    getGroupInGroupSetOfUser: state => (groupSetId, userId) =>
        state.usersById[getProps(state.groupsByUser, null, userId, groupSetId)] || null,
    getGroupsOfGroupSet: state => groupSetId => {
        const res = [];
        if (state.groupsByGroupSet[groupSetId]) {
            state.groupsByGroupSet[groupSetId].forEach(id => {
                const user = state.usersById[id];
                if (user != null && user.isGroup) {
                    res.push(user);
                }
            });

            res.sort((a, b) => a.group.createdAt - b.group.createdAt);
        }
        return res;
    },
};

function groupToVirtualUser(group) {
    const groupUser = group.virtual_user;
    delete group.virtual_user;
    groupUser.group = group;
    return groupUser;
}

function getGroupUser(state, virtualUserId) {
    const groupUser = state.usersById[virtualUserId];
    if (groupUser == null) {
        throw new Error(`No user found for id: ${virtualUserId}`);
    } else if (!groupUser.isGroup) {
        throw new Error('The given user is not a group');
    }
    return groupUser;
}

const actions = {
    addOrUpdateUser({ commit }, { user }) {
        commit(types.ADD_OR_UPDATE_USER, user);
    },

    loadGroupsOfGroupSet({ commit, state }, { groupSetId, force }) {
        if (force) {
            commit(types.UPDATE_GROUP_SET_PROMISE, { groupSetId, promise: null });
        }

        if (!state.groupSetPromises[groupSetId]) {
            commit(types.UPDATE_GROUP_SET_PROMISE, {
                groupSetId,
                promise: axios.get(`/api/v1/group_sets/${groupSetId}/groups/`).then(response => {
                    const groups = response.data;
                    groups.forEach(group => {
                        commit(types.ADD_OR_UPDATE_USER, groupToVirtualUser(group));
                    });
                    response.data = null;
                    return response;
                }),
            });
        }

        return state.groupSetPromises[groupSetId];
    },

    async createNewGroup({ commit, dispatch }, { groupSetId, memberIds = [] }) {
        await dispatch('loadGroupsOfGroupSet', { groupSetId });
        return axios
            .post(`/api/v1/group_sets/${groupSetId}/group`, {
                member_ids: memberIds,
            })
            .then(response => {
                commit(types.ADD_OR_UPDATE_USER, groupToVirtualUser(response.data));
                return response;
            });
    },

    updateGroupTitle({ commit, state }, { virtualUserId, newTitle }) {
        const groupUser = getGroupUser(state, virtualUserId);

        return axios
            .post(`/api/v1/groups/${groupUser.group.id}/name`, {
                name: newTitle,
            })
            .then(response => {
                response.onAfterSuccess = () =>
                    commit(types.ADD_OR_UPDATE_USER, groupToVirtualUser(response.data));
                return response;
            });
    },

    removeUserFromGroup({ commit, state }, { virtualUserId, toRemoveUserId }) {
        const groupUser = getGroupUser(state, virtualUserId);

        return axios
            .delete(`/api/v1/groups/${groupUser.group.id}/members/${toRemoveUserId}`)
            .then(response => {
                response.onAfterSuccess = () =>
                    commit(types.ADD_OR_UPDATE_USER, groupToVirtualUser(response.data));
                return response;
            });
    },

    addUserToGroup({ commit, state }, { virtualUserId, newUsername }) {
        const groupUser = getGroupUser(state, virtualUserId);

        return axios
            .post(`/api/v1/groups/${groupUser.group.id}/member`, { username: newUsername })
            .then(response => {
                response.onAfterSuccess = () =>
                    commit(types.ADD_OR_UPDATE_USER, groupToVirtualUser(response.data));
                return response;
            });
    },

    deleteGroup({ commit, state }, { virtualUserId }) {
        const groupUser = getGroupUser(state, virtualUserId);

        if (groupUser.group.memberIds.length !== 0) {
            throw new Error('You cannot delete a group with users.');
        }

        return axios.delete(`/api/v1/groups/${groupUser.group.id}`).then(response => {
            response.onAfterSuccess = () =>
                commit(types.DELETE_GROUP_USER, {
                    virtualUserId,
                    groupSetId: groupUser.group.groupSetId,
                });
            return response;
        });
    },
};

const mutations = {
    [types.ADD_OR_UPDATE_USER](state, serverData) {
        if (serverData.id == null) {
            throw new Error('Users should have an `id` property');
        }
        if (Object.keys(serverData) === ['id']) {
            return;
        }

        const oldObject = state.usersById[serverData.id];
        const newObject = makeUser(serverData, oldObject);

        if (oldObject != null && oldObject.isGroup !== newObject.isGroup) {
            throw new Error('Users cannot change their group status');
        }

        if (newObject.isGroup) {
            let toRemove = [];
            let toAdd;

            if (oldObject == null) {
                toAdd = newObject.group.memberIds;
            } else {
                toRemove = oldObject.group.memberIds.filter(
                    id => !newObject.group.memberIds.includes(id),
                );
                toAdd = newObject.group.memberIds.filter(
                    id => oldObject.group.memberIds.indexOf(id) < 0,
                );
            }

            const gsetId = newObject.group.groupSetId;
            toRemove.forEach(userId => {
                const groupIds = Object.assign({}, state.groupsByUser[userId] || {});
                delete groupIds[gsetId];

                Vue.set(state.groupsByUser, userId, Object.freeze(groupIds));
            });

            toAdd.forEach(userId => {
                const newGroupIds = Object.assign({}, state.groupsByUser[userId] || {}, {
                    [gsetId]: newObject.id,
                });

                Vue.set(state.groupsByUser, userId, Object.freeze(newGroupIds));
            });

            Vue.set(
                state.groupsByGroupSet,
                newObject.group.groupSetId,
                (state.groupsByGroupSet[newObject.group.groupSetId] || new Set()).add(newObject.id),
            );
        }

        Vue.set(state.usersById, newObject.id, newObject);
    },

    [types.UPDATE_GROUP_SET_PROMISE](state, { groupSetId, promise }) {
        Vue.set(state.groupSetPromises, groupSetId, promise);
    },

    [types.DELETE_GROUP_USER](state, { virtualUserId, groupSetId }) {
        Vue.delete(state.usersById, virtualUserId);
        const set = state.groupsByGroupSet[groupSetId];
        set.delete(virtualUserId);
        Vue.set(state.groupsByGroupSet, groupSetId, set);
    },

    [types.CLEAR_USERS](state) {
        state.usersById = {};
        state.groupsByUser = {};
        state.groupsByGroupSet = {};
        state.groupSetPromises = {};
    },
};

export default {
    namespaced: true,
    state: {
        usersById: {},
        groupsByUser: {},
        groupsByGroupSet: {},
        groupSetPromises: {},
    },
    getters,
    actions,
    mutations,
};
