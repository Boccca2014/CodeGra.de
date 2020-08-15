/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import axios from 'axios';

import { GradersStore } from '@/store/modules/graders';
import * as utils from '@/utils';
import { Submission } from '@/models/submission';
import * as types from '../mutation-types';

function getSubmission(state, submissionId, throwNotFound = true) {
    const submission = state.submissions[submissionId];

    if (submission == null) {
        if (throwNotFound) {
            throw ReferenceError(`Could not find submission: ${submissionId}`);
        }
        return null;
    }

    return submission;
}

const getters = {
    getSingleSubmission: state => (assignmentId, submissionId) => {
        // TODO: Get rid of the assignmentId argument.
        let id;
        if (submissionId === undefined && assignmentId !== undefined) {
            id = assignmentId;
        } else {
            id = submissionId;
        }
        return getSubmission(state, id, false);
    },
    getLatestSubmissions: state => assignmentId =>
        utils
            .getProps(state.latestSubmissions, [], assignmentId, 'array')
            .map(subId => getSubmission(state, subId, true)),
    getGroupSubmissionOfUser: state => (assignmentId, userId) => {
        const subId = utils.getProps(state.groupSubmissionUsers, null, assignmentId, userId);
        if (subId == null) {
            return null;
        }
        return getSubmission(state, subId);
    },
    getSubmissionsByUser: (state, otherGetters) => (
        assignmentId,
        userId,
        { includeGroupSubmissions = false } = {},
    ) => {
        const res = [];
        utils.getProps(state.submissionsByUser, [], assignmentId, userId).forEach(subId => {
            res.push(getSubmission(state, subId));
        });
        res.sort((a, b) => a.createdAt - b.createdAt);

        // These are always seen as newer so insert these at the end of the
        // array.
        if (includeGroupSubmissions) {
            const latestGroupSub = otherGetters.getGroupSubmissionOfUser(assignmentId, userId);
            if (latestGroupSub) {
                otherGetters
                    .getSubmissionsByUser(assignmentId, latestGroupSub.userId, {
                        includeGroupSubmissions: false,
                    })
                    .forEach(groupSub => {
                        res.push(groupSub);
                    });
            }
        }

        return res;
    },

    getIsLatestSubmissionByUser: (state, otherGetters) => submission => {
        const assignmentId = submission.assignment.id;
        const user = submission.user;
        if (!user.isGroup) {
            if (otherGetters.getGroupSubmissionOfUser(assignmentId, user.id)) {
                return false;
            }
        }

        const subIds = utils.getProps(state.submissionsByUser, [], assignmentId, user.id);
        // eslint-disable-next-line
        for (const subId of subIds.values()) {
            if (
                subId !== submission.id &&
                getSubmission(state, subId).createdAt.isAfter(submission.createdAt)
            ) {
                return false;
            }
        }
        return true;
    },
};

function getUsersInGroup(submissions, subIds) {
    const userIds = {};
    subIds.forEach(subId => {
        const sub = submissions[subId];

        if (sub.user.group) {
            sub.user.group.members.forEach(member => {
                userIds[member.id] = sub.id;
            });
        }
    });
    return userIds;
}

function addToLatest(submissions, latestSubs, newSub) {
    const index = latestSubs.lookup[newSub.userId];

    if (index != null) {
        const oldSub = submissions[latestSubs.array[index]];
        if (oldSub.createdAt.isBefore(newSub.createdAt)) {
            Vue.set(latestSubs.array, index, newSub.id);
        }
    } else {
        Vue.set(latestSubs.lookup, newSub.userId, latestSubs.array.length);
        latestSubs.array.push(newSub.id);
        Vue.set(latestSubs, 'array', latestSubs.array);
    }

    return latestSubs;
}

function getLatestSubmissions(subs) {
    // BLAZE IT: R y a n C e l s i u s ° S o u n d s
    const seen = new Set();
    return subs
        .filter(item => {
            if (seen.has(item.userId)) {
                return false;
            } else {
                seen.add(item.userId);
                return true;
            }
        })
        .reduce(
            (acc, cur) => {
                acc.lookup[cur.userId] = acc.array.length;
                acc.array.push(cur.id);
                return acc;
            },
            {
                array: [],
                lookup: {},
            },
        );
}

function commitRubricResult(commit, submissionId, result) {
    commit(`rubrics/${types.SET_RUBRIC_RESULT}`, { submissionId, result }, { root: true });
}

