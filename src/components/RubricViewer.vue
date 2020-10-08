<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div v-if="rubric && result"
     class="rubric-viewer"
     :class="{ editable }">
    <b-tabs no-fade
            v-model="currentCategory">
        <b-tab v-for="row, i in rubric.rows"
               :key="`rubric-${row.id}`"
               title-link-class="d-flex flex-row align-items-center text-nowrap">
            <template #title>
                <span v-if="row.header"
                     class="d-inline-block text-truncate"
                     :title="row.header">
                    {{ row.header }}
                </span>

                <span v-else
                      class="text-muted font-italic">
                    Unnamed
                </span>

                <template v-if="Object.hasOwnProperty.call(selectedItems, row.id)">
                    - <sup>{{
                        $utils.toMaxNDecimals(selectedItems[row.id], 2)
                    }}</sup>&frasl;<sub>{{
                        row.maxPoints
                    }}</sub>
                </template>

                <template v-else-if="!editable">
                    - <sup>Nothing</sup>&frasl;<sub>{{
                        row.maxPoints
                    }}</sub>
                </template>

                <b-badge v-if="row.locked === 'auto_test'"
                         title="This is an AutoTest category"
                         variant="primary"
                         class="ml-1">
                    AT
                </b-badge>
            </template>

            <component
                v-if="row.type === 'normal' || row.type === 'continuous'"
                :is="`rubric-viewer-${row.type}-row`"
                class="border border-top-0 rounded rounded-top-0"
                :value="internalResult"
                @input="resultUpdated(row.id, $event)"
                @submit="$emit('submit')"
                :rubric-row="row"
                :assignment="assignment"
                :auto-test="autoTestConfig"
                :auto-test-result="autoTestResult"
                :editable="editable"
                :active="currentCategory === i" />
        </b-tab>
    </b-tabs>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/angle-left';
import 'vue-awesome/icons/angle-right';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/lock';

import * as constants from '@/constants';
import { RubricResult } from '@/models';

import Loader from './Loader';
import RubricViewerNormalRow from './RubricViewerNormalRow';
import RubricViewerContinuousRow from './RubricViewerContinuousRow';

export default {
    name: 'rubric-viewer',

    props: {
        assignment: {
            type: Object,
            required: true,
        },
        submission: {
            type: Object,
            required: true,
        },
        editable: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            id: this.$utils.getUniqueId(),
            currentCategory: 0,
            changedItems: {},
        };
    },

    computed: {
        ...mapGetters('rubrics', {
            storeRubrics: 'rubrics',
            storeRubricResults: 'results',
        }),

        ...mapGetters('autotest', {
            storeAutoTests: 'tests',
            storeAutoTestResults: 'results',
        }),

        rubric() {
            const rubric = this.storeRubrics[this.assignmentId];
            return rubric === constants.NONEXISTENT ? null : rubric;
        },

        result() {
            return this.storeRubricResults[this.submissionId];
        },

        internalResult() {
            const selected = Object.assign({}, this.result.selected);
            Object.entries(this.changedItems).forEach(([rowId, item]) => {
                if (item == null) {
                    delete selected[rowId];
                } else {
                    selected[rowId] = item;
                }
            });
            return new RubricResult(this.submissionId, selected);
        },

        assignmentId() {
            return this.assignment.id;
        },

        submissionId() {
            return this.submission.id;
        },

        selectedItems() {
            const selected = this.$utils.getProps(this.internalResult, {}, 'selected');
            return Object.entries(selected).reduce((acc, [rowId, item]) => {
                const points = parseFloat(item.points);
                const mult = parseFloat(item.multiplier);
                if (!Number.isNaN(points) && !Number.isNaN(mult)) {
                    acc[rowId] = mult * points;
                }
                return acc;
            }, {});
        },

        autoTestConfigId() {
            return this.assignment.auto_test_id;
        },

        autoTestConfig() {
            return this.storeAutoTests[this.autoTestConfigId];
        },

        autoTestResult() {
            return Object.values(this.storeAutoTestResults).find(
                r => r.submissionId === this.submissionId,
            );
        },
    },

    watch: {
        assignmentId: {
            immediate: true,
            handler() {
                this.storeLoadRubric({
                    assignmentId: this.assignmentId,
                });

                if (this.autoTestConfigId) {
                    this.storeLoadAutoTest({
                        autoTestId: this.autoTestConfigId,
                    }).catch(this.$utils.makeHttpErrorHandler({
                        403: () => {},
                    }));
                }
            },
        },

        submissionId: {
            immediate: true,
            handler() {
                this.reset();

                this.storeLoadRubricResult({
                    submissionId: this.submissionId,
                    assignmentId: this.assignmentId,
                });

                if (this.autoTestConfigId) {
                    this.storeLoadAutoTestResult({
                        autoTestId: this.autoTestConfigId,
                        submissionId: this.submissionId,
                    }).catch(
                        // Autotest hasn't been started yet.
                        () => {},
                    );
                }
            },
        },

        result: {
            immediate: true,
            handler() {
                // Do not emit the result while it is still loading. This can
                // happen, for example, when the "reload submissions" button in
                // the sidebar is clicked.
                if (this.result != null) {
                    this.$emit('load', this.internalResult);
                }
            },
        },
    },

    mounted() {
        this.$root.$on('cg::rubric-viewer::open-category', this.gotoCategory);
        this.$root.$on('cg::rubric-viewer::reset', this.reset);
    },

    destroyed() {
        this.$root.$off('cg::rubric-viewer::open-category', this.gotoCategory);
        this.$root.$off('cg::rubric-viewer::reset', this.reset);
    },

    methods: {
        ...mapActions('rubrics', {
            storeLoadRubric: 'loadRubric',
            storeLoadRubricResult: 'loadResult',
        }),

        ...mapActions('autotest', {
            storeLoadAutoTest: 'loadAutoTest',
            storeLoadAutoTestResult: 'loadAutoTestResult',
        }),

        resultUpdated(rowId, item) {
            this.$set(this.changedItems, rowId, item);
            this.$emit('input', this.internalResult);
        },

        reset() {
            this.changedItems = {};
        },

        gotoCategory(rowId) {
            this.currentCategory = this.rubric.rows.findIndex(row => row.id === rowId);
        },
    },

    components: {
        Icon,
        Loader,
        RubricViewerNormalRow,
        RubricViewerContinuousRow,
    },
};
</script>

