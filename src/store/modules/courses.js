/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import axios from 'axios';

import moment from 'moment';

import { Assignment } from '@/models';
import { makeProvider } from '@/lti_providers';

import * as types from '../mutation-types';
import { MANAGE_ASSIGNMENT_PERMISSIONS, MANAGE_GENERAL_COURSE_PERMISSIONS } from '../../constants';

const getters = {
    courses: state => state.courses,
    assignments: state => {
        if (!state.courses) return {};

        return Object.values(state.courses).reduce((assignments, course) => {
            course.assignments.forEach(assignment => {
                assignments[assignment.id] = assignment;
            });
            return assignments;
        }, {});
    },
};

function getAssignment(state, assignmentId) {
    const assignment = getters.assignments(state)[assignmentId];

    if (assignment == null) {
        throw ReferenceError(`Could not find assignment: ${assignmentId}`);
    }

    return assignment;
}

export function updatePermissions(courses, perms) {
    courses.forEach(c => {
        c.permissions = perms[c.id];
    });

    return Object.entries(perms).reduce(
        ([course, assig, create], [key, val]) => {
            const entries = Object.entries(val);

            assig[key] = entries.some(
                ([k, v]) => v && MANAGE_ASSIGNMENT_PERMISSIONS.indexOf(k) !== -1,
            );

            course[key] = entries.some(
                ([k, v]) => v && MANAGE_GENERAL_COURSE_PERMISSIONS.indexOf(k) !== -1,
            );

            create[key] = !!val.can_create_assignment;

            return [course, assig, create];
        },
        [{}, {}, {}],
    );
}

export const actions = {
    loadCourses({ state, dispatch }) {
        if (state.currentCourseLoader == null) {
            return dispatch('reloadCourses');
        } else {
            return state.currentCourseLoader;
        }
    },

    async forceLoadGraders({ commit, dispatch }, assignmentId) {
        await dispatch('loadCourses');
        const graders = await axios.get(`/api/v1/assignments/${assignmentId}/graders/`).then(
            ({ data }) => data,
            () => null,
        );
        commit(types.UPDATE_ASSIGNMENT, {
            assignmentId,
            assignmentProps: { graders },
        });
    },

    reloadCourses({ commit, state }) {
        commit(`submissions/${types.CLEAR_SUBMISSIONS}`, null, { root: true });
        commit(types.CLEAR_COURSES);

        // TODO: It _may_ be possible that the permissions request is handled
        // first, and that between it and the course request a new course was
        // created, in which case the permission mapping does not contain the
        // permissions for that new course. In that case, newCourse.permissions
        // is undefined, but everywhere in CodeGrade we assume it never is. So
        // we should probably add a check for that, and retrieve the
        // permissions for that course before resolving the promise.
        const coursePromise = Promise.all([
            axios.get('/api/v1/courses/?extended=true'),
            axios.get('/api/v1/permissions/?type=course'),
        ])
            .then(([{ data: courses }, { data: perms }]) => {
                const [manageCourses, manageAssigs, createAssigs] = updatePermissions(
                    courses,
                    perms,
                );

                commit(types.SET_COURSES, [
                    courses,
                    manageCourses,
                    manageAssigs,
                    createAssigs,
                    perms,
                ]);

                return courses;
            })
            // We make this a catch-all, because if this promise does not
            // succeed then all of CodeGrade breaks.
            // TODO: do something more useful when this fails.
            .catch(() => state.courses);

        commit(types.SET_COURSES_PROMISE, coursePromise);

        return coursePromise;
    },

    async updateCourse({ commit, dispatch }, data) {
        await dispatch('loadCourses');
        commit(types.UPDATE_COURSE, data);
    },

    async updateAssignment(context, data) {
        await context.dispatch('loadCourses');
        context.commit(types.UPDATE_ASSIGNMENT, data);
        return context.getters.assignments[data.assignmentId];
    },

    async updateAssignmentReminder(
        { commit, state, dispatch },
        { assignmentId, reminderTime, doneType, doneEmail },
    ) {
        await dispatch('loadCourses');

        const assig = getAssignment(state, assignmentId);
        const newReminderTime = moment(reminderTime, moment.ISO_8601).utc();
        const props = {
            done_type: doneType,
            done_email: doneEmail,
            reminder_time: newReminderTime.isValid()
                ? newReminderTime.format('YYYY-MM-DDTHH:mm')
                : null,
        };

        return axios.patch(`/api/v1/assignments/${assig.id}`, props).then(response => {
            delete props.reminder_time;
            props.reminderTime = newReminderTime;
            response.onAfterSuccess = () =>
                commit(types.UPDATE_ASSIGNMENT, {
                    assignmentId,
                    assignmentProps: props,
                });
            return response;
        });
    },

    async updateAssignmentDeadline({ commit, state, dispatch }, { assignmentId, deadline }) {
        await dispatch('loadCourses');

        const assig = getAssignment(state, assignmentId);
        const newDeadline = moment(deadline, moment.ISO_8601).utc();
        return axios
            .patch(`/api/v1/assignments/${assig.id}`, {
                deadline: newDeadline.toISOString(),
            })
            .then(response => {
                response.onAfterSuccess = () =>
                    commit(types.UPDATE_ASSIGNMENT, {
                        assignmentId,
                        assignmentProps: {
                            deadline: newDeadline,
                        },
                    });
                return response;
            });
    },
};

