<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<component :is="inPopover ? 'b-btn' : 'div'"
           :id="btnId"
           class="preference-manager"
           :class="{ 'settings-toggle': inPopover }"
           v-b-popover.hover.top="inPopover ? 'Settings' : ''">
    <icon name="cog" v-if="inPopover"/>

    <component :is="inPopover ? 'b-popover' : 'div'"
               triggers="click blur"
               :id="popoverId"
               :target="btnId"
               :placement="placement"
               :boundary="boundary"
               :container="container"
               :disabled="popoverDisabled"
               @show="$root.$emit('bv::hide::popover')">
        <loader v-if="loading"/>
        <table v-else
               style="width: 24rem;"
               class="table mb-0 settings-content">
            <tbody>
                <tr v-if="showWhitespace">
                    <td>
                        Whitespace
                        <loader :scale="1" :center="true" v-if="whiteLoading"/>
                    </td>
                    <td>
                        <toggle v-model="whitespace" label-on="Show" label-off="Hide"/>
                    </td>
                </tr>
                <tr v-if="showLanguage">
                    <td>Language
                        <loader :scale="1" :center="true" v-if="langLoading"/>
                    </td>
                    <td>
                        <multiselect v-model="selectedLanguage"
                                     :hide-selected="selectedLanguage === 'Default'"
                                     deselect-label="Reset language"
                                     select-label="Select language"
                                     :options="languages"
                                     @open="disablePopover"
                                     @close="enablePopover"/>
                    </td>
                </tr>
                <tr v-if="showFontSize">
                    <td style="text-align: left;">
                        Code font size
                        <loader v-show="fontSizeLoading > 0" :scale="1" center/>
                    </td>
                    <td>
                        <b-input-group right="px">
                            <input :value="fontSize"
                                   @input="fontSizeChanged($event.target.value)"
                                   class="form-control"
                                   type="number"
                                   step="1"
                                   min="1"/>
                        </b-input-group>
                    </td>
                </tr>
                <tr v-if="showInlineFeedback">
                    <td>Inline feedback</td>
                    <td>
                        <toggle v-model="inlineFeedback"
                                label-on="Show"
                                label-off="Hide"/>
                    </td>
                </tr>
                <tr v-if="showContextAmount">
                    <td style="text-align: left;">
                        Amount of context
                        <loader v-show="contextAmountLoading > 0" :scale="1" center/>
                    </td>
                    <td>
                        <b-input-group right="px">
                            <input :value="contextAmount"
                                    @input="contextAmountChanged($event.target.value)"
                                    class="form-control"
                                    type="number"
                                    step="1"
                                    min="0"/>
                        </b-input-group>
                    </td>
                </tr>
                <tr v-if="showTheme">
                    <td>Theme</td>
                    <td>
                        <toggle :value="darkMode"
                                @input="setDarkMode"
                                label-on="Dark"
                                label-off="Light"/>
                    </td>
                </tr>
            </tbody>
        </table>
    </component>
</component>
</template>

<script>
import { listLanguages } from 'highlightjs';
import { mapActions, mapGetters } from 'vuex';
import Multiselect from 'vue-multiselect';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/gear';

import { cmpNoCase, waitAtLeast } from '@/utils';

import Toggle from './Toggle';
import Loader from './Loader';

