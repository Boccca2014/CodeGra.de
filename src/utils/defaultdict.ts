// SPDX-License-Identifier: AGPL-3.0-only

export function defaultdict<K extends string | number, V>(factory: (key: K) => V): Record<K, V> {
    return new Proxy<Record<K, V>>(<Record<K, V>>{}, {
        get(target: Record<K, V>, key: K, receiver: V): V {
            if (!Reflect.has(target, key)) {
                Reflect.set(target, key, factory(key), receiver);
            }
            return Reflect.get(target, key, receiver);
        },

        set(target: {}, key: K, value: V, receiver: V): boolean {
            return Reflect.set(target, key, value, receiver);
        },
    });
}

export class DefaultMap<K, V> implements ReadonlyMap<K, V> {
    private readonly map: Map<K, V> = new Map();

    constructor(private readonly factory: (key: K) => V) {}

    public get(key: K): V {
        if (!this.map.has(key)) {
            this.map.set(key, this.factory(key));
        }
        return this.map.get(key) as V;
    }

    public has(key: K): boolean {
        return this.map.has(key);
    }

    public forEach(
        callbackfn: (value: V, key: K, map: ReadonlyMap<K, V>) => void,
        thisArg?: any,
    ): void {
        this.map.forEach(callbackfn, thisArg);
    }

    get size(): number {
        return this.map.size;
    }

    public entries() {
        return this.map.entries();
    }

    public keys() {
        return this.map.keys();
    }

    public values() {
        return this.map.values();
    }

    public [Symbol.iterator]() {
        return this.map[Symbol.iterator]();
    }
}
