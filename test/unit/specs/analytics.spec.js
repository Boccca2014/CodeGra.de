import moment from 'moment';

import { store } from '@/store';
import {
    Workspace,
    WorkspaceFilter,
    WorkspaceFilterResult,
    WorkspaceSubmission,
    WorkspaceSubmissionSet,
    DataSource,
    RubricSource,
    InlineFeedbackSource,
} from '@/models/analytics';

import * as mutationTypes from '@/store/mutation-types';

function deepFreeze(obj) {
    if (typeof obj == 'object' && obj != null) {
        Object.keys(obj).forEach(k => Object.freeze(obj[k]));
    }
    return Object.freeze(obj);
}

function makeSource(name, data) {
    return deepFreeze({ name, data });
}

function makeFeedbackSource(...data) {
    return deepFreeze({
        name: 'inline_feedback',
        data: Object.fromEntries(data.map((x, i) => [i, { total_amount: x }])),
    });
}

function makeRubricSource(...data) {
    return deepFreeze({
        name: 'rubric_data',
        data: Object.fromEntries(data.map((items, i) =>
            [
                i,
                items.map(([id, mul]) => ({ item_id: id, multiplier: mul })),
            ],
        )),
    });
}

function submissionsWithProps(firstId = 0, ...propss) {
    return propss.map((props, id) => {
        return {
            id: id + firstId,
            ...props,
        };
    });
}

function submissionSetWithProps(...propss) {
    let curId = 0;

    const subs = propss.map((props, i) => {
        const s = submissionsWithProps(curId, ...props);
        curId += s.length;
        return s;
    });

    return WorkspaceSubmissionSet.fromServerData(Object.fromEntries(
        subs.map((s, i) => [i, s]),
    ));
}

function submissionSetWithGrades(...gradess) {
    return submissionSetWithProps(
        ...gradess.map(grades => grades.map(grade => ({ grade }))),
    );
}

const assignment = deepFreeze({
    id: 0,
    analytics_workspace_ids: [0],
});

// A rubric with each item's points equal to the item id.
const rubric = deepFreeze([
    {
        id: 0,
        type: 'normal',
        header: 'norm row 0',
        items: [
            { id: 0, points: 0 },
            { id: 1, points: 1 },
            { id: 2, points: 2 },
        ],
    },
    {
        id: 1,
        type: 'normal',
        header: 'norm row 1',
        items: [
            { id: 3, points: 3 },
            { id: 4, points: 4 },
            { id: 5, points: 5 },
        ],
    },
    {
        id: 2,
        type: 'continuous',
        header: 'cont row 2',
        items: [
            { id: 6, points: 6 },
        ],
    },
]);

beforeEach(async () => {
    const course = Object.assign({}, assignment.course || {}, {
        id: 1,
    });
    const assig = Object.assign({}, assignment, { course_id: 1 });

    course.assignments = [assig];

    store.dispatch('courses/addCourse', { course });

    store.commit(`rubrics/${mutationTypes.SET_RUBRIC}`, {
        assignmentId: assignment.id,
        rubric,
    });

    for (let i = 0; i < 10; ++i) {
        await store.dispatch('users/addOrUpdateUser', {
            user: {
                id: i,
                name: `Assignee: ${i}`,
            },
        });
    }
});

describe('Workspace', () => {
    const workspaceEmpty = deepFreeze({
        id: 0,
        assignment_id: assignment.id,
        data_sources: [],
        student_submissions: {},
    });

    const workspace1 = deepFreeze({
        id: 0,
        assignment_id: assignment.id,
        data_sources: ['rubric_data', 'inline_feedback'],
        student_submissions: {
            0: [{id: 0, grade: 0,  assignee_id: null, created_at: '2020-03-18T12:00:00.00000Z'}],
            1: [{id: 1, grade: 2,  assignee_id: null, created_at: '2020-03-18T13:00:00.00000Z'}],
            2: [{id: 2, grade: 5,  assignee_id: null, created_at: '2020-03-18T14:00:00.00000Z'}],
            3: [{id: 3, grade: 6,  assignee_id: null, created_at: '2020-03-18T15:00:00.00000Z'}],
            4: [{id: 4, grade: 10, assignee_id: null, created_at: '2020-03-18T16:00:00.00000Z'}],
        },
    });

    describe('fromServerData', () => {
        it('should throw an error when not passed the correct sources', () => {
            expect(() => {
                Workspace.fromServerData(workspace1);
            }).toThrow();

            expect(() => {
                Workspace.fromServerData(workspace1, []);
            }).toThrow();

            expect(() => {
                Workspace.fromServerData(workspace1, null);
            }).toThrow();
        });

        it('should throw an error when an unknown data source name was given', () => {
            const data = Object.assign({}, workspace1, {
                data_sources: ['xyz'],
            });
            const src = makeSource('xyz', {});

            expect(() => {
                Workspace.fromServerData(data, [src]);
            }).toThrow();
        });

        it('should throw an error when the data source name does not match the data source', () => {
            const data = Object.assign({}, workspace1, {
                data_sources: ['rubric_data'],
            });
            const src = makeFeedbackSource();

            expect(() => {
                Workspace.fromServerData(data, [src]);
            }).toThrow();
        });

        it('should create a WorkspaceSubmissionSet from the received submissions', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);

            expect(ws.submissions).toBeInstanceOf(WorkspaceSubmissionSet);
        });

        it('should create a subclass of DataSource for each source', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);

            Object.values(ws.dataSources).forEach(source => {
                expect(source).toBeInstanceOf(DataSource);
                expect(source.constructor).not.toBe(DataSource);
            });
        });
    });

    describe('constructor', () => {
        it('should return a frozen object', () => {
            const ws = new Workspace(workspaceEmpty);

            expect(ws).toBeFrozen();
        });

        it('should create an unfrozen dataSources prop', () => {
            const ws = new Workspace(workspaceEmpty);

            expect(ws.dataSources).not.toBeFrozen();
        });
    });

    describe('_setSources', () => {
        it('should copy the given props to the dataSources prop', () => {
            const ws = new Workspace(workspaceEmpty);
            const src = { a: 0 };
            ws._setSources(src);

            expect(ws.dataSources).toEqual(src);
        });

        it('should freeze the dataSources prop', () => {
            const ws = new Workspace(workspaceEmpty);
            const src = { a: 0 };
            ws._setSources(src);

            expect(ws.dataSources).toBeFrozen();
        });

        it('should throw an error if called twice', () => {
            const ws = new Workspace(workspaceEmpty);
            const src = { a: 0 };
            ws._setSources(src);

            expect(() => {
                ws._setSources(src);
            }).toThrow();
        });
    });

    describe('hasSource', () => {
        it('should return true if the requested source is available', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);

            workspace1.data_sources.forEach(src => {
                expect(ws.hasSource(src)).toBeTrue();
            });
        });

        it('should return false if the requested source is not available', () => {
            const ws = Workspace.fromServerData(workspaceEmpty, []);

            workspace1.data_sources.forEach(src => {
                expect(ws.hasSource(src)).toBeFalse();
            });
        });

        it('should return false on invalid input', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);

            [
                null,
                false,
                true,
                10,
                'nonexisting_source',
            ].forEach(src => {
                expect(ws.hasSource(src)).toBeFalse();
            });
        });
    });

    describe('getSource', () => {
        it('should return the source if the requested source is available', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);

            workspace1.data_sources.forEach((src, i) => {
                expect(ws.getSource(src).data).toEqual(sources[i].data);
            });
        });

        it('should return undefined if the requested source is not available', () => {
            const ws = Workspace.fromServerData(workspaceEmpty, []);

            workspace1.data_sources.forEach(src => {
                expect(ws.getSource(src)).toBeUndefined();
            });
        });

        it('should return undefined on invalid input', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);

            [
                null,
                false,
                true,
                10,
                'nonexisting_source',
            ].forEach(src => {
                expect(ws.getSource(src)).toBeUndefined();
            });
        });
    });

    describe('filter', () => {
        it('should return a WorkspaceFilterResult for each passed filter', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);
            const filter = WorkspaceFilter.emptyFilter;

            const res1 = ws.filter([filter]);
            const res2 = ws.filter([filter, filter]);

            expect(res1).toHaveLength(1);
            expect(res2).toHaveLength(2);
            [].concat(res1, res2).forEach(result => {
                expect(result).toBeInstanceOf(WorkspaceFilterResult);
            });
        });
    });
});

