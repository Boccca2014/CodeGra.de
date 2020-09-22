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
            :options="otherAssignmentsWithRubric"
            :searchable="true"
            :custom-label="getImportLabel"
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
    <div class="d-flex flex-row mb-3">
        <slick-list :value="rubricRows"
                    lock-axis="y"
                    lock-to-container-edges
                    :distance="5"
                    :should-cancel-start="() => !editable"
                    @input="reorderRows"
                    @sort-start="onSortStart"
                    @sort-end="onSortEnd"
                    class="category-list flex-grow-0">
            <slick-item v-for="row, i in rubricRows"
                        :key="`rubric-editor-${id}-row-${i}`"
                        :index="i"
                        class="category-item p-2 border border-right-0 cursor-pointer"
                        :class="{
                            grab: editable,
                            grabbing: slickItemMoving,
                            'text-muted font-italic': !row.header,
                            'active': currentCategory === i,
                            'rounded-left rounded-bottom-0': i === 0,
                            'rounded-left rounded-top-0': !editable && i === rubricRows.length - 1,
                        }"
                        @click.native.capture="currentCategory = i">
                <div class="d-inline-block mr-2 text-center"
                     style="width: 1rem"
                     :title="{normal: 'Discrete', continuous: 'Continuous'}[row.type]">
                    <fa-icon v-if="row.type === 'normal'"
                             name="ellipsis-h"
                             title="Discrete category" />
                    <fa-icon v-else-if="row.type === 'continuous'"
                             name="progress"
                             title="Continuous category" />
                </div>

                <div class="flex-grow-1">
                    <b-badge v-if="row.locked === 'auto_test'"
                             title="This is an AutoTest category"
                             variant="primary"
                             class="float-right mt-1 ml-2">
                        AT
                    </b-badge>
                    {{ row.header || 'Unnamed' }}
                </div>
            </slick-item>

            <template v-if="editable">
                <b-button class="w-100 border border-right-0 rounded-right-0"
                          :class="{ 'rounded-top-0': rubricRows.length > 0 }"
                          @click="createRow">
                    <fa-icon name="plus" /> Category
                </b-button>

                <small class="d-block p-2 text-right text-muted">
                    Reorder categories by dragging them up or down
                </small>
            </template>
        </slick-list>

        <template v-if="rubricRows.length === 0">
            <h4 v-if="editable"
                slot="empty"
                class="flex-grow-1 p-5 border rounded-right text-center text-muted">
                Click "<fa-icon name="plus" /> Category" add a category.
            </h4>
        </template>

        <div v-else
             v-for="row in [rubricRows[currentCategory]]"
             class="flex-grow-1 d-flex flex-column px-3 pt-2 border rounded-right rounded-bottom">
            <template v-if="row.type == '' && editable">
                <h4 class="text-center py-2">Select the type of category</h4>

                <div class="d-flex flex-row flex-grow-1 align-items-center justify-content-center mb-3">
                    <cg-wizard-button
                        label="Discrete"
                        icon="ellipsis-h"
                        size="medium"
                        @click="setRowType(currentCategory, 'normal')" />

                    <cg-wizard-button
                        label="Continuous"
                        icon="progress"
                        size="medium"
                        @click="setRowType(currentCategory, 'continuous')" />
                </div>
            </template>

            <component v-else-if="row.type !== ''"
                       :is="`rubric-editor-${row.type}-row`"
                       :value="row"
                       :assignment="assignment"
                       :auto-test="autoTestConfig"
                       :editable="editable"
                       :grow="grow"
                       @input="rowChanged(currentCategory, $event)"
                       @submit="() => $refs.submitButton.onClick()"
                       class="flex-grow-1"/>

            <b-alert v-else show variant="danger">
                Something went wrong unexpectedly!
            </b-alert>

            <div v-if="editable"
                 v-b-popover.top.hover="row.locked ? 'You cannot remove locked categories' : ''"
                 class="align-self-start mb-3">
                <cg-submit-button variant="danger"
                                  class="delete-category flex-grow-0"
                                  :wait-at-least="0"
                                  :submit="() => {}"
                                  :disabled="!!row.locked"
                                  @after-success="deleteRow(currentCategory)"
                                  confirm="Do you really want to delete this category?">
                    <fa-icon v-if="row.locked" name="lock" />
                    Remove category
                </cg-submit-button>
            </div>
        </div>
    </div>

    <template v-if="editable">
        <b-form-group v-if="rubric"
                      label="Points needed for a 10">
            <template #description>
                The number of points a student must achieve in this rubric to
                achieve the maximum grade.

                <cg-description-popover hug-text placement="top">
                    <p class="mb-2">
                        By default students must achieve the top item in each
                        discrete category and 100% in each continuous category.
                    </p>

                    <p class="mb-2">
                        Setting this lower than the maximum amount of points
                        possible for this rubric makes it easier to achieve the
                        maximum grade.
                    </p>

                    <p class="mb-0">
                        Values higher than the maximum amount of points make it
                        impossible to achieve the maximum grade.
                    </p>
                </cg-description-popover>
            </template>

            <b-input-group class="max-points-input-group">
                <input type="number"
                       min="0"
                       step="1"
                       class="max-points form-control"
                       @keydown.ctrl.enter="() => $refs.submitButton.onClick()"
                       v-model="internalFixedMaxPoints"
                       :placeholder="rubricMaxPoints" />

                <b-input-group-append is-text>
                    out of {{ rubricMaxPoints }}
                </b-input-group-append>
            </b-input-group>
        </b-form-group>

        <b-alert v-if="showMaxPointsWarning"
                 class="max-points-warning mt-3"
                 variant="warning"
                 show>
            {{ maximumPointsWarningText }}
        </b-alert>

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
                    <fa-icon name="times"/> Delete
                </cg-submit-button>

                <cg-submit-button class="reset-rubric border-left rounded-left-0"
                                  variant="danger"
                                  v-b-popover.top.hover="'Reset rubric'"
                                  :submit="resetRubric"
                                  confirm="Are you sure you want to revert your changes?"
                                  :disabled="serverData != null && rubricRows.length === 0">
                    <fa-icon name="reply"/> Reset
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

    <p class="max-points border rounded p-3 mb-3" v-else>
        To get a full mark you need to score
        <b>{{ internalFixedMaxPoints || rubricMaxPoints }} points</b>
        in this rubric.
    </p>
