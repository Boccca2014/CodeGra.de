<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<cg-loader class="rubric-editor" v-if="loading"/>

<b-alert show
         variant="danger"
         v-else-if="error != null">
    {{ $utils.getErrorMessage(error) }}
</b-alert>

<div v-else-if="!editable && rubric == null"
     class="rubric-editor text-muted font-italic">
    There is no rubric for this assignment.
</div>

<div v-else-if="editable && rubric === null && !showRubricImporter"
     class="rubric-editor d-flex flex-row justify-content-center"
     :class="{ grow, editable }">
    <cg-wizard-button
        label="Create new rubric"
        icon="plus"
        @click="createRubric" />

    <cg-wizard-button
        label="Copy a rubric"
        icon="copy"
        @click="showRubricImporter = true" />
</div>

<div v-else-if="editable && showRubricImporter"
     class="rubric-editor">
    <h4 class="text-center mb-3">Select an assignment to copy from</h4>

    <b-alert v-if="loadAssignmentsError"
             variant="danger"
             class="mb-0"
             show>
        Loading assignments failed: {{ loadAssignmentsError }}
    </b-alert>

    <b-input-group v-else class="mb-3">
        <multiselect
            class="assignment-selector"
            v-model="importAssignment"
            :options="otherAssignmentsWithRubric || []"
            :searchable="true"
            :custom-label="a => `${a.course.name} - ${a.name}`"
            :multiple="false"
            track-by="id"
            label="label"
            :close-on-select="true"
            :hide-selected="false"
            placeholder="Type to search an assignment"
            :internal-search="true"
            :loading="loadingAssignments">
            <span slot="noResult">
                No results were found.
            </span>
        </multiselect>
    </b-input-group>

    <b-button-toolbar justify>
        <b-button @click="showRubricImporter = false">
            Go back
        </b-button>

        <cg-submit-button :disabled="!importAssignment"
                          label="Import"
                          :submit="loadOldRubric"
                          @after-success="afterLoadOldRubric"/>
    </b-button-toolbar>
</div>