describe('WorkspaceFilter', () => {
    const defaults = {
        onlyLatestSubs: true,
        minGrade: null,
        maxGrade: null,
        submittedAfter: null,
        submittedBefore: null,
        assignees: [],
    };

    describe('constructor', () => {
        it('should return a frozen object', () => {
            const f = new WorkspaceFilter({});

            expect(f).toBeFrozen();
        });

        it('should throw when an invalid filter key is passed', () => {
            expect(() => {
                new WorkspaceFilter({ invalidKey: true });
            }).toThrow();
        });

        it('should accept a subset of the valid filter keys', () => {
            const f = new WorkspaceFilter({
                onlyLatestSubs: false,
                minGrade: 0,
            });

            expect(f.onlyLatestSubs).toBeFalse();
            expect(f.minGrade).toBe(0);
        });

        it('should use sensible defaults for omitted filter keys', () => {
            const f = new WorkspaceFilter({});

            expect(f).toEqual(defaults);
        });

        it('should convert dates to moments', () => {
            const f = new WorkspaceFilter({
                submittedAfter: new Date(),
                submittedBefore: new Date(),
            });

            expect(moment.isMoment(f.submittedAfter)).toBeTrue();
            expect(moment.isMoment(f.submittedBefore)).toBeTrue();
        });

        it('should use null if an invalid number is passed', () => {
            const f = new WorkspaceFilter({
                minGrade: 'abc',
                maxGrade: null,
            });

            expect(f.minGrade).toBeNull();
            expect(f.maxGrade).toBeNull();
        });

        it('should use null if an invalid date is passed', () => {
            const f = new WorkspaceFilter({
                submittedAfter: 'abc',
                submittedBefore: null,
            });

            expect(f.submittedAfter).toBeNull();
            expect(f.submittedBefore).toBeNull();
        });
    });

    describe('emptyFilter', () => {
        it('should return the default filter', () => {
            expect(WorkspaceFilter.emptyFilter).toEqual(defaults);
        });
    });

    describe('update', () => {
        it('should return a new object', () => {
            const f = WorkspaceFilter.emptyFilter;
            const g = f.update('assignees', f.assignees);

            expect(f).toEqual(g);
            expect(f).not.toBe(g);
        });

        it('should update the given property', () => {
            const f = WorkspaceFilter.emptyFilter
            const g = f.update('onlyLatestSubs', false);

            Object.entries(g).forEach(([k, v]) => {
                if (k === 'onlyLatestSubs') {
                    expect(v).toBeFalse();
                } else if (k === 'assignees') {
                    expect(v).toEqual(f[k]);
                } else {
                    expect(v).toBe(f[k]);
                }
            });
        });
    });

    describe('split', () => {
        it('should do nothing if splitting on nothing', () => {
            const f = WorkspaceFilter.emptyFilter;
            const s = f.split({});

            expect(s).toHaveLength(1);
            expect(s[0]).toBe(f);
        });

        describe('splitting on latest', () => {
            it('should return two new filters', () => {
                const f = WorkspaceFilter.emptyFilter;
                const s = f.split({ latest: true });

                expect(s).toHaveLength(2);
            });

            it('should put the latest submissions in the second group', () => {
                const f = WorkspaceFilter.emptyFilter;
                const s = f.split({ latest: true });

                expect(s[0].onlyLatestSubs).toBeFalse();
                expect(s[1].onlyLatestSubs).toBeTrue();
            });
        });

        describe('splitting on grade', () => {
            it('should return two new filters', () => {
                const f = WorkspaceFilter.emptyFilter;
                const s = f.split({ grade: 5 });

                expect(s).toHaveLength(2);
            });

            it('should put the lower grades in the first group', () => {
                const f = WorkspaceFilter.emptyFilter;
                const s = f.split({ grade: 5 });

                expect(s[0].maxGrade).toBe(5);
                expect(s[1].minGrade).toBe(5);
            });

            it('should throw an error when the grade is greater than the filter minGrade', () => {
                const f = WorkspaceFilter.emptyFilter;
                const g = f.update('minGrade', 10);

                expect(() => {
                    g.split({ grade: 5 });
                }).toThrow();
            });

            it('should throw an error when the date is after the filter submittedBefore', () => {
                const f = WorkspaceFilter.emptyFilter;
                const g = f.update('maxGrade', 0);

                expect(() => {
                    g.split({ grade: 5 });
                }).toThrow();
            });
        });

        describe('splitting on date', () => {
            it('should return two new filters', () => {
                const f = WorkspaceFilter.emptyFilter;
                const d = new Date();
                const s = f.split({ date: d });

                expect(s).toHaveLength(2);
            });

            it('should put the earlier dates in the first group', () => {
                const f = WorkspaceFilter.emptyFilter;
                const d = new Date();
                const s = f.split({ date: d });

                expect(s[0].submittedBefore.isSame(d)).toBeTrue();
                expect(s[1].submittedAfter.isSame(d)).toBeTrue();
            });

            it('should throw an error when the date is before the filter submittedAfter', () => {
                const f = WorkspaceFilter.emptyFilter;
                const d = new Date();
                const g = f.update('submittedAfter', d);

                expect(() => {
                    g.split({ date: moment(d).subtract(1, 'day') });
                }).toThrow();
            });

            it('should throw an error when the date is after the filter submittedBefore', () => {
                const f = WorkspaceFilter.emptyFilter;
                const d = new Date();
                const g = f.update('submittedBefore', d);

                expect(() => {
                    g.split({ date: moment(d).add(1, 'day') });
                }).toThrow();
            });
        });

        describe('splitting on assignees', () => {
            it('should return a new filter for each given assignee', () => {
                const f = WorkspaceFilter.emptyFilter;
                const s = f.split({ assignees: [0, 1, 2] });

                expect(s).toHaveLength(3);
            });

            it('should order the filters in the order the assignees were given', () => {
                const f = WorkspaceFilter.emptyFilter;
                const s = f.split({ assignees: [0, 1, 2] });

                expect(s[0].assignees.map(x => x.id)).toEqual([0]);
                expect(s[1].assignees.map(x => x.id)).toEqual([1]);
                expect(s[2].assignees.map(x => x.id)).toEqual([2]);
            });
        });

        describe('splitting on multiple filters', () => {
            const count = (s, pred) => {
                return s.reduce((acc, sf) => (pred(sf) ? acc + 1 : acc), 0);
            };

            it('should return the cartesian product of all possible splits', () => {
                const f = WorkspaceFilter.emptyFilter;
                const d = new Date();
                const s1 = f.split({ latest: true, grade: 5 });
                const s2 = f.split({ latest: true, grade: 5, date: d, assignees: [0, 1, 2] });

                expect(s1).toHaveLength(4);
                expect(s2).toHaveLength(24);
            });

            describe('latest', () => {
                it('should apply onlySplitLatest to half of the filters if selected', () => {
                    const f = WorkspaceFilter.emptyFilter;
                    const d = new Date();
                    const s = f.split({ latest: true, grade: 5, date: d, assignees: [0, 1, 2] });
                    const n = count(s, sf => sf.onlyLatestSubs);

                    expect(n).toBe(s.length / 2);
                });

                it('should keep the filter latest if not selected', () => {
                    const f = WorkspaceFilter.emptyFilter;
                    const d = new Date();
                    const s = f.split({ grade: 5, date: d, assignees: [0, 1, 2] });

                    s.forEach(sf => {
                        expect(sf.onlyLatestSubs).toBe(f.onlyLatestSubs);
                    });
                });
            });

            describe('grade', () => {
                it('should apply maxGrade to half the filters and minGrade to the other half if selected', () => {
                    const f = WorkspaceFilter.emptyFilter;
                    const d = new Date();
                    const s = f.split({ latest: true, grade: 5, date: d, assignees: [0, 1, 2] });
                    const n = count(s, sf => sf.onlyLatestSubs);

                    expect(n).toBe(s.length / 2);
                });

                it('should keep the filter min and max grade if not selected', () => {
                    const f = WorkspaceFilter.emptyFilter.update('minGrade', 5);
                    const d = new Date();
                    const s = f.split({ latest: true, date: d, assignees: [0, 1, 2] });

                    s.forEach(sf => {
                        expect(sf.minGrade).toBe(f.minGrade);
                        expect(sf.maxGrade).toBe(f.maxGrade);
                    });
                });
            });
        });
    });

    describe('serialize', () => {
        it('should convert moments to strings', () => {
            const f = WorkspaceFilter.emptyFilter;
            const g = f.update('submittedAfter', moment());
            const s = g.serialize();

            expect(typeof s.submittedAfter).toBe('string');
        });

        it('should convert assignees to their ids', () => {
            const f = WorkspaceFilter.emptyFilter;
            const g = f.update('assignees', [{ id: 0 }, { id: 1 }]);
            const s = g.serialize();

            expect(s.assignees).toEqual([0, 1]);
        });

        it('should not include default values', () => {
            const f = WorkspaceFilter.emptyFilter;
            const s = f.serialize();

            expect(s).toEqual({});
        });
    });
});

