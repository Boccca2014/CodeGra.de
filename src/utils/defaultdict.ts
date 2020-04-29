// SPDX-License-Identifier: AGPL-3.0-only

export function defaultdict<K extends string, V>(factory: (key: K) => V): Record<K, V> {
    return new Proxy<Record<K, V>>(
        <Record<K, V>>{},
        {
            get(target: Record<K, V>, key: K, receiver: V): V {
                if (!Reflect.has(target, key)) {
                    Reflect.set(target, key, factory(key), receiver);
                }
                return Reflect.get(target, key, receiver);
            },

            set(target: {}, key: K, value: V, receiver: V): boolean {
                return Reflect.set(target, key, value, receiver);
            },
        },
    );
}
