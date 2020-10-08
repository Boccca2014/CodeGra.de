/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';

import {
    range,
    last,
    formatGrade,
    formatDate,
    cmpOneNull,
    cmpNoCaseMany,
    hashString,
    getExtension,
    waitAtLeast,
    highlightCode,
    nameOfUser,
    groupMembers,
    coerceToString,
    toMaxNDecimals,
    deepEquals,
    hasAttr,
    setXor,
    ensureArray,
    mapObject,
    filterObject,
    isEmpty,
    zip,
    buildUrl,
    numberToTimes,
    readableJoin,
    safeDivide,
    sortBy,
    toMoment,
    parseOrKeepFloat,
    pickKeys,
} from '@/utils/typed';

import {
    autoTestHasCheckpointAfterHiddenStep,
    WarningHeader,
    isDecimalNumber,
    deepExtend,
    setProps,
    getNoNull,
    deepExtendArray,
    deepCopy,
    formatTimePart,
} from '@/utils';

import { makeCache } from '@/utils/cache';
import { Counter } from '@/utils/counter';
import { defaultdict } from '@/utils/defaultdict';

import * as assignmentState from '@/store/assignment-states';
import * as visualize from '@/utils/visualize';

import { UNSET_SENTINEL } from '@/constants';

import * as highlight from 'highlightjs';

jest.useFakeTimers();

