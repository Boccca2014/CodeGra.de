import * as utils from '@/utils';

expect.extend({
    toBeJust(received) {
        if (!utils.isMaybe(received)) {
            return {
                message: () => `Expected a maybe, but got ${received}`,
                pass: false,
            };
        }
        return received.caseOf({
            Just() {
                return {
                    message: () => `Expected ${received} to not be a Just`,
                    pass: true,
                };
            },
            Nothing() {
                return {
                    message: () => `Expected a Just, but got a Nothing`,
                    pass: false,
                };
            },
        });
    },

    toBeNothing(received) {
        if (!utils.isMaybe(received)) {
            return {
                message: () => `Expected a maybe, but got ${received}`,
                pass: false,
            };
        }
        return received.caseOf({
            Just(value) {
                return {
                    message: () => `Expected a Nothing, but got Just(${value})`,
                    pass: false,
                };
            },
            Nothing() {
                return {
                    message: () => `Expected ${received} to not be a Nothing`,
                    pass: true,
                };
            },
        });
    },
})
