import SubmissionList from '@/components/SubmissionList';
import { Submission } from '@/models/submission';
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

describe('SubmissionList.vue', () => {
    let users;
    let courses;
    let assignment;
    let submissions;
    let wrapper;
    let comp;
    let $route;
    let $router;
    let mockGet;

    async function wait(amount = 10) {
        await comp.$afterRerender();
        for (let i = 0; i < amount; ++i) {
            await comp.$nextTick();
        }
        await comp.$afterRerender();
    }

    beforeEach(async () => {
        users = [
            { id: 1, username: 'student1', name: 'Student1' },
            { id: 2, username: 'student2', name: 'Student2' },
        ];
        submissions = [
            { id: 1, grade: null, user: users[0] },
            { id: 2, grade: null, user: users[1] },
        ];
        courses = [{
            id: 1,
            assignments: [{ id: 1, state: 'open' }],
        }];

        mockGet = jest.fn(async (path, opts) => new Promise((resolve, reject) => {
            let res;
            if (/^.api.v1.assignments.([0-9]+|NaN).submissions./.test(path)) {
                res = submissions.map(s => Object.assign({}, s));
            } else if (/^.api.v1.assignments.rubrics./.test(path)) {
                return reject({ status: 404 });
            } else if (/^.api.v1.courses./.test(path)) {
                res = courses;
            } else if (/^.api.v1.permissions.*type=course/.test(path)) {
                res = {};
            } else if (/^.api.v1.assignments.([0-9]+|NaN).graders./.test(path)) {
                res = [];
            } else {
                return reject({ status: 403 });
            }
            resolve({ data: res });
        }));

        axios.get = mockGet;

        $route = {
            name: 'assignment_submissions',
            params: {
                courseId: 1,
                assignmentId: 1,
            },
            query: {
                q: '',
                mine: false,
            },
        };
        $router = {
            push: jest.fn(),
            replace: jest.fn(),
        };

        await store.dispatch('courses/loadCourses');
        assignment = store.getters['courses/assignments'][$route.params.assignmentId];

        await store.dispatch('submissions/loadSubmissions', { assignmentId: $route.params.assignmentId });

        wrapper = shallowMount(SubmissionList, {
            store,
            localVue,
            router,
            mocks: {
                $route,
                $router,
                $http: axios,
            },
            propsData: {
                assignment,
                canSeeAssignee: true,
            },
        });

        comp = wrapper.vm;
        await wait();
    });

    afterEach(() => {
        wrapper.destroy();
    });

    it('should display the correct number even if some students have the same name', async () => {
        expect(comp.submissions.map(s => s.user.name).sort()).toEqual(['Student1', 'Student2']);
        expect(comp.numStudents).toBe(2);
        expect(comp.numFilteredStudents).toBe(2);

        await store.dispatch('users/addOrUpdateUser', {
            user: Object.assign({}, users[1], {
                name: users[0].name,
            }),
        });

        expect(comp.submissions.map(s => s.user.name)).toEqual(['Student1', 'Student1']);
        expect(comp.numStudents).toBe(2);
        expect(comp.numFilteredStudents).toBe(2);
    });
});
