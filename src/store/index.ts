/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import Vuex from 'vuex';
// @ts-ignore
import createPersistedState from 'vuex-persistedstate';

import { getStoreBuilder } from 'vuex-typex';

import user from './modules/user';
import pref from './modules/preference';
// @ts-ignore
import rubrics from './modules/rubrics';
import autotest from './modules/autotest';
import analytics from './modules/analytics';
import plagiarism from './modules/plagiarism';
import submissions from './modules/submissions';
import code from './modules/code';
import users from './modules/users';
import fileTrees from './modules/file_trees';

import { RootState } from './state';

import { onDone as coursesOnDone } from './modules/courses';

export { NotificationStore } from './modules/notification';
export { FeedbackStore } from './modules/feedback';
export { PeerFeedbackStore } from './modules/peer_feedback';
export { AssignmentsStore } from './modules/assignments';
export { CoursesStore } from './modules/courses';

Vue.use(Vuex);

const debug = process.env.NODE_ENV !== 'production';
const plugins = [];

let disabledPersistance = false;
let toastMessage: string | null = null;

try {
    plugins.push(
        createPersistedState({
            paths: ['user', 'pref'],
            storage: {
                getItem: (key: string) => window.localStorage.getItem(key),
                setItem: (key: string, value: string) => {
                    if (disabledPersistance && key !== '@@') {
                        const cleanedValue = {
                            pref: JSON.parse(value).pref,
                        };
                        return window.localStorage.setItem(key, JSON.stringify(cleanedValue));
                    }
                    return window.localStorage.setItem(key, value);
                },
                removeItem: (key: string) => window.localStorage.removeItem(key),
            },
        }),
    );
} catch (e) {
    toastMessage = `Unable to persistently store user credentials, please check
        you browser privacy levels. You will not be logged-in in other tabs or
        when reloading.`;
}

const rootBuilder = getStoreBuilder<RootState>();

Object.entries({
    user,
    pref,
    rubrics,
    autotest,
    analytics,
    plagiarism,
    submissions,
    code,
    users,
    fileTrees,
}).forEach(([key, value]) => {
    const builder = rootBuilder.module(key);
    builder.vuexModule = () => value;
});

export const store = rootBuilder.vuexStore({
    strict: debug,
    plugins,
});

export function disablePersistance() {
    disabledPersistance = true;
}

export function onVueCreated($root: Vue) {
    if (!disabledPersistance && toastMessage != null) {
        $root.$bvToast.toast(toastMessage, {
            title: 'Warning',
            variant: 'warning',
            toaster: 'b-toaster-top-right',
            noAutoHide: true,
            solid: true,
        });
    }
}

coursesOnDone(store);
