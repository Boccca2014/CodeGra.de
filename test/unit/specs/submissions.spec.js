// We first need to import the main store, to prevent undefined errors.
import * as _ from '@/store';
import moment from 'moment';
import store from '@/store/modules/submissions';
import * as types from '@/store/mutation-types';
import * as utils from '@/utils/typed';
import axios from 'axios';
import { User, Submission } from '@/models';

function now(minDays = 0) {
    return moment.utc().add(minDays, 'days').toISOString();
}

function createState() {
    const user = { id: 1000 };
    const submissions = [
        { id: 1, user, assignment_id: 2, created_at: now() },
        { id: 2, user, assignment_id: 2, created_at: now() },
        { id: 3, user, assignment_id: 2, created_at: now() },
        { id: 4, user, assignment_id: 2, created_at: now() },
    ];

    const state = {
        submissions: {},
        latestSubmissions: {},
        submissionsByUser: {},
        submissionsByUserPromises: {},
        submissionsLoaders: {},
        singleSubmissionLoaders: {},
        groupSubmissionUsers: {},
    };

    submissions.forEach(sub => {
        store.mutations[types.ADD_SINGLE_SUBMISSION](state, {
            submission: Submission.fromServerData(sub, 1),
        });
    });

    return state;
};

const mockFormatGrade = jest.fn();
const mockAxiosGet = jest.fn();
axios.get = mockAxiosGet;

utils.formatGrade = mockFormatGrade;

describe('mutations', () => {
    let state;
    beforeEach(() => {
        state = createState();
    })

    describe('set submissions promise', () => {
        it('should set the state prop with correct key', () => {
            const obj1 = {};
            const obj2 = {};

            store.mutations[types.SET_SUBMISSIONS_PROMISE](state, { promise: obj1, assignmentId: 2 });
            expect(state.submissionsLoaders).toEqual({
                2: obj1,
            });

            store.mutations[types.SET_SUBMISSIONS_PROMISE](state, { promise: obj2, assignmentId: 3 });
            expect(state.submissionsLoaders).toEqual({
                2: obj1,
                3: obj2,
            });
        });
    });

    describe('add submission', () => {
        it('should work and have correct order', () => {
            const obj1 = {id: 1, user: { id: 1001 }, created_at: now(-1) };
            const obj2 = {id: 2, user: { id: 1001 }, created_at: now(-2) };
            const obj3 = {id: 3, user: { id: 1001 }, created_at: now(), assignee: { id: 5 } };

            [obj1, obj2, obj3].forEach(obj => {
                store.mutations[types.ADD_SINGLE_SUBMISSION](state, {
                    submission: Submission.fromServerData(obj, 2),
                });
            });

            delete obj3.created_at;
            const latest = store.getters.getLatestSubmissions(state)(2)
            expect(latest).toMatchObject([
                Object.assign(obj3, { assignmentId: 2 })
            ]);
            expect(latest[0].user.id).toEqual(1001);
            expect(latest[0].assignee.id).toEqual(5);
            expect(latest[0].assignee.name).toEqual(null);
        });

        it('should work when assignment has no submissions', () => {
            const obj = {id: 10, user: { id: 1001 }, created_at: now() };

            store.mutations[types.ADD_SINGLE_SUBMISSION](state, {
                submission: Submission.fromServerData(obj, 10)
            });
            delete obj.created_at;
            expect(store.getters.getLatestSubmissions(state)(10)).toMatchObject([
                Object.assign(obj, { assignmentId: 10 })
            ]);
        });
    });

    describe('update submission', () => {
        beforeEach(() => {
            const obj1 = {id: 15, user: { id: 1001 }, created_at: now() };
            const obj2 = {id: 25, user: { id: 1002 }, created_at: now() };
            const obj3 = {id: 35, user: { id: 1003 }, created_at: now() };

            [obj1, obj2, obj3].forEach(obj => {
                store.mutations[types.ADD_SINGLE_SUBMISSION](state, {
                    submission: Submission.fromServerData(obj, 15),
                });
            });
        });
        it('should work for normal props', () => {
            store.mutations[types.UPDATE_SUBMISSION](state, {
                submissionId: 25,
                submissionProps: { origin: 'xxx' },
            });
            expect(state.submissions[25]).toHaveProperty('origin', 'xxx');
            expect(store.getters.getLatestSubmissions(state)(15)[1].origin).toEqual('xxx');
        });

        it('should work for not unknown submissions', () => {
            expect(
                () => store.mutations[types.UPDATE_SUBMISSION](state, {
                    submissionId: 'UNKNOWN',
                    submissionProps: { name: 4 },
                }),
            ).toThrow();
        });

        it('should work for not work for id', () => {
            expect(
                () => store.mutations[types.UPDATE_SUBMISSION](state, {
                    submissionId: 25,
                    submissionProps: { id: 4 },
                }),
            ).toThrow();
        });

        it('grade prop should be formatted', () => {
            mockFormatGrade.mockClear();
            const single1 = {};
            const single2 = {};
            mockFormatGrade.mockReturnValueOnce(single2);

            store.mutations[types.UPDATE_SUBMISSION](state, {
                submissionId: 25,
                submissionProps: { grade: single1 },
            });
            expect(store.getters.getLatestSubmissions(state)(15)[1]).toHaveProperty('grade', single2);

            expect(mockFormatGrade).toBeCalledTimes(1);
            expect(mockFormatGrade).toBeCalledWith(single1);
        });
    });
});

