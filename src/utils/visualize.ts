// SPDX-License-Identifier: AGPL-3.0-only
// Exported for testing purposes
export function nSpaces(n: number): string {
    const arr = Array(n + 1);
    return `<span class="whitespace space" data-whitespace="${arr.join('&middot;')}">${arr.join(
        ' ',
    )}</span><wbr>`;
}

const spacesCache = [1, 2, 3, 4, 5, 6, 7, 8].map(nSpaces);

// Exported for testing purposes
export function nTabs(n: number): string {
    const arr = Array(n + 1);
    const oneTab = `<span class="whitespace tab" data-whitespace="&#8594;">${'\t'}</span><wbr>`;
    return arr.join(oneTab);
}

const tabsCache = [1, 2, 3, 4].map(nTabs);

export function visualizeWhitespace(line: string): string {
    const newLine = [];

    // eslint-disable-next-line
    for (let i = 0; i < line.length;) {
        const start = i;
        if (line[i] === '<') {
            while (line[i] !== '>' && i < line.length) i += 1;
            newLine.push(line.slice(start, i + 1));
            i += 1;
        } else if (line[i] === ' ' || line[i] === '\t') {
            while (line[i] === line[start] && i < line.length) i += 1;

            let n = i - start;
            const cache = line[start] === ' ' ? spacesCache : tabsCache;
            while (n > 0) {
                let index = n % cache.length;
                if (index === 0) {
                    index = cache.length;
                }
                newLine.push(cache[index - 1]);
                n -= index;
            }
        } else {
            while (line[i] !== '<' && line[i] !== ' ' && line[i] !== '\t' && i < line.length) {
                i += 1;
            }
            newLine.push(line.slice(start, i));
        }
    }
    return newLine.join('');
}