describe('utils.js', () => {
    describe('range', () => {
        it('should work for zero length', () => {
            expect(range(2, 2)).toEqual([]);
        });

        it('should work for non zero length', () => {
            expect(range(2, 10)).toEqual([2, 3, 4, 5, 6, 7, 8, 9]);
        });

        it('should work for without begin', () => {
            expect(range(10)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
        });

        it('should return an empty list when end is less than start', () => {
            expect(range(10, 0)).toEqual([]);
        });
    });

    describe('last', () => {
        it('should return a reference to the last item of the array', () => {
            const lastItem = { c: 'd' };
            expect(last([{ a: 'b' }, lastItem])).toBe(lastItem);
            expect(last([{ a: 'b' }, last])).not.toBe({ c: 'd' });
        });
    });

    describe('isDecimalNumber', () => {
        it('should accept numbers', () => {
            expect(isDecimalNumber(5)).toBe(true);
            expect(isDecimalNumber(-2)).toBe(true);
            expect(isDecimalNumber(11)).toBe(true);
        });

        it('should only accept numbers and strings', () => {
            expect(isDecimalNumber({})).toBe(false);
            expect(isDecimalNumber([])).toBe(false);
            expect(isDecimalNumber(new Number(5))).toBe(true);
            expect(isDecimalNumber(new String('5'))).toBe(true);
        });

        it('should work for some strings', () => {
            expect(isDecimalNumber('hello')).toBe(false);
            expect(isDecimalNumber('0x5')).toBe(false);
            expect(isDecimalNumber('08')).toBe(false);
            expect(isDecimalNumber('1.')).toBe(false);
            expect(isDecimalNumber('0.')).toBe(false);
            expect(isDecimalNumber('.50')).toBe(false);

            expect(isDecimalNumber('0')).toBe(true);
            expect(isDecimalNumber('0.8')).toBe(true);
            expect(isDecimalNumber('-0.8')).toBe(true);
            expect(isDecimalNumber('10')).toBe(true);
            expect(isDecimalNumber('-10')).toBe(true);
            expect(isDecimalNumber('-10.10')).toBe(true);
            expect(isDecimalNumber('10.10')).toBe(true);
        });
    });

    describe('formatGrade', () => {
        it('should work with normal numbers', () => {
            expect(formatGrade(5.5)).toBe('5.50');
            expect(formatGrade(5.55555)).toBe('5.56');
            expect(formatGrade(-5.55555)).toBe('-5.56');
        });

        it('should work with string numbers', () => {
            expect(formatGrade('5.5')).toBe('5.50');
            expect(formatGrade('5.55555')).toBe('5.56');
            expect(formatGrade('-5.55555')).toBe('-5.56');
            expect(formatGrade('11')).toBe('11.00');
        });

        it('zero should return a string', () => {
            expect(typeof formatGrade('0')).toBe('string');
            expect(formatGrade('0')).toBe('0.00');
        });

        it('non floats should return null', () => {
            expect(formatGrade('NO FLOAT')).toBe(null);
            expect(formatGrade(null)).toBe(null);
        });
    });

    describe('cmpOneNull', () => {
        it('should work with all permutations', () => {
            expect(cmpOneNull(null, null)).toBe(0);
            expect(cmpOneNull('not null', null)).toBe(1);
            expect(cmpOneNull(null, 'not null')).toBe(-1);
            expect(cmpOneNull('not null', 'not null')).toBe(null);
        });
    });

    describe('hashString', () => {
        it('should be a number', () => {
            expect(typeof hashString('hello')).toBe('number');
        });

        it('should be different for different strings', () => {
            expect(hashString('hello')).not.toBe(hashString('not hello'));
        });

        it('should work for empty strings', () => {
            expect(typeof hashString('')).toBe('number');
        });
    });

    describe('getExtension', () => {
        it('should work', () => {
            expect(getExtension('noextension')).toBe(null);
            expect(getExtension('hello.c')).toBe('c');
            expect(getExtension('hello.tar.gz')).toBe('gz');
        });
    });

    describe('waitAtLeast', () => {
        const time = 5000000;
        const obj1 = {n: 1};
        const obj2 = {n: 2};

        it('should work with one Promise', async () => {
            const fn = jest.fn();
            const promise = waitAtLeast(time, Promise.resolve(obj1));
            promise.then(fn);

            jest.advanceTimersByTime(250);
            expect(fn).not.toBeCalled();

            jest.advanceTimersByTime(time - 1);
            await expect(promise).resolves.toBe(obj1);
        });

        it('should work with multiple Promises', async () => {
            const fn = jest.fn();
            const promise = waitAtLeast(time, Promise.resolve(obj1), Promise.resolve(obj2));
            promise.then(fn);

            jest.advanceTimersByTime(250);
            expect(fn).not.toBeCalled();

            jest.advanceTimersByTime(time - 1);
            await expect(promise).resolves.toEqual([obj1, obj2]);
        });

        it('longest time should be used', async () => {
            const fn = jest.fn();
            const promise = waitAtLeast(time, new Promise(resolve => setTimeout(() => resolve(obj1), time + time)));
            promise.then(fn);

            jest.advanceTimersByTime(250);
            expect(fn).not.toBeCalled();

            jest.advanceTimersByTime(time - 1);
            expect(fn).not.toBeCalled();

            jest.advanceTimersByTime(time);
            await expect(promise).resolves.toBe(obj1);
        });
    });

    describe('highlightCode', () => {
        let mockVisul;
        let mockHighlight;
        let mockGetLang;
        let i = 0;

        beforeEach(() => {
            mockVisul = jest.fn(x => x);
            visualize.visualizeWhitespace = mockVisul;

            mockHighlight = jest.fn(function() {
                return {
                    value: Array.prototype.slice.call(arguments),
                    top: `STATE${++i}`,
                };
            });
            highlight.default.highlight = mockHighlight;
            mockGetLang = jest.spyOn(highlight.default, 'getLanguage');
        });

        afterEach(() => {
            i = 0;
            mockVisul.mockRestore();
            mockHighlight.mockRestore();
            mockGetLang.mockRestore();
        });

        it('should work without a language', () => {
            const data = Array(10).fill('<a>code line</a>')
            const res = Array(10).fill('&lt;a&gt;code line&lt;/a&gt;');
            expect(highlightCode(data)).toEqual(res);
            expect(mockVisul).toHaveBeenCalledTimes(data.length);
            expect(mockGetLang).toHaveBeenCalledTimes(1);
        });

        it('should work for very large arrays', () => {
            const data = Array(100).fill('hello');
            expect(highlightCode(data, 'NOT USED!', 99)).toEqual(data);
            // Should not be called for large files
            expect(mockVisul).not.toBeCalled();
            expect(mockGetLang).not.toBeCalled();
        });

        it('should work with a language', () => {
            const code = [
                'import os',
                '',
                'with open(os.path.join("dir", "file")) as f:',
                '\tprint(f.read())',
            ];
            const result = code.map(
                (x, idx) => ['python', x, true, idx ? `STATE${idx}` : undefined],
            );
            expect(highlightCode(code, 'python')).toEqual(result);
            expect(mockVisul).toHaveBeenCalledTimes(code.length);
            expect(mockGetLang).toHaveBeenCalledTimes(1);
        });
    });

    describe('nameOfUser', () => {
        const obj = {};

        it('should work for normal users', () => {
            expect(nameOfUser({
                name: obj
            })).toBe(obj);
        });

        it('should work for groups', () => {
            const groupName = `The name ${Math.random()}`;
            expect(nameOfUser({
                name: obj,
                group: { name: groupName },
            })).toEqual(`Group "${groupName}"`);
        });

        it('should work for empty objects', () => {
            expect(nameOfUser(null)).toEqual('');
            expect(nameOfUser({})).toEqual('');
        });

        it('should the `readableName` property if available', () => {
            const obj = {};
            expect(nameOfUser({ readableName: obj })).toBe(obj);
        });
    });

    describe('groupMembers', () => {
        it('should work for normal users', () => {
            expect(groupMembers({
                name: 'hello'
            })).toEqual([]);
        });

        it('should work for groups', () => {
            const name1 = Math.random();
            const name2 = Math.random();

            const groupName = `The name ${Math.random()}`;
            expect(groupMembers({
                name: 'HALLO',
                group: {
                    members: [
                        { name: name1 },
                        { name: name2 },
                    ],
                },
            })).toEqual([name1, name2]);
        });

        it('should work for empty objects', () => {
            expect(groupMembers(null)).toEqual([]);
            expect(groupMembers({})).toEqual([]);
        });
    });

    describe('autoTestHasCheckpointAfterHiddenStep', () => {
        function makeTest(sets) {
            return {
                sets,
            };
        }

        function makeSet(suites, stopPoints = 0) {
            return {
                suites,
                stop_points: stopPoints,
            };
        }

        function makeSuite(steps) {
            return {
                steps,
            };
        }

        function makeStep(type, hidden = false) {
            return {
                type,
                hidden,
            };
        }

        it('should return false when the test has no checkpoints', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test', true),
                        makeStep('run_program', true),
                    ]),
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program', true),
                    ]),
                ]),
                makeSet([
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test', true),
                        makeStep('run_program'),
                    ]),
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                ]),
            ]))).toBe(false);
        });

        it('should return false when the test has no hidden steps but does contain check_points steps', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('check_points'),
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                        makeStep('check_points'),
                    ]),
                ]),
                makeSet([
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('check_points'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('check_points'),
                        makeStep('run_program'),
                    ]),
                ]),
            ]))).toBe(false);
        });

        it('should return false when the test has no hidden steps but does contain set checkpoints', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                ], 0.5),
                makeSet([
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                ]),
            ]))).toBe(false);
        });

        it('should return false when all check_points steps occur before the first hidden step in the same suite', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('check_points'),
                        makeStep('custom_output', true),
                        makeStep('io_test', true),
                        makeStep('run_program', true),
                    ]),
                ]),
            ]))).toBe(false);
        });

        it('should return false when a check_points step occurs after a suite with hidden steps', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test', true),
                        makeStep('run_program', true),
                    ]),
                    makeSuite([
                        makeStep('check_points'),
                    ]),
                ]),
            ]))).toBe(false);
        });

        it('should return false when all set checkpoints occur before the first hidden step', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                ], 0.5),
                makeSet([
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test'),
                        makeStep('run_program', true),
                    ]),
                ]),
            ]))).toBe(false);
        });

        it('should return false when a set checkpoint of the only set happens after hidden steps', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test', true),
                        makeStep('run_program'),
                    ]),
                ], 1.0),
            ]))).toBe(false);
        });

        it('should return false when a set checkpoint of the last set happens after hidden steps in a previous set', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test', true),
                        makeStep('run_program'),
                    ]),
                ]),
                makeSet([
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                ], 1.0),
            ]))).toBe(false);
        });

        it('should return false when a set checkpoint of the last set happens after hidden steps in the same set', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output'),
                        makeStep('io_test'),
                        makeStep('run_program'),
                    ]),
                ]),
                makeSet([
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test', true),
                        makeStep('run_program'),
                    ]),
                ], 1.0),
            ]))).toBe(false);
        });

        it('should return true when a check_points step happens after hidden steps in the same suite', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test', true),
                        makeStep('run_program'),
                        makeStep('check_points'),
                    ]),
                ]),
            ]))).toBe(true);
        });

        it('should return true when a set checkpoint happens after hidden steps', () => {
            expect(autoTestHasCheckpointAfterHiddenStep(makeTest([
                makeSet([
                    makeSuite([
                        makeStep('custom_output', true),
                        makeStep('io_test', true),
                        makeStep('run_program'),
                    ]),
                ], 1.0),
                makeSet([
                    makeSuite([
                        makeStep('custom_output'),
                    ]),
                ]),
            ]))).toBe(true);
        });
    });

    describe('safeDivide', () => {
        it('should work when both are not 0', () => {
            expect(safeDivide(4, 10, {})).toBe(4 / 10);
        });
        it('should work when both are 0', () => {
            const res = {};
            expect(safeDivide(0, 0, res)).toBe(res);
        });
        it('should work when one is 0', () => {
            const res = {};
            expect(safeDivide(10, 0, res)).toBe(res);
            expect(safeDivide(0, 10, res)).toBe(0);
        });
    });

    describe('WarningHeader', () => {
        describe('.fromWarningStr', () => {
            it('should work for simple single warnings', () => {
                expect(WarningHeader.fromWarningStr('14 C "Hello warning"')).toEqual({
                    messages: [{
                        code: 14,
                        agent: 'C',
                        text: 'Hello warning',
                    }],
                });
            });

            it('should work for multiple simple warnings', () => {
                expect(WarningHeader.fromWarningStr('14 C "Hello warning", 15 C "W2"')).toEqual({
                    messages: [{
                        code: 14,
                        agent: 'C',
                        text: 'Hello warning',
                    }, {
                        code: 15,
                        agent: 'C',
                        text: 'W2',
                    }],
                });
            });

            it('should work for difficult warnings', () => {
                const warningStr = '14 C_C ",\\"WARN\\\\ING\\\\", 14 C ",,"';
                expect(WarningHeader.fromWarningStr(warningStr)).toEqual({
                    messages: [{
                        code: 14,
                        agent: 'C_C',
                        text: ',"WARN\\ING\\',
                    }, {
                        code: 14,
                        agent: 'C',
                        text: ',,',
                    }],
                });
            });

            it('should return the same if passed a WarningHeader', () => {
                const res = WarningHeader.fromWarningStr('14 C "?asdfasd"');
                expect(WarningHeader.fromWarningStr(res)).toBe(res);
            });
        })

        describe('.fromResponse', () => {
            it('should work when passed null', () => {
                expect(WarningHeader.fromResponse(null)).toEqual({
                    messages: [],
                });
            });

            it('should work when a response', () => {
                expect(WarningHeader.fromResponse({ headers: { warning: '14 c "d"'}})).toEqual({
                    messages: [{
                        code: 14,
                        agent: 'c',
                        text: 'd',
                    }],
                });
            });
        });

        describe('.merge', () => {
            const base = WarningHeader.fromWarningStr('14 c "d"');

            it('should work when passed a string', () => {
                expect(base.merge('15 d "c"')).toEqual({
                    messages: [{
                        code: 14,
                        agent: 'c',
                        text: 'd'
                    }, {
                        code: 15,
                        agent: 'd',
                        text: 'c'
                    }],
                });
            });

            it('should work when passed a WarningHeader', () => {
                expect(base.merge(WarningHeader.fromWarningStr('15 d "c"'))).toEqual({
                    messages: [{
                        code: 14,
                        agent: 'c',
                        text: 'd'
                    }, {
                        code: 15,
                        agent: 'd',
                        text: 'c'
                    }],
                });
            });

            it('should work when passed a response', () => {
                expect(base.merge({ headers: { warning: '14 c "c"' } })).toEqual({
                    messages: [{
                        code: 14,
                        agent: 'c',
                        text: 'd'
                    }, {
                        code: 14,
                        agent: 'c',
                        text: 'c'
                    }],
                });
            });

            it('should create a new object every time', () => {
                const msgs = deepCopy(base.messages);
                base.merge(base);
                expect(base.messages).toEqual(msgs);
            });
        });
    });

    describe('setProps', () => {
        it('should work when the key is not there yet', () => {
            let obj = {};
            let value = {};
            setProps(obj, value, '1', '2', '3', '4');
            expect(obj).toEqual({
                1: {
                    2: {
                        3: {
                            4: value,
                        }
                    }
                }
            })
            expect(obj[1][2][3][4]).toBe(value);
        });

        it('should work when a part of the path is there', () => {
            let obj = {};
            let value = {1: { 2: { }}};
            setProps(obj, value, '1', '2', '3', '4');
            expect(obj).toEqual({
                1: {
                    2: {
                        3: {
                            4: value,
                        }
                    }
                }
            })
            expect(obj[1][2][3][4]).toBe(value);
        });

        it('should throw when the given object is null', () => {
            expect(() => setProps(null, 5, 1)).toThrow(Error);
        });
    });

    describe('coerceToString', () => {
        it('should work for strings', () => {
            expect(coerceToString('abc')).toBe('abc');
        });

        it('should work for null', () => {
            expect(coerceToString(null)).toBe('');
        });

        it('should work for objects', () => {
            expect(coerceToString(true)).toBe('true');

            expect(coerceToString({})).toBe('[object Object]');
            expect(coerceToString({ toString() { return 'abc'; }})).toBe('abc');
        });

        it('should work for numbers', () => {
            expect(coerceToString(-1)).toBe('-1');
            expect(coerceToString(15.555)).toBe('15.555');
            expect(coerceToString(0)).toBe('0');
            expect(coerceToString(1)).toBe('1');
        });
    });

    describe('getNoNull', () => {
        const obj1 = {};
        const obj2 = {};

        it('should work when it is in the first obj', () => {
            expect(getNoNull('a', {a: obj1}, {a: obj2})).toBe(obj1);
        });
        it('should work when it is not the first obj', () => {
            expect(getNoNull('b', {a: obj1}, null, {b: obj2})).toBe(obj2);
        });
        it('should return null if it is not found', () => {
            expect(getNoNull('c', {a: obj1}, null, {b: obj2})).toBe(null);
        });
    });

    describe('numberToTimes', () => {
        it('should work with 1', () => expect(numberToTimes(1)).toBe('once'));

        it('should work with 2', () => expect(numberToTimes(2)).toBe('twice'));

        it('should work with other numbers', () => {
            expect(numberToTimes(3)).toBe('3 times');
            expect(numberToTimes(15)).toBe('15 times');
        });

        it('should throw for non numbers', () => {
            expect(() => numberToTimes('five')).toThrow();
        });
    });

    describe('toMaxNDecimals', () => {
        it('should work', () => {
            [
                [0.5, 2, '0.5'],
                [0.025, 3, '0.025'],
                [0.25, 1, '0.3'],
                [0.5, 0, '1'],
                [150, 0, '150'],
                [150, 50, '150'],
                [null, 0, null],
            ].forEach(([input, n, result]) => {
                expect(toMaxNDecimals(input, n)).toBe(result);
            })
        })
    });

    describe('cmpNoCaseMany', () => {
        it('should work when the first option is different', () => {
            expect(cmpNoCaseMany(['a', 'b'], ['a', 'a'])).toBe(-1);
            expect(cmpNoCaseMany(['b', 'a'], ['a', 'a'])).toBe(1);
        });

        it('should work when the second option is different', () => {
            expect(cmpNoCaseMany(['a', 'a'], ['a', 'B'], ['B', 'a'])).toBe(-1);
        });

        it('should work when the all options are the same', () => {
            expect(cmpNoCaseMany(['a', 'a'], ['a', 'A'], ['A', 'a'])).toBe(0);
        });
    });

    describe('setXor', () => {
        it('should return all elements that are in A or in B but not in both', () => {
            const A = new Set([1, 2, 3]);
            const B = new Set([3, 4, 5]);
            expect(setXor(A, B)).toEqual(new Set([1, 2, 4, 5]));
        });

        it('should return a copy of B if A is empty', () => {
            const A = new Set();
            const B = new Set([1, 2, 3]);
            expect(setXor(A, B)).toEqual(B);
        });

        it('should return a copy of A if B is empty', () => {
            const A = new Set([1, 2, 3]);
            const B = new Set();
            expect(setXor(A, B)).toEqual(A);
        });
    });

    describe('ensureArray', () => {
        it('should return an array untouched', () => {
            expect(ensureArray([])).toEqual([]);
            expect(ensureArray([1, 2, 3])).toEqual([1, 2, 3]);

            const a = [];
            a[0] = a;
            expect(ensureArray(a)).toBe(a);
        });

        it('should wrap anything other than an array', () => {
            expect(ensureArray(null)).toEqual([null]);
            expect(ensureArray(3)).toEqual([3]);
            expect(ensureArray()).toEqual([undefined]);
        });
    });

    describe('deepEquals', () => {
        it('should return true if the contents of two objects are equal', () => {
            expect(deepEquals({a: 3}, {a: 3})).toBeTrue();
            expect(deepEquals({a: 3, b: 3}, {a: 3, b: 3})).toBeTrue();
            expect(deepEquals({a: 3, b: {c: 3}}, {a: 3, b: {c: 3}})).toBeTrue();
        });

        it('should return false if the contents of two objects are equal', () => {
            expect(deepEquals({a: 3}, {b: 3})).toBeFalse();
            expect(deepEquals({a: 3}, {a: 3, b: 3})).toBeFalse();
            expect(deepEquals({a: 3, b: 3}, {a: 3})).toBeFalse();
        });

        it('should not throw when it encounters a null', () => {
            expect(deepEquals(null, null)).toBeTrue();
            expect(deepEquals({a: null}, {a: null})).toBeTrue();

            expect(deepEquals({a: 3}, null)).toBeFalse();
            expect(deepEquals({a: null}, null)).toBeFalse();
        });

        it('should also work for arrays', () => {
            expect(deepEquals([1, 2, 3], [1, 2, 3])).toBeTrue();
            expect(deepEquals({a: [1, 2, 3]}, {a: [1, 2, 3]})).toBeTrue();
            expect(deepEquals([{a: 3}], [{a: 3}])).toBeTrue();

            expect(deepEquals([1, 2, 3], [1, 2, 4])).toBeFalse();
        });

        it('should also work for primitive values', () => {
            expect(deepEquals(1, 1)).toBeTrue();
            expect(deepEquals("abc", "abc")).toBeTrue();

            expect(deepEquals(1, 2)).toBeFalse();
            expect(deepEquals("abc", "def")).toBeFalse();
        });
    });

    describe('deepExtend', () => {
        it('should recursively extend objects', () => {
            expect(deepExtend({a: 3}, {b: 3})).toEqual({a: 3, b: 3});
            expect(deepExtend({a: 3, c: 3}, {b: 3})).toEqual({a: 3, b: 3, c: 3});
            expect(deepExtend({a: {b: 3}}, {b: 3})).toEqual({a: {b: 3}, b: 3});
            expect(deepExtend({a: {b: 3}}, {a: {b: 3}})).toEqual({a: {b: 3}});
            expect(deepExtend({a: {b: 3}}, {a: {c: 3}})).toEqual({a: {b: 3, c: 3}});
        });

        it('should overwrite keys in earlier arguments with keys in later arguments', () => {
            expect(deepExtend({a: 3}, {a: 4})).toEqual({a: 4});
            expect(deepExtend({a: 3, b: 3}, {b: 4})).toEqual({a: 3, b: 4});
            expect(deepExtend({a: {b: 3}}, {a: 3})).toEqual({a: 3});
            expect(deepExtend({a: 3}, {a: {b: 3}})).toEqual({a: {b: 3}});
            expect(deepExtend({a: {b: 3}}, {a: {b: 4}})).toEqual({a: {b: 4}});
            expect(deepExtend({a: {b: 3}}, {a: {b: 4}})).toEqual({a: {b: 4}});
        });

        it('should throw when the target is not an object', () => {
            const dext = tgt => () => deepExtend(tgt, {a: 3});

            expect(dext(null)).toThrow();
            expect(dext(1)).toThrow();
            expect(dext("abc")).toThrow();
        });

        it('should throw if any of the sources is null', () => {
            expect(() => deepExtend({a: 3}, null)).toThrow();
        });

        // TODO: Do we want this behaviour?
        it('should not throw if any of the sources is a primitive value', () => {
            expect(deepExtend({a: 3}, 1)).toEqual({a: 3});
            expect(deepExtend({a: 3}, true)).toEqual({a: 3});
        });

        it('should not throw when it encounters a null', () => {
            expect(deepExtend({a: 3}, {b: null})).toEqual({a: 3, b: null});
            expect(deepExtend({a: null}, {a: 3})).toEqual({a: 3});
        });

        it('should treat arrays as standard values and not recurse into them', () => {
            expect(deepExtend({a: [1, 2, 3]}, {a: [4, 5, 6]})).toEqual({a: [4, 5, 6]});
            expect(deepExtend({a: [{b: 3}]}, {a: [{c: 4}]})).toEqual({a: [{c: 4}]});
        });
    });

    describe('deepExtendArray', () => {
        it('should recursively extend objects', () => {
            expect(deepExtendArray({a: 3}, {b: 3})).toEqual({a: 3, b: 3});
            expect(deepExtendArray({a: 3, c: 3}, {b: 3})).toEqual({a: 3, b: 3, c: 3});
            expect(deepExtendArray({a: {b: 3}}, {b: 3})).toEqual({a: {b: 3}, b: 3});
            expect(deepExtendArray({a: {b: 3}}, {a: {b: 3}})).toEqual({a: {b: 3}});
            expect(deepExtendArray({a: {b: 3}}, {a: {c: 3}})).toEqual({a: {b: 3, c: 3}});
        });

        it('should overwrite keys in earlier arguments with keys in later arguments', () => {
            expect(deepExtendArray({a: 3}, {a: 4})).toEqual({a: 4});
            expect(deepExtendArray({a: 3, b: 3}, {b: 4})).toEqual({a: 3, b: 4});
            expect(deepExtendArray({a: {b: 3}}, {a: 3})).toEqual({a: 3});
            expect(deepExtendArray({a: 3}, {a: {b: 3}})).toEqual({a: {b: 3}});
            expect(deepExtendArray({a: {b: 3}}, {a: {b: 4}})).toEqual({a: {b: 4}});
            expect(deepExtendArray({a: {b: 3}}, {a: {b: 4}})).toEqual({a: {b: 4}});
        });

        it('should throw when the target is not an object', () => {
            const dext = tgt => () => deepExtendArray(tgt, {a: 3});

            expect(dext(null)).toThrow();
            expect(dext(1)).toThrow();
            expect(dext("abc")).toThrow();
        });

        it('should throw if any of the sources is null', () => {
            expect(() => deepExtendArray({a: 3}, null)).toThrow();
        });

        // TODO: Do we want this behaviour?
        it('should not throw if any of the sources is a primitive value', () => {
            expect(deepExtendArray({a: 3}, 1)).toEqual({a: 3});
            expect(deepExtendArray({a: 3}, true)).toEqual({a: 3});
        });

        it('should not throw when it encounters a null', () => {
            expect(deepExtendArray({a: 3}, {b: null})).toEqual({a: 3, b: null});
            expect(deepExtendArray({a: null}, {a: 3})).toEqual({a: 3});
        });

        it('should recurse into arrays', () => {
            expect(deepExtendArray({a: [1, 2, 3]}, {a: [4, 5, 6]})).toEqual({a: [4, 5, 6]});
            expect(deepExtendArray({a: [1, 2, 3, 4, 5, 6]}, {a: [4, 5, 6]})).toEqual({a: [4, 5, 6, 4, 5, 6]});
            expect(deepExtendArray({a: [{b: 3}]}, {a: [{c: 4}]})).toEqual({a: [{b: 3, c: 4}]});
        });
    });

    describe('hasAttr', () => {
        it('should return true if the given key is in the object', () => {
            expect(hasAttr({a: 3}, 'a')).toBeTrue();
            const o = Object.defineProperty({}, 'a', { enumerable: true, value: 3 });
            expect(hasAttr(o, 'a')).toBeTrue();
        });

        it('should return true even if the key is not enumerable', () => {
            const o = Object.defineProperty({}, 'a', { value: 3 });
            expect(hasAttr(o, 'a')).toBeTrue();
        });

        it('should return false if the object does not have the property', () => {
            expect(hasAttr({a: 3}, 'b')).toBeFalse();
            const o = Object.defineProperty({}, 'a', { value: 3 });
            expect(hasAttr(o, 'b')).toBeFalse();
        });

        it('should throw an error if the target is null', () => {
            expect(() => hasAttr(null, 'a')).toThrow();
        });

        // TODO: Do we want this behaviour?
        it('should not throw an error if the target is not an object', () => {
            expect(hasAttr(3, 'a')).toBeFalse();
            expect(hasAttr('abc', 'a')).toBeFalse();
        });
    });

    describe('mapObject', () => {
        const id = x => x;

        it('should return a new object', () => {
            const o = {};
            expect(mapObject(o, id)).not.toBe(o);
        });

        it('should return an equal object when mapping the identity function', () => {
            const o = {a: 3, b: {c: 3}};
            expect(mapObject(o, id)).toEqual(o);
        });

        it('should map over the values of the object', () => {
            const o = mapObject({a: 1, b: 2, c: 3}, v => {
                expect(v).toBeNumber();
                return 2 * v;
            });
            expect(o).toEqual({a: 2, b: 4, c: 6});
        });

        it('should pass the key as the second argument', () => {
            const o = {a: 'a', b: 'b', c: 'c'};
            mapObject(o, (v, k) => {
                expect(v).toEqual(k);
            });
        });

        it('should throw an error when mapping over null', () => {
            expect(() => {
                mapObject(null, id);
            }).toThrow();
        });
    });

    describe('filterObject', () => {
        const id = x => x;

        it('should return a new object', () => {
            const o = {};
            expect(filterObject(o, id)).not.toBe(o);
        });

        it('should filter over the values in the object', () => {
            const o = filterObject({a: 1, b: 2, c: 3 }, v => {
                expect(v).toBeNumber();
                return v % 2;
            });
            expect(o).toEqual({a: 1, c: 3});
        });

        it('should pass the key as the second argument', () => {
            const o = {a: 'a', b: 'b', c: 'c'};
            filterObject(o, (v, k) => {
                expect(v).toEqual(k);
            });
        });

        it('should throw an error when filtering null', () => {
            expect(() => {
                filterObject(null, id);
            }).toThrow();
        });
    });

    describe('zip', () => {
        it('should zip lists', () => {
            expect(zip([1, 2, 3], [1, 2, 3])).toEqual([[1, 1], [2, 2], [3, 3]]);
        });

        it('should zip up to the end of the shortest list', () => {
            expect(zip([1], [1, 2, 3])).toEqual([[1, 1]]);
        });

        it('should accept an arbitrary number of lists', () => {
            expect(zip([1, 2, 3], [1, 2, 3], [1, 2, 3])).toEqual([
                [1, 1, 1],
                [2, 2, 2],
                [3, 3, 3],
            ]);
        });

        it('should not throw or loop forever when given an empty list', () => {
            expect(zip()).toEqual([]);
        });

        it('should not throw when given a single list', () => {
            expect(zip([1, 2, 3])).toEqual([[1], [2], [3]]);
        });
    });

    describe('isEmpty', () => {
        it('should return true for objects without keys', () => {
            expect(isEmpty({})).toBeTrue();
        });

        it('should return true for arrays without elements', () => {
            expect(isEmpty([])).toBeTrue();
            expect(isEmpty(Array(0))).toBeTrue();
        });

        it('should return true for null and undefined', () => {
            expect(isEmpty(null)).toBeTrue();
            expect(isEmpty(undefined)).toBeTrue();
        });

        it('should return true for falsey primitives', () => {
            expect(isEmpty(false)).toBeTrue();
            expect(isEmpty(0)).toBeTrue();
            expect(isEmpty('')).toBeTrue();
        });

        it('should return false otherwise', () => {
            expect(isEmpty({a: 3})).toBeFalse();
            expect(isEmpty([1])).toBeFalse();
            expect(isEmpty(true)).toBeFalse();
            expect(isEmpty(1000)).toBeFalse();
            expect(isEmpty('abc')).toBeFalse();
        });
    });

    describe('readableJoin', () => {
        it('should work for empty arrays', () => {
            expect(readableJoin([])).toBe('');
        });

        it('should work for arrays with 1 item', () => {
            expect(readableJoin(['hello'])).toBe('hello');
        });

        it('should work for arrays with multiple items', () => {
            expect(readableJoin(['hello', 'by', 'whoo'])).toBe('hello, by, and whoo');
        });

        it('should use its second optional sep argument', () => {
            expect(readableJoin(['hello', 'by', 'whoo'], 'or')).toBe('hello, by, or whoo');
        });
    });

    describe('buildUrl', () => {
        it('should be possible to give the path a raw string', () => {
            expect(buildUrl('/a/b/c')).toBe('/a/b/c');
            expect(buildUrl('a/b/')).toBe('a/b/');
        }),

        it('should give an absolute url if no host is given', () => {
            expect(buildUrl(['a', 'b', 'c'])).toBe('/a/b/c');
            expect(buildUrl(['a', 'b', ''])).toBe('/a/b/');
            expect(buildUrl(['a', 'b'], {
                addTrailingSlash: true,
            })).toBe('/a/b/');
        }),

        it('should escape parts of the url', () => {
            expect(buildUrl(['a', '%b%'])).toBe('/a/%25b%25');
        });

        it('should escape the query of the url', () => {
            expect(buildUrl(
                ['a', 'b'],
                { query: { a: '%b%' }},
            )).toBe('/a/b?a=%25b%25');
        });

        it('should escape the given hash', () => {
            expect(buildUrl(
                ['a', 'b', ''],
                { hash: 'ah#ah'},
            )).toBe('/a/b/#ah%23ah');
        });

        it('should use the host if given', () => {
            expect(buildUrl(
                ['a', 'b'],
                {
                    host: 'example.com',
                    protocol: 'ftp:',
                },
            )).toBe('ftp://example.com/a/b');

            expect(buildUrl(
                'a/b',
                {
                    host: 'example.com',
                    protocol: 'ftp:',
                },
            )).toBe('ftp://example.com/a/b');
        });
    });

    describe('sortBy', () => {
        const today = moment();
        const tomorrow = today.clone().add(1, 'd');
        const yesterday = today.clone().add(-1, 'd');
        const xs = [1, 7, 2, 9, 3, 4, 8, 0, 6, 5];

        it('should sort correctly', () => {
            const oldXs = xs.slice();
            expect(
                sortBy(xs, x => [x]),
            ).toEqual(
                xs.slice().sort(),
            );
            // Should not mutate array in place
            expect(oldXs).toEqual(xs);
        });

        it('should sort by later keys if former were equal', () => {
            expect(
                sortBy(xs.slice(), x => [x % 2, x]),
            ).toEqual(
                [0, 2, 4, 6, 8, 1, 3, 5, 7, 9],
            );
        });

        it('should be stable in sorting', () => {
            expect(
                sortBy(xs.slice(), x => [1]),
            ).toEqual(xs);
        });

        it('should support sorting booleans with duplicated', () => {
            expect(
                sortBy(xs, x => [x % 2 != 0]),
            ).toEqual(
                [2, 4, 8, 0, 6, 1, 7, 9, 3, 5],
            );
        });

        it('should support sorting strings', () => {
            expect(
                sortBy(['A', 'B', 'AA', 'BB'], x => [x]),
            ).toEqual(
                ['A', 'AA', 'B', 'BB'],
            );
        });

        it('should support sorting moments', () => {
            expect(
                sortBy([today, tomorrow, yesterday], x => [x]),
            ).toEqual(
                [yesterday, today, tomorrow],
            );
        });

        it('should support reversing', () => {
            expect(sortBy(xs, x => [x], {
                reverse: true
            })).toEqual(xs.slice().sort().reverse());
        });

        it('should support reversing specific keys', () => {
            const values = [0, 2, 4, 6, 8, 10, 1, 5];
            const keyFunc = x => [x % 2 != 0, x % 5 != 0];

            expect(sortBy(values, keyFunc, {
                reversePerKey: [true, false]
            })).toEqual([5, 1, 0, 10, 2, 4, 6, 8]);
            expect(sortBy(values, keyFunc, {
                reversePerKey: [false, false]
            })).toEqual([0, 10, 2, 4, 6, 8, 5, 1]);
            expect(sortBy(values, keyFunc, {
                reversePerKey: [false, false],
                // reverse should be overridden
                reverse: true,
            })).toEqual([0, 10, 2, 4, 6, 8, 5, 1]);
        });

        it('reverse should also be stable', () => {
            // Should keep same order, as the key was the same for every item.
            expect(sortBy(xs, x => [1], {
                reverse: true,
            })).toEqual(xs);
        });

        it('Test sorting multiple keys', () => {
            // Should keep same order, as the key was the same for every item.
            expect(sortBy([0, 1, 2], x => [-x, x])).toEqual([2, 1, 0]);
            expect(sortBy([0, 1, 2], x => [x, -x])).toEqual([0, 1, 2]);
        });

        it('should be possible to sort something complex', () => {
            // This test also tests the sorting algorithm defined in
            // `src/components/AutoTestRun.vue::sortedResults` So when this test
            // fails and you need to update the `makeKey` function make sure you
            // copy your changed.
            const results = [{
                idx: 0,
                state: 'running',
                startedAt: today.toISOString(),
            }, {
                idx: 1,
                state: 'done',
                startedAt: yesterday.toISOString(),
            }, {
                idx: 2,
                state: 'failed',
            }, {
                idx: 3,
                state: 'running',
                startedAt: yesterday.toISOString(),
            }, {
                idx: 4,
                state: 'not_started',
            }, {
                idx: 5,
                state: 'done',
                startedAt: tomorrow.toISOString(),
            }]
            const stateMap = {
                running: 1,
                failed: 2,
                skipped: 3,
                timed_out: 4,
                not_started: 5,
                done: 10,
            };
            const res = sortBy(results, result => {
                const { startedAt: startedAtAsString, state } = result;
                const startedAt = toMoment(startedAtAsString);

                return [
                    stateMap[state] || 0,
                    !!startedAt,
                    // We want the done results to be sorted latest first, but
                    // the running ones we want the oldest first. It is possible
                    // that `startedAt` is `null` here, but because the previous
                    // key already sorts on that the actual value used when
                    // `startedAt` is `null` doesn't matter here.
                    (startedAt ? startedAt.valueOf() : 0) * (state === 'done' ? -1 : 1),
                ];
            });
            expect(res.map(x => x.idx)).toEqual([3, 0, 2, 4, 5, 1]);
        })
    });

    describe('formatTimePart', () => {
        it('should work for numbers larger than 10', () => {
            expect(typeof formatTimePart(50)).toBe('string');
            expect(formatTimePart(50)).toBe('50');
        });

        it('should work for numbers smaller than 10', () => {
            expect(typeof formatTimePart(2)).toBe('string');
            expect(formatTimePart(5)).toBe('05');
        });

        it('should pad integers in the range [0, 60) to a length of 2', () => {
            for (let x = 0; x < 60; x++) {
                const y = formatTimePart(x);
                expect(typeof y).toBe('string');
                expect(y).toMatch(/^\d\d$/);
                expect(parseInt(y, 10)).toBe(x);
            }
        });
    })

    describe('parseOrKeepFloat', () => {
        it('should return its argument if it is a number', () => {
            const x = Math.random();
            const y = 1000000 * Math.random();

            expect(parseOrKeepFloat(x)).toBe(x);
            expect(parseOrKeepFloat(y)).toBe(y);
            expect(parseOrKeepFloat(x * y)).toBe(x * y);
        });

        it.each([
            ['0', 0],
            ['+0', 0],
            ['-0', -0],
            ['1', 1],
            ['+1', 1],
            ['-1', -1],
            ['0.1', 0.1],
            ['+0.1', 0.1],
            ['-0.1', -0.1],
            ['.25', 0.25],
            ['+.25', 0.25],
            ['-.25', -0.25],
            ['3.', 3],
            ['+3.', 3],
            ['-3.', -3],
            ['5e2', 5e2],
            ['5E2', 5E2],
        ])('should accept correctly formatted string "%s" with value "%f"', (x, expected) => {
            expect(parseOrKeepFloat(x)).toBe(expected);
        });

        it.each([
            '',
            '-',
            'abc',
            '5a',
            '-5a',
            '5a2',
            'a5',
            'e52',
            '..3',
            '3.4.5',
        ])('should return NaN when input is not formatted correctly: "%s"', (x) => {
            expect(parseOrKeepFloat(x)).toBeNaN();
        });

        it.each([
            null,
            true,
            false,
            {},
            [],
            {a: []},
            [{}],
            {key: null},
            [null],
        ])('should return NaN when the input is not a number or a string: "%p"', (x) => {
            expect(parseOrKeepFloat(x)).toBeNaN();
        });
    });

    describe('pickKeys', () => {
        it('should return a new object', () => {
            const a = { id: 1 };
            const b = pickKeys(a, ['id']);

            expect(b).not.toBe(a);
            expect(b).toEqual(a);
        });

        it('should pick all the given keys', () => {
            const a = { id: 1 };
            const b = pickKeys(a, ['id', 'a']);

            expect(b).toHaveProperty('id');
            expect(b.id).toBe(a.id);

            expect(b).toHaveProperty('a');
            expect(b.a).toBeUndefined();
        });

        it('should not pick keys that are not present if strict is false', () => {
            const a = { id: 1 };
            const b = pickKeys(a, ['id', 'a'], false);

            expect(b).toHaveProperty('id');
            expect(b.id).toBe(a.id);

            expect(b).not.toHaveProperty('a');
        });

        it('should pick keys that are present and have value undefined if strict is false', () => {
            const a = { id: undefined };
            const b = pickKeys(a, ['id'], false);

            expect(b).toHaveProperty('id');
            expect(b.a).toBeUndefined();
        });
    });
});

