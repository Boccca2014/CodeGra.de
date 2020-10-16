// SPDX-License-Identifier: AGPL-3.0-only
// @ts-ignore
import DiffMatchPatch from 'diff-match-patch';

import { visualizeWhitespace } from './visualize';
import { htmlEscape } from './index';

const ADDED = 1 as const;
const REMOVED = -1 as const;
const SAME = 0 as const;
export const NEWLINE_CHAR = '¶';

function internalMakeSpan(cls: string, inner: string): string {
    return `<span class="${cls}">${inner}</span>`;
}

type Diff = [typeof ADDED | typeof REMOVED | typeof SAME, string];

export function getCapturePointsDiff(
    expected: string,
    got: string,
    options: string[],
    showIgnored: boolean,
    makeSpan = internalMakeSpan,
) {
    const ignoreAllWhitespace = options.find(o => o === 'all_whitespace') != null;
    const ignoreTrailingWhitespace = options.find(o => o === 'trailing_whitespace') != null;
    const caseInsensitive = options.find(o => o === 'case') != null;
    const substring = options.find(o => o === 'substring') != null;

    if (caseInsensitive) {
        // eslint-disable-next-line
        got = got.toLowerCase();
        // eslint-disable-next-line
        expected = expected.toLowerCase();
    }

    const dmp = new DiffMatchPatch();
    const diffs: Diff[] = dmp.diff_main(got, expected, false);
    dmp.diff_cleanupSemantic(diffs);
    const lines = [''];

    if (substring && diffs.length >= 2) {
        /*
        If the last/first diff is an addition and the second/second to
        last is a deletion these can be swapped. This is only necessary
        as the deletion can be safely ignored if 'substring' match is
        enabled.
        */
        if (diffs[diffs.length - 2][0] === REMOVED && diffs[diffs.length - 1][0] === ADDED) {
            const old = diffs[diffs.length - 2];
            diffs[diffs.length - 2] = diffs[diffs.length - 1];
            diffs[diffs.length - 1] = old;
        }

        if (diffs[0][0] === ADDED && diffs[1][0] === REMOVED) {
            const old = diffs[1];
            diffs[1] = diffs[0];
            diffs[0] = old;
        }
    }

    diffs.forEach(([state, text], diffIndex) => {
        let cls = '';
        if (state === ADDED) {
            cls = 'added';
        } else if (state === REMOVED) {
            // If substring is enabled and we are at the first or last item we
            // can safely ignore this entry.
            if (substring && (diffIndex === 0 || diffIndex === diffs.length - 1)) {
                cls = 'ignored';
            } else {
                cls = 'removed';
            }
        }

        if (!showIgnored && cls === 'ignored') {
            return;
        }

        let splitted;
        // We use cls == 'removed' here and not state == REMOVED because we
        // don't need to do anything special (read slow) for ignored pieces.
        if (ignoreAllWhitespace && cls === 'removed') {
            splitted = text.replace(/\n/g, '\0\n').split('\n');
        } else if (ignoreAllWhitespace && state === ADDED) {
            splitted = [text.replace(/\n/g, '\0')];
        } else if ((ignoreTrailingWhitespace && cls === 'removed') || cls === 'added') {
            splitted = text.replace(/\n/g, '\0\n').split('\n');
        } else if (cls) {
            splitted = text.replace(/\n/g, `${NEWLINE_CHAR}\n`).split('\n');
        } else {
            splitted = text.split('\n');
        }

        function nextIsNewline(i: number) {
            if (splitted.length - 1 > i) {
                return true;
            }

            // Last line is always followed by a newline (not really, but it is
            // the case for trailing whitespace)
            if (diffIndex === diffs.length - 1) {
                return true;
            }

            return diffs[diffIndex + 1][1][0] === '\n';
        }

        splitted.forEach((line, i) => {
            let toAdd = '';
            function highlight(str: string, spanCls = cls) {
                if (!str) {
                    return '';
                }
                const inner = visualizeWhitespace(htmlEscape(str));
                return makeSpan(spanCls, inner);
            }

            // If we want to ignore all whitespace we want to mark all pieces of
            // whitespace in this line as ignored. This is of course only needed
            // if we would otherwise mark them as deleted or added.
            if (ignoreAllWhitespace && cls && cls !== 'ignored') {
                // XXX: Is it faster to use a reduce here, as we have quite some
                // cases where we don't really need to add anything to the
                // resulting array.
                toAdd = line
                    .split(/([\s\0]+)/g)
                    .map(tempPart => {
                        if (!tempPart) {
                            return '';
                        }

                        const whitePart = /(\s|\0)/.test(tempPart);
                        if (whitePart && !showIgnored) {
                            return '';
                        }

                        const part = tempPart.replace('\0', NEWLINE_CHAR);
                        if (whitePart) {
                            return highlight(part, 'ignored');
                        } else {
                            return highlight(part);
                        }
                    })
                    .join('');
            } else if (
                ignoreTrailingWhitespace &&
                cls &&
                cls !== 'ignored' &&
                nextIsNewline(i) &&
                /\s+\0?$/.test(line)
            ) {
                // If we need to ignore trailing whitespace and this line
                // contains trailing whitespace mark it as ignored.

                const [before, after] = line.split(/([\s\0]+)$/);
                const constainsNewlineChar = line.includes('\u0000');

                if (showIgnored) {
                    toAdd = highlight(before) + highlight(after.replace('\0', ''), 'ignored');
                } else {
                    toAdd = highlight(before);
                }

                if (constainsNewlineChar) {
                    toAdd += highlight(NEWLINE_CHAR);
                }
            } else if (line && cls) {
                // Nothing special about this, simply highlight it.
                toAdd = highlight(line.replace(/\0/g, NEWLINE_CHAR));
            } else if (line) {
                // We don't need to add any class to this line, so don't render
                // the span around it.
                toAdd = visualizeWhitespace(htmlEscape(line));
            }

            // Pushing the lines array causes a newline to render. We want to do
            // this if the index is higher than 0 (this means we splitted on a
            // newline) but not if the state is ADDED as we simply render a
            // `NEWLINE_CHAR` to indicate that the student is missing a newline.
            if (i === 0 || state === ADDED) {
                if (toAdd) {
                    lines[lines.length - 1] += toAdd;
                }
            } else {
                lines.push(toAdd);
            }
        });
    });
    return lines;
}
