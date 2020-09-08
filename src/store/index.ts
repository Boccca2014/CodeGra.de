/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import Vuex, { Store } from 'vuex';

import { getStoreBuilder } from 'vuex-typex';

import user from './modules/user';
import pref from './modules/preference';
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

let disabledPersistance = false;
let toastMessage: string | null = null;

const pathsToPersist = [
    ['pref', 'fontSize'],
    ['pref', 'darkMode'],
    ['pref', 'contextAmount'],
    ['user', 'jwtToken'],
] as const;

const makePersistanceKey = (ns: 'pref' | 'user', path: string) => `CG_PERSIST-${ns}|${path}`;

const enablePersistance = (store: Store<RootState>) => {
    pathsToPersist.forEach(([ns, path]) => {
        const key = makePersistanceKey(ns, path);
        store.watch(
            state => state[ns][path],
            value => {
                if (!disabledPersistance) {
                    window.localStorage.setItem(key, JSON.stringify(value));
                }
            },
        );
    });
};

try {
    window.localStorage.setItem('vuex', '""');
    window.localStorage.removeItem('vuex');
    window.localStorage.setItem('@@', '1');
    window.localStorage.removeItem('@@');
} catch (e) {
    toastMessage = `Unable to persistently store user credentials, please check
        you browser privacy levels. You will not be logged-in in other tabs or
        when reloading.`;
    disabledPersistance = true;
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
    mutations: {
        RESTORE_STATE(
            state: RootState,
            payload: { ns: 'user' | 'pref'; path: string; value: any },
        ) {
            Vue.set(state[payload.ns], payload.path, payload.value);
        },
    },
});

export function disablePersistance() {
    let error: Error | undefined;

    pathsToPersist.forEach(([ns, path]) => {
        const key = makePersistanceKey(ns, path);
        // Even on an error we try to clear all the remaining keys.
        try {
            window.localStorage.removeItem(key);
            window.localStorage.setItem(key, '""');
        } catch (e) {
            error = e;
        }
    });
    if (error != null) {
        throw error;
    }
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

if (!disabledPersistance) {
    pathsToPersist.forEach(([ns, path]) => {
        const key = makePersistanceKey(ns, path);
        const res = window.localStorage.getItem(key);
        if (res) {
            store.commit('RESTORE_STATE', {
                ns,
                path,
                value: JSON.parse(res),
            });
        }
    });
    enablePersistance(store);
}

coursesOnDone(store);