<div v-else
     class="rubric-editor"
     :class="{ grow, editable }">
    <b-tabs no-fade
            nav-class="border-0"
            v-model="currentCategory">
        <b-nav-item slot="tabs-end"
                    class="add-row font-weight-bold"
                    @click.prevent="createRow"
                    href="#"
                    v-b-popover.top.hover="'Click here to add a new category.'"
                    v-if="editable">
            <fa-icon name="plus" class="align-middle"/>
        </b-nav-item>

        <b-tab class="border px-3 pt-3 pb-0"
               :class="{ 'rounded-bottom': editable, 'border-bottom-0': !editable }"
               v-for="row, i in rubricRows"
               :key="`rubric-${id}-${i}`">

            <template #title>
                <template v-if="row.header">
                    {{ row.header }}
                </template>

                <span v-else
                      class="text-muted font-italic">
                    Unnamed
                </span>

                <b-badge v-if="row.locked === 'auto_test'"
                         title="This is an AutoTest category"
                         variant="primary"
                         class="ml-1">
                    AT
                </b-badge>
            </template>

            <template v-if="row.type == '' && editable">
                <h4 class="text-center py-2">Select the type of category</h4>

                <div class="d-flex flex-row justify-content-center mb-3">
                    <cg-wizard-button
                        label="Discrete"
                        icon="ellipsis-h"
                        size="small"
                        @click="setRowType(i, 'normal')" />

                    <cg-wizard-button
                        label="Continuous"
                        icon="progress"
                        size="small"
                        @click="setRowType(i, 'continuous')" />
                </div>
            </template>

            <component
                v-else-if="row.type !== ''"
                :is="`rubric-editor-${row.type}-row`"
                :value="row"
                :assignment="assignment"
                :auto-test="autoTestConfig"
                :editable="editable"
                :active="currentCategory === i"
                :grow="grow"
                @input="rowChanged(i, $event)"
                @submit="() => $refs.submitButton.onClick()"
                @delete="deleteRow(i)" />

            <b-alert v-else show variant="danger">
                Something went wrong unexpectedly!
            </b-alert>
        </b-tab>

        <h4 v-if="editable"
             slot="empty"
             class="border rounded-bottom p-5 text-center text-muted">
            Click the '+' above to add a category.
        </h4>
    </b-tabs>

    <template v-if="editable">
        <b-alert v-if="showMaxPointsWarning"
                 class="max-points-warning mt-3"
                 variant="warning"
                 show>
            {{ maximumPointsWarningText }}
        </b-alert>

        <b-button-toolbar v-if="rubric"
                          class="my-3 justify-content-center">
            <b-input-group class="max-points-input-group">
                <b-input-group-prepend is-text>
                    Points needed for a 10:
                </b-input-group-prepend>

                <input type="number"
                       min="0"
                       step="1"
                       class="max-points form-control"
                       @keydown.ctrl.enter="() => $refs.submitButton.onClick()"
                       v-model="internalFixedMaxPoints"
                       :placeholder="rubricMaxPoints" />

                <b-input-group-append is-text>
                    out of {{ rubricMaxPoints }}

                    <cg-description-popover hug-text placement="top">
                        The number of points a student must achieve in this
                        rubric to achieve the maximum grade. By default students
                        must achieve the top item in each discrete category and
                        100% in each continuous category.<br>

                        Setting this lower than the maximum amount of points
                        possible for this rubric makes it easier to achieve the
                        maximum grade.<br>

                        Values higher than the maximum amount of points make it
                        impossible to achieve the maximum grade.
                    </cg-description-popover>
                </b-input-group-append>
            </b-input-group>
        </b-button-toolbar>

        <hr />

        <b-button-toolbar justify>
            <b-button-group v-if="serverData == null && rubricRows.length === 0">
                <b-button @click="rubric = null">
                    Go back
                </b-button>
            </b-button-group>

            <!-- Can't use a b-button-group here; for some reason the
                 confirmation modal in the submit button glitches like hell
                 when the button is in a button group... -->
            <div v-else-if="rubric != null"
                 class="d-inline-flex align-middle">
                <cg-submit-button class="delete-rubric border-right rounded-right-0"
                                  style="margin-right: -1px;"
                                  variant="danger"
                                  v-b-popover.top.hover="'Delete rubric'"
                                  :submit="deleteRubric"
                                  :filter-error="deleteFilter"
                                  @after-success="afterDeleteRubric"
                                  confirm="By deleting a rubric the rubric and all grades given with it
                                       will be lost forever! So are you really sure?"
                                  confirm-in-modal>
                    <fa-icon name="times"/>
                </cg-submit-button>

                <cg-submit-button class="reset-rubric border-left rounded-left-0"
                                  variant="danger"
                                  v-b-popover.top.hover="'Reset rubric'"
                                  :submit="resetRubric"
                                  confirm="Are you sure you want to revert your changes?"
                                  :disabled="serverData != null && rubricRows.length === 0">
                    <fa-icon name="reply"/>
                </cg-submit-button>
            </div>

            <cg-submit-button class="submit-rubric"
                              ref="submitButton"
                              :confirm="shouldConfirm ? 'yes' : ''"
                              :submit="submit"
                              @after-success="afterSubmit">
                <div slot="confirm" class="text-justify">
                    <template v-if="rowsWithSingleItem.length > 0">
                        <b>Rows with only a single item</b>

                        <p class="mb-2">
                            The following categories contain only a single
                            item, which means it is only possible to select
                            this item, and an AutoTest will always select it:
                        </p>

                        <ul>
                            <li v-for="row in rowsWithSingleItem">
                                {{ row.nonEmptyHeader }} - {{ row.items[0].nonEmptyHeader }}
                            </li>
                        </ul>
                    </template>

                    <template v-if="rowsWithEqualItems.length > 0">
                        <b>Rows with items with equal points</b>

                        <p class="mb-2">
                            The following categories contain items with an
                            equal number of points, which can lead to
                            unpredictable behavior when filled by an AutoTest:
                        </p>

                        <ul>
                            <li v-for="row in rowsWithEqualItems">
                                {{ row }}
                            </li>
                        </ul>
                    </template>

                    <template v-if="rowsWithoutZeroItem.length > 0">
                        <b>Rows without items with 0 points</b>

                        <p class="mb-2">
                            There are categories without an item with zero
                            points, without which it may be unclear if the
                            category is yet to be filled in or was
                            intentionally left blank. The following categories
                            do not contain an item with 0 points:
                        </p>

                        <ul>
                            <li v-for="row in rowsWithoutZeroItem">
                                {{ row.nonEmptyHeader }}
                            </li>
                        </ul>
                    </template>

                    <template v-if="deletedItems.length > 0">
                        <b>Deleted item{{ deletedItems.length > 1 ? 's' : ''}}</b>

                        <p class="mb-2">
                            The following
                            item{{ deletedItems.length > 1 ? 's were' : ' was'}}
                            removed from the rubric:
                        </p>

                        <ul class="mb-2">
                            <li v-for="item in deletedItems">{{ item }}</li>
                        </ul>
                    </template>

                    <p class="mb-2">
                        Are you sure you want to save this rubric?
                    </p>
                </div>

                <div slot="error"
                     slot-scope="scope"
                     class="submit-popover text-justify">
                    <template v-if="scope.error instanceof ValidationError">
                        <p v-if="scope.error.unnamed" class="mb-2">
                            There are unnamed categories.
                        </p>

                        <p v-if="scope.error.categories.length > 0" class="mb-2">
                            The following categor{{ scope.error.categories.length >= 2 ? 'ies have' : 'y has' }}
                            no items.

                            <ul>
                                <li v-for="msg in scope.error.categories">
                                    {{ msg }}
                                </li>
                            </ul>
                        </p>

                        <p v-if="scope.error.continuous.length > 0" class="mb-2">
                            The following continuous
                            categor{{ scope.error.categories.length >= 2 ? 'ies have' : 'y has' }}
                            a score less than 0 which is not supported.

                            <ul>
                                <li v-for="msg in scope.error.continuous">
                                    {{ msg }}
                                </li>
                            </ul>
                        </p>

                        <p v-if="scope.error.itemHeader.length > 0" class="mb-2">
                            The following
                            categor{{ scope.error.itemHeader.length >= 2 ? 'ies have' : 'y has' }}
                            items without a name:

                            <ul>
                                <li v-for="msg in scope.error.itemHeader">
                                    {{ msg }}
                                </li>
                            </ul>
                        </p>

                        <p v-if="scope.error.itemPoints.length > 0" class="mb-2">
                            Make sure "points" is a number for the following
                            item{{ scope.error.itemPoints.length >= 2 ? 's' : '' }}:

                            <ul>
                                <li v-for="msg in scope.error.itemPoints">
                                    {{ msg }}
                                </li>
                            </ul>
                        </p>

                        <p v-if="scope.error.maxPoints" class="mb-2">
                            The given max points {{ this.internalFixedMaxPoints }} is not a number.
                        </p>
                    </template>

                    <p v-else>
                        {{ $utils.getErrorMessage(scope.error) }}
                    </p>
                </div>
            </cg-submit-button>
        </b-button-toolbar>
    </template>

    <p class="max-points border rounded-bottom p-3 mb-3" v-else>
        To get a full mark you need to score
        {{ internalFixedMaxPoints || rubricMaxPoints }} points in this rubric.
    </p>
