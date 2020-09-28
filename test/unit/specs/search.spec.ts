import { Search } from '@/utils/search';
import { range } from '@/utils';
import fastcheck from 'fast-check';

describe('Search', () => {
    describe('search', () => {
        const s = new Search(['a', 'b']);

        it('should only accept items having all required keys', () => {
            // @ts-expect-error
            s.search('a', [{ a: 'a' }]);
        });

        it('should only accept items where all required keys are strings', () => {
            // @ts-expect-error
            s.search('a', [{ a: 'a', b: 0 }]);
            // @ts-expect-error
            s.search('a', [{ a: 'a', b: null }]);
        });

        it('should accept items with keys other than the required keys of any type', () => {
            const items = [
                {
                    a: 'a',
                    b: 'b',
                    e: 'string',
                    f: { a: 3 },
                },
                {
                    a: 'b',
                    b: 'b',
                    c: 0,
                    d: null,
                },
            ];
            const result = s.search('a', items);

            expect(result).toEqual(items.slice(0, 1));
        });

        it('should accept classes with the required properties', () => {
            class MyRecord {
                constructor(public a: string, public b: string) {}
            }

            class MyRecordSub extends MyRecord {}

            class MyRecordSub2 extends MyRecord {
                constructor(public a: string, public b: string, public c: string) {
                    super(a, b);
                }
            }

            const items = [
                new MyRecord('a', 'b'),
                new MyRecordSub('b', 'b'),
                new MyRecordSub2('b', 'b', 'c'),
            ];
            const result = s.search('a', items);

            expect(result).toEqual(items.slice(0, 1));
        });

        it('should find matching items', () => {
            const items = [
                { a: 'a', b: 'b' },
                { a: 'b', b: 'b' },
            ];
            const result = s.search('a', items);

            expect(result).toEqual(items.slice(0, 1));
        });

        it('should discard items that do not match', () => {
            const items = [
                { a: 'a', b: 'b' },
                { a: 'b', b: 'b' },
            ];
            const result = s.search('z', items);

            expect(result).toEqual([]);
        });

        it('should preserve the relative order of matching items', () => {
            const items = range(0, 10).map(i => ({
                a: i % 2 ? 'a' : 'b',
                b: 'b',
                i: i,
            }));
            const result = s.search('a', items);

            for (let i = 0; i < result.length - 1; i++) {
                const [a, b] = result.slice(i, i + 2);
                expect(a).toBe(items[a.i]);
                expect(b).toBe(items[b.i]);
                expect(a.i).toBeLessThan(b.i);
            }
        });

        it('should search through all keys', () => {
            const items = [
                { a: 'a', b: 'b' },
                { a: 'b', b: 'a' },
            ];
            const result = s.search('a', items);

            expect(result).toEqual(items);
        });

        it('should only search through keys passed to the constructor', () => {
            const items = [
                { a: 'a', b: 'b' },
                { a: 'b', b: 'a' },
                { a: 'b', b: 'b', c: 'a' },
            ];
            const result = s.search('a', items);

            expect(result).toEqual(items.slice(0, 2));
        });

        it('should only select items that match each term in the query', () => {
            const items = [
                { a: 'a', b: 'b' },
                { a: 'b', b: 'a' },
                { a: 'a', b: 'a' },
                { a: 'b', b: 'b' },
            ];
            const result = s.search('a b', items);

            expect(result).toEqual(items.slice(0, 2));
        });

        it('should only match on a specific key for terms written <key>:<term>', () => {
            const items = [
                { a: 'a', b: 'b' },
                { a: 'a', b: 'a' },
                { a: 'b', b: 'a' },
                { a: 'b', b: 'b' },
            ];
            const result = s.search('a:a', items);

            expect(result).toEqual(items.slice(0, 2));
        });

        it('should only match on a specific key if it is one of the keys passed to the constructor', () => {
            const items = [
                { a: 'a', b: 'b', c: 'a' },
            ];
            const result = s.search('c:a', items);

            expect(result).toEqual([]);
        });

        it('$x should always find $x', () => {
            const searcher = new Search(['text']);
            fastcheck.assert(fastcheck.property(
                fastcheck.string(),
                text => searcher.search(text, [{ text }]).length === 1,
            ));
        });

        it('$x should always find $x plus extra', () => {
            const searcher = new Search(['text']);
            fastcheck.assert(fastcheck.property(
                fastcheck.string(),
                text => searcher.search(text, [{ text: `${text} extra` }]).length === 1,
            ));
        });

        it('$x + extra should never find $x', () => {
            const searcher = new Search(['text']);
            fastcheck.assert(fastcheck.property(
                // Property is not valid for strings only containing
                // whitespace.
                fastcheck.string(),
                text => searcher.search(`${text} extra`, [{ text }]).length === 0,
            ));
        });

    });

    describe('options', () => {
        describe('caseInsensitive', () => {
            it('should match case-sensitively when unset', () => {
                const s = new Search(['a', 'b'], { caseInsensitive: false });
                const items = [
                    { a: 'a', b: 'b' },
                    { a: 'A', b: 'b' },
                ];
                const result = s.search('a', items);

                expect(result).toEqual(items.slice(0, 1));
            });

            it('should match case-insensitively when set', () => {
                const s = new Search(['a', 'b'], { caseInsensitive: true });
                const items = [
                    { a: 'a', b: 'b' },
                    { a: 'A', b: 'b' },
                ];
                const result = s.search('a', items);

                expect(result).toEqual(items);
            });
        });
    });

    describe('regex escaping', () => {
        it.each(
            ['()', '(!!)', '[^2]', ']'],
        )('should work for %s', (input) => {
            const searcher = new Search(['text']);
            const obj = [{ text: input }, { text: 'wrong' }];
            expect(searcher.search(input, obj)).toEqual([obj[0]]);
        });
    });
});
