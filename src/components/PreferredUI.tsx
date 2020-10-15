import { VNode, CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import { modifiers as m } from 'vue-tsx-support';

// @ts-ignore
import * as comp from '@/components';
import * as api from '@/api/v1';
import * as types from '@/types';
import * as utils from '@/utils';
import * as models from '@/models';
import { store, UIPrefsStore } from '@/store';

export default tsx.component({
    name: 'preferred-ui',

    props: {
        prefName: p.ofType<models.UIPreference>().required,
        componentName: p(String).required,
        defaultValue: p(Boolean).default(false),
        hideSwitcher: p(Boolean).default(false),
    },

    data() {
        return {
            error: utils.Nothing as utils.Maybe<Error>,
        };
    },

    computed: {
        userId(): number {
            return store.getters['user/id'];
        },

        prefValue(): utils.Maybe<utils.Maybe<boolean>> {
            return UIPrefsStore.getUIPref()(this.prefName);
        },
    },

    watch: {
        userId: {
            immediate: true,
            handler() {
                UIPrefsStore.loadUIPreference({ preference: this.prefName }).then(
                    () => {
                        this.error = utils.Nothing;
                    },
                    err => {
                        this.error = err;
                    },
                );
            },
        },
    },

    render(h: CreateElement) {
        return (
            <div class="preferred-ui">
                {this.renderError(h)}
                {this.renderMessage(h)}
                {this.prefValue.caseOf({
                    Just: prefValue => this.renderContent(h, prefValue),
                    Nothing: () => <comp.Loader page-loader />,
                })}
                {this.renderSwitcher(h)}
            </div>
        );
    },

    methods: {
        renderError(h: CreateElement): VNode {
            return utils.ifJustOrEmpty(this.error, e => <comp.CgError error={e} />);
        },

        renderMessage(h: CreateElement): VNode {
            const shouldRender =
                !this.hideSwitcher && this.prefValue.map(v => v.isNothing()).orDefault(false);

            return utils.ifOrEmpty(shouldRender, () => (
                <b-alert
                    show
                    dismissible
                    variant={store.getters['pref/darkMode'] ? 'dark' : 'light'}
                    class="mb-3"
                    onDismissed={() => this.updatePreference(false)}
                >
                    {this.$slots.ifUnset}{' '}
                    <a
                        href="#"
                        class="inline-link"
                        onClick={m.prevent(() => this.updatePreference(true))}
                    >
                        Click here to try the new version.
                    </a>
                </b-alert>
            ));
        },

        renderContent(
            h: CreateElement,
            prefValue: utils.Maybe<boolean>,
        ): VNode | VNode[] | undefined {
            const value = prefValue.orDefault(this.defaultValue);
            return value ? this.$slots.ifTrue : this.$slots.ifFalse;
        },

        renderSwitcher(h: CreateElement): VNode {
            if (this.hideSwitcher) {
                return utils.emptyVNode();
            }

            const compName = this.componentName;

            return utils.ifJustOrEmpty(this.prefValue.join(), value => (
                <div class="mt-3 text-right">
                    <a
                        href="#"
                        onClick={m.prevent(this.togglePreference)}
                        class="ui-switcher inline-link"
                    >
                        {value ? 'Switch back to the old interface' : 'Switch to the new interface'}
                    </a>
                </div>
            ));
        },

        updatePreference(value: boolean) {
            return UIPrefsStore.patchUIPreference({
                name: this.prefName,
                value,
            });
        },

        togglePreference() {
            return this.prefValue.join().caseOf({
                Just: value => this.updatePreference(!value),
                Nothing: () => Promise.reject(new Error('No value set.')),
            });
        },
    },
});
