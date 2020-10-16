import { Maybe } from 'purify-ts/Maybe';

declare global {
    namespace jest {
        interface Matchers<R> {
            toBeJust: () => CustomMatcherResult;
            toBeNothing: () => CustomMatcherResult;
        }
    }
}
