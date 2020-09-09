/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder } from 'vuex-typex';
import { Store } from 'vuex';

import * as utils from '@/utils';
import axios from 'axios';
import * as api from '@/api/v1';
import { CoursePermissionOptions as CPermOpts } from '@/permissions';
import * as models from '@/models';
import { RootState } from '@/store/state';
import { INITIAL_COURSES_AMOUNT } from '@/constants';

import { DefaultMap } from '@/utils/defaultdict';
import { AssignmentsStore } from './assignments';

const storeBuilder = getStoreBuilder<RootState>();

interface SimpleLoaders {
    firstCourses: Promise<unknown> | null;
    allCourses: Promise<unknown> | null;
    permissions: Promise<unknown> | null;
}

interface Loaders extends SimpleLoaders {
    singleCourse: Record<number, Promise<unknown>>;
}

export interface CoursesState {
    courses: { [courseId: number]: models.Course };
    permissions: { [courseId: number]: CPermMap };
    loaders: Loaders;
    gotAllCourses: boolean;
}

type CPermMap = Record<CPermOpts, boolean>;

const makeInitialState = () => ({
    courses: {},
    permissions: {},
    loaders: {
        singleCourse: {},
        firstCourses: null,
        allCourses: null,
        permissions: null,
    },
    gotAllCourses: false,
});

const moduleBuilder = storeBuilder.module<CoursesState>('courses', makeInitialState());

const MAX_COURSES_TO_LOAD = 2500;

export namespace CoursesStore {
    // eslint-disable-next-line
    function _getCourse(state: CoursesState) {
        return (courseId: number): utils.Maybe<models.Course> =>
            utils.Maybe.fromNullable(state.courses?.[courseId]);
    }

    export const getCourse = moduleBuilder.read(_getCourse, 'getCourse');

    export const allCourses = moduleBuilder.read(
        state => Object.values(state.courses),
        'allCourses',
    );

    export const sortedCourses = moduleBuilder.read(state => {
        const getVisibleNumber = (course: models.Course) => {
            switch (course.state) {
                case models.CourseState.visible:
                    return 0;
                case models.CourseState.archived:
                    return 1;
                case models.CourseState.deleted:
                    return 2;
                default:
                    return utils.AssertionError.assertNever(course.state);
            }
        };

        return utils.sortBy(
            Object.values(state.courses),
            course => [getVisibleNumber(course), course.createdAt, course.name],
            { reversePerKey: [false, true, false] },
        );
    }, 'sortedCourses');

    type CourseCounts = Readonly<{
        total: readonly number[];
        byYear: DefaultMap<number, readonly number[]>;
    }>;

    // eslint-disable-next-line
    function _getCourseCounts(_: CoursesState): (course: models.Course) => CourseCounts {
        // eslint-disable-next-line
        const lookup = new DefaultMap((name: string) => {
            // eslint-disable-next-line
            const byYear: DefaultMap<number, number[]> = new DefaultMap((year: number) => []);
            return {
                total: [] as number[],
                byYear,
            };
        });

        sortedCourses().forEach(course => {
            const value = lookup.get(course.name);
            value.total.push(course.id);
            value.byYear.get(course.createdAt.year()).push(course.id);
        });

        return function getCourseCounts(course: models.Course) {
            return lookup.get(course.name);
        };
    }

    export const getCourseCounts = moduleBuilder.read(_getCourseCounts, 'getCourseCounts');

    export const retrievedAllCourses = moduleBuilder.read(
        state => state.gotAllCourses,
        'retrievedAllCourses',
    );

    const commitCourse = moduleBuilder.commit((state, payload: { course: models.Course }) => {
        const { course } = payload;
        utils.vueSet(state.courses, course.id, course);
    }, 'commitCourse');

    const commitCourses = moduleBuilder.commit(
        (state, payload: { courses: ReadonlyArray<models.Course> }) => {
            const { courses } = payload;
            state.courses = Object.assign(
                {},
                state.courses,
                courses.reduce((acc: Record<number, models.Course>, course) => {
                    acc[course.id] = course;
                    return acc;
                }, {}),
            );
        },
        'commitCourses',
    );

