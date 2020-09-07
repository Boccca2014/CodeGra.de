/* SPDX-License-Identifier: AGPL-3.0-only */
import * as Sentry from '@sentry/browser';
import { Vue as VueIntegration } from '@sentry/integrations';
import Vue from 'vue';

// Some users might want to block sentry which should be just fine.
if (UserConfig.sentryDsn && Sentry) {
    Sentry.init({
        dsn: UserConfig.sentryDsn,
        integrations: [
            new VueIntegration({
                Vue,
                attachProps: true,
                logErrors: true,
            }),
        ],
        release: `CodeGra.de@${UserConfig.release.commit}`,
    });
}

/* eslint-disable import/first */
import { polyFilled } from '@/polyfills';

import 'bootstrap/dist/css/bootstrap.css';
import 'bootstrap-vue/dist/bootstrap-vue.css';
import 'highlightjs/styles/solarized-dark.css';
import 'vue-multiselect/dist/vue-multiselect.min.css';
import '@/style.less';
import 'reflect-metadata';

import BootstrapVue from 'bootstrap-vue';
import axios from 'axios';
import axiosRetry from 'axios-retry';
import localforage from 'localforage';
import memoryStorageDriver from 'localforage-memoryStorageDriver';
import VueMasonry from 'vue-masonry-css';
import VueClipboard from 'vue-clipboard2';
import moment from 'moment';
import vueDebounce from 'vue-debounce';

import App from '@/App';
import router, { setRestoreRoute } from '@/router';
import * as utils from '@/utils';
import { NO_LOGIN_REQUIRED_ROUTES } from '@/constants';
import '@/icons';
import * as store from './store';
import { NotificationStore } from './store/modules/notification';
import * as mutationTypes from './store/mutation-types';
import './my-vue';

import RelativeTime from './components/RelativeTime';
import User from './components/User';
import Loader from './components/Loader';
import SubmitButton from './components/SubmitButton';
import PromiseLoader from './components/PromiseLoader';
import DescriptionPopover from './components/DescriptionPopover';
import CgLogo from './components/CgLogo';
import CatchError from './components/CatchError';
import Toggle from './components/Toggle';
import Collapse from './components/Collapse';
import NumberInput from './components/NumberInput';
import WizardWrapper from './components/WizardWrapper';
import Error from './components/Error';
import WizardButton from './components/WizardButton';
/* eslint-enable import/first */

Vue.component('cg-relative-time', RelativeTime);
Vue.component('cg-user', User);
Vue.component('cg-loader', Loader);
Vue.component('cg-submit-button', SubmitButton);
Vue.component('cg-promise-loader', PromiseLoader);
Vue.component('cg-description-popover', DescriptionPopover);
Vue.component('cg-logo', CgLogo);
Vue.component('cg-catch-error', CatchError);
Vue.component('cg-toggle', Toggle);
Vue.component('cg-collapse', Collapse);
Vue.component('cg-number-input', NumberInput);
Vue.component('cg-wizard-wrapper', WizardWrapper);
Vue.component('cg-error', Error);
Vue.component('cg-wizard-button', WizardButton);

Vue.use(BootstrapVue);
Vue.use(VueMasonry);
Vue.use(VueClipboard);
Vue.use(vueDebounce);

Vue.config.productionTip = false;

moment.relativeTimeThreshold('h', 48);
moment.defineLocale('en-original', {
    parentLocale: 'en',
});
moment.updateLocale('en', {
    relativeTime: {
        past(input) {
            return input === 'just now' ? input : `${input} ago`;
        },
        future(input) {
            return input === 'just now' ? input : `in ${input}`;
        },
        s: 'just now',
        ss: '%d seconds',
        m: 'a minute',
        mm: '%d minutes',
        h: 'an hour',
        hh: '%d hours',
        d: 'a day',
        dd: '%d days',
        M: 'a month',
        MM: '%d months',
        y: 'a year',
        yy: '%d years',
    },
    calendar: {
        lastDay: '[yesterday at] LT',
        sameDay: '[today at] LT',
        nextDay: '[tomorrow at] LT',
        lastWeek: '[last] dddd [at] LT',
        nextWeek: 'dddd [at] LT',
        sameElse: 'YYYY-MM-DD HH:mm',
    },
});

axios.defaults.transformRequest.push((data, headers) => {
    if (store.store.state.user.jwtToken) {
        headers.Authorization = `Bearer ${store.store.state.user.jwtToken}`;
    }
    return data;
});

