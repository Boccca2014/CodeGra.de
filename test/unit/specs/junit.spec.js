/* SPDX-License-Identifier: AGPL-3.0-only */
import fs from 'fs';
import decodeBuffer from '@/utils/decode';

import { CGJunit } from '@/utils/junit';

function fixture(path) {
    return fs.readFileSync(`${__dirname}/../../../test_data/test_junit_xml/${path}`, null);
}

describe('CGJunit', () => {
    it.each([
        'valid.xml',
        'valid_many_errors.xml',
        'valid_system_out.xml',
    ])('should work with a valid JUnit XML file', (xmlFile) => {
        const xml = fixture(xmlFile);
        const res = CGJunit.fromXml('1', xml);

        expect(res).toBeInstanceOf(CGJunit);
        expect(res.suites).toBeArray();
        expect(res.suites).not.toHaveLength(0);

        for (let suite of res.suites) {
            expect(suite.cases).toBeArray();
            expect(suite.cases).not.toHaveLength(0);
            expect(suite.successful).toBeNumber();
            expect(suite.failures).toBeNumber();
            expect(suite.errors).toBeNumber();
            expect(suite.totalTests).toBeNumber();
            expect(suite.successful + suite.failures + suite.errors).toBe(suite.totalTests);

            for (let c of suite.cases) {
                expect(c.state).not.toBe('unknown');

                if (c.state === 'success') {
                    expect(c.content.extract()).toBeUndefined();
                } else {
                    expect(c.content.extract()).toBeArray();
                    expect(c.content.extract()).not.toHaveLength(0);
                }

                expect(c.fontAwesomeIcon).toEqual(
                    expect.objectContaining({
                        icon: expect.any(String),
                        cls: expect.any(String),
                    }),
                );
            }
        }
    });

    it('should work with weights', () => {
        const xml = fixture('valid_with_weight.xml');
        const res = CGJunit.fromXml('1', xml);
        expect(res.suites[0].weight).toBe(1);
        expect(res.suites[1].weight).toBe(3);

        expect(res.suites[0].successful).toBe(4);
        expect(res.suites[0].totalTests).toBe(5);
        expect(res.suites[0].runTests).toBe(5);
        expect(res.suites[0].failures).toBe(1);

        expect(res.suites[1].successful).toBe(3);
        expect(res.suites[1].runTests).toBe(3);
        expect(res.suites[1].totalTests).toBe(3);
        expect(res.suites[1].failures).toBe(0);
    });

    it('should work when the state of a case is invalid', () => {
        const xml = fixture('valid_unknown_state.xml');
        const res = CGJunit.fromXml('1', xml);

        expect(res).toBeInstanceOf(CGJunit);
        expect(res.suites[0].cases[0].state).toBe('unknown');
    });

    it('should work when the the number of skipped tests is not given', () => {
        const xml = fixture('valid_no_skipped.xml');
        const res = CGJunit.fromXml('1', xml);

        expect(res).toBeInstanceOf(CGJunit);
        expect(res.suites[0].skipped).toBe(0);
    });

    it('should work when there is only a single top-level <testsuite> tag', () => {
        const xml = fixture('valid_no_testsuites_tag.xml');
        const res = CGJunit.fromXml('1', xml);

        expect(res).toBeInstanceOf(CGJunit);
        expect(res.suites).toBeArray();
        expect(res.suites).toHaveLength(1);
    });

    it('should not work when the XML is invalid', () => {
        const xml = fixture('invalid_xml.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/unclosed tag/i);

        const python = fixture('../test_submissions/hello.py');

        expect(() => {
            CGJunit.fromXml('1', python);
        }).toThrow(/text data outside of root node/i);
    });

    it('should not work when the top level tag is not "testsuites"', () => {
        const xml = fixture('invalid_top_level_tag.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow();
    });

    it('should not work when a suite\'s failures does not match the <failure> nodes', () => {
        const xml = fixture('invalid_mismatch_failures.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Amount of failures does not match/);
    });

    it('should not work when a suite\'s errors does not match the <error> nodes', () => {
        const xml = fixture('invalid_mismatch_errors.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Amount of errors does not match/);
    });

    it('should not work when a suite\'s skipped cases does not match the <skipped> nodes', () => {
        const xml = fixture('invalid_mismatch_skipped.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Amount of skipped cases does not match/);
    });

    it('should not work when a case is missing the "classname" attribute', () => {
        const xml = fixture('invalid_missing_case_classname_attr.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Attribute classname not found/);
    });

    it('should not work when a case is missing the "name" attribute', () => {
        const xml = fixture('invalid_missing_case_name_attr.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Attribute name not found/);
    });

    it('should not work when a suite is missing the "failures" attribute', () => {
        const xml = fixture('invalid_missing_failures_attr.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Attribute failures not found/);
    });

    it('should not work when a suite is missing the "errors" attribute', () => {
        const xml = fixture('invalid_missing_errors_attr.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Attribute errors not found/);
    });

    it('should not work when a suite is m issing the "name" attribute', () => {
        const xml = fixture('invalid_missing_name_attr.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Attribute name not found/);
    });

    it('should not work when a suite is m issing the "tests" attribute', () => {
        const xml = fixture('invalid_missing_tests_attr.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow(/Attribute tests not found/);
    });

    it('should not work when the XML is valid but not JUnit-compatible', () => {
        const xml = fixture('invalid_valid_xml_but_not_junit.xml');

        expect(() => {
            CGJunit.fromXml('1', xml);
        }).toThrow();
    });
});
