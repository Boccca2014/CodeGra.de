/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder } from 'vuex-typex';
import { Store } from 'vuex';

import * as utils from '@/utils';
import * as models from '@/models';
import * as api from '@/api/v1';
import { RootState } from '@/store/state';

const storeBuilder = getStoreBuilder<RootState>();

export interface UIPrefsState {
    uiPrefs: utils.Maybe<models.UIPreferenceMap>;
}

const makeInitialState = () => ({
    uiPrefs: utils.Nothing,
});

const moduleBuilder = storeBuilder.module<UIPrefsState>('ui_prefs', makeInitialState());

export namespace UIPrefsStore {
    export const uiPrefs = moduleBuilder.read(state => state.uiPrefs, 'uiPrefs');

    export const getUIPref = moduleBuilder.read(
        state => (name: models.UIPreference) => state.uiPrefs.map(prefs => prefs[name]).join(),
        'getUIPref',
    );

    export const commitUIPrefs = moduleBuilder.commit((state, prefs: models.UIPreferenceMap) => {
        state.uiPrefs = utils.Just(prefs);
    }, 'commitUIPrefs');

    export const commitPatchedUIPref = moduleBuilder.commit(
        (state, { name, value }: { name: models.UIPreference; value: boolean }) => {
            state.uiPrefs = utils.Just(
                state.uiPrefs.mapOrDefault(
                    prefs => {
                        prefs[name] = utils.Just(value);
                        return prefs;
                    },
                    { [name]: utils.Just(value) },
                ),
            );
        },
        'commitPatchedUIPref',
    );

    export const commitClear = moduleBuilder.commit(state => {
        state.uiPrefs = utils.Nothing;
    }, 'commitClear');

    export const loadUIPreferences = moduleBuilder.dispatch(({ state }): Promise<
        utils.Maybe<models.UIPreferenceMap>
    > => {
        if (state.uiPrefs.isJust()) {
            return Promise.resolve(state.uiPrefs);
        }

        return api.uiPrefs.getUIPreferences().then(res => {
            commitUIPrefs(res.data);
            return utils.Just(res.data);
        });
    }, 'loadUIPreferences');

    export const patchUIPreference = moduleBuilder.dispatch(
        (ctx, { name, value }: { name: models.UIPreference; value: boolean }) =>
            api.uiPrefs.patchUIPreference(name, value).then(res => {
                commitPatchedUIPref({ name, value });
                return res;
            }),
        'patchUIPreference',
    );
}

export function onDone(store: Store<RootState>) {
    store.watch(
        // @ts-ignore
        (_: RootState, allGetters: Record<string, any>) => allGetters['user/loggedIn'],
        loggedIn => {
            if (!loggedIn) {
                UIPrefsStore.commitClear();
            }
        },
    );
}