<style lang="less">
@import '~mixins.less';

.rubric-viewer {
    .nav-link.active {
        background-color: @card-header-background;
        border-bottom-color: @card-header-background;

        @{dark-mode} {
            border-bottom-color: @dark-card-header-background !important;
            background-color: @dark-card-header-background !important;
        }
    }
}

.rubric-viewer-row {
    .row-description {
        position: relative;
        max-height: 6.66rem;
        overflow: auto;
        line-height: 1.3;
        background-color: @card-header-background;

        @{dark-mode} {
            background-color: @dark-card-header-background;
        }

        .rubric-lock {
            position: sticky;
            top: 0.5rem;
        }
    }

    .progress-meter {
        position: absolute;
        top: 0;
        left: 0;
        height: 100%;
        pointer-events: none;
        background-color: fade(@color-secondary, 10%);
        border-right: 1px solid fade(@color-secondary, 15%);
        color: @color-secondary;
        transition: width @transition-duration;

        @{dark-mode} {
            background-color: fade(white, 15%);
            border-right: 1px solid fade(white, 25%);
            color: @text-color-dark;
        }

        small {
            position: absolute;
            bottom: 0.5rem;
            right: 0.5rem;
            line-height: 1;
            font-size: 90%;
            text-shadow: -1px 0 rgba(255, 255, 255, 0.75), 0 1px rgba(255, 255, 255, 0.75),
                1px 0 rgba(255, 255, 255, 0.75), 0 -1px rgba(255, 255, 255, 0.75);
            font-weight: bold !important;

            @{dark-mode} {
                text-shadow: -1px 0 @color-primary, 0 1px @color-primary, 1px 0 @color-primary,
                    0 -1px @color-primary;
            }

            &.progress-0,
            &.progress-1,
            &.progress-2 {
                left: 0.5rem;
            }

            @media @media-no-large {
                &.progress-3,
                &.progress-4,
                &.progress-5,
                &.progress-6 {
                    left: 0.5rem;
                }
            }

            @media @media-small {
                &.progress-7,
                &.progress-8,
                &.progress-9,
                &.progress-10 {
                    left: 0.5rem;
                }
            }
        }
    }
}
</style>

<style lang="less">
.rubric-viewer .inner-markdown-viewer > :last-child {
    margin-bottom: 0;
}
</style>
