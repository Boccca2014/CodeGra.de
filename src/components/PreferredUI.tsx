import { VNode, CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import { modifiers as m } from 'vue-tsx-support';

// @ts-ignore
import * as comp from '@/components';
import * as api from '@/api/v1';
import * as utils from '@/utils';
import { store } from '@/store';

export default tsx.component({
    name: 'preferred-ui',

    props: {
        prefName: p.ofType<api.user.UIPreferenceName>().required,
        defaultValue: p(Boolean).default(true),
    },

    data() {
        return {
            error: utils.Nothing as utils.Maybe<Error>,
            updating: false,
        };
    },

    computed: {
        userId() {
            return store.getters['user/id'];
        },

        allPrefs() {
            return store.getters['user/uiPrefs'];
        },

        prefValue(): utils.Maybe<boolean> {
            return store.getters['user/getUIPref'](this.prefName);
        },
    },

    watch: {
        userId: {
            immediate: true,
            handler() {
                store.dispatch('user/loadUIPreferences').then(
                    () => { this.error = utils.Nothing; },
                    err => { this.error = err; },
                );
            },
        },
    },

    render(h: CreateElement) {
        return <div class="preferred-ui">
            {this.renderError(h)}
            {this.renderWarning(h)}
            {this.allPrefs.caseOf({
                Just: () => this.renderContent(h),
                Nothing: () => <comp.Loader page-loader />
            })}
        </div>;
    },

    methods: {
        renderContent(h: CreateElement) {
            const value = this.prefValue.orDefault(this.defaultValue);
            return value ? this.$slots.ifTrue : this.$slots.ifFalse;
        },

        renderWarning(h: CreateElement) {
            return utils.ifOrEmpty(
                this.prefValue.isNothing(),
                () => <b-alert show variant="info">
                    {this.$slots.ifUnset}

                    <p>
                        You can still use the old version, but it will be
                        removed in a couple of months. Do you want to keep
                        using the new version?
                    </p>

                    <b-button-toolbar justify class="mb-3">
                        <comp.SubmitButton
                            label="No"
                            variant="outline-danger"
                            submit={() => this.updatePreference(false)} />
                        <comp.SubmitButton
                            label="Yes"
                            variant="primary"
                            submit={() => this.updatePreference(true)} />
                    </b-button-toolbar>
                </b-alert>,
            );
        },

        renderError(h: CreateElement) {
            return this.error.mapOrDefault(
                e => <comp.CgError error={e} /> as VNode,
                utils.emptyVNode() as VNode,
            );
        },

        updatePreference(value: boolean) {
            return store.dispatch('user/patchUIPreference', {
                name: this.prefName,
                value,
            });
        },
    },
});