describe('cache.js', () => {
    describe('makeCache', () => {
        it('should return a frozen object', () => {
            const c = makeCache();
            expect(c).toBeFrozen();
        });

        describe('_cache', () => {
            it('should be sealed', () => {
                const c = makeCache();
                expect(c._cache).toBeSealed();
            });

            it('should include the given keys in its inner store', () => {
                const c = makeCache('a', 'b');
                expect(Object.keys(c._cache)).toEqual(['a', 'b']);
            });

            it('should initialize each key with UNSET_SENTINEL', () => {
                const c = makeCache('a', 'b');
                expect(Object.values(c._cache)).toEqual([UNSET_SENTINEL, UNSET_SENTINEL]);
            });
        });

        describe('get', () => {
            it('should call its second argument if the key is not present', () => {
                const c = makeCache('a');
                const f = jest.fn(() => 1);

                expect(c.get('a', f)).toBe(1);
                expect(f).toBeCalled();
            });

            it('should not call the function more than once', () => {
                const c = makeCache('a');
                const f = jest.fn(() => 1);
                c.get('a', f);
                c.get('a', f);

                expect(f).toBeCalledTimes(1);
            });

            it('should keep returning the cached value', () => {
                const c = makeCache('a');
                const a = c.get('a', () => 1);
                const b = c.get('a', () => 2);

                expect(a).toBe(1);
                expect(b).toBe(1);
            });
        });
    });
});