describe('WorkspaceFilterResult', () => {
    const workspace1 = deepFreeze({
        id: 0,
        assignment_id: assignment.id,
        data_sources: ['rubric_data', 'inline_feedback'],
        student_submissions: {
            0: [{id: 0, grade: 0,  assignee_id: null, created_at: '2020-03-18T12:00:00.00000Z'}],
            1: [{id: 1, grade: 2,  assignee_id: null, created_at: '2020-03-18T13:00:00.00000Z'}],
            2: [{id: 2, grade: 5,  assignee_id: null, created_at: '2020-03-18T14:00:00.00000Z'}],
            3: [{id: 3, grade: 6,  assignee_id: null, created_at: '2020-03-18T15:00:00.00000Z'}],
            4: [{id: 4, grade: 10, assignee_id: null, created_at: '2020-03-18T16:00:00.00000Z'}],
        },
    });

    describe('constructor', () => {
        it('should return a frozen object', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);
            const f = new WorkspaceFilter({ minGrade: 5 });
            const r = new WorkspaceFilterResult(ws, f);

            expect(r).toBeFrozen();
        });

        it('should keep a reference to the workspace', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);
            const f = new WorkspaceFilter({ minGrade: 5 });
            const r = new WorkspaceFilterResult(ws, f);

            expect(r.workspace).toBe(ws);
        });

        it('should keep a reference to the filter', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);
            const f = new WorkspaceFilter({ minGrade: 5 });
            const r = new WorkspaceFilterResult(ws, f);

            expect(r.filter).toBe(f);
        });

        it('should filter the workspace submissions', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);
            const f = new WorkspaceFilter({ minGrade: 5 });
            const r = new WorkspaceFilterResult(ws, f);

            r.submissions.allSubmissions.forEach(sub => {
                expect(sub.grade).toBeGreaterThanOrEqual(5);
            });
        });

        it('should filter each data source', () => {
            const feedbackSource = makeFeedbackSource(0, 1, 2, 3, 4);

            const rubricSource = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1], [6, 0.4]],
                [[2, 1], [4, 1], [6, 0.6]],
                [[2, 1], [4, 1], [6, 0.8]],
                [[1, 1], [3, 1], [6, 1.0]],
            );

            const ws = Workspace.fromServerData(workspace1, [rubricSource, feedbackSource]);
            const f = new WorkspaceFilter({ minGrade: 5 });
            const r = new WorkspaceFilterResult(ws, f);
            const ids = [...r.submissions.submissionIds].sort();

            Object.keys(ws.dataSources).forEach(name => {
                const source = r.dataSources[name];
                const sourceIds = Object.keys(source.data).map(Number);
                expect([...sourceIds].sort()).toEqual(ids);
            });
        });
    });

    describe('getSource', () => {
        it('should return the requested source if it is available', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);
            const f = new WorkspaceFilter({ minGrade: 5 });
            const r = new WorkspaceFilterResult(ws, f);

            Object.keys(ws.dataSources).forEach(name => {
                expect(r.getSource(name)).not.toBeNull();
            });
        });

        it('should return undefined if the requested source is not available', () => {
            const sources = [makeRubricSource(), makeFeedbackSource()];
            const ws = Workspace.fromServerData(workspace1, sources);
            const f = new WorkspaceFilter({ minGrade: 5 });
            const r = new WorkspaceFilterResult(ws, f);

            expect(r.getSource('xyz')).toBeUndefined();
            expect(r.getSource(null)).toBeUndefined();
        });
    });
});

