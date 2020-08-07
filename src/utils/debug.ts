/* SPDX-License-Identifier: AGPL-3.0-only */

export function trace<X>(x: X, transform: (x: X) => any = y => y): X {
    // Logs the passed value, a stack trace to the call site of this function,
    // and returns the value unchanged. Optionally pass a transformation
    // function which is applied only to the logged value.

    console.log(transform(x), new Error().stack);
    return x;
}