</div>
</template>

<script>
import Multiselect from 'vue-multiselect';
import { mapActions, mapGetters } from 'vuex';
import { SlickList, SlickItem } from 'vue-slicksort';

import 'vue-awesome/icons/copy';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/reply';
import 'vue-awesome/icons/ellipsis-h';

import { NONEXISTENT, INITIAL_COURSES_AMOUNT } from '@/constants';
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

            slickItemMoving: false,

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

        editable() {
            this.maybeLoadOtherAssignments();
        },

        serverData() {
            this.resetRubric();
        },

        courseIdsWithRubric(newVal) {
            if (newVal.size > INITIAL_COURSES_AMOUNT) {
                this.loadAllCourses();
            }
            newVal.forEach(courseId => this.loadSingleCourse({ courseId }));
        },
    },

    computed: {
        ...mapGetters('autotest', {
            allAutoTests: 'tests',
        }),

        ...mapGetters('rubrics', {
            allRubrics: 'rubrics',
        }),

        ...mapGetters('assignments', ['getAssignment']),
        ...mapGetters('courses', ['getCourse']),

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
                return `This means that it will not be possible to achieve a 10; ${formatGrade(
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
            return (this.assignmentsWithRubric || []).filter(
                ({ id }) => id !== this.assignmentId,
            );
        },

        courseIdsWithRubric() {
            return this.otherAssignmentsWithRubric.reduce((acc, assigLike) => {
                acc.add(assigLike.courseId);
                return acc;
            }, new Set());
        },

        canMoveLeft() {
            return this.currentCategory > 0;
        },

        canMoveRight() {
            return this.currentCategory < this.rubricRows.length - 1;
        },
    },

    methods: {
        ...mapActions('submissions', ['forceLoadSubmissions']),
        ...mapActions('courses', ['loadSingleCourse', 'loadAllCourses']),

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
                    () => this.resetRubric(),
                    this.$utils.makeHttpErrorHandler({
                        404: () => this.maybeLoadOtherAssignments(),
                    }),
                ),
                this.autoTestConfigId &&
                    this.storeLoadAutoTest({
                        autoTestId: this.autoTestConfigId,
                    }).catch(err => {
                        // eslint-disable-next-line
                        console.log('Could not load AutoTest configuration.', err);
                    }),
                this.maybeLoadOtherAssignments(),
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
                this.assignmentsWithRubric === null &&
                this.rubricRows.length === 0
            ) {
                this.loadAssignments();
            }
        },

        loadAssignments() {
            this.loadingAssignments = true;
            this.assignmentsWithRubric = [];
            const url = this.$utils.buildUrl(
                ['api', 'v1', 'assignments'],
                {
                    query: {
                        no_course_in_assignment: true,
                        only_with_rubric: true,
                    },
                    addTrailingSlash: true,
                },
            );
            this.$http.get(url).then(
                ({ data }) => {
                    // We cannot (!) use real models here as all getters will be
                    // removed by vue-multiselect as it tries to copy the
                    // objects, however that doesn't work with getters.
                    this.assignmentsWithRubric = data.map(x => ({
                        id: x.id,
                        name: x.name,
                        courseId: x.course_id,
                    }));
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
            this.forceLoadSubmissions({
                assignmentId: this.assignmentId,
            });
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
            this.forceLoadSubmissions({ assignmentId: this.assignmentId });
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

            if (idx === rows.length - 1) {
                this.currentCategory -= 1;
            }
        },

        rowChanged(idx, rowData) {
            this.rubric = this.rubric.updateRow(idx, rowData);
        },

        setRowType(idx, type) {
            const row = this.rubric.rows[idx].setType(type);
            this.rubric = this.rubric.updateRow(idx, row);
        },

        getImportLabel(assigLike) {
            const courseName = this.getCourse(assigLike.courseId).mapOrDefault(
                c => c.name,
                '…',
            );
            return `${courseName} - ${assigLike.name}`;
        },

        reorderRows(rows) {
            this.ensureEditable();

            this.rubric = this.rubric.setRows(rows);
        },

        onSortStart() {
            this.slickItemMoving = true;
        },

        onSortEnd({ oldIndex, newIndex }) {
            this.slickItemMoving = false;

            const curr = this.currentCategory;
            if (oldIndex === curr) {
                this.currentCategory = newIndex;
            } else if (oldIndex < curr && newIndex >= curr) {
                this.currentCategory -= 1;
            } else if (oldIndex > curr && newIndex <= curr) {
                this.currentCategory += 1;
            }
        },
    },

    components: {
        RubricEditorNormalRow,
        RubricEditorContinuousRow,
        Multiselect,
        SlickList,
        SlickItem,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.rubric-editor.grow {
    min-height: 100%;
    display: flex;
    flex-direction: column;
}

.wizard-button-container:not(:last-child) {
    margin-right: 1rem;
}

.category-list {
    width: 12rem;
    font-size: 90%;
}

.category-item {
    z-index: 99999;
    user-select: none;
    background-color: rgba(255, 255, 255, 0.75);
    display: flex;
    flex-direction: row;
    align-items: flex-start;

    &:not(:last-child) {
        margin-bottom: -1px;
    }

    &.active {
        background-color: rgba(0, 0, 0, 0.0625);
    }

    &:hover {
        background-color: rgba(0, 0, 0, 0.0925);
    }

    &.grab {
        cursor: grab !important;
    }

    &.grabbing {
        cursor: grabbing !important;
    }
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
    }

    .tab-pane {
        padding-bottom: 0;
    }

    .assignment-selector {
        z-index: 8;
    }

    .inner-markdown-viewer > :last-child {
        margin-bottom: 0.5rem;
    }
}
</style>