describe('WorkspaceSubmissionSet', () => {
    function getBins(data) {
        return Object.keys(data).map(Number);
    }

    const workspace0 = deepFreeze({
        id: 0,
        assignment_id: assignment.id,
        data_sources: ['rubric_data', 'inline_feedback'],
        student_submissions: {},
    });

    const workspace1 = deepFreeze({
        id: 0,
        assignment_id: assignment.id,
        data_sources: ['rubric_data', 'inline_feedback'],
        student_submissions: {
            0: [
                {id: 0, grade: null, assignee_id: null, created_at: '2020-03-18T12:00:00.00000Z'},
                {id: 1, grade: null, assignee_id: null, created_at: '2020-03-19T12:00:00.00000Z'},
                {id: 2, grade: null, assignee_id: null, created_at: '2020-03-20T12:00:00.00000Z'},
                {id: 3, grade: 8,    assignee_id: null, created_at: '2020-03-21T12:00:00.00000Z'},
                {id: 4, grade: 10,   assignee_id: null, created_at: '2020-03-22T12:00:00.00000Z'},
            ],
            1: [
                {id: 5, grade: null, assignee_id: null, created_at: '2020-03-18T13:00:00.00000Z'},
                {id: 6, grade: null, assignee_id: null, created_at: '2020-03-19T13:00:00.00000Z'},
                {id: 7, grade: null, assignee_id: null, created_at: '2020-03-20T13:00:00.00000Z'},
                {id: 8, grade: null, assignee_id: null, created_at: '2020-03-21T13:00:00.00000Z'},
                {id: 9, grade: 5,    assignee_id: null, created_at: '2020-03-22T13:00:00.00000Z'},
            ],
            2: [
                {id: 10, grade: null, assignee_id: null, created_at: '2020-03-18T14:00:00.00000Z'},
                {id: 11, grade: null, assignee_id: null, created_at: '2020-03-19T14:00:00.00000Z'},
                {id: 12, grade: null, assignee_id: null, created_at: '2020-03-20T14:00:00.00000Z'},
                {id: 13, grade: null, assignee_id: null, created_at: '2020-03-21T14:00:00.00000Z'},
                {id: 14, grade: 8,    assignee_id: null, created_at: '2020-03-22T14:00:00.00000Z'},
            ],
            3: [
                {id: 15, grade: null, assignee_id: null, created_at: '2020-03-18T15:00:00.00000Z'},
                {id: 16, grade: null, assignee_id: null, created_at: '2020-03-19T15:00:00.00000Z'},
                {id: 17, grade: null, assignee_id: null, created_at: '2020-03-20T15:00:00.00000Z'},
                {id: 18, grade: null, assignee_id: null, created_at: '2020-03-21T15:00:00.00000Z'},
                {id: 19, grade: 6,    assignee_id: null, created_at: '2020-03-22T15:00:00.00000Z'},
            ],
            4: [
                {id: 20, grade: null, assignee_id: null, created_at: '2020-03-18T16:00:00.00000Z'},
                {id: 21, grade: null, assignee_id: null, created_at: '2020-03-19T16:00:00.00000Z'},
                {id: 22, grade: null, assignee_id: null, created_at: '2020-03-20T16:00:00.00000Z'},
                {id: 23, grade: 2,    assignee_id: null, created_at: '2020-03-21T16:00:00.00000Z'},
                {id: 24, grade: 7,    assignee_id: null, created_at: '2020-03-22T16:00:00.00000Z'},
            ],
        },
    });

    describe('fromServerData', () => {
        it('should convert the given submissions to instances of WorkspaceSubmission', () => {
            const wss = WorkspaceSubmissionSet.fromServerData(workspace1.student_submissions);

            Object.values(wss.submissions).forEach(subs => {
                subs.forEach(sub => {
                    expect(sub).toBeInstanceOf(WorkspaceSubmission);
                });
            });
        });
    });

    describe('constructor', () => {
        it('should return a frozen object', () => {
            const wss = WorkspaceSubmissionSet.fromServerData(workspace1.student_submissions);

            expect(wss).toBeFrozen();
        });

        it('should freeze the submission data', () => {
            const wss = WorkspaceSubmissionSet.fromServerData(workspace1.student_submissions);

            expect(wss.submissions).toBeFrozen();
            Object.values(wss.submissions).forEach(subs => {
                expect(subs).toBeFrozen();
            });
        });
    });

    describe('allSubmissions', () => {
        it('should return a list of all submissions', () => {
            const wss = WorkspaceSubmissionSet.fromServerData(workspace1.student_submissions);
            const allSubs = new Set(wss.allSubmissions);

            Object.values(wss.submissions).forEach(subs => {
                subs.forEach(sub => {
                    expect(allSubs.has(sub)).toBeTrue();
                });
            });
        });

        it('should return the empty list if there are no submissions', () => {
            const wss = WorkspaceSubmissionSet.fromServerData(workspace0.student_submissions);

            expect(wss.allSubmissions).toHaveLength(0);
        });
    });

    describe('firstSubmissionDate', () => {
        it('should return the date of the first submission in the set', () => {
            const data = workspace1.student_submissions;
            const wss = WorkspaceSubmissionSet.fromServerData(data);

            expect(wss.firstSubmissionDate.isSame(data[0][0].created_at)).toBeTrue();
        });

        it('should return null if there are no submissions', () => {
            const wss = WorkspaceSubmissionSet.fromServerData(workspace0.student_submissions);

            expect(wss.firstSubmissionDate).toBeNull();
        });
    });

    describe('lastSubmissionDate', () => {
        it('should return the date of the last submission in the set', () => {
            const data = workspace1.student_submissions;
            const wss = WorkspaceSubmissionSet.fromServerData(data);
            const n = Object.keys(data).length - 1;
            const m = data[n].length - 1;

            expect(wss.lastSubmissionDate.isSame(data[n][m].created_at)).toBeTrue();
        });

        it('should return null if there are no submissions', () => {
            const wss = WorkspaceSubmissionSet.fromServerData(workspace0.student_submissions);

            expect(wss.lastSubmissionDate).toBeNull();
        });
    });

    describe('binSubmissionsByGrade', () => {
        it('should return a defaultdict with bin index as keys and lists of submissions as values', () => {
            const wss = submissionSetWithGrades([1, 5, 10]);
            const bin = wss.binSubmissionsByGrade();

            expect(getBins(bin)).toEqual([1, 5, 9]);
            expect(bin[0]).toHaveLength(0);
            expect(bin[1]).toHaveLength(1);
            expect(bin[5]).toHaveLength(1);
            expect(bin[9]).toHaveLength(1);
            expect(bin[1][0]).toEqual(wss.submissions[0][0]);
            expect(bin[5][0]).toEqual(wss.submissions[0][1]);
            expect(bin[9][0]).toEqual(wss.submissions[0][2]);
        });

        it('should accept a bin size', () => {
            const wss = submissionSetWithGrades([1, 5, 10]);
            const bin1 = wss.binSubmissionsByGrade(2);
            const bin2 = wss.binSubmissionsByGrade(0.5);

            expect(getBins(bin1)).toEqual([0, 2, 4]);
            expect(getBins(bin2)).toEqual([2, 10, 19]);
        });

        it('should round down to a multiple of the bin size', () => {
            const wss = submissionSetWithGrades([4.999]);
            const bin1 = wss.binSubmissionsByGrade();
            const bin2 = wss.binSubmissionsByGrade(3);
            const bin3 = wss.binSubmissionsByGrade(0.5);

            expect(bin1[4]).toHaveLength(1);
            expect(bin2[1]).toHaveLength(1);
            expect(bin3[9]).toHaveLength(1);
        });

        it('should return an empty dict if there are no submissions', () => {
            const wss = submissionSetWithGrades();
            const bin = wss.binSubmissionsByGrade();

            expect(getBins(bin)).toBeEmpty();
        });
    });

    describe('submissionCount', () => {
        it('should return the total number of submissions', () => {
            const wss = submissionSetWithGrades([1, 2, 3], [4, 5], [6]);

            expect(wss.submissionCount).toBe(6);
        });

        it('should work even if there are no submissions', () => {
            const wss = submissionSetWithGrades();

            expect(wss.submissionCount).toBe(0);
        });

        it('should count submissions with grade null', () => {
            const wss = submissionSetWithGrades([1, null, 3], [4, null], [6]);

            expect(wss.submissionCount).toBe(6);
        });
    });

    describe('studentCount', () => {
        it('should return the total number of students', () => {
            const wss = submissionSetWithGrades([1, 2, 3], [4, 5], [6]);

            expect(wss.studentCount).toBe(3);
        });

        it('should work even if there are no submissions', () => {
            const wss = submissionSetWithGrades();

            expect(wss.studentCount).toBe(0);
        });

        it('should include students without submissions', () => {
            const wss = submissionSetWithGrades([], [4, 5], [6]);

            expect(wss.studentCount).toBe(3);
        });
    });

    describe('gradeStats', () => {
        it('should return the various averages over all grades', () => {
            const wss = submissionSetWithGrades([1, 2, 3], [4, 5]);
            const avgs = wss.gradeStats;

            expect(avgs.mean).toBeNumber();
            expect(avgs.median).toBeNumber();
            expect(avgs.mode).toBeNumber();
            expect(avgs.stdev).toBeNumber();
        });

        it('should return 0 stdev when there is just one submission', () => {
            const wss = submissionSetWithGrades([1]);
            const avgs = wss.gradeStats;

            expect(avgs.mean).toBeNumber();
            expect(avgs.median).toBeNumber();
            expect(avgs.mode).toBeNumber();
            expect(avgs.stdev).toBe(0);
        });

        it('should return null when there are no submissions', () => {
            const wss = submissionSetWithGrades();

            expect(wss.gradeStats).toBeNull();
        });
    });

    describe('submissionStats', () => {
        it('should return the various averages over number of submissions per student', () => {
            const wss = submissionSetWithGrades([1, 2, 3], [4, 5], [6]);
            const avgs = wss.submissionStats;

            expect(avgs.mean).toBeNumber();
            expect(avgs.median).toBeNumber();
            expect(avgs.mode).toBeNumber();
            expect(avgs.stdev).toBeNumber();
        });

        it('should return 0 stdev when there is just one submission', () => {
            const wss = submissionSetWithGrades([1]);
            const avgs = wss.submissionStats;

            expect(avgs.mean).toBeNumber();
            expect(avgs.median).toBeNumber();
            expect(avgs.mode).toBeNumber();
            expect(avgs.stdev).toBe(0);
        });

        it('should return null when there are no submissions', () => {
            const wss = submissionSetWithGrades();

            expect(wss.submissionStats).toBeNull();
        });
    });

    describe('submissionsPerStudent', () => {
        it('should return the number of submissions per student', () => {
            const wss = submissionSetWithGrades([1, 2, 3], [4, 5], [6, 7]);
            const subs = wss.submissionsPerStudent;

            expect(subs[2]).toBe(2);
            expect(subs[3]).toBe(1);
        });

        it('should not count students without submissions', () => {
            const wss = submissionSetWithGrades([], [4, 5], [6, 7]);
            const subs = wss.submissionsPerStudent;

            expect(subs[0]).toBe(0);
        });
    });

    describe('filter', () => {
        it('should return a new WorkspaceSubmissionSet', () => {
            const wss = submissionSetWithGrades([1, 2, 3], [4, 5], [6, 7]);
            const filtered = wss.filter(WorkspaceFilter.emptyFilter);

            expect(filtered).not.toBe(wss);
        });

        it('should only return submissions that satisfy the given filter', () => {
            const wss = submissionSetWithGrades([1, 2, 4.999], [4, 5], [6, 7]);
            const f = WorkspaceFilter.emptyFilter
                .update('onlyLatestSubs', false)
                .update('minGrade', 5);
            const filtered = wss.filter(f);

            expect(filtered.allSubmissions.length).toBe(3);

            filtered.allSubmissions.forEach(sub => {
                expect(sub.grade).toBeGreaterThanOrEqual(5);
            });
        });

        it('should leave the empty set empty', () => {
            const wss = submissionSetWithGrades();
            const filtered = wss.filter(WorkspaceFilter.emptyFilter);

            expect(filtered.submissionCount).toBe(0);
        });
    });
});

