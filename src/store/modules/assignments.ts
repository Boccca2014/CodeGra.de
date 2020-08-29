/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder } from 'vuex-typex';
import * as utils from '@/utils';

import * as models from '@/models';
import * as api from '@/api/v1';
import { RootState } from '@/store/state';
import { Assignment } from '@/models';

import { CoursesStore } from '@/store';

const storeBuilder = getStoreBuilder<RootState>();

export interface AssignmentState {
    assignments: { [assignmentId: number]: models.Assignment };
    loaders: Record<number, Promise<unknown>>;
}

const moduleBuilder = storeBuilder.module<AssignmentState>('assignments', {
    assignments: {},
    loaders: {},
});

export namespace AssignmentsStore {
    export const commitAssignment = moduleBuilder.commit(
        (state, payload: { assignment: models.Assignment }) => {
            const { assignment } = payload;
            utils.vueSet(state.assignments, assignment.id, assignment);
        },
        'commitAssignment',
    );

    export const commitAssignments = moduleBuilder.commit(
        (state, payload: { assignmentsById: Record<number, models.Assignment> }) => {
            const { assignmentsById } = payload;
            state.assignments = Object.assign({}, state.assignments, assignmentsById);
        },
        'commitAssignments',
    );

    export const commitClearAll = moduleBuilder.commit(state => {
        state.assignments = {};
        state.loaders = {};
    }, 'commitClearAll');

    export const commitRemoveAssignment = moduleBuilder.commit(
        (state, payload: { assignmentId: number }) => {
            utils.vueDelete(state.assignments, payload.assignmentId);
            utils.vueDelete(state.loaders, payload.assignmentId);
        },
        'commitRemoveAssignment',
    );

    // eslint-disable-next-line
    function _getAssignment(state: AssignmentState) {
        return (assignmentId: number): utils.Maybe<models.Assignment> =>
            utils.Maybe.fromNullable(state.assignments?.[assignmentId]);
    }

    export const getAssignment = moduleBuilder.read(_getAssignment, 'getAssignment');

    export const allAssignments = moduleBuilder.read(
        state => Object.values(state.assignments),
        'allAssignments',
    );

    const removeLoader = moduleBuilder.commit((state, payload: { assignmentId: number }) => {
        utils.vueDelete(state.loaders, payload.assignmentId);
    }, 'removeLoader');

    const commitLoader = moduleBuilder.commit(
        (state, payload: { assignmentId: number; value: Promise<unknown> }) => {
            const { assignmentId, value } = payload;
            const removeAfter = () => removeLoader({ assignmentId });
            value.then(removeAfter, removeAfter);
            utils.vueSet(state.loaders, assignmentId, value);
        },
        'commitLoader',
    );

    export const updateAssignment = moduleBuilder.dispatch(
        (
            context,
            payload: { assignmentId: number; assignmentProps: models.AssignmentUpdateableProps },
        ) => {
            const { assignmentId, assignmentProps } = payload;
            const assig = _getAssignment(context.state)(assignmentId);
            assig.caseOf({
                Just(value) {
                    commitAssignment({ assignment: value.update(assignmentProps) });
                },
                Nothing() {
                    throw new ReferenceError('Could not find assignment');
                },
            });
        },
        'updateAssignment',
    );

    export const loadSingleAssignment = moduleBuilder.dispatch(
        ({ state }, payload: { assignmentId: number; courseId?: number; force?: boolean }) => {
            const { assignmentId, force = false, courseId } = payload;
            // A quick early quit, without awaiting any promise.
            if (_getAssignment(state)(assignmentId).isJust()) {
                return Promise.resolve();
            }

            if (state.loaders[assignmentId] == null || force) {
                commitLoader({
                    assignmentId,
                    value: CoursesStore.loadPermissions().then(async () => {
                        if (courseId != null) {
                            await CoursesStore.loadSingleCourse({ courseId, force });
                        }
                        if (_getAssignment(state)(assignmentId).isNothing()) {
                            await api.assignments
                                .getCourse(assignmentId)
                                .then(course => CoursesStore.addCourse({ course }));
                        }
                    }),
                });
            }

            return state.loaders[assignmentId];
        },
        'loadSingleAssignment',
    );

    export const patchAssignment = moduleBuilder.dispatch(
        async (
            _,
            payload: { assignmentId: number; assignmentProps: api.assignments.PatchableProps },
        ) => {
            const { assignmentId, assignmentProps } = payload;
            const res = await api.assignments.patch(assignmentId, assignmentProps);
            function onAfterSuccess() {
                commitAssignment({
                    assignment: Assignment.fromServerData(res.data),
                });
            }
            return { ...res, onAfterSuccess };
        },
        'patchAssignment',
    );
}
