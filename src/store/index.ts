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
let localStorageError = false;
let toastMessage: string | null = null;
const useLocalStorage: () => boolean = () => !disabledPersistance && !localStorageError;

const pathsToPersist = [
    ['pref', 'fontSize'],
    ['pref', 'darkMode'],
    ['pref', 'contextAmount'],
    ['user', 'jwtToken'],
    ['user', 'id'],
] as const;

const makePersistanceKey = (ns: 'pref' | 'user', path: string) => `CG_PERSIST-${ns}|${path}`;

const enablePersistance = (store: Store<RootState>) => {
    pathsToPersist.forEach(([ns, path]) => {
        const key = makePersistanceKey(ns, path);
        store.watch(
            state => state[ns][path],
            value => {
                if (useLocalStorage()) {
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
    if (window.localStorage.getItem('@@') !== '1') {
        throw new Error('Localstorage did not save state');
    }
    window.localStorage.removeItem('@@');
} catch (e) {
    localStorageError = true;
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

export const store = rootBuilder.vuexStore({ strict: debug });

export function disablePersistance() {
    let error: Error | undefined;
    if (!useLocalStorage()) {
        disabledPersistance = true;
        return;
    }

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
    // Do this in a timeout so that when we disable persistence when launching
    // in LTI we do not show this warning message as it makes no sense.
    setTimeout(() => {
        if (!disabledPersistance && toastMessage != null) {
            $root.$bvToast.toast(toastMessage, {
                title: 'Warning',
                variant: 'warning',
                toaster: 'b-toaster-top-right',
                noAutoHide: true,
                solid: true,
            });
        }
    }, 1000);
}

if (useLocalStorage()) {
    const newState = pathsToPersist.reduce((acc, [ns, path]) => {
        const key = makePersistanceKey(ns, path);
        const res = window.localStorage.getItem(key);
        if (res) {
            acc[ns] = Object.assign({}, acc[ns], { [path]: JSON.parse(res) });
        }
        return acc;
    }, Object.assign({}, store.state));

    store.replaceState(newState);
    enablePersistance(store);
}

coursesOnDone(store);