</div>
</template>

<script>
import Multiselect from 'vue-multiselect';
import { mapActions, mapGetters } from 'vuex';

import 'vue-awesome/icons/copy';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/reply';
import 'vue-awesome/icons/ellipsis-h';

import { NONEXISTENT } from '@/constants';
import { Rubric } from '@/models';
import { ValidationError } from '@/models/errors';
import { formatGrade } from '@/utils';

import RubricEditorNormalRow from './RubricEditorNormalRow';
import RubricEditorContinuousRow from './RubricEditorContinuousRow';

export default {
    name: 'rubric-editor',

    props: {
        assignment: {
            type: Object,
            required: true,
        },
        editable: {
            type: Boolean,
            default: false,
        },
        hidden: {
            type: Boolean,
            default: false,
        },
        grow: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            id: this.$utils.getUniqueId(),
            rubric: null,
            loading: true,
            error: null,
            currentCategory: 0,
            internalFixedMaxPoints: this.assignment.fixed_max_rubric_points,
            assignmentsWithRubric: null,
            importAssignment: null,
            loadingAssignments: false,
            loadAssignmentsError: '',
            showRubricImporter: false,

            ValidationError,
        };
    },

    watch: {
        assignmentId: {
            immediate: true,
            handler() {
                this.assignmentsWithRubric = null;
                this.loadData();
            },
        },

        hidden() {
            this.maybeLoadOtherAssignments();
        },

        editable() {
            this.maybeLoadOtherAssignments();
        },

        serverData() {
            this.resetRubric();
        },
    },

    computed: {
        ...mapGetters('autotest', {
            allAutoTests: 'tests',
        }),

        ...mapGetters('rubrics', {
            allRubrics: 'rubrics',
        }),

        assignmentId() {
            return this.assignment.id;
        },

        serverData() {
            const rubric = this.allRubrics[this.assignment.id];
            return rubric === NONEXISTENT ? null : rubric;
        },

        serverItemIds() {
            return this.serverData && this.serverData.getItemIds();
        },

        rubricRows() {
            return this.$utils.getProps(this.rubric, [], 'rows');
        },

        itemIds() {
            return this.rubric && this.rubric.getItemIds();
        },

        deletedItems() {
            const curItems = this.itemIds;
            const oldItems = this.serverItemIds;

            if (curItems == null || oldItems == null) {
                return [];
            }

            const removedIds = Object.keys(oldItems).filter(id => curItems[id] == null);
            return removedIds.map(id => oldItems[id]);
        },

        rubricMaxPoints() {
            return this.rubric.maxPoints;
        },

        autoTestConfigId() {
            return this.assignment.auto_test_id;
        },

        autoTestConfig() {
            return this.autoTestConfigId && this.allAutoTests[this.autoTestConfigId];
        },

        maximumPointsWarningText() {
            const num = Number(this.internalFixedMaxPoints);
            if (num < this.rubricMaxPoints) {
                return `This means that a 10 will already be achieved with ${num} out of ${
                    this.rubricMaxPoints
                } rubric points.`;
            } else if (num > this.rubricMaxPoints) {
                return `This means that it will not be possible to achieve a 10; a ${formatGrade(
                    this.rubricMaxPoints / num * 10,
                )} will be the maximum achievable grade.`;
            } else {
                return null;
            }
        },

        showMaxPointsWarning() {
            const num = parseFloat(this.internalFixedMaxPoints);
            return !Number.isNaN(num) && num !== this.rubricMaxPoints;
        },

        rowsWithEqualItems() {
            return this.rubricRows.reduce((acc, row) => {
                const points = new Set();
                for (let i = 0, l = row.items.length; i < l; i++) {
                    const itemPoints = row.items[i].points;
                    if (points.has(itemPoints)) {
                        acc.push(row.header);
                        break;
                    }
                    points.add(itemPoints);
                }
                return acc;
            }, []);
        },

        rowsWithSingleItem() {
            return this.rubricRows.filter(row => row.type === 'normal' && row.items.length === 1);
        },

        rowsWithoutZeroItem() {
            return this.rubricRows.filter(
                row => row.type === 'normal' && !row.items.find(item => item.points === 0),
            );
        },

        shouldConfirm() {
            return (
                this.deletedItems.length +
                    this.rowsWithEqualItems.length +
                    this.rowsWithoutZeroItem.length +
                    this.rowsWithSingleItem.length >
                0
            );
        },

        otherAssignmentsWithRubric() {
            return this.assignmentsWithRubric.filter(assig => assig.id !== this.assignmentId);
        },
    },

    methods: {
        ...mapActions('submissions', ['forceLoadSubmissions']),

        ...mapActions('autotest', {
            storeLoadAutoTest: 'loadAutoTest',
        }),

        ...mapActions('rubrics', {
            storeLoadRubric: 'loadRubric',
            storeCopyRubric: 'copyRubric',
            storeUpdateRubric: 'updateRubric',
            storeDeleteRubric: 'deleteRubric',
        }),

        loadData() {
            this.loading = true;
            this.rubric = null;

            Promise.all([
                this.storeLoadRubric({
                    assignmentId: this.assignmentId,
                }).then(
                    () => {
                        this.resetRubric();
                        this.maybeLoadOtherAssignments();
                    },
                    this.$utils.makeHttpErrorHandler({
                        404: () => {},
                    }),
                ),
                this.autoTestConfigId &&
                    this.storeLoadAutoTest({
                        autoTestId: this.autoTestConfigId,
                    }).catch(err => {
                        // eslint-disable-next-line
                        console.log('Could not load AutoTest configuration.', err);
                    }),
            ]).then(
                () => {
                    this.error = null;
                    this.loading = false;
                },
                err => {
                    this.error = err;
                    this.loading = false;
                },
            );
        },

        createRubric() {
            this.rubric = Rubric.fromServerData([]);
        },

        maybeLoadOtherAssignments() {
            if (
                this.editable &&
                !this.hidden &&
                this.assignmentsWithRubric === null &&
                this.rubricRows.length === 0
            ) {
                this.loadAssignments();
            }
        },

        loadAssignments() {
            this.loadingAssignments = true;
            this.assignmentsWithRubric = [];
            this.$http.get('/api/v1/assignments/?only_with=rubric').then(
                ({ data }) => {
                    this.assignmentsWithRubric = data;
                    this.loadingAssignments = false;
                },
                err => {
                    this.loadAssignmentsError = this.$utils.getErrorMessage(err);
                    this.loadingAssignments = false;
                },
            );
        },

        loadOldRubric() {
            return this.storeCopyRubric({
                assignmentId: this.assignmentId,
                otherAssignmentId: this.importAssignment.id,
            });
        },

        afterLoadOldRubric() {
            this.showRubricImporter = false;
            this.importAssignment = null;
            this.forceLoadSubmissions(this.assignmentId);
            this.resetRubric();
        },

        resetRubric() {
            if (this.serverData == null) {
                this.rubric = null;
            } else {
                this.rubric = this.serverData;
            }
        },

        deleteRubric() {
            return this.storeDeleteRubric({
                assignmentId: this.assignmentId,
            });
        },

        deleteFilter(err) {
            if (err.response && err.response.status === 404) {
                return err;
            } else {
                throw err;
            }
        },

        afterDeleteRubric() {
            this.loadAssignments();
            this.resetRubric();
        },

        validateRubric() {
            if (this.rubricRows.length === 0) {
                throw new Error('This rubric is empty, you should create at least one category.');
            }

            const errors = this.rubricRows.reduce((acc, cur) => cur.validate(acc), null);

            const maxPoints = this.internalFixedMaxPoints;
            if (maxPoints === '' || maxPoints == null) {
                this.internalFixedMaxPoints = null;
            } else if (Number.isNaN(Number(maxPoints))) {
                errors.maxPoints = true;
            } else {
                this.internalFixedMaxPoints = Number(maxPoints);
            }

            errors.throwOnError();
        },

        submit() {
            this.ensureEditable();
            this.validateRubric();

            return this.storeUpdateRubric({
                assignmentId: this.assignmentId,
                rows: this.rubricRows,
                maxPoints: this.internalFixedMaxPoints,
            });
        },

        afterSubmit() {
            this.forceLoadSubmissions(this.assignmentId);
        },

        ensureEditable() {
            if (!this.editable) {
                throw new Error('This rubric editor is not editable!');
            }
        },

        createRow() {
            this.ensureEditable();
            this.rubric = this.rubric.createRow();

            this.$afterRerender(() => {
                this.currentCategory = this.rubric.rows.length - 1;
            });
        },

        deleteRow(idx) {
            this.ensureEditable();

            const rows = this.rubricRows;

            if (rows[idx] == null) {
                throw new Error('Deleting nonexistent row.');
            } else if (rows[idx].locked) {
                throw new Error(`This rubric category is locked by: ${rows[idx].locked}.`);
            }

            this.rubric = this.rubric.deleteRow(idx);
        },

        rowChanged(idx, rowData) {
            this.rubric = this.rubric.updateRow(idx, rowData);
        },

        setRowType(idx, type) {
            const row = this.rubric.rows[idx].setType(type);
            this.rubric = this.rubric.updateRow(idx, row);
        },
    },

    components: {
        RubricEditorNormalRow,
        RubricEditorContinuousRow,
        Multiselect,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.rubric-editor {
    &.grow {
        min-height: 100%;
        display: flex;
        flex-direction: column;
    }
}

.wizard-button-container:not(:last-child) {
    margin-right: 1rem;
}

input.max-points {
    width: 6.66rem;
}
</style>

<style lang="less">
@import '~mixins.less';

.rubric-editor {
    &:not(.editable) .nav-tabs {
        .nav-item:first-child {
            margin-left: 15px;
        }
    }

    .nav-tabs {
        .nav-item.add-row .nav-link {
            .primary-button-color;
            transition: background-color @transition-duration;
            color: white;
        }

        .badge {
            transform: translateY(-2px);
        }
    }

    .tab-pane {
        padding-bottom: 0;
    }

    .assignment-selector {
        z-index: 8;
    }
}
</style>