describe('WorkspaceSubmission', () => {
    describe('fromServerData', () => {
        it('should create a createdAt property which is a moment instance', () => {
            const d = new Date();
            const sub = WorkspaceSubmission.fromServerData({ created_at: d });

            expect(moment.isMoment(sub.createdAt)).toBeTrue();
            expect(sub.createdAt.isSame(d)).toBeTrue();
        });
    });

    describe('constructor', () => {
        it('should return a frozen object', () => {
            const sub = new WorkspaceSubmission({});

            expect(sub).toBeFrozen();
        });
    });

    describe('satisfiesGrade', () => {
        it('should ignore arguments that are null', () => {
            const sub = new WorkspaceSubmission({ grade: null });

            expect(sub.satisfiesGrade(null, null)).toBeTrue();
        });

        it('should return false for submissions without a grade if one of the arguments is not null', () => {
            const sub = new WorkspaceSubmission({ grade: null });

            expect(sub.satisfiesGrade(0, null)).toBeFalse();
            expect(sub.satisfiesGrade(null, 10)).toBeFalse();
        });

        it('should return true if minGrade is less than the submission grade', () => {
            const sub = new WorkspaceSubmission({ grade: 5 });

            expect(sub.satisfiesGrade(0, null)).toBeTrue();
        });

        it('should return false if minGrade is greater than the submission grade', () => {
            const sub = new WorkspaceSubmission({ grade: 5 });

            expect(sub.satisfiesGrade(10, null)).toBeFalse();
        });

        it('should return true if maxGrade is greater than the submission grade', () => {
            const sub = new WorkspaceSubmission({ grade: 5 });

            expect(sub.satisfiesGrade(null, 10)).toBeTrue();
        });

        it('should return false if maxGrade is less than the submission grade', () => {
            const sub = new WorkspaceSubmission({ grade: 5 });

            expect(sub.satisfiesGrade(null, 0)).toBeFalse();
        });
    });

    describe('satisfiesDate', () => {
        it('should ignore arguments that are null', () => {
            const sub = new WorkspaceSubmission({ createdAt: moment() });

            expect(sub.satisfiesGrade(null, null)).toBeTrue();
        });

        it('should return true if submittedAfter is before the submission date', () => {
            const sub = new WorkspaceSubmission({ createdAt: moment() });
            const d = sub.createdAt.clone().subtract(1, 'day');

            expect(sub.satisfiesDate(d, null)).toBeTrue();
        });

        it('should return false if submittedAfter is before the submission date', () => {
            const sub = new WorkspaceSubmission({ createdAt: moment() });
            const d = sub.createdAt.clone().add(1, 'day');

            expect(sub.satisfiesDate(d, null)).toBeFalse();
        });

        it('should return true if submittedBefore is after the submission date', () => {
            const sub = new WorkspaceSubmission({ createdAt: moment() });
            const d = sub.createdAt.clone().add(1, 'day');

            expect(sub.satisfiesDate(null, d)).toBeTrue();
        });

        it('should return false if submittedBefore is before the submission date', () => {
            const sub = new WorkspaceSubmission({ createdAt: moment() });
            const d = sub.createdAt.clone().subtract(1, 'day');

            expect(sub.satisfiesDate(null, d)).toBeFalse();
        });
    });

    describe('satisfiesAssignees', () => {
        it('should return true if no assignees are given', () => {
            const sub = new WorkspaceSubmission({ assignee_id: null });

            expect(sub.satisfiesAssignees([])).toBeTrue();
        });

        it('should return true if any of the given assignees matches the submission assignee', () => {
            const sub = new WorkspaceSubmission({ assignee_id: 0 });

            expect(sub.satisfiesAssignees([{ id: 0 }])).toBeTrue();
            expect(sub.satisfiesAssignees([{ id: 1 }, { id: 0 }])).toBeTrue();
        });
    });
});