// Fix axios automatically parsing all responses as JSON... WTF!!!
axios.defaults.transformResponse = [
    function defaultTransformResponse(data, headers) {
        const contentType = headers['content-type'];

        if (contentType && contentType.startsWith('application/json')) {
            // Somehow axios gives us an ArrayBuffer sometimes, even though
            // the Content-Type header is application/json. JSON.parse does
            // not work on ArrayBuffers (they're silently converted to the
            // string "[object ArrayBuffer]", which is invalid JSON), so we
            // must do that ourselves.
            if (data instanceof ArrayBuffer) {
                const view = new Int8Array(data);
                const dataStr = String.fromCharCode.apply(null, view);
                return JSON.parse(dataStr);
            }
            return JSON.parse(data);
        } else {
            return data;
        }
    },
];

axiosRetry(axios, {
    retries: 3,
    retryDelay: (retryNumber = 0) => {
        const delay = 2 ** retryNumber * 500;
        const randomSum = delay * 0.2 * Math.random(); // 0-20% of the delay
        return delay + randomSum;
    },
});

Vue.prototype.$http = axios;

const DRIVERS = [
    localforage.INDEXEDDB,
    localforage.WEBSQL,
    localforage.LOCALSTORAGE,
    'memoryStorageDriver',
];

Vue.util.defineReactive(Vue.prototype, '$inLTI', false, null, true);

Vue.util.defineReactive(Vue.prototype, '$ltiProvider', null, null, true);

Vue.util.defineReactive(Vue.prototype, '$LTIAssignmentId', null, null, true);

try {
    Vue.prototype.$devMode = process.env.NODE_ENV === 'development';
} catch (e) {
    Vue.prototype.$devMode = false;
}
Vue.prototype.$utils = utils;
Vue.prototype.$routeParamAsId = function $routeParamAsId(name) {
    const res = utils.parseOrKeepFloat(this.$route.params[name]);
    return Number.isNaN(res) ? undefined : res;
};
Vue.prototype.$userConfig = UserConfig;

Vue.prototype.$afterRerender = function doubleRequestAnimationFrame(cb) {
    return new Promise(resolve => {
        this.$nextTick(() => {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    if (cb) {
                        cb();
                    }
                    resolve();
                });
            });
        });
    });
};

Vue.prototype.$waitForRef = async function waitForRef(refName, retries = 5) {
    for (let i = 0; i < retries; i++) {
        if (this.$refs[refName] == null) {
            // eslint-disable-next-line no-await-in-loop
            await this.$afterRerender();
        } else {
            break;
        }
    }
    return this.$refs[refName];
};

