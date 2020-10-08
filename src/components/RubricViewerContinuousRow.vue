<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="rubric-viewer-row continuous"
     :class="{ editable, locked }"
     @mouseenter="lockPopoverVisible = true"
     @mouseleave="lockPopoverVisible = false">
    <div class="rubric-row-header">
        <div class="row-description d-flex border-bottom">
            <p class="flex-grow-1 mb-0 pt-2 px-3">
                <span v-if="!rubricRow.description"
                    class="d-block mb-2 text-muted font-italic">
                    This category has no description.
                </span>
                <inner-markdown-viewer
                    v-else-if="rubricRow.isMarkdown"
                    :markdown="rubricRow.description"
                    class="mb-2" />
                <span v-else
                   class="d-block mb-2 text-wrap-pre"
                   >{{ rubricRow.description }}</span>
            </p>

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

        <div class="position-relative mb-0 pt-2 pb-4 px-4">
            <b>0</b>
            <b class="float-right">{{ onlyItem.points }}</b>

            <div class="progress-meter"
                 :style="{
                     opacity: showProgressMeter ? 1 : 0,
                     width: `${progressWidth}%`,
                 }">
                <small class="text-center" :class="`progress-${readableMultiplier}`">
                    {{ readableScore }}
                </small>
            </div>
        </div>
    </div>

    <b-input-group class="percentage-input"
                   append="%">
        <cg-number-input
               class="percentage border-bottom-0 border-left-0 rounded-left-0"
               :min="0"
               :max="100"
               placeholder="Percentage"
               :disabled="!editable || locked"
               :value="multiplier"
               debounce
               @input="setMultiplier"
               @keydown.ctrl.enter.native="submitResult"
               ref="multiplierInput" />
    </b-input-group>
</div>
</template>

<script>
import 'vue-awesome/icons/lock';
import 'vue-awesome/icons/check';

import { AutoTestResult, RubricRow, RubricResult } from '@/models';
import { Nothing } from '@/utils';

import InnerMarkdownViewer from './InnerMarkdownViewer';
import { numberInputValue } from './NumberInput';

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

            let val;
            if (typeof this.autoTestProgress === 'number') {
                val = this.autoTestProgress;
            } else if (typeof resultMult === 'number') {
                // Prevent rounding errors such as 58 -> 57.999...
                val = Number(this.$utils.toMaxNDecimals(100 * resultMult, 2));
            } else {
                val = null;
            }

            return numberInputValue(val);
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

        maybeMultiplier() {
            return this.multiplier.orDefault(Nothing);
        },

        readableMultiplier() {
            return this.maybeMultiplier.mapOrDefault(
                m => this.$utils.toMaxNDecimals(m, 0),
                null,
            );
        },

        readableScore() {
            return this.maybeMultiplier.mapOrDefault(
                m => this.$utils.toMaxNDecimals(this.onlyItem.points * m / 100, 2),
                null,
            );
        },

        locked() {
            return this.rubricRow.locked;
        },

        showProgressMeter() {
            return this.maybeMultiplier.mapOrDefault(() => true, false);
        },

        progressWidth() {
            return this.maybeMultiplier.extractNullable();
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
        setMultiplier(errOrMul) {
            errOrMul.ifRight(mul => this.emitItem(
                mul.map(m => m / 100).extractNullable(),
            ));
        },

        submitResult() {
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
                input.$el.focus();
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