    // This is only exported to be used in tests, don't call this commit from
    // your own code.
    export const commitPermissions = moduleBuilder.commit(
        (state, payload: { permissions: Record<number, CPermMap> }) => {
            state.permissions = Object.assign({}, state.permissions, payload.permissions);
        },
        'commitPermissions',
    );

    export const commitClearAll = moduleBuilder.commit(state => {
        Object.assign(state, makeInitialState());
    }, 'commitClearAll');

    const removeSingleCourseLoader = moduleBuilder.commit(
        (state, payload: { courseId: number }) => {
            const { courseId } = payload;
            utils.vueDelete(state.loaders.singleCourse, courseId);
        },
        'removeSingleCourseLoader',
    );

    const commitSingleCourseLoader = moduleBuilder.commit(
        (state, payload: { courseId: number; value: Promise<unknown> }) => {
            const { courseId, value } = payload;
            const removeAfter = () => removeSingleCourseLoader({ courseId });
            value.then(removeAfter, removeAfter);
            utils.vueSet(state.loaders.singleCourse, courseId, value);
        },
        'commitSingleCourseLoader',
    );

    const removeLoader = moduleBuilder.commit(
        (state: CoursesState, payload: { key: keyof SimpleLoaders }) => {
            delete state.loaders[payload.key];
        },
        'removeLoader',
    );

    const commitLoader = moduleBuilder.commit(
        (state, payload: { key: keyof SimpleLoaders; value: Promise<unknown> }) => {
            const { key, value } = payload;
            value.catch(() => {
                removeLoader({ key });
            });
            state.loaders[key] = value;
        },
        'commitLoader',
    );

    const commitGotAllCourses = moduleBuilder.commit((state, payload: { value: boolean }) => {
        state.gotAllCourses = payload.value;
    }, 'commitGotAllCourses');

    export const loadPermissions = moduleBuilder.dispatch(
        ({ state }, payload: { force?: boolean } = {}) => {
            const { force = false } = payload;
            if (state.loaders.permissions == null || force) {
                commitLoader({
                    key: 'permissions',
                    value: axios.get('/api/v1/permissions/?type=course').then(({ data }) => {
                        commitPermissions({ permissions: data });
                    }),
                });
            }
            return state.loaders.permissions;
        },
        'loadPermissions',
    );

    // eslint-disable-next-line
    function _getPermissionsForCourse(state: CoursesState) {
        return (courseId: number): CPermMap => state.permissions[courseId] || {};
    }

    export const getPermissionsForCourse = moduleBuilder.read(
        _getPermissionsForCourse,
        'getPermissionsForCourse',
    );

    export const commitPermission = moduleBuilder.commit(
        (state, payload: { courseId: number; perm: CPermOpts; value: boolean }) => {
            const { courseId, perm, value } = payload;
            const perms = state.permissions[courseId];
            if (perms == null) {
                throw new Error(
                    `Cannot update permission for course ${courseId}, no permissions were found. Available courses: ${Object.keys(
                        state.permissions,
                    ).join(', ')}`,
                );
            }
            utils.vueSet(perms, perm, value);
            utils.vueSet(state.permissions, courseId, perms);
        },
        'commitPermission',
    );

    export const addCourses = moduleBuilder.dispatch(
        ({ state }, payload: { courses: ReadonlyArray<models.CourseExtendedServerData> }) => {
            const { courses } = payload;
            const allAssignments = courses.reduce(
                (acc: Record<number, models.Assignment>, course) => {
                    course.assignments.forEach(assignment => {
                        acc[assignment.id] = models.Assignment.fromServerData(assignment);
                    });
                    return acc;
                },
                {},
            );
            const courseGetter = _getCourse(state);
            courses.forEach(course => {
                courseGetter(course.id).ifJust(oldCourse => {
                    oldCourse.assignmentIds.forEach(assignmentId => {
                        if (!utils.hasAttr(allAssignments, assignmentId)) {
                            AssignmentsStore.commitRemoveAssignment({ assignmentId });
                        }
                    });
                });
            });

            AssignmentsStore.commitAssignments({ assignmentsById: allAssignments });

            commitCourses({ courses: courses.map(course => models.Course.fromServerData(course)) });
        },
        'addCourses',
    );

    export const addCourse = moduleBuilder.dispatch(
        (_, payload: { course: models.CourseExtendedServerData }) => {
            addCourses({ courses: [payload.course] });
        },
        'addCourse',
    );

