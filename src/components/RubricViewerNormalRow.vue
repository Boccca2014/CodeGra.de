<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="rubric-viewer-row normal"
     :class="{ editable, locked }"
     @mouseenter="lockPopoverVisible = true"
     @mouseleave="lockPopoverVisible = false">
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
               class="d-block text-wrap-pre mb-2"
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

    <div class="rubric-row-items position-relative d-flex flex-row">
        <div v-for="item, i in rowItems"
             class="rubric-item pt-2 pl-2"
             :class="{
                 selected: item.id === selectedId,
                 'border-left': i > 0,
                 'pb-4': showProgressMeter,
             }"
             :style="{ flex: `0 0 ${itemWidth}`, maxWidth: itemWidth  }"
             @click="toggleItem(item)">
            <b class="mb-2">
                {{ item.points }} - {{ item.header }}

                <fa-icon v-if="item.id === selectedId"
                         name="check"
                         class="float-right mr-2" />
            </b>

            <p v-if="!item.description"
               class="text-muted font-italic">
                No description.
            </p>
            <inner-markdown-viewer
                v-if="rubricRow.isMarkdown"
                :markdown="item.description"
                class="description pr-2 text-justify" />
            <p v-else
               class="description mb-0 pb-2 pr-2 text-justify text-wrap-pre"
               >{{ item.description }}</p>
        </div>

        <div class="progress-meter"
             :style="{
                 opacity: showProgressMeter ? 1 : 0,
                 width: `${autoTestProgress}%`,
             }">
            <small :class="`progress-${readableAutoTestProgress}`">
                {{ readableAutoTestProgress }}%
            </small>
        </div>
    </div>
</div>
</template>

<script>
import 'vue-awesome/icons/lock';
import 'vue-awesome/icons/check';

import { AutoTestResult, RubricRow, RubricResult } from '@/models';

import InnerMarkdownViewer from './InnerMarkdownViewer';

export default {
    name: 'rubric-viewer-normal-row',

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
        rowItems() {
            return this.rubricRow.items;
        },

        selectedItem() {
            return this.value.selected[this.rubricRow.id];
        },

        selectedId() {
            return this.$utils.getProps(this.selectedItem, null, 'id');
        },

        locked() {
            return this.rubricRow.locked;
        },

        showProgressMeter() {
            return this.locked === 'auto_test' && this.autoTestProgress != null;
        },

        lockPopover() {
            return this.rubricRow.lockMessage(this.autoTest, this.autoTestResult, this.value);
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

        readableAutoTestProgress() {
            const progress = this.autoTestProgress;
            return progress == null ? 0 : progress.toFixed(0);
        },

        itemWidth() {
            return `${100 / this.rowItems.length}%`;
        },
    },

    methods: {
        toggleItem(item) {
            if (!this.editable || this.locked) {
                return;
            }

            this.$emit(
                'input',
                item.id === this.selectedId ? null : Object.assign({}, item, { multiplier: 1 }),
            );
        },
    },

    components: {
        InnerMarkdownViewer,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.rubric-item {
    line-height: 1.3;

    .rubric-viewer.editable .rubric-viewer-row.normal:not(.locked) & {
        cursor: pointer;

        &:hover {
            background-color: darken(@card-header-background, 5%);

            @{dark-mode} {
                background-color: darken(@dark-card-header-background, 5%);
            }
        }
    }

    &.selected {
        background-color: @card-header-background;

        @{dark-mode} {
            background-color: @dark-card-header-background;
        }
    }

    .description {
        max-height: 5rem;
        overflow: auto;
    }
}
</style>