describe('actions', () => {
    let state;
    let mockDispatch;
    let mockCommit;
    let context;

    beforeEach(() => {
        state = createState();
        mockDispatch = jest.fn();
        mockCommit = jest.fn();
        context = {
            state,
            dispatch: mockDispatch,
            commit: mockCommit,
        };
    });

    describe('load submissions', () => {
        it('should reload submissions', async () => {
            const obj1 = {};
            const obj2 = {};
            mockDispatch.mockReturnValueOnce(obj1);

            await store.actions.loadSubmissions(context, obj2);

            expect(mockDispatch).toBeCalledTimes(1);
            expect(mockDispatch).toBeCalledWith('forceLoadSubmissions', obj2);
        });

        it('should return submissions promise', async () => {
            const obj1 = {};
            const obj2 = {};
            state.submissionsLoaders[obj2] = obj1;

            await expect(store.actions.loadSubmissions(context, { assignmentId: obj2 })).toBe(obj1);

            expect(mockDispatch).not.toBeCalled();
            expect(mockCommit).not.toBeCalled();
        });
    });

    describe('update submission', () => {
        it('should simply work', () => {
            const props = {};
            const data = {
                assignmentId: 2,
                submissionId: 4,
                submissionProps: props,
                other: 4,
            };
            store.actions.updateSubmission(context, data);

            expect(mockCommit).toBeCalledTimes(1);
            expect(mockCommit).toBeCalledWith(types.UPDATE_SUBMISSION, {
                assignmentId: 2,
                submissionId: 4,
                submissionProps: props,
            });
        });
    });

    describe('add submission', () => {
        it('should simply work', () => {
            mockFormatGrade.mockClear();
            const single1 = {a: 1};
            const single2 = {b: 2};
            const props = {
                grade: single1,
                anything: 5,
                user: {
                    id: 100,
                },
                created_at: now(),
            };
            const data = {
                assignmentId: 2,
                submissionId: 4,
                submission: props,
            };
            mockFormatGrade.mockReturnValueOnce(single2);

            store.actions.addSubmission(context, data);

            expect(mockCommit).toBeCalledTimes(1);
            expect(mockCommit).toBeCalledWith(types.ADD_SINGLE_SUBMISSION, {
                submission: expect.any(Submission),
            });
            expect(mockCommit).toBeCalledWith(types.ADD_SINGLE_SUBMISSION, {
                submission: expect.objectContaining({
                    fullGrade: single1,
                    grade: single2,
                    // `anything` should not be there
                    assigneeId: null,
                    commentAuthorId: null,
                    userId: 100,
                    assignmentId: 2,
                }),
            });
            expect(mockFormatGrade).toBeCalledTimes(1);
            expect(mockFormatGrade).toBeCalledWith(single1);
        });
    });
});
