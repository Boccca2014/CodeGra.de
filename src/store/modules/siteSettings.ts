/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder } from 'vuex-typex';

import * as api from '@/api/v1';
import { FrontendSiteSettings, FRONTEND_SETTINGS_DEFAULTS } from '@/models';
import { RootState } from '../state';

const storeBuilder = getStoreBuilder<RootState>();

export interface SiteSettingsState {
    settings: FrontendSiteSettings | undefined;
    loader: Promise<unknown> | undefined;
}

const makeInitialState = () => ({
    settings: undefined,
    loader: undefined,
});

const moduleBuilder = storeBuilder.module<SiteSettingsState>('siteSettings', makeInitialState());

export namespace SiteSettingsStore {
    // eslint-disable-next-line
    function _getSetting(state: SiteSettingsState) {
        return <T extends keyof FrontendSiteSettings>(opt: T): FrontendSiteSettings[T] =>
            state.settings?.[opt] ?? FRONTEND_SETTINGS_DEFAULTS[opt];
    }

    export const getSetting = moduleBuilder.read(_getSetting, 'getSetting');

    const removeLoader = moduleBuilder.commit(state => {
        state.loader = undefined;
    }, 'removeLoader');

    const commitLoader = moduleBuilder.commit((state, loader: Promise<unknown>) => {
        loader.catch(removeLoader);
        state.loader = loader;
    }, 'commitLoader');

    const commitSettings = moduleBuilder.commit((state, settings: FrontendSiteSettings) => {
        state.settings = settings;
    }, 'commitSettings');

    export const loadSettings = moduleBuilder.dispatch(
        ({ state }, payload: { force?: boolean } = {}) => {
            const { force = false } = payload;
            if (force || state.loader == null) {
                commitLoader(api.siteSettings.getAll().then(commitSettings));
            }
            return state.loader;
        },
        'loadSettings',
    );
}
