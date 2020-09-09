// We first need to import the main store, to prevent undefined errors.
import { store } from '@/store';
import { actions, updatePermissions } from '@/store/modules/courses';

import * as types from '@/store/mutation-types';
import * as utils from '@/utils/typed';
import Vuex from 'vuex';
import Vue from 'vue';
import { Assignment } from '@/models/assignment';
import axios from 'axios';

import { CoursesStore, AssignmentsStore } from '@/store'

const mockAxiosGet = jest.fn(async (path, opts) => new Promise((resolve, reject) => {
    if (path === '/api/v1/permissions/?type=course') {
        return resolve({ data: {} });
    }
    reject(`Axios should not be used, tried to access: ${path}`);
}));
axios.get = mockAxiosGet;

function makeAssig(data, course, canManage) {
    return Assignment.fromServerData(data, course.id, canManage);
}

const initialCourses = [
    {
        assignments: [{
            id: 2,
            name: '2',
            course_id: 1,
        }, {
            id: 3,
            name: '3',
            course_id: 1,
        }],
        name: 'hello',
        id: 1,
        state: 'visible',
    }, {
        assignments: [{
            id: 5,
            name: '5',
            course_id: 4,
        }],
        name: 'bye',
        id: 4,
        state: 'visible',
    },
];

function setInitialState() {
    return CoursesStore.addCourses({
            courses: initialCourses,
    });
};

describe('getters', () => {
    let state;

    beforeEach(() => setInitialState());

    describe('sortedCourses', () => {
        it('should return sorted courses', () => {
            expect(CoursesStore.sortedCourses()).toHaveLength(2);
            expect(CoursesStore.sortedCourses()).toMatchObject([{
                id: 1,
                name: 'hello',
                assignments: [
                    { id: 2 },
                    { id: 3 },
                ],
            }, {
                id: 4,
                assignments: [{ id: 5 }],
            }]);
        });
    });

    describe('assignments', () => {
        it('should work without courses', async () => {
            await CoursesStore.commitClearAll();
            await AssignmentsStore.commitClearAll();
            expect(CoursesStore.sortedCourses()).toEqual([]);
            expect(AssignmentsStore.allAssignments()).toEqual([]);
        });

        it('should work with courses', () => {
            const assigs = AssignmentsStore.allAssignments();
            expect(assigs).toHaveLength(3);
            expect(assigs).toMatchObject([
                {
                    id: 2,
                    name: '2',
                    courseId: 1,
                    course: { id: 1 },
                },
                {
                    id: 3,
                    name: '3',
                    courseId: 1,
                    course: { id: 1 },
                },
                {
                    id: 5,
                    name: '5',
                    courseId: 4,
                    course: { id: 4 },
                },
            ]);
            expect(Object.values(assigs).every(x => x instanceof Assignment)).toBe(true);
        });
    });
});

describe('mutations', () => {
    beforeEach(() => {
        setInitialState();
    })

    describe('clear courses', () => {
        it('should clear all the things', () => {
            CoursesStore.commitClearAll();
            expect(CoursesStore.sortedCourses()).toEqual([]);
        });
    });

    describe('update course', () => {
        function getCourse(courseId) {
            return CoursesStore.getCourse()(courseId);
        }

        it('should not work for id', async () => {
            CoursesStore.updateCourse({
                courseId: 1,
                courseProps: { id: 5 }
            });
            expect(getCourse(5)).toBeNothing();
            expect(getCourse(1).extract().id).toBe(1);
        });

        it('should not work for new props', async () => {
            await CoursesStore.updateCourse({
                courseId: 1,
                courseProps: { newProp: 5 }
            });
            expect(getCourse(1).extract().newProp).toBeUndefined();
            expect(utils.hasAttr(getCourse(1).extract(), 'newProp')).toBeFalse();
        });

        it('should work for known props', async () => {
            await CoursesStore.updateCourse({
                courseId: 1,
                courseProps: { name: 5 },
            });
            expect(getCourse(1).extract().name).toBe(5);
            expect(getCourse(4).extract().name).toBe('bye');
        });
    });


    describe('update assignment', () => {
        function getAssig(assigId) {
            return AssignmentsStore.getAssignment()(assigId);
        }

        it('should not work for id', () => {
            expect(
                () => AssignmentsStore.updateAssignment({
                    assignmentId: 2,
                    assignmentProps: { id: 5 },
                }),
            ).toThrow();
        });

        it('should not work for new props', () => {
            expect(
                () => AssignmentsStore.updateAssignment({
                    assignmentId: 2,
                    assignmentProps: { newProp: 5 },
                }),
            ).toThrow();

            expect(
                () => AssignmentsStore.updateAssignment({
                    assignmentId: 2,
                    assignmentProps: { submission: 5 },
                }),
            ).toThrow();
        });

        it('should work for some unknown props', () => {
            ['auto_test_id'].forEach((key) => {
                const obj1 = {};

                AssignmentsStore.updateAssignment({
                    assignmentId: 2,
                    assignmentProps: { [key]: obj1 },
                });

                expect(getAssig(2).extract()[key]).toBe(obj1);
                expect(getAssig(3).extract()[key]).not.toBe(obj1);
            });
        });
    });
});