const actions = {
    async loadSubmissionsByUser(context, { assignmentId, userId, force }) {
        await context.dispatch('loadSubmissions', assignmentId);

        if (force) {
            context.commit(types.SET_SUBMISSIONS_BY_USER_PROMISE, {
                assignmentId,
                userId,
                promise: null,
            });
        }

        if (context.state.submissionsByUserPromises[assignmentId][userId] == null) {
            const promise = axios
                .get(`/api/v1/assignments/${assignmentId}/users/${userId}/submissions/?extended`)
                .then(({ data: subs }) => {
                    subs.forEach(sub => {
                        context.commit(types.ADD_SINGLE_SUBMISSION, {
                            submission: Submission.fromServerData(sub, assignmentId),
                        });
                        if (sub.rubric_result != null) {
                            commitRubricResult(context.commit, sub.id, sub.rubric_result);
                        }
                    });
                });
            context.commit(types.SET_SUBMISSIONS_BY_USER_PROMISE, {
                assignmentId,
                userId,
                promise,
            });
        }

        await context.state.submissionsByUserPromises[assignmentId][userId];

        return context.getters.getSubmissionsByUser(assignmentId, userId);
    },

    loadGivenSubmissions(context, { assignmentId, submissionIds, onError }) {
        return Promise.all(
            submissionIds.map(submissionId =>
                context
                    .dispatch('loadSingleSubmission', {
                        assignmentId,
                        submissionId,
                    })
                    .catch(err => {
                        if (onError) {
                            return onError(err, submissionId);
                        } else {
                            throw err;
                        }
                    }),
            ),
        );
    },

    async loadSingleSubmission(context, { assignmentId, submissionId, force }) {
        // Don't wait for anything if we simply have the submission
        let submission = getSubmission(context.state, submissionId, false);
        if (submission != null && !force) {
            return submission;
        }

        await context.dispatch('loadSubmissions', assignmentId);

        if (context.state.singleSubmissionLoaders[submissionId] != null && !force) {
            return context.state.singleSubmissionLoaders[submissionId];
        }

        submission = getSubmission(context.state, submissionId, false);
        if (submission != null && !force) {
            return submission;
        }

        const promise = axios.get(`/api/v1/submissions/${submissionId}`).then(({ data }) => {
            const sub = Submission.fromServerData(data, assignmentId);
            context.commit(types.ADD_SINGLE_SUBMISSION, { submission: sub });
            if (data.rubric_result != null) {
                commitRubricResult(context.commit, sub.id, data.rubric_result);
            }
            return sub;
        });

        context.commit(types.SET_SINGLE_SUBMISSION_PROMISE, {
            submissionId,
            promise,
        });

        return promise.then(data => {
            context.commit(types.SET_SINGLE_SUBMISSION_PROMISE, {
                submissionId,
                promise: null,
            });
            return data;
        });
    },

    addSubmission({ commit }, { submission, assignmentId }) {
        commit(types.ADD_SINGLE_SUBMISSION, {
            submission: Submission.fromServerData(submission, assignmentId),
        });
        if (submission.rubric_result != null) {
            commitRubricResult(commit, submission.id, submission.rubric_result);
        }
    },

    async deleteSubmission({ dispatch }, { assignmentId }) {
        return dispatch('forceLoadSubmissions', assignmentId);
    },

    forceLoadSubmissions(context, assignmentId) {
        // This needs to be in one promise to make sure that two very quick
        // calls to `loadSubmissions` still only does one request (for the
        // same arguments of course).
        const promiseFun = async () => {
            await Promise.all([
                context.dispatch('fileTrees/deleteFileTree', { assignmentId }, { root: true }),
                context.dispatch('feedback/deleteFeedback', { assignmentId }, { root: true }),
                context.dispatch('courses/loadCourses', null, { root: true }),
                context.dispatch(
                    'rubrics/clearResult',
                    {
                        submissionIds: utils.getProps(
                            context.state.latestSubmissions,
                            [],
                            assignmentId,
                            'array',
                        ),
                    },
                    { root: true },
                ),
            ]);

            await Promise.all([
                axios
                    .get(`/api/v1/assignments/${assignmentId}/submissions/?extended&latest_only`)
                    .then(({ data: submissions }) => {
                        submissions.forEach(sub => {
                            if (sub.rubric_result != null) {
                                commitRubricResult(context.commit, sub.id, sub.rubric_result);
                            }
                        });
                        return submissions.map(s => Submission.fromServerData(s, assignmentId));
                    }),
                // TODO: Maybe not force load the graders here?
                GradersStore.loadGraders({
                    assignmentId,
                    force: true,
                }).catch(
                    utils.makeHttpErrorHandler({
                        403: () => null,
                    }),
                ),
            ]).then(([submissions]) => {
                context.commit(types.UPDATE_SUBMISSIONS, {
                    assignmentId,
                    submissions,
                });
            });

            // It is possible that in the mean time these promises were
            // cleared. Simply store them again to prevent double loading.
            context.commit(types.SET_SUBMISSIONS_PROMISE, {
                assignmentId,
                promise: Promise.resolve(),
            });
        };

        const promise = promiseFun();
        context.commit(types.SET_SUBMISSIONS_PROMISE, {
            assignmentId,
            promise,
        });

        return promise;
    },

    async loadSubmissions(context, assignmentId) {
        if (context.state.submissionsLoaders[assignmentId] == null) {
            await context.dispatch('forceLoadSubmissions', assignmentId);
        }

        return context.state.submissionsLoaders[assignmentId];
    },

    updateSubmission({ commit }, { assignmentId, submissionId, submissionProps }) {
        commit(types.UPDATE_SUBMISSION, {
            assignmentId,
            submissionId,
            submissionProps,
        });
    },

    async loadLatestByUserInCourse(context, { courseId, userId }) {
        return axios
            .get(`/api/v1/courses/${courseId}/users/${userId}/submissions/?latest_only`)
            .then(res =>
                utils.mapObject(res.data, ([sub]) => {
                    if (sub == null) {
                        return null;
                    }

                    const assignmentId = sub.assignment_id;
                    const submission = Submission.fromServerData(sub, assignmentId);
                    context.commit(types.ADD_SINGLE_SUBMISSION, { submission });
                    return submission;
                }),
            );
    },
};