export default {
    name: 'preference-manager',

    components: {
        Icon,
        Toggle,
        Loader,
        Multiselect,
    },

    props: {
        showWhitespace: {
            type: Boolean,
            default: true,
        },
        showLanguage: {
            type: Boolean,
            default: true,
        },
        showFontSize: {
            type: Boolean,
            default: true,
        },
        showInlineFeedback: {
            type: Boolean,
            default: true,
        },
        showTheme: {
            type: Boolean,
            default: true,
        },
        showContextAmount: {
            default: false,
        },
        fileId: {
            type: String,
            default: null,
        },
        inPopover: {
            type: Boolean,
            default: false,
        },
        boundary: {
            type: String,
            default: 'window',
        },
        container: {
            type: String,
            default: null,
        },
        placement: {
            type: String,
            default: 'bottom',
        },
    },

    data() {
        const id = this.$utils.getUniqueId();
        const languages = listLanguages();
        languages.push('plain');
        languages.sort(cmpNoCase);
        languages.unshift('Default');
        return {
            btnId: `settings-toggle-${id}`,
            popoverId: `settings-popover-${id}`,
            loading: true,
            languages,
            whitespace: true,
            contextAmountLoading: 0,
            fontSizeLoading: 0,
            langLoading: false,
            whiteLoading: false,
            selectedLanguage: -1,
            inlineFeedback: this.$utils.parseBool(this.$utils.getProps(
                this.$route.query,
                true,
                'showInlineFeedback',
            )),
            minLoadTime: 200,
            popoverDisabled: false,
        };
    },

    computed: {
        ...mapGetters('pref', ['fontSize', 'contextAmount', 'darkMode']),
    },

    methods: {
        ...mapActions('pref', ['setFontSize', 'setContextAmount', 'setDarkMode']),

        contextAmountChanged(val) {
            this.contextAmountLoading += 1;
            const contextAmount = Math.max(Number(val), 0);
            waitAtLeast(this.minLoadTime, this.setContextAmount(contextAmount)).then(() => {
                this.contextAmountLoading -= 1;
                this.$emit('context-amount', contextAmount);
            });
        },

        fontSizeChanged(val) {
            this.fontSizeLoading += 1;
            const fontSize = Math.max(Number(val), 1);
            waitAtLeast(this.minLoadTime, this.setFontSize(fontSize)).then(() => {
                this.fontSizeLoading -= 1;
                this.$emit('font-size', fontSize);
            });
        },

        loadValues(fileId) {
            this.loading = true;

            return Promise.all([this.loadWhitespace(fileId), this.loadLanguage(fileId)]).then(
                () => {
                    this.loading = false;
                },
            );
        },

        loadWhitespace(fileId) {
            if (this.showWhitespace && fileId) {
                return this.$whitespaceStore.getItem(`${fileId}`).then(white => {
                    if (fileId === this.fileId) {
                        this.whitespace = white === null || white;
                    }
                });
            } else {
                return null;
            }
        },

        loadLanguage(fileId) {
            if (this.showLanguage && fileId) {
                return this.$hlanguageStore.getItem(`${fileId}`).then(lang => {
                    if (fileId === this.fileId) {
                        this.selectedLanguage = lang || 'Default';
                    }
                });
            } else {
                return null;
            }
        },

        // Disable the popover so a blur event on an element in it will not
        // cause it to close.
        disablePopover() {
            this.popoverDisabled = true;
        },

        // Enable the popover again. Make sure this happens _after_ the blur
        // event on elements inside it. We focus the button before enabling
        // the popover again to make sure that at least something is focused
        // that, when blurred, will cause the popover to close.
        enablePopover() {
            this.$el.focus();
            this.$afterRerender().then(() => {
                this.popoverDisabled = false;
            });
        },
    },

    mounted() {
        this.loadValues(this.fileId);
    },

    watch: {
        showWhitespace(newVal) {
            if (newVal) {
                this.loadWhitespace(this.fileId);
            }
        },

        showLanguage(newVal) {
            if (newVal) {
                this.loadLanguage(this.fileId);
            }
        },

        fileId(newVal, oldVal) {
            if (newVal != null && newVal !== oldVal) {
                this.loadValues(newVal);
            }
        },

        inlineFeedback: {
            immediate: true,
            handler(show) {
                this.$emit('inline-feedback', show);
                const query = {
                    showInlineFeedback: show ? undefined : false,
                };
                this.$router.replace(
                    this.$utils.deepExtend({}, this.$route, { query }),
                );
            },
        },

        selectedLanguage(lang, old) {
            if (old === -1) return;

            this.langLoading = true;

            let promise;
            if (lang == null) {
                promise = Promise.resolve((this.selectedLanguage = 'Default'));
            } else {
                promise = this.$hlanguageStore.setItem(`${this.fileId}`, lang);
            }

            waitAtLeast(this.minLoadTime, promise).then(() => {
                this.langLoading = false;
                if (lang) {
                    this.$emit('language', lang);
                }
            });
        },

        whitespace(val) {
            this.whiteLoading = true;
            waitAtLeast(
                this.minLoadTime,
                this.$whitespaceStore.setItem(`${this.fileId}`, val),
            ).then(() => {
                this.whiteLoading = false;
                this.$emit('whitespace', val);
            });
        },
    },
};
</script>

<style lang="less">
@import '~mixins.less';

.settings-content {
    .loader {
        margin-top: 4px;
        float: right;
    }

    .multiselect__option--highlight {
        background: @color-primary;

        &::after {
            background: @color-primary;
        }

        &.multiselect__option--selected {
            background: rgb(217, 83, 79) !important;

            &::after {
                background: rgb(217, 83, 79) !important;
            }
        }
    }

    td {
        vertical-align: middle;
        text-align: left;

        &:first-child {
            width: 10em;
        }
    }
}
</style>
