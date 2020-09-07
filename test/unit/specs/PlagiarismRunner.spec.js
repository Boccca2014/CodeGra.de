/* SPDX-License-Identifier: AGPL-3.0-only */
import PlagiarismRunner from '@/components/PlagiarismRunner';
import BootstrapVue from 'bootstrap-vue';
import { shallowMount, createLocalVue } from '@vue/test-utils';
import VueRouter from 'vue-router';
import Vuex from 'vuex';

import * as utils from '@/utils';

jest.mock('axios');

const localVue = createLocalVue();
localVue.use(VueRouter);
const router = new VueRouter();

localVue.use(Vuex);

localVue.use(BootstrapVue);

describe('PlagiarismRunner.vue', () => {
    let store;
    let wrapper;
    let comp;
    let mockPost;
    let mockGet;
    let runs;
    let providers;
    let remount;
    let mockLoadCourses;
    let mockLoadSingleAssignment;

    beforeEach(() => {
        jest.useFakeTimers();
        runs = [
            { state: 'done', provider_name: 'testProvider' },
            { state: 'running', provider_name: 'testProvider2' },
            { state: 'crashed', provider_name: 'testProvider' },
        ];
        providers = [
            {
                name: 'testProvider',
                options: [
                    { name: 'a', title: 'b' },
                ],
                base_code: true,
                progress: false,
            },
            {
                name: 'testProvider2',
                options: [
                    { name: 'a', title: 'c' },
                ],
                base_code: true,
                progress: false,
            },
        ];

        mockPost = jest.fn(() => Promise.resolve({ data: { state: 'running', provider_name: 'testProvider' } }));
        mockGet = jest.fn((route) => {
            let res = null;
            if (/^.api.v1.assignments.[0-9]+.plagiarism\/(\?.*)?$/.test(route)) {
                res = { data: runs };
            }
            if (/^.api.v1.plagiarism\/(\?(.*))?$/.test(route)) {
                res = { data: providers };
            }
            if (/^.api.v1.permissions..type.course.*$/.test(route)) {
                res = {
                    data: {}
                }
            };
            return Promise.resolve(res);
        });

        mockLoadCourses = jest.fn();
        mockLoadSingleAssignment = jest.fn();
        store = new Vuex.Store({
            modules: {
                courses: {
                    namespaced: true,
                    getters: {
                        allCourses: () => [],
                        getCourse: state => () => utils.Nothing,
                    },
                    actions: {
                        loadAllCourses: mockLoadCourses,
                        loadSingleCourse: mockLoadCourses,
                    },
                },
                assignments: {
                    namespaced: true,
                    getters: {
                        allAssignments: () => [],
                        getAssignment: state => () => utils.Nothing,
                    },
                    actions: {
                        loadSingleAssignment: mockLoadSingleAssignment,
                    },
                }
            },
        });

        remount = () => {
            wrapper = shallowMount(PlagiarismRunner, {
                store,
                localVue,
                router,
                methods: {
                    $hasPermission() { return true; },
                },
                mocks: {
                    $http: { post: mockPost, get: mockGet },
                },
                propsData: {
                    canManage: true,
                    assignment: { id: 0 },
                    canView: true,
                },
            });
            comp = wrapper.vm;
        }
        remount();
    });

    describe('canGoToOverview', () => {
        it('should be a function', () => {
            expect(comp).not.toBe(null);
            expect(typeof comp.canGoToOverview).toBe('function');
        });

        it('should work', () => {
            expect(comp.canGoToOverview(runs[0])).toBe(true);
            expect(comp.canGoToOverview(runs[1])).toBe(false);
            expect(comp.canGoToOverview(runs[2])).toBe(true);
        });
    });

    describe('setOption', () => {
        it('should copy old selectedOptions', () => {
            const old = comp.selectedOptions;
            comp.setOption({ name: 'a' }, 'b');
            expect(comp.selectedOptions).not.toBe(old);
        });

        it('should work', () => {
            const old = comp.selectedOptions;
            comp.setOption({ name: 'a' }, 'b');
            expect(comp.selectedOptions).toEqual({
                a: 'b',
                ...old,
            });
        });
    });

    describe('translateOption', () => {
        it('should be a function', () => {
            expect(comp).not.toBe(null);
            expect(typeof comp.translateOption).toBe('function');
        });

        it('should work for special cases', () => {
            expect(comp).not.toBe(null);
            [
                'provider',
                'has_old_submissions',
                'has_base_code',
                'old_assignments',
            ].forEach((opt) => {
                expect(comp.translateOption(
                    opt,
                    runs[0],
                )).toBe(comp.translateOptionSpecialCases[opt]);
            });
        });

        it('should work for normal options', () => {
            expect(comp.translateOption('a', runs[0])).toBe('b');
            expect(comp.translateOption('a', runs[1])).toBe('c');
        });

        it('should work when provider is not found', () => {
            expect(comp.translateOption('unkown', { })).toBe('unkown');
        });
    });

    describe('runPlagiarismChecker', () => {
        it('should be a function', () => {
            expect(comp).not.toBe(null);
            expect(typeof comp.runPlagiarismChecker).toBe('function');
        });

        it('should work in the most simple case', async () => {
            comp.selectedProvider = comp.providers[0];
            comp.selectedOptions = { hello: 'goodbye' };
            await comp.runPlagiarismChecker().then(comp.afterRunPlagiarismChecker);

            expect(mockPost).toBeCalledTimes(1);
            expect(mockPost).toBeCalledWith('/api/v1/assignments/0/plagiarism?no_course_in_assignment=true', {
                hello: 'goodbye',
                old_assignments: [],
                has_base_code: false,
                has_old_submissions: false,
            });

            expect(comp.runs[comp.runs.length - 1]).toEqual(
                await mockPost.mock.results[0].value.then(a => a.data),
            );
        });

        it('should work in with base code and old submissions', async () => {
            const base = 'BASE__BASE__';
            const oldSubs = '__OLDSUB__OLDSUB__';

            comp.selectedProvider = comp.providers[0];
            comp.selectedOptions = { hello: 'goodbye', 'base_code': base, 'old_submissions': oldSubs };

            await comp.runPlagiarismChecker().then(comp.afterRunPlagiarismChecker);
            expect(mockPost).toBeCalledTimes(1);
            expect(mockPost).toBeCalledWith('/api/v1/assignments/0/plagiarism?no_course_in_assignment=true', expect.any(FormData));
            const form = mockPost.mock.calls[0][1];

            expect(form.has('json')).toBe(true);
            const reader = new FileReader();
            reader.readAsText(form.get('json'));
            await new Promise((resolve) => {
                reader.onload = resolve;
            });
            expect(JSON.parse(reader.result)).toEqual({
                hello: 'goodbye',
                old_assignments: [],
                has_base_code: true,
                has_old_submissions: true,
            });

            expect(form.has('old_submissions')).toBe(true);
            expect(form.get('old_submissions')).toBe(oldSubs);

            expect(form.has('base_code')).toBe(true);
            expect(form.get('base_code')).toBe(base);

            expect(comp.runs[comp.runs.length - 1]).toEqual(
                await mockPost.mock.results[0].value.then(a => a.data),
            );
        });
    });

    describe('load providers', () => {
        it('should work with multiple providers', async () => {
            await comp.$nextTick();
            expect(comp.selectedProvider).toEqual(null);
            expect(comp.providers).toEqual(providers);
            expect(wrapper.findAll('.provider-selectors').exists()).toBe(true);
        });

        it('should work with a single provider', async () => {
            providers = [providers[0]];
            remount();
            await comp.$nextTick();
            expect(comp.selectedProvider).toEqual(providers[0]);
            expect(comp.providers).toEqual(providers);
            expect(wrapper.findAll('.provider-selectors').exists()).toBe(false);
        });
    });
});