describe('DataSource', () => {
    describe('fromServerData', () => {
        it('should throw an error if the source name does not match the class name', () => {
            const src = makeSource('xyz', {});

            expect(() => {
                DataSource.fromServerData(src);
            }).toThrow(/invalid datasource type/i);
        });

        it('should throw an error if the data source does not have a data prop', () => {
            expect(() => {
                DataSource.fromServerData({ name: DataSource.sourceName });
            }).toThrow(/data source without data/i);
        });

        it('should return an instance of the correct subclass', () => {
            const srcData = makeFeedbackSource(0);
            const src = InlineFeedbackSource.fromServerData(srcData);

            expect(src).toBeInstanceOf(InlineFeedbackSource);
        });
    });

    describe('constructor', () => {
        it('should throw an error if called directly', () => {
            expect(() => {
                new DataSource();
            }).toThrow(/datasource should not be instantiated directly/i);
        });

        it('should freeze the data it has been given', () => {
            const srcData = makeFeedbackSource(0);
            const src = InlineFeedbackSource.fromServerData(srcData);

            expect(src.data).toBeFrozen();
        });
    });

    describe('filter', () => {
        it('should return a new instance of the data source with only the filtered data', () => {
            const srcData = makeFeedbackSource(0);
            const src = InlineFeedbackSource.fromServerData(srcData);
            const ids = Object.keys(src.data).map(Number).slice(2).sort();
            const filtered = src.filter(new Set(ids));
            const filteredIds = Object.keys(filtered.data).map(Number).sort();

            expect(filtered).toBeInstanceOf(InlineFeedbackSource);
            expect(ids).toEqual(filteredIds);
        });
    });
});