const mutations = {
    [types.SET_COURSES](state, [courses, manageCourses, manageAssigs, createAssigs, perms]) {
        state.courses = courses.reduce((res, course) => {
            course.assignments = course.assignments.map(serverData =>
                Assignment.fromServerData(serverData, course.id, manageAssigs[course.id]),
            );

            course.permissions = perms[course.id] || {};
            course.canManage = manageCourses[course.id] || false;
            course.canManageAssignments = manageAssigs[course.id] || false;
            course.canCreateAssignments = createAssigs[course.id] || false;

            Object.defineProperty(course, 'ltiProvider', {
                get() {
                    const provider = this.lti_provider;
                    if (provider == null) {
                        return null;
                    } else {
                        return makeProvider(provider);
                    }
                },
                enumerable: true,
            });

            Object.defineProperty(course, 'isStudent', {
                get() {
                    return !(
                        this.canManage ||
                        this.canManageAssignments ||
                        this.canCreateAssignments
                    );
                },
                enumerable: true,
            });

            res[course.id] = course;
            return res;
        }, {});
    },

    [types.CLEAR_COURSES](state) {
        state.courses = {};
        state.currentCourseLoader = null;
    },

    [types.UPDATE_COURSE](state, { courseId, courseProps }) {
        const course = state.courses[courseId];

        if (course == null) {
            throw ReferenceError(`Could not find course: ${courseId}`);
        }

        Object.keys(courseProps).forEach(key => {
            if (!{}.hasOwnProperty.call(course, key) || key === 'id') {
                throw TypeError(`Cannot set course property: ${key}`);
            }

            Vue.set(course, key, courseProps[key]);
        });
    },

    [types.SET_COURSES_PROMISE](state, promise) {
        state.currentCourseLoader = promise;
    },

    [types.UPDATE_ASSIGNMENT](state, { assignmentId, assignmentProps }) {
        const assignment = getAssignment(state, assignmentId).update(assignmentProps);
        const assigs = state.courses[assignment.courseId].assignments;
        const assigindex = assigs.findIndex(x => x.id === assignment.id);
        Vue.set(assigs, assigindex, assignment);
    },
};

export default {
    namespaced: true,
    state: {
        courses: {},
        currentCourseLoader: null,
    },

    getters,
    actions,
    mutations,
};

export function onDone(store) {
    store.watch(
        (_, allGetters) => allGetters['user/loggedIn'],
        loggedIn => {
            if (loggedIn) {
                store.dispatch('courses/loadCourses');
            } else {
                store.commit(`courses/${types.CLEAR_COURSES}`, null, { root: true });
            }
        },
    );
}