    export const loadSingleCourse = moduleBuilder.dispatch(
        async ({ state }, payload: { courseId: number; force?: boolean }) => {
            const { courseId, force = false } = payload;
            await Promise.all([
                loadPermissions({ force }),
                state.loaders.firstCourses,
                state.loaders.allCourses,
            ]);
            const hasCourse = _getCourse(state)(courseId).isJust();
            const isLoading = state.loaders.singleCourse[courseId] != null;
            if (force || (!hasCourse && !isLoading)) {
                commitSingleCourseLoader({
                    courseId,
                    value: api.courses.getById(courseId).then(course => addCourse({ course })),
                });
            }
            await state.loaders.singleCourse[courseId];
        },
        'loadSingleCourse',
    );

    export const loadFirstCourses = moduleBuilder.dispatch(
        async ({ state }, payload?: { force?: boolean }) => {
            const { force = false } = payload ?? {};
            await loadPermissions({ force });

            const didLoad = state.loaders.firstCourses != null;
            const didLoadAll = state.loaders.allCourses != null;

            if ((!didLoad && !didLoadAll) || force) {
                if (force) {
                    await state.loaders.firstCourses;
                }
                commitLoader({
                    key: 'firstCourses',
                    value: api.courses
                        .get({
                            limit: INITIAL_COURSES_AMOUNT,
                            offset: 0,
                        })
                        .then(data => {
                            addCourses({ courses: data });

                            // If we got less than our limit there are no more
                            // courses.
                            commitGotAllCourses({
                                value: state.gotAllCourses || data.length < INITIAL_COURSES_AMOUNT,
                            });
                        }),
                });
            } else if (didLoadAll) {
                return state.loaders.allCourses;
            }
            return state.loaders.firstCourses;
        },
        'loadFirstCourses',
    );

    export const loadAllCourses = moduleBuilder.dispatch(
        async ({ state }, payload?: { force?: boolean }) => {
            const { force = false } = payload ?? {};
            await loadPermissions({ force });
            if (state.loaders.allCourses == null || force) {
                commitLoader({
                    key: 'allCourses',
                    value: api.courses
                        .get({
                            limit: MAX_COURSES_TO_LOAD,
                            offset: 0,
                        })
                        .then(data => {
                            addCourses({ courses: data });
                            commitGotAllCourses({ value: true });
                        }),
                });
            }
            return state.loaders.allCourses;
        },
        'loadAllCourses',
    );

    export const reloadCourses = moduleBuilder.dispatch((_, payload: { fullReload: boolean }) => {
        const { fullReload } = payload;
        commitClearAll();
        AssignmentsStore.commitClearAll();
        if (fullReload) {
            return loadAllCourses({ force: false });
        } else {
            return loadFirstCourses({ force: false });
        }
    }, 'reloadCourses');

    export const updateCourse = moduleBuilder.dispatch(
        async (
            { state },
            payload: { courseId: number; courseProps: models.CourseUpdatableProps },
        ) => {
            const { courseId, courseProps } = payload;
            await loadSingleCourse({ courseId });
            _getCourse(state)(courseId).caseOf({
                Just(course) {
                    commitCourse({ course: course.update(courseProps) });
                },
                Nothing() {
                    throw new ReferenceError(`Could not find course ${courseId}`);
                },
            });
        },
        'updateCourse',
    );

    export const createCourse = moduleBuilder.dispatch(async (_, payload: { name: string }) => {
        const response = await api.courses.create(payload);
        await loadPermissions({ force: true });
        addCourse({ course: response.data });
        return response;
    }, 'createCourse');

    export const patchCourse = moduleBuilder.dispatch(
        async (_, payload: { courseId: number; data: api.courses.PatchableProps }) => {
            const response = await api.courses.patch(payload.courseId, payload.data);
            addCourse({ course: response.data });
            return response;
        },
        'patchCourse',
    );
}

export function onDone(store: Store<RootState>) {
    store.watch(
        // @ts-ignore
        (_: RootState, allGetters: Record<string, any>) => allGetters['user/loggedIn'],
        loggedIn => {
            if (!loggedIn) {
                CoursesStore.commitClearAll();
                AssignmentsStore.commitClearAll();
            }
        },
    );
}
