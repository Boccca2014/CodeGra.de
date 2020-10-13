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
    private readonly _map: Map<K, V> = new Map();

    constructor(private readonly factory: (key: K) => V) {}

    public get(key: K): V {
        if (!this._map.has(key)) {
            this._map.set(key, this.factory(key));
        }
        return this._map.get(key) as V;
    }

    public has(key: K): boolean {
        return this._map.has(key);
    }

    public forEach(
        callbackfn: (value: V, key: K, map: ReadonlyMap<K, V>) => void,
        thisArg?: any,
    ): void {
        this._map.forEach(callbackfn, thisArg);
    }

    get size(): number {
        return this._map.size;
    }

    public entries() {
        return this._map.entries();
    }

    public keys() {
        return this._map.keys();
    }

    public values() {
        return this._map.values();
    }

    public [Symbol.iterator]() {
        return this._map[Symbol.iterator]();
    }

    public map<T>(fun: (val: V, key: K) => T): Map<K, T> {
        const m = new Map();
        for (const [key, val] of this) {
            m.set(key, fun(val, key));
        }
        return m;
    }
}
