/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder } from 'vuex-typex';
import { Store } from 'vuex';

import * as utils from '@/utils';
import * as models from '@/models';
import * as api from '@/api/v1';
import { RootState } from '@/store/state';
import { UIPreference } from '@/models';

const storeBuilder = getStoreBuilder<RootState>();

export interface UIPrefsState {
    uiPrefs: Partial<models.UIPreferenceMap>;
}

const makeInitialState = () => ({
    uiPrefs: { ...models.DefaultUIPreferenceMap },
});

const moduleBuilder = storeBuilder.module<UIPrefsState>('ui_prefs', makeInitialState());

export namespace UIPrefsStore {
    export const getUIPref = moduleBuilder.read(
        state => (name: models.UIPreference) => {
            const pref = state.uiPrefs[name];
            if (pref == null) {
                return utils.Nothing;
            }
            return pref;
        },
        'getUIPref',
    );

    export const commitUIPrefs = moduleBuilder.commit(
        (state, prefs: Partial<models.UIPreferenceMap>) => {
            state.uiPrefs = { ...state.uiPrefs, ...prefs };
        },
        'commitUIPrefs',
    );

    export const commitPatchedUIPref = moduleBuilder.commit(
        (state, { name, value }: { name: models.UIPreference; value: utils.Maybe<boolean> }) => {
            utils.vueSet(state.uiPrefs, name, utils.Just(value));
        },
        'commitPatchedUIPref',
    );

    export const commitClear = moduleBuilder.commit(state => {
        state.uiPrefs = { ...models.DefaultUIPreferenceMap };
    }, 'commitClear');

    export const loadUIPreference = moduleBuilder.dispatch(
        (_, { preference }: { preference: UIPreference }): Promise<utils.Maybe<boolean>> =>
            getUIPref()(preference).caseOf({
                Just: value => Promise.resolve(value),
                Nothing: () =>
                    api.uiPrefs.getUIPreferences().then(data => {
                        commitUIPrefs(data);
                        return getUIPref()(preference).caseOf({
                            Just: v => v,
                            // This only happens when the backend doesn't have
                            // this setting, so add it with its default value.
                            Nothing() {
                                commitPatchedUIPref({ name: preference, value: utils.Nothing });
                                return utils.Nothing;
                            },
                        });
                    }),
            }),
        'loadUIPreference',
    );

    export const patchUIPreference = moduleBuilder.dispatch(
        async (_, { name, value }: { name: models.UIPreference; value: boolean }) => {
            commitPatchedUIPref({ name, value: utils.Just(value) });
            await api.uiPrefs.patchUIPreference(name, value);
        },
        'patchUIPreference',
    );
}

export function onDone(store: Store<RootState>) {
    store.watch(
        // @ts-ignore
        (_: RootState, allGetters: Record<string, any>) => allGetters['user/loggedIn'],
        (loggedIn: boolean) => {
            if (!loggedIn) {
                UIPrefsStore.commitClear();
            }
        },
    );
}
