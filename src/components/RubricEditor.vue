<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<cg-loader class="rubric-editor" v-if="loading"/>

<b-alert show
         variant="danger"
         v-else-if="error != null">
    {{ $utils.getErrorMessage(error) }}
</b-alert>

<div v-else-if="!editable && rubric == null"
     class="rubric-editor border rounded p-3 text-muted font-italic">
    There is no rubric for this assignment.
</div>

<div v-else-if="editable && rubric === null && !showRubricImporter"
     class="rubric-editor d-flex flex-row justify-content-center"
     :class="{ editable }">
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
     :class="{ editable }">
    <b-alert v-if="showMaxPointsWarning"
             class="max-points-warning"
             variant="warning"
             show>
        {{ maximumPointsWarningText }}
    </b-alert>

    <div v-if="rubricRows.length === 0"
         class="no-categories border rounded mb-3 p-3 text-muted font-italic">
        The rubric has no categories yet.

        <template v-if="editable">
            Click the buttons below to create a new category.
        </template>
    </div>

    <template v-else>
        <h5 class="position-relative text-center mb-3">
            <fa-icon class="collapse-all-btn text-muted mt-1"
                     :name="collapseAllIcon"
                     @click.native="toggleAllCategories"
                     v-b-popover.hover.top="collapseAllPopover" />

            Categories
        </h5>

        <slick-list :value="rubricRows"
                    lock-axis="y"
                    lock-to-container-edges
                    :should-cancel-start="shouldCancelDrag"
                    @input="reorderRows"
                    @sort-start="onSortStart"
                    @sort-end="onSortEnd"
                    class="category-list">
            <transition-group name="rubric-row">
                <slick-item v-for="row, i in rubricRows"
                            :key="`rubric-editor-${id}-row-${i}`"
                            :index="i"
                            class="category-item d-flex flex-row mb-3"
                            :class="{
                                grab: editable,
                                grabbing: slickItemMoving,
                            }">
                    <div v-handle
                         v-if="editable"
                         class="drag-handle d-flex pr-3 text-muted flex-grow-0">
                        <fa-icon class="align-self-center" name="bars"/>
                    </div>

                    <b-card no-body
                            class="rubric-category flex-grow-1 mb-0">
                        <collapse :collapsed="collapsedCategories[row.trackingId]"
                                  @change="collapsedCategories[row.trackingId] = $event"
                                  :key="row.trackingId">
                            <b-card-header slot="handle"
                                           class="d-flex flex-row align-items-center pl-3"
                                           :class="{ 'pr-1 py-1': editable }">
                                <fa-icon class="chevron" name="chevron-down" :scale="0.75" />

                                <div class="flex-grow-1 px-2">
                                    <template v-if="row.header">
                                        {{ row.header }}
                                    </template>
                                    <span v-else class="text-muted font-italic">
                                        Unnamed
                                    </span>

                                    <small v-if="achievablePointsPerRow[row.trackingId]"
                                           :title="achievablePointsPerRow[row.trackingId].title">
                                        {{ achievablePointsPerRow[row.trackingId].header }}
                                    </small>

                                    <b-badge v-if="row.locked === 'auto_test'"
                                             variant="primary"
                                             class="ml-1"
                                             :title="row.lockMessage(autoTestConfig, null, null)">
                                        AT
                                    </b-badge>
                                </div>

                                <b-popover v-if="row.locked"
                                           :show="visibleLockPopover === i"
                                           :target="`rubric-lock-${id}-${i}`"
                                           triggers="hover"
                                           placement="top">
                                    {{ row.lockMessage(autoTestConfig, null, null) }}

                                    <template v-if="editable">
                                        You cannot remove locked categories.
                                    </template>
                                </b-popover>

                                <div :id="`rubric-lock-${id}-${i}`"
                                     class="flex-grow-0">
                                    <cg-submit-button
                                        v-if="editable"
                                        v-b-popover.top.hover="'Remove category'"
                                        variant="danger"
                                        class="delete-category"
                                        :wait-at-least="0"
                                        :submit="() => {}"
                                        @after-success="() => deleteRow(i)"
                                        :disabled="!!row.locked"
                                        confirm="Do you really want to delete this category?">
                                        <fa-icon v-if="row.locked" name="lock" class="lock" />
                                        <fa-icon v-else name="times" />
                                    </cg-submit-button>

                                    <fa-icon v-else-if="row.locked"
                                             name="lock"
                                             class="lock" />
                                </div>
                            </b-card-header>

                            <component
                                :is="`rubric-editor-${row.type}-row`"
                                :value="row"
                                :assignment="assignment"
                                :auto-test="autoTestConfig"
                                :editable="editable"
                                @input="rowChanged(i, $event)"
                                @submit="() => submitWithModal()"
                                @mouseenter.native="visibleLockPopover = editable ? null : i"
                                @mouseleave.native="visibleLockPopover = null"
                                class="mx-3 mt-3"/>
                        </collapse>
                    </b-card>
                </slick-item>
            </transition-group>
        </slick-list>
    </template>

    <div class="position-relative text-center mb-3">
        <fa-icon v-if="rubricRows.length > 0"
                 class="collapse-all-btn text-muted"
                 :class="{ 'mt-2': editable, 'mt-n2': !editable }"
                 :name="collapseAllIcon"
                 @click.native="toggleAllCategories"
                 v-b-popover.hover.top="collapseAllPopover" />

        <b-button-toolbar v-if="editable"
                          class="justify-content-center">
            <b-button class="add-row normal"
                      @click="createRow('normal')">
                <fa-icon name="ellipsis-h" /> Discrete
            </b-button>

            <b-button class="add-row continuous"
                      @click="createRow('continuous')">
                <fa-icon name="progress" /> Continuous
            </b-button>
        </b-button-toolbar>

        <hr v-else class="my-4 ml-5" />
    </div>

    <template v-if="editable">
        <advanced-collapse v-if="rubric"
                           class="border rounded mb-3 px-3 py-2"
                           :start-open="showMaxPointsWarning">
            <b-form-group label="Points needed for a 10"
                          class="mb-0">
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
                        @keydown.ctrl.enter="() => submitWithModal()"
                        v-model="internalFixedMaxPoints"
                        :placeholder="rubricMaxPoints" />

                    <b-input-group-append is-text>
                        out of {{ rubricMaxPoints }}
                    </b-input-group-append>
                </b-input-group>
            </b-form-group>
        </advanced-collapse>

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

                <div v-b-popover.top.hover="rubricChangedPopover('Reset rubric.')">
                    <cg-submit-button class="reset-rubric border-left rounded-left-0"
                                      variant="danger"
                                      :submit="resetRubric"
                                      confirm="Are you sure you want to revert your changes?"
                                      :disabled="resetDisabled">
                        <fa-icon name="reply"/> Reset
                    </cg-submit-button>
                </div>
            </div>

            <div v-b-popover.top.hover="rubricChangedPopover()">
                <cg-submit-button class="submit-rubric"
                                  ref="submitButton"
                                  :disabled="submitDisabled"
                                  :confirm="shouldConfirm ? 'yes' : ''"
                                  :confirm-in-modal="confirmInModal"
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
                                The following
                                categor{{ scope.error.categories.length >= 2 ? 'ies have' : 'y has' }}
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
                                categor{{ scope.error.itemHeader.length >= 2 ? 'ies have' : 'y has' }} items without a name:

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
                                The given max points
                                {{ this.internalFixedMaxPoints }} is not a
                                number.
                            </p>
                        </template>

                        <p v-else>
                            {{ $utils.getErrorMessage(scope.error) }}
                        </p>
                    </div>
                </cg-submit-button>
            </div>
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
import { SlickList, SlickItem, Handle } from 'vue-slicksort';

