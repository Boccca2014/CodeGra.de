/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';

import { hasAttr, getProps } from './typed';

export * from './typed';

export function convertToUTC(timeStr) {
    return moment(timeStr, moment.ISO_8601)
        .utc()
        .format('YYYY-MM-DDTHH:mm');
}

export function setProps(object, value, ...props) {
    if (object == null) {
        throw new Error('Given object to set props on is null');
    }
    const lastProp = props.pop();
    let inner = object;

    for (let i = 0; i < props.length; ++i) {
        if (inner[props[i]] == null) {
            inner[props[i]] = {};
        }
        inner = inner[props[i]];
    }

    inner[lastProp] = value;
}

export class WarningHeader {
    static fromWarningStr(warningStr) {
        if (warningStr instanceof WarningHeader) {
            return warningStr;
        } else if (!warningStr) {
            return new WarningHeader([]);
        }

        let startIndex = 0;
        const res = [];
        const len = warningStr.length;

        function consume(part) {
            const arr = part.split(' ');

            const code = parseFloat(arr[0]);
            const agent = arr[1];
            const text = arr
                .slice(2)
                .join(' ')
                .replace(/\\(.)/g, '$1')
                .slice(1, -1);

            return { code, agent, text };
        }

        for (let i = 0, seenQuote = false; i < len; ++i) {
            const cur = warningStr.charAt(i);
            if (cur === '"') {
                if (seenQuote) {
                    res.push(consume(warningStr.slice(startIndex, i + 1)));
                    // Next char is a comma and then a space
                    startIndex = i + 3;
                    seenQuote = false;
                } else {
                    seenQuote = true;
                }
            } else if (cur === '\\') {
                // Skip next char
                i++;
            }
        }

        return new WarningHeader(res);
    }

    static fromResponse(response) {
        const warningStr = getProps(response, null, 'headers', 'warning');

        return WarningHeader.fromWarningStr(warningStr);
    }

    constructor(warnings) {
        this.messages = Object.freeze(warnings);
        Object.freeze(this);
    }

    merge(obj) {
        let other;
        if (other instanceof WarningHeader) {
            other = obj;
        } else if (obj.headers) {
            other = WarningHeader.fromResponse(obj);
        } else if (obj) {
            other = WarningHeader.fromWarningStr(obj);
        } else {
            return new WarningHeader(this.messages);
        }
        return new WarningHeader(this.messages.concat(other.messages));
    }
}

export function isDecimalNumber(val) {
    if (typeof val === 'number' || val instanceof Number) return true;
    else if (!(typeof val === 'string' || val instanceof String)) return false;

    let res = /^-?[1-9]\d*$/.test(val);
    res = res || /^0$/.test(val);
    res = res || /^-?[1-9]\d*\.\d+$/.test(val);
    res = res || /^-?0\.\d+$/.test(val);
    return res;
}

export function getOtherAssignmentPlagiarismDesc(item, index) {
    const assig = item.assignments[index];
    if (assig && assig.course.virtual) {
        return 'This submission was uploaded during running as part of an archive of old submissions.';
    }

    let desc = `This assignment was submitted to the assignment "${item.assignments[index].name}" of "${item.assignments[index].course.name}"`;

    if (item.submissions != null) {
        // These submissions are not yet submission object, so we don't have
        // `createdAt` property.
        const date = moment
            .utc(item.submissions[index].created_at, moment.ISO_8601)
            .local()
            .format('YYYY-MM-DD');
        desc = `${desc} on ${date}`;
    }

    return desc;
}

export function withOrdinalSuffix(i) {
    const endsWith = i % 10;
    const mod100 = i % 100;
    const isTeen = mod100 >= 10 && mod100 < 20;
    let suffix = 'th';

    if (endsWith === 1 && !isTeen) {
        suffix = 'st';
    }
    if (endsWith === 2 && !isTeen) {
        suffix = 'nd';
    }
    if (endsWith === 3 && !isTeen) {
        suffix = 'rd';
    }

    return `${i}${suffix}`;
}

export function deepExtend(target, ...sources) {
    sources.forEach(source => {
        Object.entries(source).forEach(([key, val]) => {
            if (typeof val !== 'object' || Array.isArray(val) || val == null) {
                target[key] = val;
                return;
            }
            if (!hasAttr(target, key) || typeof target[key] !== 'object') {
                target[key] = {};
            }
            deepExtend(target[key], val);
        });
    });
    return target;
}

export function deepExtendArray(target, ...sources) {
    // deepExtend with support for arrays. We couldn't rewrite deepExtend to
    // support arrays, because there are places in our codebase where we depend
    // on the property that it doesn't.
    sources.forEach(source => {
        Object.entries(source).forEach(([key, val]) => {
            if (typeof val !== 'object' || val == null) {
                target[key] = val;
                return;
            }
            if (!hasAttr(target, key) || typeof target[key] !== 'object') {
                target[key] = Array.isArray(val) ? [] : {};
            }
            deepExtendArray(target[key], val);
        });
    });
    return target;
}

export function autoTestHasCheckpointAfterHiddenStep(autoTest) {
    let testHasHiddenStep = false;

    const sets = autoTest.sets;
    const nSets = sets.length;

    for (let i = 0; i < nSets; i++) {
        const set = sets[i];
        const suites = set.suites;
        const nSuites = suites.length;

        for (let j = 0; j < nSuites; j++) {
            const steps = suites[j].steps;
            const nSteps = steps.length;

            let suiteHasHiddenStep = false;

            for (let k = 0; k < nSteps; k++) {
                const step = steps[k];
                if (step.hidden) {
                    testHasHiddenStep = true;
                    suiteHasHiddenStep = true;
                }
                if (suiteHasHiddenStep && step.type === 'check_points') {
                    return true;
                }
            }
        }

        if (testHasHiddenStep && set.stop_points && i < nSets - 1) {
            return true;
        }
    }

    return false;
}

export function snakeToCamelCase(val) {
    return val.replace(/[-_]([a-z])/gi, inner => inner[1].toUpperCase());
}