const mutations = {
    [types.UPDATE_SUBMISSIONS](state, { assignmentId, submissions }) {
        Vue.set(
            state,
            'submissions',
            Object.assign(
                {},
                state.submissions,
                submissions.reduce((acc, cur) => {
                    acc[cur.id] = cur;
                    return acc;
                }, {}),
            ),
        );

        const newLatest = getLatestSubmissions(submissions);

        Vue.set(state.latestSubmissions, assignmentId, newLatest);
        Vue.set(
            state.groupSubmissionUsers,
            assignmentId,
            getUsersInGroup(state.submissions, newLatest.array),
        );
        Vue.set(
            state.submissionsByUser,
            assignmentId,
            submissions.reduce((accum, val) => {
                accum[val.userId] = new Set([val.id]);
                return accum;
            }, {}),
        );
        Vue.set(state.submissionsByUserPromises, assignmentId, {});
    },

    [types.SET_SUBMISSIONS_BY_USER_PROMISE](state, { assignmentId, userId, promise }) {
        const all = state.submissionsByUserPromises[assignmentId];
        Vue.set(all, userId, promise);
        Vue.set(state.submissionsByUserPromises, assignmentId, all);
    },

    [types.UPDATE_SUBMISSION](state, { submissionId, submissionProps }) {
        const submission = getSubmission(state, submissionId).update(submissionProps);
        Vue.set(state.submissions, submission.id, submission);
    },

    [types.SET_SUBMISSIONS_PROMISE](state, { promise, assignmentId }) {
        Vue.set(state.submissionsLoaders, assignmentId, promise);
    },

    [types.SET_SINGLE_SUBMISSION_PROMISE](state, { promise, submissionId }) {
        if (promise) {
            Vue.set(state.singleSubmissionLoaders, submissionId, promise);
        } else {
            Vue.delete(state.singleSubmissionLoaders, submissionId);
        }
    },

    [types.ADD_SINGLE_SUBMISSION](state, { submission }) {
        Vue.set(state.submissions, submission.id, submission);

        const userId = submission.userId;
        const assignmentId = submission.assignmentId;

        const userSubmissions = utils.getProps(
            state.submissionsByUser,
            new Set(),
            assignmentId,
            userId,
        );
        userSubmissions.add(submission.id);

        const oldLatest = state.latestSubmissions[assignmentId] || { lookup: {}, array: [] };
        const newLatest = addToLatest(state.submissions, oldLatest, submission);

        Vue.set(state.latestSubmissions, assignmentId, newLatest);
        Vue.set(
            state.groupSubmissionUsers,
            assignmentId,
            getUsersInGroup(state.submissions, newLatest.array),
        );

        if (state.submissionsByUser[assignmentId] == null) {
            Vue.set(state.submissionsByUser, assignmentId, { userId: userSubmissions });
        } else {
            Vue.set(state.submissionsByUser[assignmentId], userId, userSubmissions);
        }
    },

    [types.CLEAR_SUBMISSIONS](state) {
        Vue.set(state, 'submissions', {});
        Vue.set(state, 'latestSubmissions', {});
        Vue.set(state, 'submissionsByUser', {});
        Vue.set(state, 'submissionsByUserPromises', {});
        Vue.set(state, 'submissionsLoaders', {});
        Vue.set(state, 'singleSubmissionLoaders', {});
        Vue.set(state, 'groupSubmissionUsers', {});
    },
};

export default {
    namespaced: true,
    state: {
        submissions: {},
        latestSubmissions: {},
        submissionsByUser: {},
        submissionsByUserPromises: {},
        submissionsLoaders: {},
        singleSubmissionLoaders: {},
        groupSubmissionUsers: {},
    },

    getters,
    actions,
    mutations,
};