// eslint-disable-next-line
Promise.all([
    polyFilled,
    localforage.defineDriver(memoryStorageDriver),
]).then(() => {
    Vue.prototype.$hlanguageStore = localforage.createInstance({
        name: 'highlightLanguageStore',
        driver: DRIVERS,
    });
    Vue.prototype.$whitespaceStore = localforage.createInstance({
        name: 'showWhitespaceStore',
        driver: DRIVERS,
    });
    [Vue.prototype.$hlanguageStore, Vue.prototype.$whitespaceStore].forEach(forageStore => {
        // `localForage` does some initialization on the first get, but when
        // doing two first gets at the same time (in different promise chains
        // for example) this creates a race condition that fails in Firefox in
        // private mode. So we initialize the stores here.
        try {
            forageStore.getItem('test key');
        } catch (_) {
            // PASS
        }
    });

    Vue.prototype.$hasPermission = (permission, _, asMap) => {
        function makeResponse(map) {
            if (typeof permission === 'string') {
                return map[permission];
            } else if (asMap) {
                return map;
            } else {
                return permission.map(p => map[p]);
            }
        }
        return Promise.resolve(makeResponse(store.store.getters['user/permissions']));
    };

    function getUTCEpoch() {
        return moment();
    }

    /* eslint-disable no-new */
    const app = new Vue({
        el: '#app',
        router,
        template: '<App/>',
        components: { App },
        store: store.store,

        data() {
            return {
                screenWidth: window.innerWidth,
                smallWidth: 628,
                mediumWidth: 768,
                largeWidth: 992,
                xlargeWidth: 1200,
                // `Now` and `epoch` both contain the current time. They are
                // the same, except that `epoch` is recalculated every second
                // while `now` is set only every minute. We do not want `now`
                // to be updated as often because that would trigger a redraw
                // of the sidebar every second.
                now: moment(),
                epoch: getUTCEpoch(),

                caughtErrors: [],
                $loadFullNotifications: false,
            };
        },

        created() {
            axios.interceptors.response.use(res => res, this.httpErrorHandler);

            store.onVueCreated(this);

            window.addEventListener('resize', () => {
                this.screenWidth = window.innerWidth;
            });

            this.$on('cg::root::update-now', () => {
                this.epoch = getUTCEpoch();
                this.now = moment();
            });

            setInterval(() => {
                this.now = moment();
            }, 60000);

            setInterval(() => {
                this.epoch = getUTCEpoch();
            }, 1000);

            this._loadNotifications();
            this._checkForUpdates();
        },

        computed: {
            $windowWidth() {
                return this.screenWidth;
            },

            $isSmallWindow() {
                return this.screenWidth <= this.smallWidth;
            },

            $isMediumWindow() {
                return this.screenWidth >= this.mediumWidth;
            },

            $isLargeWindow() {
                return this.screenWidth >= this.largeWidth;
            },

            $isXLargeWindow() {
                return this.screenWidth >= this.xlargeWidth;
            },

            isEdge() {
                return window.navigator.userAgent.indexOf('Edge') > -1;
            },

            isSafari() {
                const ua = window.navigator.userAgent;
                // Contains safari and does not contain Chrome as Google Chrome
                // contains Safari and Chrome.
                return ua.indexOf('Safari') > -1 && ua.indexOf('Chrome') < 0;
            },

            $now() {
                return this.now;
            },

            $epoch() {
                return this.epoch;
            },

            httpErrorHandler() {
                return utils.makeHttpErrorHandler({
                    401: err => {
                        const { config } = err;

                        if (
                            !config ||
                            config.method !== 'get' ||
                            config.url.match(/\/api\/v1\/login/) ||
                            NO_LOGIN_REQUIRED_ROUTES.has(router.currentRoute.name)
                        ) {
                            throw err;
                        }

                        if (store.store.getters['user/dangerousJwtToken'] == null) {
                            this.notLoggedInError(
                                'You are currently not logged in. Please log in to view this page.',
                            );
                        } else {
                            this.notLoggedInError(
                                'Your session has expired. Please log in again to view this page.',
                            );
                        }

                        if (router.currentRoute.name !== 'login') {
                            setRestoreRoute(router.currentRoute);
                            store.store.dispatch('user/logout').then(() => {
                                router.push({ name: 'login' });
                            });
                        }
                        throw err;
                    },
                    noResponse: err => {
                        this.connectionError();
                        throw err;
                    },
                });
            },
        },

        methods: {
            async _loadNotifications() {
                let sleepTime = UserConfig.notificationPollTime;
                try {
                    if (this.$store.getters['user/loggedIn']) {
                        if (this.$loadFullNotifications) {
                            await NotificationStore.dispatchLoadNotifications();
                        } else {
                            await NotificationStore.dispatchLoadHasUnread();
                        }
                    }
                } catch (e) {
                    // eslint-disable-next-line
                    console.log('Loading notifications went wrong', e);
                    sleepTime += sleepTime;
                }

                setTimeout(() => {
                    this._loadNotifications();
                }, sleepTime);
            },

            notLoggedInError(message) {
                this.$emit('cg::app::toast', {
                    tag: 'NotLoggedIn',
                    title: 'Not logged in',
                    message,
                    variant: 'danger',
                });
            },

            connectionError() {
                this.$emit('cg::app::toast', {
                    tag: 'ConnectionError',
                    title: 'Connection error',
                    message:
                        'There was an error connecting to the server... Please try again later.',
                    variant: 'danger',
                });
            },

            async _checkForUpdates() {
                const res = await this.$http
                    .get(
                        utils.buildUrl(['static', 'commitHash'], {
                            query: { cacheBuster: Math.random() },
                        }),
                    )
                    .catch(() => null);
                const ourCommit = UserConfig.release.commitHash;
                const remoteCommit = utils.getProps(res, ourCommit, 'data');
                if (UserConfig.isProduction && ourCommit !== remoteCommit) {
                    this.$emit('cg::app::toast', {
                        tag: 'UpdateAvailable',
                        title: 'CodeGrade update available!',
                        message:
                            'An updated version of CodeGrade is available. Please click here to reload the page and start using the latest version!',
                        variant: '',
                        href: '#',
                        onClick() {
                            window.location.reload();
                        },
                    });
                } else {
                    setTimeout(this._checkForUpdates, 10 * 60 * 1000);
                }
            },
        },

        watch: {
            isEdge: {
                immediate: true,
                handler() {
                    if (this.isEdge) {
                        document.body.classList.add('cg-edge');
                    }
                },
            },
        },
    });

    // eslint-disable-next-line
    window.__app__ = app;

    // Clear some items in vuex store on CTRL-F5
    document.addEventListener(
        'keydown',
        async event => {
            let isF5;
            if (event.key !== undefined) {
                isF5 = event.key === 'F5';
            } else if (event.keyIdentifier !== undefined) {
                isF5 = event.keyIdentifier === 'F5';
            } else if (event.keyCode !== undefined) {
                isF5 = event.keyCode === 116;
            }

            if (isF5 && (event.ctrlKey || event.shiftKey)) {
                event.preventDefault();
                await app.$store.commit(`user/${mutationTypes.CLEAR_CACHE}`);
                window.location.reload(true);
            }
        },
        true,
    );
});
