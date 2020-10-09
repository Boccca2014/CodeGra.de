import axios from 'axios';

import { store } from '@/store';
import * as mutationTypes from '@/store/mutation-types';
import { actions, mutations } from '@/store/modules/rubrics';
import { NONEXISTENT, UNSET_SENTINEL } from '@/constants';
import {
    Rubric,
    ContinuousRubricRow,
    NormalRubricRow,
    RubricRow,
    RubricResult,
} from '@/models/rubric';
import { AutoTestResult } from '@/models/auto_test';
import { CoursesStore, AssignmentsStore } from '@/store';

describe('The rubric store', () => {
    let state;
    let assignmentId;
    let submissionId;
    let mockRubric;
    let mockResult;
    let mockAxiosGet;

    function getResult() {
        return state.results[submissionId];
    }

    beforeAll(() => {
        CoursesStore.addCourse({
            course: {
                id: 1,
                assignments: [{
                    id: 1,
                }],
            }
        })
    });

    beforeEach(() => {
        state = {
            rubrics: {},
            results: {},
        };
        assignmentId = 1;
        submissionId = 1;
        mockRubric = [
            {
                id: 0,
                type: 'normal',
                header: 'row 0',
                description: 'row 0',
                description_type: 'markdown',
                items: [
                    { id: 0, points: 0, header: 'item 0', description: '' },
                    { id: 1, points: 1, header: 'item 1', description: '' },
                    { id: 2, points: 2, header: 'item 2', description: '' },
                ],
            },
            {
                id: 1,
                type: 'normal',
                header: 'row 1',
                description: 'row 1',
                description_type: 'markdown',
                items: [
                    { id: 5, points: 16, header: 'item 2', description: '' },
                    { id: 3, points: 4,  header: 'item 0', description: '' },
                    { id: 4, points: 8,  header: 'item 1', description: '' },
                ],
            },
        ];
        mockResult = {
            rubrics: mockRubric,
            selected: [{ id: 1, points: 1, multiplier: 1 }],
        };
    });

    describe('actions', () => {
        beforeEach(() => {
            store.commit(`rubrics/${mutationTypes.CLEAR_RUBRICS}`);
            store.commit(`rubrics/${mutationTypes.CLEAR_RUBRIC_RESULTS}`);
            state = store.state.rubrics;
        });

        describe('loadRubric', () => {
            it('should load the rubric if it is not already available', async () => {
                const mockGet = jest.fn(() => Promise.resolve({}));
                axios.get = mockGet;

                await store.dispatch('rubrics/loadRubric', { assignmentId });

                expect(mockGet).toBeCalledTimes(1);
                expect(mockGet).toHaveBeenCalledWith(`/api/v1/assignments/${assignmentId}/rubrics/`);
                expect(state.rubrics).toHaveProperty(`${assignmentId}`);
            });

            it('should not send a request if the rubric is already available', async () => {
                const mockGet = jest.fn(() => Promise.resolve({}));
                axios.get = mockGet;

                await store.dispatch('rubrics/loadRubric', { assignmentId });
                await store.dispatch('rubrics/loadRubric', { assignmentId });

                expect(mockGet).toBeCalledTimes(1);
                expect(state.rubrics).toHaveProperty(`${assignmentId}`);
            });

            it('should send a request if the rubric is already available and "force" is true', async () => {
                const mockGet = jest.fn(() => Promise.resolve({}));
                axios.get = mockGet;

                await store.dispatch('rubrics/loadRubric', { assignmentId });
                await store.dispatch('rubrics/loadRubric', { assignmentId, force: true });

                expect(mockGet).toBeCalledTimes(2);
                expect(state.rubrics).toHaveProperty(`${assignmentId}`);
            });

            it('should set the rubric to NONEXISTENT on error during loading', async () => {
                const mockErr = {};
                const mockGet = jest.fn(() => Promise.reject(mockErr));
                axios.get = mockGet;

                try {
                    await store.dispatch('rubrics/loadRubric', { assignmentId });
                } catch (e) {
                    expect(e).toBe(mockErr);
                }

                expect(mockGet).toBeCalledTimes(1);
                expect(state.rubrics).toHaveProperty(`${assignmentId}`);
                expect(state.rubrics[assignmentId]).toBe(NONEXISTENT);
            });
        });

        describe('copyRubric', () => {
            it('should send a request to the server', async () => {
                const mockPost = jest.fn(() => Promise.resolve({ data: mockRubric }));
                axios.post = mockPost;

                const otherAssignmentId = 2;
                await store.dispatch('rubrics/copyRubric', { assignmentId, otherAssignmentId });

                expect(mockPost).toBeCalledTimes(1);
                expect(mockPost).toHaveBeenCalledWith(
                    `/api/v1/assignments/${assignmentId}/rubric`,
                    { old_assignment_id: otherAssignmentId },
                );
                expect(state.rubrics).toHaveProperty(`${assignmentId}`);
            });
        });

        describe('updateRubric', () => {
            it('should send a request to the server and update the store', async () => {
                const mockRubricModel = Rubric.fromServerData(mockRubric);
                const mockPut = jest.fn(() => Promise.resolve({ data: mockRubric }));
                axios.put = mockPut;

                const maxPoints = 3;
                await store.dispatch('rubrics/updateRubric', {
                    assignmentId,
                    rubric: mockRubricModel,
                    maxPoints,
                });

                expect(mockPut).toHaveBeenCalledTimes(1);
                expect(mockPut).toHaveBeenCalledWith(
                    `/api/v1/assignments/${assignmentId}/rubrics/`,
                    {
                        rows: mockRubricModel.rows,
                        max_points: maxPoints,
                    },
                );

                state.rubrics[assignmentId].rows.forEach((row, i) => {
                    expect(row).toEqual(expect.objectContaining(mockRubricModel.rows[i]));
                });
                expect(AssignmentsStore.getAssignment()(assignmentId)).toBeJust();
                expect(AssignmentsStore.getAssignment()(assignmentId).extract().fixed_max_rubric_points).toBe(maxPoints);
            });
        });

        describe('deleteRubric', () => {
            it('should send a request to the server and delete the rubric from the store', async () => {
                const response = {};
                const mockDelete = jest.fn(() => Promise.resolve(response));
                axios.delete = mockDelete;

                store.commit(`rubrics/${mutationTypes.SET_RUBRIC}`, {
                    assignmentId,
                    rubric: mockRubric,
                });
                await store.dispatch(`rubrics/deleteRubric`, { assignmentId });

                expect(mockDelete).toHaveBeenCalledTimes(1);
                expect(mockDelete).toHaveBeenCalledWith(
                    `/api/v1/assignments/${assignmentId}/rubrics/`,
                );

                response.onAfterSuccess();
                expect(state.rubrics).toHaveProperty(`${assignmentId}`);
                expect(state.rubrics[assignmentId]).toBe(NONEXISTENT);
            });
        });

        describe('clearRubric', () => {
            it('should not send a request to the server and delete the rubric from the store', async () => {
                const mockDelete = jest.fn(() => Promise.resolve());
                axios.delete = mockDelete;

                store.commit(`rubrics/${mutationTypes.SET_RUBRIC}`, {
                    assignmentId,
                    rubric: mockRubric,
                });
                await store.dispatch(`rubrics/clearRubric`, { assignmentId });

                expect(mockDelete).toHaveBeenCalledTimes(0);
                expect(state.rubrics).not.toHaveProperty(`${assignmentId}`);
            });
        });
    });

    describe('mutations', () => {
        describe('SET_RUBRIC', () => {
            it('should store a new Rubric model', () => {
                mutations[mutationTypes.SET_RUBRIC](state, {
                    assignmentId,
                    rubric: mockRubric,
                });

                const rubric = state.rubrics[assignmentId];

                expect(rubric).toBeInstanceOf(Rubric);
                expect(rubric.maxPoints).toBe(18);
            });

            it('should not try to convert NONEXISTENT to a Rubric model', () => {
                mutations[mutationTypes.SET_RUBRIC](state, {
                    assignmentId,
                    rubric: NONEXISTENT,
                });

                const rubric = state.rubrics[assignmentId];

                expect(rubric).toBe(NONEXISTENT);
            });
        });

        describe('CLEAR_RUBRIC', () => {
            it('should delete the rubric from the store', () => {
                state.rubrics[assignmentId] = {};

                mutations[mutationTypes.CLEAR_RUBRIC](state, { assignmentId });

                expect(state.rubrics[assignmentId]).toBeUndefined();
            });
        });

        describe('CLEAR_RUBRICS', () => {
            it('should delete all rubrics from the store', () => {
                state.rubrics[assignmentId] = {};

                mutations[mutationTypes.CLEAR_RUBRICS](state);

                expect(Object.values(state.rubrics).length).toBe(0);
            });
        });

        describe('SET_RUBRIC_RESULT', () => {
            it('should store a new RubricResult model', () => {
                mutations[mutationTypes.SET_RUBRIC_RESULT](state, {
                    submissionId,
                    result: mockResult,
                });

                const result = state.results[submissionId];

                expect(result).toBeInstanceOf(RubricResult);
                expect(Object.values(result.selected).length).toBe(mockResult.selected.length);
                expect(result.points).toBe(1);
            });

            it('should store null as points if no items are selected', () => {
                mutations[mutationTypes.SET_RUBRIC_RESULT](state, {
                    submissionId,
                    result: Object.assign(mockResult, {
                        selected: [],
                    }),
                });

                const result = state.results[submissionId];

                expect(result).toBeInstanceOf(RubricResult);
                expect(Object.values(result.selected).length).toBe(0);
                expect(result.points).toBeNull();
            });
        });

        describe('CLEAR_RUBRIC_RESULT', () => {
            it('should delete the rubric from the store', () => {
                state.results[submissionId] = {};

                mutations[mutationTypes.CLEAR_RUBRIC_RESULT](state, { submissionId });

                expect(getResult()).toBeUndefined();
            });
        });

        describe('CLEAR_RUBRIC_RESULTS', () => {
            it('should delete all rubric results from the store', () => {
                state.results[submissionId] = {};

                mutations[mutationTypes.CLEAR_RUBRIC_RESULTS](state);

                expect(Object.values(state.results).length).toBe(0);
            });
        });
    });

    describe('The Rubric model', () => {
        describe('fromServerData', () => {
            it('should return an immutable object', () => {
                const rubric = Rubric.fromServerData(mockRubric);

                expect(rubric).toBeInstanceOf(Rubric);
                expect(() => {
                    rubric.rows = [];
                }).toThrow(TypeError);
            });

            it('should sort items in a row by points, ascendingly', () => {
                const reversed = [...mockRubric];
                reversed[0].items = [...reversed[0].items].reverse();

                const rubric = Rubric.fromServerData(mockRubric);
                const rubricReversed = Rubric.fromServerData(reversed);

                expect(rubric.equals(rubricReversed)).toBeTrue();
            });

            it('should instantiate a NormalRubricRow model for each row', () => {
                const rubric = Rubric.fromServerData(mockRubric);
                rubric.rows.forEach(row => {
                    expect(row).toBeInstanceOf(NormalRubricRow);
                });
            });
        });

        describe('maxPoints', () => {
            it('should be unset initially and cache the result', () => {
                const rubric = Rubric.fromServerData(mockRubric);

                expect(rubric._cache._cache.maxPoints).toBe(UNSET_SENTINEL);
                expect(rubric.maxPoints).toBe(18);
                expect(rubric._cache._cache.maxPoints).toBe(18);
            });
        });

        describe('createRow', () => {
            it('should return a new copy', () => {
                const rubric = Rubric.fromServerData(mockRubric);
                const newRubric = rubric.createRow('normal');

                expect(newRubric).not.toBe(rubric);
            });

            it('should insert a normal row', () => {
                const rubric = Rubric.fromServerData(mockRubric);
                const newRubric = rubric.createRow('normal');
                const newRow = newRubric.rows[newRubric.rows.length - 1];

                expect(newRubric.rows.length).toBe(rubric.rows.length + 1);
                expect(newRow.items.length).toBe(0);
            });

            it('should insert a continuous row', () => {
                const rubric = Rubric.fromServerData(mockRubric);
                const newRubric = rubric.createRow('continuous');
                const newRow = newRubric.rows[newRubric.rows.length - 1];

                expect(newRubric.rows.length).toBe(rubric.rows.length + 1);
                expect(newRow.type).toBe('continuous');
                expect(newRow.items.length).toBe(1);
            });

            // TODO: Unskip this test after removing the old rubric editor.
            it.skip('should throw an error when no type is passed', () => {
                const rubric = Rubric.fromServerData(mockRubric);
                expect(() => {
                    rubric.createRow();
                }).toThrow(TypeError);
            });

            it('should throw an error when an invalid type is passed', () => {
                const rubric = Rubric.fromServerData(mockRubric);
                expect(() => {
                    rubric.createRow('xxx');
                }).toThrow(TypeError);
            });
        });

        describe('deleteRow', () => {
            it('should return a new copy', () => {
                const rubric = Rubric.fromServerData(mockRubric);
                const newRubric = rubric.deleteRow(0);

                expect(rubric).not.toBe(newRubric);
            });

            it('should delete the given row', () => {
                const rubric = Rubric.fromServerData(mockRubric);
                const newRubric = rubric.deleteRow(0);

                expect(newRubric.rows.length).toBe(rubric.rows.length - 1);
                newRubric.rows.forEach(row => {
                    expect(row).not.toEqual(rubric.rows[0]);
                });
            });

            it('should throw an error when an invalid index is given', () => {
                let rubric = Rubric.fromServerData(mockRubric);

                expect(() => rubric.deleteRow(-1)).toThrow(ReferenceError);
                expect(() => rubric.deleteRow(10)).toThrow(ReferenceError);

                while (rubric.rows.length > 0) {
                    rubric = rubric.deleteRow(0);
                }

                expect(rubric.rows.length).toBe(0);
                expect(() => rubric.deleteRow(0)).toThrow(ReferenceError);
            });
        });

        describe('updateRow', () => {
            it('should throw an error when the argument is not of type NormalRubricRow', () => {
                const rubric = Rubric.fromServerData(mockRubric);

                expect(() => {
                    rubric.updateRow(0, 0);
                }).toThrow(TypeError);

                expect(() => {
                    rubric.updateRow(0, '0');
                }).toThrow(TypeError);

                expect(() => {
                    rubric.updateRow(0, null);
                }).toThrow(TypeError);

                expect(() => {
                    rubric.updateRow(0, []);
                }).toThrow(TypeError);

                expect(() => {
                    rubric.updateRow(0, {});
                }).toThrow(TypeError);

                expect(() => {
                    rubric.updateRow(0, undefined);
                }).toThrow(TypeError);
            });
        });
    });

    describe('The NormalRubricRow model', () => {
        describe('constructor', () => {
            it('should return an immutable object', () => {
                const row = new NormalRubricRow(mockRubric[0]);

                expect(row).toBeInstanceOf(NormalRubricRow);
                expect(() => {
                    row.id = 3;
                }).toThrow(TypeError);
            });
        });

        describe('maxPoints',  () => {
            it('should be unset initially and cache the result', () => {
                const row = new NormalRubricRow(mockRubric[0]);

                expect(row._cache._cache.maxPoints).toBe(UNSET_SENTINEL);
                expect(row.maxPoints).toBe(2);
                expect(row._cache._cache.maxPoints).toBe(2);
            });
        });

        describe('update', () => {
            let row, row_upd;
            let props = { header: 'NEW HEADER' };

            beforeEach(() => {
                row = new NormalRubricRow(mockRubric[0]);
                row_upd = row.update(props);
            });

            it('should return a new copy', () => {
                expect(row).not.toBe(row_upd);
            });

            it('should update the given props', () => {
                expect(row_upd.header).toBe(props.header);
            });
        });

        describe('createItem', () => {
            let row, row2;

            beforeEach(() => {
                row = new NormalRubricRow(mockRubric[0]);
                row2 = row.createItem();
            });

            it('should return a new copy', () => {
                expect(row).not.toBe(row2);
            });

            it('should insert an item in the items list', () => {
                expect(row2.items.length).toBe(row.items.length + 1);
            });

            it('should insert an empty item', () => {
                const item = row2.items[row2.items.length - 1];

                expect(item.points).toBe('');
                expect(item.header).toBe('');
                expect(item.description).toBe('');
            });
        });

        describe('deleteItem', () => {
            let row, row2;

            beforeEach(() => {
                row = new NormalRubricRow(mockRubric[0]);
                row2 = row.deleteItem(0);
            });

            it('should return a new copy', () => {
                expect(row).not.toBe(row2);
            });

            it('should throw an error when the index is invalid', () => {
                expect(() => row.deleteItem(-1)).toThrow(ReferenceError);
                expect(() => row.deleteItem(10)).toThrow(ReferenceError);

                while (row2.items.length > 0) {
                    row2 = row2.deleteItem(0);
                }

                expect(row2.items.length).toBe(0);
                expect(() => row2.deleteItem(0)).toThrow(ReferenceError);
            });

            it('should delete the item at the given index', () => {
                expect(row2.items[0]).toEqual(row.items[1]);
                expect(row2.items[1]).toEqual(row.items[2]);

                row2 = row.deleteItem(1);
                expect(row2.items[0]).toEqual(row.items[0]);
                expect(row2.items[1]).toEqual(row.items[2]);

                row2 = row.deleteItem(2);
                expect(row2.items[0]).toEqual(row.items[0]);
                expect(row2.items[1]).toEqual(row.items[1]);
            });
        });

        describe('lockMessagge', () => {
            let row;

            beforeEach(() => {
                row = new ContinuousRubricRow(Object.assign({}, mockRubric[0], {
                    locked: 'auto_test',
                    type: 'continuous',
                }));

            });

            it('should be empty when the row is not an AutoTest row', () => {
                row = new NormalRubricRow(mockRubric[0]);
                expect(row.lockMessage(null, null, null)).toBe('');
            });

            it('should return a message when the row is an AutoTest row', () => {
                expect(row.lockMessage(null, null, null)).toBe('This is an AutoTest category.');

                row = new NormalRubricRow(Object.assign({}, mockRubric[0], {
                    locked: 'auto_test',
                }));

                expect(row.lockMessage(null, null, null).startsWith('This is an AutoTest category.')).toBeTrue();
            });

            it('should get the correct message for a not filled in rubric with a result', () => {
                const atResult = new AutoTestResult({
                    id: 5,
                    work_id: 6,
                    state: 'failed',
                })

                expect(row.lockMessage(
                    null, atResult, null
                )).toBe(
                    'This is an AutoTest category. It will be filled in' +
                        ' once all hidden steps have been run, which will' +
                        ' happen after the deadline.'
                );
            });

            it ('should get the correct message for a final finished result', () => {
                const atResult = new AutoTestResult({
                    id: 5,
                    work_id: 6,
                })
                atResult.update({ final_result: true, state: 'working' });

                expect(row.lockMessage(
                    null, atResult, null
                )).toBe(
                    'This is an AutoTest category. It will be filled in once the test has finished running.'
                );
            });

            it('should get the correct message for passed and final results', () => {
                const atResult = new AutoTestResult({
                    id: 5,
                    work_id: 6,
                })
                atResult.update({ final_result: true, state: 'passed' });

                expect(row.lockMessage(
                    null, atResult, null
                )).toBe(
                    'This is an AutoTest category. It will be filled in once you have the permission to see the final grade.'
                );
            });
        });
    });
});
