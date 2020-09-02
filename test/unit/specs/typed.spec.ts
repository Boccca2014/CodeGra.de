import { Maybe, Just, Nothing, getPropMaybe } from '@/utils/typed';

describe('getPropMaybe', () => {
    const obj: { a: string, c: string | null, d: number, just: Maybe<5> } = {
        a: 'b',
        c: null,
        d: 5,
        just: Just(5),
    };

    it('should return object found if it is a maybe', () => {
        const res: Maybe<number> = getPropMaybe(obj, 'just');
        expect(res).toEqual(Just(5));
        // @ts-expect-error
        const err: Maybe<string> = getPropMaybe(obj, 'just');
        expect(err).toBe(res);
    });

    it('should wrap the object in a Maybe if it is not a maybe', () => {
        const res1: Maybe<string> = getPropMaybe(obj, 'a');
        expect(res1).toEqual(Just('b'));

        const res2: Maybe<string> = getPropMaybe(obj, 'c');
        expect(res2).toBe(Nothing);

        // @ts-expect-error
        const err1: Nothing = getPropMaybe(obj, 'c');
        expect(err1).toBe(Nothing);
    });

    it('should return Nothing if the key is not in the object', () => {
        // @ts-expect-error
        const res3 = getPropMaybe(obj, 'not_present');
        expect(res3).toBe(Nothing);
    });

    it('should return `Nothing` if the first argument is `null`', () => {
        const res: typeof Nothing = getPropMaybe(null, 'c');
        expect(res).toBe(Nothing);
    });

    it('should work for normal records', () => {
        const record: Record<string, number | string | null> = {
            a: 5,
            b: 'c',
            d: null,
        };

        const res1: Maybe<string | number> = getPropMaybe(record, 'c');
        expect(res1).toBe(Nothing);

        const res2: Maybe<string | number> = getPropMaybe(record, 'a');
        expect(res2).toEqual(Just(5));

        const res3: Maybe<string | number> = getPropMaybe(record, 'd');
        expect(res3).toBe(Nothing);
    });
});
