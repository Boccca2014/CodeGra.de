/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder } from 'vuex-typex';
import * as moment from 'moment';

import * as api from '@/api/v1';
import * as models from '@/models';
import { FrontendSiteSettings, FRONTEND_SETTINGS_DEFAULTS } from '@/models';
import { toMoment, Maybe, Just, Nothing, AllOrNone } from '@/utils';

import { RootState } from '../state';

const storeBuilder = getStoreBuilder<RootState>();

type ReleaseInfo = {
    commit: string;
} & AllOrNone<{
    date: moment.Moment;
    message: string;
    version: string;
    uiPreference: models.UIPreference;
}>;

export interface SiteSettingsState {
    settings: FrontendSiteSettings | undefined;
    serverRelease: ReleaseInfo | undefined;
    loader: Promise<unknown> | undefined;
}

const makeInitialState = () => ({
    settings: undefined,
    serverCommit: undefined,
    loader: undefined,
    serverRelease: undefined,
});

const moduleBuilder = storeBuilder.module<SiteSettingsState>('siteSettings', makeInitialState());

export namespace SiteSettingsStore {
    // eslint-disable-next-line
    function _getSetting(state: SiteSettingsState) {
        return <T extends keyof FrontendSiteSettings>(opt: T): FrontendSiteSettings[T] =>
            state.settings?.[opt] ?? FRONTEND_SETTINGS_DEFAULTS[opt];
    }

    export const getSetting = moduleBuilder.read(_getSetting, 'getSetting');

    export const releaseInfo = moduleBuilder.read(
        state =>
            Maybe.fromNullable(state.serverRelease).chain(info => {
                if (info.commit === COMMIT_HASH) {
                    return Just(info);
                }
                return Nothing;
            }),
        'releaseInfo',
    );

    const removeLoader = moduleBuilder.commit(state => {
        state.loader = undefined;
    }, 'removeLoader');

    const commitLoader = moduleBuilder.commit((state, loader: Promise<unknown>) => {
        loader.catch(removeLoader);
        state.loader = loader;
    }, 'commitLoader');

    const commitServerRelease = moduleBuilder.commit(
        (state, data: api.about.AboutData['release']) => {
            if (
                data.version == null ||
                data.date == null ||
                data.message == null ||
                data.ui_preference == null
            ) {
                state.serverRelease = {
                    commit: data.commit,
                };
            } else {
                state.serverRelease = {
                    version: data.version,
                    message: data.message,
                    commit: data.commit,
                    date: toMoment(data.date),
                    uiPreference: data.ui_preference,
                };
            }
        },
        'commitServerCommit',
    );

    const commitSettings = moduleBuilder.commit((state, settings: FrontendSiteSettings) => {
        state.settings = settings;
    }, 'commitSettings');

    export const loadSettings = moduleBuilder.dispatch(
        ({ state }, payload: { force?: boolean } = {}) => {
            const { force = false } = payload;
            if (force || state.loader == null) {
                commitLoader(
                    api.about.get().then(data => {
                        commitSettings(data.settings);
                        commitServerRelease(data.release);
                    }),
                );
            }
            return state.loader;
        },
        'loadSettings',
    );

    export const updateSettings = moduleBuilder.dispatch(
        (_, payload: { data: readonly api.siteSettings.PatchData[] }) =>
            api.siteSettings.patch(payload.data).then(data => {
                commitSettings(data);
                return data;
            }),
        'updateSettings',
    );
}