describe('counter.js', () => {
    describe('Counter', () => {
        const obj1 = {};
        const obj2 = {};
        let c1 = new Counter([1, 2, '3', '4', '4', 1, obj1, obj1, obj2])

        it('should work for simple keys', () => {
            expect(c1.getCount(1)).toBe(2);
            expect(c1.getCount(2)).toBe(1);
            expect(c1.getCount('3')).toBe(1);
            expect(c1.getCount('4')).toBe(2);
        });

        it('should work for object keys', () => {
            expect(c1.getCount(obj1)).toBe(2);
            expect(c1.getCount(obj2)).toBe(1);
        });

        it('should work missing keys', () => {
            expect(c1.getCount(4)).toBe(0);
            expect(c1.getCount({})).toBe(0);
            expect(c1.getCount('1')).toBe(0);
            expect(c1.getCount(0)).toBe(0);
        });
    })
});

describe('defaultdict.js', () => {
    describe('defaultdict', () => {
        it('should return the default value if a key does not exist', () => {
            const d = defaultdict(() => 0);

            expect(d.xyz).toBe(0);
            expect(d[0]).toBe(0);
            expect(d[null]).toBe(0);
        });

        it('should be possible to set values', () => {
            const d = defaultdict(() => 0);
            d.xyz = 3;
            d[0] = 3;
            d[null] = 3;

            expect(d.xyz).toBe(3);
            expect(d[0]).toBe(3);
            expect(d[null]).toBe(3);
        });

        it('should be possible to increment missing values', () => {
            const d = defaultdict(() => 0);
            d.x++;

            expect(d.x).toBe(1);
        });

        it('should throw on the first missing key when the argument is not a function', () => {
            const d = defaultdict(0);

            expect(() => {
                d.x;
            }).toThrow();
        });
    });
});
