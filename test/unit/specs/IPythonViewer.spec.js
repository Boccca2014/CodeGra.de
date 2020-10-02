/* SPDX-License-Identifier: AGPL-3.0-only */
import IPythonViewer from '@/components/IPythonViewer';
import { shallowMount, createLocalVue } from '@vue/test-utils';
import VueRouter from 'vue-router';
import Vuex from 'vuex';
import BootstrapVue from 'bootstrap-vue';
import * as utils from '@/utils/typed';
import * as decode from '@/utils/decode'
import * as ipythonUtils from '@/utils/ipython'
import axios from 'axios';
import util from 'util';

jest.mock('axios');

const localVue = createLocalVue();

localVue.use(Vuex);
localVue.use(BootstrapVue);

const router = new VueRouter();

function jsonCopy(src) {
    return JSON.parse(JSON.stringify(src));
}

describe('IPythonViewer.vue', () => {
    let wrapper;
    let comp;

    let assignment;
    let submission;
    let file;
    let fileId;
    let mockIPython = JSON.stringify({
        nbformat: 4,
        metadata: {
            language_info: { name: 'python' },
        },
    });

    let mockGet;
    let curId = 1;

    const setData = async (data) => {
        let str;
        if (typeof data === 'string') {
            str = data;
        } else {
            str = JSON.stringify({
                nbformat: 4,
                metadata: {
                    language_info: { name: 'python' },
                },
                cells: data,
            });
        }

        mockIPython = (new util.TextEncoder()).encode(str);
        wrapper.setProps({ fileContent: mockIPython });

        await comp.$afterRerender();
        await comp.$afterRerender();
    };

    beforeEach(async () => {
        jest.spyOn(utils, 'highlightCode').mockImplementation(x => x);
        fileId = `${Math.random()}`;

        curId = Math.round(Math.random() * 1000);
        assignment = { id: curId++ };
        submission = {
            id: curId++,
            feedback: {
                general: '',
                authos: {},
                user: {},
                linter: {},
            },
        };
        file = { id: fileId };

        mockGet = jest.fn(async (path, opts) => new Promise((resolve, reject) => {
            let res;
            if (/^.api.v1.code.[0-9]+.type=feedback$/.test(path)) {
                reject();
                return;
            }
            resolve({ data: res });
        }));

        jest.spyOn(axios, 'get').mockImplementation(mockGet);

        wrapper = shallowMount(IPythonViewer, {
            localVue,
            router,
            mocks: {
                $http: {
                    get: mockGet,
                },
            },
            propsData: {
                assignment,
                submission,
                file,
                editable: true,
                fontSize: 12,
                showWhitespace: true,
                canUseSnippets: true,
                fileContent: null,
                fileId,
            },
            store: new Vuex.Store({
                modules: {
                    pref: {
                        namespaced: true,
                        state: {
                            contextAmount: 2,
                            fontSize: 12,
                        },
                        getters: {
                            contextAmount: state => state.contextAmount,
                            fontSize: state => state.fontSize,
                        },
                    },
                    code: {
                        namespaced: true,
                        actions: {
                            loadCode: id => mockGet(`/api/v1/code/${id}`).then(() => mockIPython),
                        },
                    },
                },
            }),
        });
        comp = wrapper.vm;
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    describe('outputCells', () => {
        it('should be an array', () => {
            expect(Array.isArray(comp.outputCells)).toBe(true);
        });

        it('should be an empty array when the data is invalid', () => {
            expect(Array.isArray(comp.outputCells)).toBe(true);
        });

        it('should join test in sources', async () => {
            await setData([
                {
                    cell_type: 'markdown',
                    source: ['hello'],
                },
                {
                    cell_type: 'markdown',
                    source: ['hello', 'bye'],
                },
                {
                    cell_type: 'raw',
                    source: 'DO NOT INCLUDE',
                },
                {
                    cell_type: 'markdown',
                    source: 'bye',
                },
            ]);

            expect(comp.outputCells).toEqual([
                {
                    cell_type: 'markdown',
                    source: 'hello',
                    feedback_offset: 0,
                },
                {
                    cell_type: 'markdown',
                    source: 'hellobye',
                    feedback_offset: 1,
                },
                {
                    cell_type: 'markdown',
                    source: 'bye',
                    feedback_offset: 2,
                },
            ]);
        });

        it('should work with code', async () => {
            await setData([
                {
                    cell_type: 'markdown',
                    source: ['hello'],
                },
                {
                    cell_type: 'code',
                    source: ['import os\n\n\nprint(os.path.join(', 'a, b))'],
                    outputs: [
                        {
                            output_type: 'stream',
                            text: ['hello'],
                        },
                        {
                            output_type: 'not stream',
                            text: ['hello'],
                        },
                    ],
                },
            ]);
            expect(comp.data).not.toEqual({});
            expect(comp.outputCells).toEqual([
                {
                    cell_type: 'markdown',
                    source: 'hello',
                    feedback_offset: 0,
                },
                {
                    cell_type: 'code',
                    source: ['import os', '', '', 'print(os.path.join(a, b))'],
                    feedback_offset: 1,
                    outputs: [
                        {
                            output_type: 'stream',
                            text: ['hello'],
                            feedback_offset: 5
                        },
                        {
                            output_type: 'not stream',
                            text: ['hello'],
                            feedback_offset: 6,
                        },
                    ],
                },
            ]);
            expect(utils.highlightCode).toHaveBeenCalledTimes(1);
        });

        it('should work with nbformat version 3', async () => {
            await setData(JSON.stringify({
                nbformat: 3,
                metadata: {
                    language_info: { name: 'python' },
                },
                cells: [
                    {
                        cell_type: 'markdown',
                        input: ['hello'],
                    },
                    {
                        cell_type: 'code', input: ['import os\n\n\nprint(os.path.join(', 'a, b))'],
                        outputs: [
                            {
                                output_type: 'stream',
                                text: ['hello'],
                            },
                            {
                                output_type: 'not stream',
                                text: ['hello'],
                            },
                        ],
                    },
                ],
            }));
            expect(comp.data).not.toEqual({});
            expect(comp.outputCells).toMatchObject([
                {
                    cell_type: 'markdown',
                    source: 'hello',
                    feedback_offset: 0,
                },
                {
                    cell_type: 'code',
                    source: ['import os', '', '', 'print(os.path.join(a, b))'],
                    feedback_offset: 1,
                    outputs: [
                        {
                            output_type: 'stream',
                            text: ['hello'],
                            feedback_offset: 5
                        },
                        {
                            output_type: 'not stream',
                            text: ['hello'],
                            feedback_offset: 6,
                        },
                    ],
                },
            ]);
        });

        it('should not work with nbformat versions < 3', async () => {
            let err;
            comp.$emit = jest.fn((_, e) => { err = e; });

            await setData(JSON.stringify({
                nbformat: 2,
            }));

            expect(comp.data).not.toEqual({});
            expect(comp.outputCells).toEqual([]);
            expect(comp.$emit).toBeCalledTimes(1);
            expect(comp.$emit).lastCalledWith('error', err);
            expect(err.error).toBeInstanceOf(Error);
            expect(err.error.message).toMatch('Only Jupyter Notebook format v3 or greater is supported.');
        });

        it('should accept strings and lists of strings as output text', async () => {
            await setData(JSON.stringify({
                nbformat: 4,
                metadata: {
                    language_info: { name: 'python' },
                },
                cells: [
                    {
                        cell_type: 'code',
                        input: ['import os\n\n\nprint(os.path.join(', 'a, b))'],
                        outputs: [
                            {
                                output_type: 'execute_result',
                                text: ['line1\n', 'line2\n'],
                            },
                            {
                                output_type: 'execute_result',
                                text: 'line1\nline2\n',
                            },
                            {
                                output_type: 'not stream',
                                text: 'line1\nline2\n',
                            },
                        ],
                    },
                ],
            }));
            expect(comp.data).not.toEqual({});
            expect(comp.outputCells).toMatchObject([
                {
                    cell_type: 'code',
                    source: ['import os', '', '', 'print(os.path.join(a, b))'],
                    feedback_offset: 0,
                    outputs: [
                        {
                            output_type: 'execute_result',
                            text: ['line1\n', 'line2\n'],
                            feedback_offset: 4
                        },
                        {
                            output_type: 'execute_result',
                            text: 'line1\nline2\n',
                            feedback_offset: 5,
                        },
                        {
                            output_type: 'not stream',
                            text: 'line1\nline2\n',
                            feedback_offset: 6,
                        },
                    ],
                },
            ]);
        });
    });

    describe('loadCode', () => {
        it('should work when the api returns invalid JSON', async () => {
            await setData('THIS IS NOT JSON');
            expect(wrapper.emitted().error).toEqual([[{
                error: comp.invalidJsonMessage,
                fileId: fileId,
            }]]);
        });

        it('should work when the buffer cannot be decoded', async () => {
            const err = Math.random();
            const error = new Error(err)
            jest.spyOn(decode, 'default').mockImplementation(
                () => { throw error; },
            )
            wrapper.setProps({ fileContent: 'AAH' });

            await comp.$nextTick();
            await comp.$nextTick();
            await comp.$nextTick();

            expect(decode.default).toBeCalledWith('AAH');
            expect(wrapper.emitted().error).toEqual([[{
                error,
                fileId: fileId,
            }]]);
        });

        it('should work when getOutputCells errors', async () => {
            const err = Math.random();
            const error = new Error(err)
            jest.spyOn(ipythonUtils, 'getOutputCells')
                .mockImplementation(() => { throw error; });

            await setData('{"val": "AAAH"}');

            expect(ipythonUtils.getOutputCells).toBeCalledWith({ val: 'AAAH' });
            expect(wrapper.emitted().error).toEqual([[{
                error,
                fileId: fileId,
            }]]);
        });
    });

    describe('outputData', () => {
        const data = {
            data: {
                'not type': 'not value',
                'aaaa type': 'not value',
                'type': 'value',
                'ztype': 'not value',
                'zzztype': 'not value',
            },
        };
        it('should return the value if the value was found', () => {
            expect(comp.outputData(data, ['not found', 'type', 'not type'])).toBe('value');
        });
        it('should return null if the value was not found', () => {
            expect(comp.outputData(data, ['not found', 'nope not in there'])).toBe(null);
        });
    });
});