describe('RubricSource', () => {
    const workspace = deepFreeze({
        id: 0,
        assignment_id: assignment.id,
        data_sources: ['rubric_data'],
        student_submissions: {
            0: [{id: 0, grade: 0,  assignee_id: null, created_at: '2020-03-18T12:00:00.00000Z'}],
            1: [{id: 1, grade: 2,  assignee_id: null, created_at: '2020-03-18T13:00:00.00000Z'}],
            2: [{id: 2, grade: 5,  assignee_id: null, created_at: '2020-03-18T14:00:00.00000Z'}],
            3: [{id: 3, grade: 6,  assignee_id: null, created_at: '2020-03-18T15:00:00.00000Z'}],
            4: [{id: 4, grade: 10, assignee_id: null, created_at: '2020-03-18T16:00:00.00000Z'}],
        },
    });

    describe('constructor', () => {
        it('should return a frozen object', () => {
            // We need to construct the rubric source via the workspace,
            // because the rubric source needs a back reference to the
            // workspace to be able to get the rubric data from the assignment.
            const srcData = makeRubricSource();
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;

            expect(src).toBeFrozen();
            expect(src.data).toBeFrozen();

            Object.values(src.data).forEach(val => {
                expect(val).toBeFrozen();
                val.forEach(x => {
                    expect(x).toBeFrozen();
                });
            });
        });

        it('should throw if the assignment does not have a rubric', () => {
            store.commit(
                `rubrics/${mutationTypes.CLEAR_RUBRIC}`,
                { assignmentId: assignment.id },
            );

            const src = makeRubricSource();

            expect(() => {
                Workspace.fromServerData(workspace, [src]);
            }).toThrow(/assignment does not have a rubric/i);
        });

        it('should calculate per item the exact amount of achieved points', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1], [6, 0.4]],
                [[2, 1], [4, 1], [6, 0.6]],
                [[2, 1], [4, 1], [6, 0.8]],
                [[1, 1], [3, 1], [6, 1.0]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;

            Object.values(src.data).forEach(subItems => {
                subItems.forEach(item => {
                    // The rubric's item ids are equal to the points per item.
                    expect(item.points).toBe(item.item_id * item.multiplier);
                });
            });
        });
    });

    describe('rubricItems', () => {
        it('should return a mapping from item id to item', () => {
            const srcData = makeRubricSource();
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const items = src.rubricItems;

            ws.assignment.rubric.rows.forEach(row => {
                row.items.forEach(item => {
                    expect(items[item.id]).toBe(item);
                });
            });
        });
    });

    describe('rubricRowPerItem', () => {
        it('should return a mapping from item id to rubric row', () => {
            const sources = [makeRubricSource()];
            const ws = Workspace.fromServerData(workspace, sources);
            const src = ws.dataSources.rubric_data;
            const rows = src.rubricRowPerItem;

            ws.assignment.rubric.rows.forEach(row => {
                row.items.forEach(item => {
                    expect(rows[item.id]).toBe(row);
                });
            });
        });
    });

    describe('itemsPerCat', () => {
        it('should return a mapping from rubric row id to the achieved items in that row', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1], [6, 0.4]],
                [[2, 1], [4, 1], [6, 0.6]],
                [[2, 1], [4, 1], [6, 0.8]],
                [[1, 1], [3, 1], [6, 1.0]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const items = src.itemsPerCat;

            const getIds = rowId => items[rowId].map(x => x.item_id).sort();

            expect(getIds(0)).toEqual([0, 1, 1, 2, 2]);
            expect(getIds(1)).toEqual([3, 3, 4, 4, 5]);
            expect(getIds(2)).toEqual([6, 6, 6, 6, 6]);
        });
    });

    describe('nTimesFilledPerCat', () => {
        it('should return a mapping from rubric row id to the number of times that row was filled', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const filled = src.nTimesFilledPerCat;

            expect(filled[0]).toBe(3);
            expect(filled[1]).toBe(2);
            expect(filled[2]).toBe(1);
        });
    });

    describe('meanPerCat', () => {
        it('should return the mean per category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const means = src.meanPerCat;

            expect(means[0]).toBeNumber();
            expect(means[1]).toBeNumber();
            expect(means[2]).toBeNumber();
        });

        it('should return null if the row was never filled', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const means = src.meanPerCat;

            expect(means[0]).toBeNumber();
            expect(means[1]).toBeNumber();
            expect(means[2]).toBeNull();
        });
    });

    describe('stdevPerCat', () => {
        it('should return the standard deviation per category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1], [6, 0]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const stdevs = src.stdevPerCat;

            expect(stdevs[0]).toBeNumber();
            expect(stdevs[1]).toBeNumber();
            expect(stdevs[2]).toBeNumber();
        });

        it('should return 0 if a row is filled only once', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const stdevs = src.stdevPerCat;

            expect(stdevs[0]).toBeNumber();
            expect(stdevs[1]).toBeNumber();
            expect(stdevs[2]).toBe(0);
        });

        it('should return null if the row was never filled', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const stdevs = src.stdevPerCat;

            expect(stdevs[0]).toBeNumber();
            expect(stdevs[1]).toBeNumber();
            expect(stdevs[2]).toBeNull();
        });
    });

    describe('medianPerCat', () => {
        it('should return the median per category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const medians = src.medianPerCat;

            expect(medians[0]).toBeNumber();
            expect(medians[1]).toBeNumber();
            expect(medians[2]).toBeNumber();
        });

        it('should return null if the row was never filled', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const medians = src.medianPerCat;

            expect(medians[0]).toBeNumber();
            expect(medians[1]).toBeNumber();
            expect(medians[2]).toBeNull();
        });
    });

    describe('modePerCat', () => {
        it('should return the mode per category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.2]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const modes = src.modePerCat;

            expect(modes[0]).toBeNumber();
            expect(modes[1]).toBeNumber();
            expect(modes[2]).toBeNumber();
        });

        it('should return null if the row was never filled', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const modes = src.modePerCat;

            expect(modes[0]).toBeNumber();
            expect(modes[1]).toBeNumber();
            expect(modes[2]).toBeNull();
        });
    });

    describe('scorePerCatPerSubmission', () => {
        it('should return a list of mappings from row id to score per submission', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const scores = src.scorePerCatPerSubmission;

            expect(scores).toEqual({
                0: { 0: 0, 1: 5, 2: 6 },
                1: { 0: 1, 1: 3 },
                2: { 0: 2 },
            });
        });
    });

    describe('totalScorePerSubmission', () => {
        it('should return a mapping from submission id to their total score on the rubric', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const scores = src.totalScorePerSubmission;

            expect(scores).toEqual({
                0: 11,
                1: 4,
                2: 2,
            });
        });
    });

    describe('ritItemsPerCat', () => {
        it('should return a list of pairs (item score, total score) per category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const ritItems = src.ritItemsPerCat;

            expect(ritItems).toEqual({
                0: [[0, 11], [1, 4], [2, 2]],
                1: [[5, 11], [3, 4]],
                2: [[6, 11]],
            });
        });
    });

    describe('rirItemsPerCat', () => {
        it('should return a list of pairs (item score, reduced score) per category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const rirItems = src.rirItemsPerCat;

            expect(rirItems).toEqual({
                0: [[0, 11], [1, 3], [2, 0]],
                1: [[5, 6],  [3, 1]],
                2: [[6, 5]],
            });
        });
    });

    describe('ritPerCat', () => {
        it('should return the rit value per category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.5]],
                [[1, 1], [3, 1], [6, 1]],
                [[2, 1], [4, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const rits = src.ritPerCat;

            expect(rits[0]).toBeNumber();
            expect(rits[1]).toBeNumber();
            expect(rits[2]).toBeNumber();
        });

        it('should return null if the row was filled less than 2 times', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const rits = src.ritPerCat;

            expect(rits[0]).toBeNumber();
            expect(rits[1]).toBeNumber();
            expect(rits[2]).toBeNull();
        });

        it('should return null if all students scored the same in a category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [3, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const rits = src.ritPerCat;

            expect(rits[0]).toBeNumber();
            expect(rits[1]).toBeNull();
        });
    });

    describe('rirPerCat', () => {
        it('should return the rir value per category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1], [6, 0.5]],
                [[1, 1], [3, 1], [6, 1]],
                [[2, 1], [4, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const rirs = src.rirPerCat;

            expect(rirs[0]).toBeNumber();
            expect(rirs[1]).toBeNumber();
            expect(rirs[2]).toBeNumber();
        });

        it('should return null if the row was filled less than 2 times', () => {
            const srcData = makeRubricSource(
                [[0, 1], [5, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const rirs = src.rirPerCat;

            expect(rirs[0]).toBeNumber();
            expect(rirs[1]).toBeNumber();
            expect(rirs[2]).toBeNull();
        });

        it('should return null if all students scored the same in a category', () => {
            const srcData = makeRubricSource(
                [[0, 1], [3, 1]],
                [[1, 1], [3, 1]],
                [[2, 1]],
            );
            const ws = Workspace.fromServerData(workspace, [srcData]);
            const src = ws.dataSources.rubric_data;
            const rits = src.ritPerCat;

            expect(rits[0]).toBeNumber();
            expect(rits[1]).toBeNull();
        });
    });
});

describe('InlineFeedbackSource', () => {
    describe('constructor', () => {
        it('should return a frozen object', () => {
            const srcData = makeFeedbackSource();
            const src = InlineFeedbackSource.fromServerData(srcData);

            expect(src).toBeFrozen();
        });
    });

    describe('entryStats', () => {
        it('should return the various averages over the number of feedback entries per submission', () => {
            const srcData = makeFeedbackSource(0, 1, 2, 3, 4);
            const src = InlineFeedbackSource.fromServerData(srcData);
            const avgs = src.entryStats;

            expect(avgs.mean).toBeNumber();
            expect(avgs.median).toBeNumber();
            expect(avgs.mode).toBeNumber();
            expect(avgs.stdev).toBeNumber();
        });

        it('should return 0 stdev when there is just one submission', () => {
            const srcData = makeFeedbackSource(1);
            const src = InlineFeedbackSource.fromServerData(srcData);
            const avgs = src.entryStats;

            expect(avgs.mean).toBeNumber();
            expect(avgs.median).toBeNumber();
            expect(avgs.mode).toBeNumber();
            expect(avgs.stdev).toBe(0);
        });

        it('should return null when there are no submissions', () => {
            const srcData = makeFeedbackSource();
            const src = InlineFeedbackSource.fromServerData(srcData);

            expect(src.entryStats).toBeNull();
        });
    });
});
