<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="rubric-viewer-row continuous"
     :class="{ editable, locked }"
     @mouseenter="lockPopoverVisible = true"
     @mouseleave="lockPopoverVisible = false">
    <div class="rubric-row-header">
        <div class="row-description d-flex border-bottom">
            <p v-if="!rubricRow.description"
               class="flex-grow-1 my-2 px-3 text-muted font-italic"
               >This category has no description.</p>
            <inner-markdown-viewer
                v-else-if="rubricRow.isMarkdown"
                :markdown="rubricRow.description"
                class="flex-grow-1 my-2 px-3" />
            <p v-else
               class="flex-grow-1 my-2 px-3 text-wrap-pre"
               >{{ rubricRow.description }}</p>

            <template v-if="locked">
                <!-- Due to a rendering issue in edge, giving the icon
                     a margin-right moves it left by twice that amount... -->
                <fa-icon name="lock"
                         class="rubric-lock my-2"
                         :class="{ 'mr-3': !$root.isEdge, 'mr-2': $root.isEdge }"
                         :id="`rubric-lock-${id}`" />

                <!-- We need to key this popover to make sure it actually
                    changes when the content changes. -->
                <b-popover :show="lockPopoverVisible"
                           :target="`rubric-lock-${id}`"
                           :content="lockPopover"
                           :key="lockPopover"
                           triggers=""
                           placement="top"
                           boundary="window" />
            </template>
        </div>

        <div class="position-relative mb-0 pt-2 pb-3 px-4"
             :class="{ 'pb-4': showProgressMeter }">
            <b>0</b>
            <b class="float-right">{{ onlyItem.points }}</b>

            <div class="progress-meter"
                 :style="{
                     opacity: showProgressMeter ? 1 : 0,
                     width: `${progressWidth}%`,
                 }">
                <small class="text-center" :class="`progress-${readableMultiplier}`">
                    {{ $utils.toMaxNDecimals(onlyItem.points * multiplier / 100, 2) }}
                </small>
            </div>
        </div>
    </div>

    <b-input-group class="percentage-input"
                   append="%">
        <input class="percentage form-control border-bottom-0 border-left-0 rounded-left-0"
               type="number"
               step="any"
               min="0"
               max="100"
               placeholder="Percentage"
               :value="$utils.toMaxNDecimals(multiplier, 2)"
               :disabled="!editable || locked"
               @input="setMultiplier(timerDelay)"
               @keydown.ctrl.enter="submitResult"
               ref="multiplierInput" />
    </b-input-group>
</div>
</template>

<script>
import 'vue-awesome/icons/lock';
import 'vue-awesome/icons/check';

import { AutoTestResult, RubricRow, RubricResult } from '@/models';

import InnerMarkdownViewer from './InnerMarkdownViewer';

export default {
    name: 'rubric-viewer-continuous-row',

    props: {
        value: {
            type: RubricResult,
            required: true,
        },
        rubricRow: {
            type: RubricRow,
            required: true,
        },
        assignment: {
            type: Object,
            required: true,
        },
        autoTest: {
            type: Object,
            default: null,
        },
        autoTestResult: {
            type: AutoTestResult,
            default: null,
        },
        editable: {
            type: Boolean,
            default: false,
        },
        active: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            id: this.$utils.getUniqueId(),
            lockPopoverVisible: false,
            timerId: null,
            timerDelay: 75,
        };
    },

    computed: {
        onlyItem() {
            return this.rubricRow.items[0];
        },

        resultItem() {
            return this.$utils.getProps(this.value, null, 'selected', this.rubricRow.id);
        },

        multiplier() {
            const resultMult = this.$utils.getProps(this.resultItem, null, 'multiplier');

            if (typeof this.autoTestProgress === 'number') {
                return this.autoTestProgress;
            } else if (typeof resultMult === 'number') {
                return 100 * resultMult;
            } else {
                return null;
            }
        },

        autoTestProgress() {
            if (this.autoTestResult == null) {
                return null;
            }

            const state = this.$utils.getProps(this.autoTestResult, null, 'state');
            const percentage = this.$utils.getProps(
                this.autoTestResult,
                null,
                'rubricResults',
                this.rubricRow.id,
                'percentage',
            );

            return state === 'not_started' ? null : percentage;
        },

        readableMultiplier() {
            return this.$utils.toMaxNDecimals(this.multiplier, 0);
        },

        locked() {
            return this.rubricRow.locked;
        },

        showProgressMeter() {
            if (this.multiplier != null) {
                return this.multiplier >= 0 && this.multiplier <= 100;
            } else {
                return false;
            }
        },

        progressWidth() {
            if (this.multiplier == null) {
                return null;
            } else {
                return Math.max(0, Math.min(this.multiplier, 100));
            }
        },

        lockPopover() {
            return this.rubricRow.lockMessage(this.autoTest, this.autoTestResult, this.value);
        },
    },

    watch: {
        active: {
            immediate: true,
            handler() {
                if (this.active) {
                    this.focusInput();
                }
            },
        },
    },

    methods: {
        setMultiplier(delay = 0) {
            if (!this.editable || this.locked) {
                return;
            }

            clearTimeout(this.timerId);

            const inputEl = this.$refs.multiplierInput;

            let value = parseFloat(inputEl.value);
            if (!Number.isNaN(value)) {
                value /= 100;
            } else if (inputEl.validity.valid) {
                value = null;
            } else {
                return;
            }

            if (delay) {
                this.timerId = setTimeout(() => {
                    this.timerId = null;
                    this.emitItem(value);
                }, this.timerDelay);
            } else {
                this.emitItem(value);
            }
        },

        submitResult() {
            clearTimeout(this.timerId);
            this.setMultiplier(this.$refs.multiplierInput);
            this.$nextTick(() => {
                this.$emit('submit');
            });
        },

        emitItem(multiplier) {
            if (multiplier == null) {
                this.$emit('input', null);
            } else {
                this.$emit('input', Object.assign({}, this.onlyItem, { multiplier }));
            }
        },

        async focusInput() {
            const input = await this.$waitForRef('multiplierInput');
            if (input != null) {
                input.focus();
            }
        },
    },

    components: {
        InnerMarkdownViewer,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.rubric-viewer-row.continuous {
    overflow: hidden;
}

.rubric-item {
    line-height: 1.3;

    .rubric-viewer.editable .rubric-viewer-row.normal:not(.locked) & {
        cursor: pointer;

        &:hover {
            background-color: rgba(0, 0, 0, 0.0625);
        }
    }

    &.selected {
        background-color: rgba(0, 0, 0, 0.125) !important;
    }
}

input.percentage {
    background-color: white;
}
</style>

<style lang="less">
.rubric-viewer-row.continuous .percentage-input {
    .input-group-text {
        border-bottom: 0;
        border-right: 0;
        border-top-right-radius: 0;
    }
}
</style>
