/* SPDX-License-Identifier: AGPL-3.0-only */
import Submission from '@/pages/Submission';
import * as assignmentState from '@/store/assignment-states';
import { FileTree, Feedback } from '@/models/submission';

import { shallowMount, createLocalVue } from '@vue/test-utils';
import VueRouter from 'vue-router';
import Vuex from 'vuex';
import BootstrapVue from 'bootstrap-vue';

jest.mock('axios');

const localVue = createLocalVue();

localVue.use(Vuex);
localVue.use(BootstrapVue);

const router = new VueRouter();

function jsonCopy(src) {
    return JSON.parse(JSON.stringify(src));
}

describe('Submission.vue', () => {
    let store;
    let courses;
    let submissions;
    let mockLoadSubs;
    let mockLoadTree;
    let mockLoadFeedback;
    let wrapper;
    let comp;
    let tree1;
    let tree2;
    let tree3;
    let tree4;
    let $route;
    let $router;
    let mockGet;
    let rubric = {};
    let feedback = {
        general: {},
        authors: {},
        user: {},
        linter: {},
    };

    beforeEach(() => {
        tree1 = {
            name: 'root1',
            id: 1,
            entries: [
                {
                    name: 'file1',
                    id: 2,
                },
                {
                    name: 'sub1',
                    id: 3,
                    entries: [{ name: 'file2', id: 4 }],
                },
            ],
        };

        tree2 = jsonCopy(tree1);
        tree2.entries.splice(0, 1);
        tree2.entries[0].entries[0].id = 5;
        tree2.entries[0].entries.push({ name: 'file3', id: 6 });

        tree3 = jsonCopy(tree1);
        tree3.entries.push({
            name: 'sub2',
            id: 4,
            entries: [{
                name: 'file4',
                id: 7,
            }],
        });

        tree4 = jsonCopy(tree1);
        tree4.entries.splice(1, 1);
        tree4.entries.push({
            name: 'sub1',
            id: 8,
        });

        const user = {id: 1000};
        submissions = [
            { id: 1, user, grade: null, feedback: null, fileTree: null },
            { id: 2, user, grade: null, feedback: null, fileTree: null },
            { id: 3, user, grade: null, feedback: null, fileTree: null },
            { id: 4, user, grade: null, feedback: null, fileTree: null },
        ];
        courses = {
            1: {
                assignments: [{
                    id: 2,
                    submissions,
                }],
                is_lti: false,
            },
        };
        courses[1].assignments.forEach(assig => { assig.course = courses[1]; });

        mockGet = jest.fn(async (path, opts) => new Promise((resolve) => {
            let res;
            if (/^.api.v1.submissions.[0-9]+.files./.test(path)) {
                if (opts && opts.params.owner === 'teacher') {
                    res = jsonCopy(tree2);
                } else {
                    res = jsonCopy(tree1);
                }
            } else if (/^.api.v1.submissions.[0-9]+.rubrics./.test(path)) {
                res = rubric;
            } else if (/^.api.v1.submissions.[0-9]+.feedbacks./.test(path)) {
                res = feedback;
            }
            resolve({ data: res });
        }));

        mockLoadSubs = jest.fn(() => Promise.resolve(true));
        mockLoadTree = jest.fn((context, { submissionId }) => {
            return Promise.all([
                mockGet(`/api/v1/submissions/${submissionId}/files/`),
                mockGet(`/api/v1/submissions/${submissionId}/files/`, {
                    params: { owner: 'teacher' },
                }),
            ]).then(([student, teacher]) => {
                const sub = submissions.find(x => x.id === submissionId);
                sub.fileTree = new FileTree(student.data, teacher.data);
            });
        });
        mockLoadFeedback = jest.fn((context, { submissionId }) =>
            mockGet(`/api/v1/submissions/${submissionId}/feedbacks/`).then(({ data }) => {
                const sub = submissions.find(x => x.id === submissionId);
                sub.feedback = new Feedback(data);
            }),
        );

        store = new Vuex.Store({
            modules: {
                courses: {
                    state: {
                        courses,
                    },
                    getters: {
                        courses: () => courses,
                        assignments: () => ({ 2: courses[1].assignments[0] }),
                    },
                    actions: {
                        loadSubmissions: mockLoadSubs,
                        loadSubmissionFileTree: mockLoadTree,
                        loadSubmissionFeedback: mockLoadFeedback,
                    },
                    namespaced: true,
                },
                user: {
                    getters: {
                        id: () => -1,
                    },
                    namespaced: true,
                },
            },
        });

        $route = {
            query: {
                revision: undefined,
            },
            params: {
                courseId: '1',
                assignmentId: '2',
                submissionId: '3',
                fileId: undefined,
            },
        };
        $router = {
            push: jest.fn(),
            replace: jest.fn(),
        };

        wrapper = shallowMount(Submission, {
            store,
            localVue,
            router,
            mocks: {
                $hasPermission(perms) {
                    if (Array.isArray(perms))
                        return perms.map(() => true)
                    else
                        return true;
                },
                $route,
                $router,
                $http: {
                    get: mockGet,
                },
            },
        });
        comp = wrapper.vm;
    });

    describe('Computed', () => {
        it('ids should be numbers or NaN', () => {
            expect(typeof comp.courseId).toBe('number');
            expect(typeof comp.assignmentId).toBe('number');
            expect(typeof comp.submissionId).toBe('number');
            expect(comp.courseId).toBe(1);
            expect(comp.assignmentId).toBe(2);
            expect(comp.submissionId).toBe(3);

            $route.params.assignmentId = 'hello';
            $route.params.courseId = 'hello';
            $route.params.submissionId = 'hello';

            expect(comp.courseId).toBeNaN();
            expect(comp.assignmentId).toBeNaN();
            expect(comp.submissionId).toBeNaN();
        });

        it('objects should be retrieved from the store or default', () => {
            expect(comp.assignment).toBe(courses[1].assignments[0]);
            expect(comp.assignment.id).toBe(2);

            expect(comp.submissions).toBe(submissions);
            expect(comp.submission).toBe(submissions[2]);
            expect(comp.submission.id).toBe(3);

            $route.params.assignmentId = 'hello';
            $route.params.courseId = 'hello';
            $route.params.submissionId = 'hello';

            expect(comp.assignment).toBeNull();
            expect(comp.submissions).toHaveLength(0);
            expect(comp.submission).toBeNull();
        });

        describe('prefFileId', () => {
            it('should equal fileId if the selected category is "Code"', () => {
                comp.selectedCat = 'code';
                expect(comp.prefFileId).toBeNull();

                $route.params.fileId = 4;
                expect(comp.prefFileId).toBe(comp.fileId);
            });

            it('should be a number if the selected category is "Feedback Overview"', () => {
                comp.selectedCat = 'feedback-overview';
                expect(comp.prefFileId).toMatch(/^\d+-feedback-overview$/);
            });

            it('should be a number if the selected category is "AutoTest"', () => {
                comp.selectedCat = 'auto-test';
                expect(comp.prefFileId).toMatch(/^\d+-auto-test$/);
            });

            it('should be a number if the selected category is "Teacher Diff"', () => {
                comp.selectedCat = 'teacher-diff';
                expect(comp.prefFileId).toMatch(/^\d+-teacher-diff$/);
            });
        });

        describe('revision', () => {
            it('should default to "student"', () => {
                delete $route.query.revision;
                expect(comp.revision).toBe('student');
            });

            it.each(['student', 'teacher', 'diff'])('should take the value from the route', (rev) => {
                $route.query.revision = rev;
                expect(comp.revision).toBe(rev);
            });
        });

        describe('defaultCat', () => {
            it('should be "Feedback Overview" when a submission is graded and the user can view the feedback', () => {
                comp.canSeeFeedback = true;

                for (let i = 0; i <= 10; i++) {
                    comp.submission.grade = i;
                    expect(comp.defaultCat).toBe('feedback-overview');
                }
            });

            it('should be "Code" when a submission is not graded or the user cannot view the feedback', () => {
                comp.canSeeFeedback = false;
                comp.submission.grade = null;

                expect(comp.defaultCat).toBe('code');

                for (let i = 0; i <= 10; i++) {
                    comp.submission.grade = i;
                    expect(comp.defaultCat).toBe('code');
                }

                comp.canSeeFeedback = true;
                comp.submission.grade = null;

                expect(comp.defaultCat).toBe('code');
            });
        });
    });

    describe('Watchers', () => {
        it('should reload submissions when assignmentId changes', () => {
            expect(mockLoadSubs).toBeCalledTimes(1);
            $route.params.assignmentId = '100';
            expect(mockLoadSubs).toBeCalledTimes(2);
        });

        it('should reload submission data when submissionId changes', async () => {
            expect(mockLoadTree).toBeCalledTimes(1);
            expect(mockLoadFeedback).toBeCalledTimes(1);

            $route.params.submissionId = '4';
            await comp.$nextTick();

            expect(mockLoadTree).toBeCalledTimes(2);
            expect(mockLoadFeedback).toBeCalledTimes(2);
        });
    });
});