import 'vue-awesome/icons/bars';
import 'vue-awesome/icons/chevron-down';
import 'vue-awesome/icons/copy';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/reply';
import 'vue-awesome/icons/ellipsis-h';
import 'vue-awesome/icons/minus-square';
import 'vue-awesome/icons/plus-square';

import { NONEXISTENT, INITIAL_COURSES_AMOUNT } from '@/constants';
import { Rubric } from '@/models';
import { ValidationError } from '@/models/errors';
import { formatGrade } from '@/utils';

import Collapse from './Collapse';
import AdvancedCollapse from './AdvancedCollapse';
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
    },

    data() {
        return {
            id: this.$utils.getUniqueId(),
            rubric: null,
            loading: true,
            error: null,
            internalFixedMaxPoints: this.assignment.fixed_max_rubric_points,

            assignmentsWithRubric: null,
            importAssignment: null,
            loadingAssignments: false,
            loadAssignmentsError: '',
            showRubricImporter: false,

            collapsedCategories: {},

            confirmInModal: false,
            slickItemMoving: false,
            visibleLockPopover: null,

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

        rubric(newVal, oldVal) {
            // We may need to recalculate which categories should be collapsed
            // when the rubric changes because we either
            // * may reload the rubric, causing the tracking ids of rows to
            //   change
            // * add new rows to the rubric when submitting, in which case the
            //   tracking ids change
            if (newVal == null) {
                this.collapsedCategories = {};
                return;
            }

            const newRows = newVal.rows;
            const oldRows = oldVal && oldVal.rows;

            this.collapsedCategories = this.$utils.mapToObject(
                newRows,
                newRow => {
                    let collapse = this.collapsedCategories[newRow.trackingId];

                    // The tracking id may have changed, so check if we can
                    // find a row with the same id, or otherwise a row with the
                    // same content because newly added rows previously had no
                    // id but now do have an id.
                    if (collapse == null && oldRows != null) {
                        const oldRow = oldRows.find(r =>
                            r.id === newRow.id || r.equals(newRow),
                        );
                        if (oldRow != null) {
                            collapse = this.collapsedCategories[oldRow.trackingId];
                        }
                    }

                    // Added but not yet submitted rows have no id and should
                    // start expanded.
                    if (collapse == null) {
                        if (newRow.id == null) {
                            collapse = false;
                        } else {
                            collapse = this.collapseByDefault;
                        }
                    }

                    return [newRow.trackingId, collapse || false];
                },
            );
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
                return `To achieve a 10 students need to score ${num} out of
                    ${this.rubricMaxPoints} rubric points.`;
            } else if (num > this.rubricMaxPoints) {
                return `It is not possible to achieve a 10 for this rubric; a
                    ${formatGrade(this.rubricMaxPoints / num * 10)} is the
                    maximum grade that can be achieved.`;
            } else {
                return null;
            }
        },

        showMaxPointsWarning() {
            const num = parseFloat(this.internalFixedMaxPoints);
            return this.editable && !Number.isNaN(num) && num !== this.rubricMaxPoints;
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

        rubricChanged() {
            const { rubric, serverData } = this;

            if (rubric == null) {
                return serverData != null;
            } else {
                return !rubric.equals(serverData);
            }
        },

        maxPointsChanged() {
            const serverValue = this.assignment.fixed_max_rubric_points;
            const ourValue = this.internalFixedMaxPoints;
            if (ourValue == null) {
                return serverValue != null;
            } else {
                return parseFloat(ourValue) !== serverValue;
            }
        },

        submitDisabled() {
            return !this.rubricChanged && !this.maxPointsChanged;
        },

        resetDisabled() {
            if (this.submitDisabled) {
                return true;
            } else {
                return this.serverData != null && this.rubricRows.length === 0;
            }
        },

        collapseByDefault() {
            return this.editable || this.rubricRows.length > 1;
        },

        canCollapseAll() {
            return Object.values(this.collapsedCategories).some(
                collapsed => !collapsed,
            );
        },

        collapseAllIcon() {
            return this.canCollapseAll ? 'minus-square' : 'plus-square';
        },

        collapseAllPopover() {
            return `${this.canCollapseAll ? 'Collapse' : 'Expand'} all categories.`;
        },

        achievablePointsPerRow() {
            return this.rubricRows.reduce((acc, row) => {
                // Used in row header.
                let header;
                // Used in hover title.
                let title;

                switch (row.type) {
                case 'normal': {
                    const points = this.$utils.filterMap(
                        row.items,
                            item => {
                                if (Number.isFinite(item.points)) {
                                    return this.$utils.Just(item.points);
                                } else {
                                    return this.$utils.Nothing;
                                }
                            },
                    ).sort();
                    if (points.length) {
                        header = points.join(' / ');
                        title = this.$utils.readableJoin(points, 'or');
                    }
                    break;
                }
                case 'continuous': {
                    if (row.maxPoints) {
                        header = `${row.minPoints} - ${row.maxPoints}`;
                        title = `anywhere between ${row.minPoints} and ${row.maxPoints}`;
                    }
                    break;
                }
                default:
                    break;
                }
                if (header && title) {
                    acc[row.trackingId] = {
                        header: `(${header} pts.)`,
                        title: `You can score ${title} points in this category.`,
                    };
                }
                return acc;
            }, {});
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
            this.rubric = this.serverData;
            this.internalFixedMaxPoints = this.assignment.fixed_max_rubric_points;
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
            this.confirmInModal = false;
            this.forceLoadSubmissions({ assignmentId: this.assignmentId });
        },

        ensureEditable() {
            if (!this.editable) {
                throw new Error('This rubric editor is not editable!');
            }
        },

        createRow(type) {
            this.ensureEditable();
            this.rubric = this.rubric.createRow(type);

            const newRow = this.rubric.rows[this.rubric.rows.length - 1];
            this.collapsedCategories[newRow.trackingId] = false;
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

            return Promise.resolve();
        },

        rowChanged(idx, rowData) {
            this.rubric = this.rubric.updateRow(idx, rowData);
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

        onSortEnd() {
            this.slickItemMoving = false;
        },

        rubricChangedPopover(ifChanged = '') {
            if (this.submitDisabled) {
                return 'You have not made any modifications to the rubric.';
            } else {
                return ifChanged;
            }
        },

        shouldCancelDrag(event) {
            if (!this.editable) {
                return true;
            }
            if (event.target.closest('.card.rubric-category')) {
                return true;
            }
            return false;
        },

        submitWithModal() {
            this.confirmInModal = true;
            this.$refs.submitButton.onClick();
        },

        toggleAllCategories() {
            const value = this.canCollapseAll;
            this.rubricRows.forEach(row => {
                this.collapsedCategories[row.trackingId] = value;
            });
        },
    },

    components: {
        Collapse,
        AdvancedCollapse,
        RubricEditorNormalRow,
        RubricEditorContinuousRow,
        Multiselect,
        SlickList,
        SlickItem,
    },

    directives: {
        Handle,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.wizard-button-container:not(:last-child) {
    margin-right: 1rem;
}

.category-item {
    &.grab .drag-handle {
        cursor: grab !important;
    }

    &.grabbing {
        z-index: 99999;
        user-select: none !important;

        .drag-handle {
            cursor: grabbing !important;
        }
    }

    .fa-icon.chevron {
        transform: rotate(0);
        transition: transform @transition-duration;
    }

    .x-collapsing,
    .x-collapsed {
        > .handle .fa-icon.chevron {
            transform: rotate(-90deg);
        }
    }
}

input.max-points {
    width: 6.66rem;
}

.rubric-row-enter-active,
.rubric-row-leave-active {
    transition: all @transition-duration;
    overflow: hidden;
}

.rubric-row-enter,
.rubric-row-leave-to {
    opacity: 0;
    max-height: 0;
}

.rubric-row-enter-to,
.rubric-row-leave {
    max-height: 15rem;
    opacity: 1;
}

.collapse-all-btn {
    position: absolute;
    top: 0;
    left: 1rem;
    cursor: pointer;
    opacity: 0.8;

    &:hover {
        opacity: 1;
    }

    .rubric-editor.editable & {
        left: 0;
    }
}

.btn.add-row {
    &:not(:last-child) {
        margin-right: 0.5rem;
    }
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
