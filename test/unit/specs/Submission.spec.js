/* SPDX-License-Identifier: AGPL-3.0-only */
import Submission from '@/pages/Submission';
import * as mutationTypes from '@/store/mutation-types';
import * as assignmentState from '@/store/assignment-states';
import { FileTree, Feedback } from '@/models/submission';
import axios from 'axios';

import { store } from '@/store';
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
    let courses;
    let submissions;
    let autoTests;
    let subsLoadedAmount;
    let mockLoadSub;
    let treeLoadedAmount;
    let feedbackLoadedAmount;
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
    let feedback;

    async function wait(amount = 10) {
        await comp.$afterRerender();
        for (let i = 0; i < amount; ++i) {
            await comp.$nextTick();
        }
        await comp.$afterRerender();
    }

    function setFeedback(newFeedback) {
        feedback = newFeedback;
        store.dispatch('feedback/loadFeedback', {
            assignmentId: comp.assignmentId,
            submissionId: comp.submissionId,
            force: true,
        });
    }

    beforeEach(async () => {
        feedback = {
            general: {},
            authors: [],
            user: [],
            linter: {},
        };
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

        submissions = [
            { id: 1, user: { id: 101 }, grade: null, feedback: null, fileTree: null },
            { id: 2, user: { id: 102 }, grade: null, feedback: null, fileTree: null },
            { id: 3, user: { id: 103 }, grade: null, feedback: null, fileTree: null },
            { id: 4, user: { id: 104 }, grade: null, feedback: null, fileTree: null },
            { id: 5, user: { id: 105 }, grade: null, feedback: null, fileTree: null },
        ];
        courses = [{
            id: 1,
            assignments: [{
                id: 2,
                state: 'open',
                auto_test_id: null,
                course_id: 1,
            }, {
                id: 100,
                state: 'done',
                auto_test_id: null,
                course_id: 1,
            }],
            is_lti: false,
        }];

        autoTests = {
            1: {
                id: 1,
                runs: [
                    { isContinuous: true },
                ],
            },
        };

        mockGet = jest.fn(async (path, opts) => new Promise((resolve, reject) => {
            let res;
            if (/^.api.v1.submissions.[0-9]+.files./.test(path)) {
                if (opts && opts.params.owner === 'teacher') {
                    treeLoadedAmount.teacher++;
                    res = jsonCopy(tree2);
                } else {
                    treeLoadedAmount.student++;
                    res = jsonCopy(tree1);
                }
            } else if (/^.api.v1.submissions.[0-9]+.root_file_trees/.test(path)) {
                treeLoadedAmount.student++;
                treeLoadedAmount.teacher++;
                res = { student: tree1, teacher: tree2 };
            } else if (/^.api.v1.submissions.[0-9]+.rubrics./.test(path)) {
                res = rubric;
            } else if (/^.api.v1.submissions.[0-9]+.feedbacks./.test(path)) {
                feedbackLoadedAmount++;
                res = feedback;
            } else if (/^.api.v1.assignments.([0-9]+|NaN).submissions./.test(path)) {
                subsLoadedAmount++;
                if (/assignments.2/.test(path)) {
                    res = submissions.map(s => Object.assign({}, s)).slice(0, -1);
                } else {
                    res = submissions.map(s => Object.assign({}, s)).slice(-1);
                }
            } else if (/^.api.v1.assignments.([0-9]+|NaN).graders./.test(path)) {
                res = [];
            } else if (/^.api.v1.courses.1(\?.*)?/.test(path)) {
                res = courses[0];
            } else if (/^.api.v1.courses./.test(path)) {
                res = courses;
            } else if (/^.api.v1.permissions.*type=course/.test(path)) {
                res = {
                    1: { can_see_grade_before_done: true },
                };
            } else if (/^.api.v1.auto_tests.1/.test(path)) {
                res = {
                    sets: [],
                    runs: [{
                        results: submissions.map(sub => ({
                            id: sub.id,
                            work_id: sub.id,
                        })),
                    }],
                    id: 1,
                };
            } else if (/^.api.v1.submissions.[0-9]+$/.test(path)) {
                const parts = path.split('/')
                const id = Number(parts[parts.length - 1]);
                res = Object.assign({}, submissions.find(s => s.id === id));
            } else if (/^.api.v1.assignments.*rubrics\/$/.test(path)) {
                res = [];
            } else {
                return reject({ status: 403 });
            }
            resolve({ data: res });
        }));

        axios.get = mockGet;
        subsLoadedAmount = 0;
        feedbackLoadedAmount = 0;
        treeLoadedAmount = { student: 0, teacher: 0 };

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

        await wait();
    });

    afterEach(() => {
        wrapper.destroy();
        store.dispatch('user/logout');
    });

    describe('Computed', () => {
        it('ids should be numbers', async () => {
            expect(comp.courseId).toBeNumber();
            expect(comp.assignmentId).toBeNumber();
            expect(comp.submissionId).toBeNumber();
            expect(comp.courseId).toBe(1);
            expect(comp.assignmentId).toBe(2);
            expect(comp.submissionId).toBe(3);
        });

        it('objects should be retrieved from the store or default', async () => {
            await wait();

            expect(comp.assignment.id).toBe(courses[0].assignments[0].id);
            expect(comp.assignment.id).toBe(2);

            await wait();
            expect(comp.latestSubmissions.map(
                x => x.id,
            )).toEqual(submissions.slice(0, -1).map(x => x.id));

            expect(comp.submission.id).toBe(submissions[2].id);
            expect(comp.submission.id).toBe(3);
        });

        describe('prefFileId', () => {
            it('should equal fileId if the selected category is "Code"', () => {
                comp.selectedCat = 'code';
                expect(comp.prefFileId).toBeUndefined();

                $route.params.fileId = '4';
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

        describe('getDefaultCat', () => {
            it.each([
                [false, false, false, null, 'code'],
                [false, false, false, {},   'auto-test'],
                [false, false, true,  null, 'code'],
                [false, false, true,  {},   'code'],
                [false, true,  false, null, 'code'],
                [false, true,  false, {},   'auto-test'],
                [false, true,  true,  null, 'code'],
                [false, true,  true,  {},   'code'],
                [true,  false, false, null, 'feedback-overview'],
                [true,  false, false, {},   'auto-test'],
                [true,  false, true,  null, 'feedback-overview'],
                [true,  false, true,  {},   'auto-test'],
                [true,  true,  false, null, 'feedback-overview'],
                [true,  true,  false, {},   'feedback-overview'],
                [true,  true,  true,  null, 'feedback-overview'],
                [true,  true,  true,  {},   'feedback-overview'],
            ])('should behave correctly', (
                assignmentDone,
                hasFeedback,
                feedbackEditable,
                autoTestRun,
                expected = 'code',
            ) => {
                expect(comp.getDefaultCat(
                    feedbackEditable,
                    assignmentDone,
                    hasFeedback,
                    autoTestRun,
                )).toBe(expected);
            });
        });
    });

    describe('Watchers', () => {
        it('should reload submissions when assignmentId changes', async () => {
            await wait();
            expect(subsLoadedAmount).toBe(1);

            $route.params = Object.assign({}, $router.params, {
                submissionId: 5,
                assignmentId: 100,
            });
            await wait();
            expect(comp.assignmentId).toBe(100);
            expect(subsLoadedAmount).toBe(2);
        });

        it('should reload submission data when submissionId changes', async () => {
            expect(treeLoadedAmount).toEqual({ student: 1, teacher: 1 });
            expect(feedbackLoadedAmount).toBe(1);

            treeLoadedAmount = { teacher: 0, student: 0 };
            feedbackLoadedAmount = 0;
            comp.$set(comp.$route.params, 'submissionId', '4');
            await wait();

            expect(treeLoadedAmount).toEqual({ student: 1, teacher: 1 });
            expect(feedbackLoadedAmount).toBe(1);
        });
    });
});
