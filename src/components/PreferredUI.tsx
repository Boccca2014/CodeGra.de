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
    },

    data() {
        return {
            error: utils.Nothing as utils.Maybe<Error>,
            updating: false,
        };
    },

    computed: {
        userId(): number {
            return store.getters['user/id'];
        },

        allPrefs(): utils.Maybe<models.UIPreferenceMap> {
            return UIPrefsStore.uiPrefs();
        },

        prefValue(): utils.Maybe<boolean> {
            return UIPrefsStore.getUIPref()(this.prefName);
        },
    },

    watch: {
        userId: {
            immediate: true,
            handler() {
                store.dispatch('ui_prefs/loadUIPreferences').then(
                    () => { this.error = utils.Nothing; },
                    err => { this.error = err; },
                );
            },
        },
    },

    render(h: CreateElement) {
        return <div class="preferred-ui">
            {this.renderError(h)}
            {this.renderMessage(h)}
            {this.allPrefs.caseOf({
                Just: () => this.renderContent(h),
                Nothing: () => [<comp.Loader page-loader />],
            })}
            {this.renderToggle(h)}
        </div>;
    },

    methods: {
        renderError(h: CreateElement): VNode {
            return utils.ifOrEmpty(
                this.error.isJust(),
                () => <comp.CgError error={this.error.unsafeCoerce()} />,
            );
        },

        renderMessage(h: CreateElement): VNode {
            return utils.ifOrEmpty(
                this.allPrefs.isJust() && this.prefValue.isNothing(),
                () => <b-alert show variant="info">
                    {this.$slots.ifUnset}

                    <b-button-toolbar justify class="mt-3">
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

        renderContent(h: CreateElement): VNode[] | undefined {
            const value = this.prefValue.orDefault(this.defaultValue);
            return value ? this.$slots.ifTrue : this.$slots.ifFalse;
        },

        renderToggle(h: CreateElement): VNode {
            const compName = this.componentName;

            const renderLabel = () =>
                <template slot="label">
                    {utils.capitalize(compName)}
                    {utils.ifOrEmpty(
                        this.updating,
                        () => <comp.Loader class="d-inline-block ml-2" scale={1} />
                    )}
                </template>;

            const renderSelect = () =>
                <b-form-select
                    class="float-right"
                    value={this.prefValue.unsafeCoerce()}
                    disabled={this.updating}
                    onInput={() => this.togglePreference()}>
                    <b-form-select-option value={true}>
                        New interface
                    </b-form-select-option>
                    <b-form-select-option value={false}>
                        Old interface
                    </b-form-select-option>
                </b-form-select>;

            return utils.ifOrEmpty(
                this.allPrefs.isJust() && this.prefValue.isJust(),
                () => <div>
                    <hr />

                    <b-form-group
                        class="mb-0"
                        description={`You can switch between the old and the new ${compName} here.`}>
                        {renderLabel()}
                        {renderSelect()}
                    </b-form-group>
                </div>,
            );
        },

        updatePreference(value: boolean) {
            this.updating = true;
            return UIPrefsStore.patchUIPreference({
                name: this.prefName,
                value,
            }).then(
                res => {
                    this.updating = false;
                    return res;
                },
                err => {
                    this.updating = false
                    throw err;
                },
            ) as Promise<types.APIResponse<null>>;
        },

        togglePreference() {
            return this.prefValue.caseOf({
                Just: value => this.updatePreference(!value).then(res => {
                    const afterSuccess = res.onAfterSuccess;
                    if (afterSuccess != null) {
                        afterSuccess(res);
                    }
                    return res;
                }),
                Nothing: () => Promise.reject(new Error('No value set.')),
            });
        },
    },
});
