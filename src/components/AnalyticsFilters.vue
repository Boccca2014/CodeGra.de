<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-card class="analytics-filters"
        header-class="d-flex"
        body-class="pb-1">
    <template #header>
        <div class="flex-grow-1">
            Filters
        </div>

        <div class="d-flex flex-grow-0">
            <div class="icon-button add-filter"
                 @click="addFilter()"
                 v-b-popover.hover.top="'Add filter'">
                <icon name="plus" />
            </div>

            <div :id="shareBtnId"
                 class="icon-button share"
                 tabindex="-1"
                 style="outline: none !important;"
                 v-b-popover.hover.top="'Share current filters'">
                <icon name="share-alt" />
            </div>

            <b-popover :target="shareBtnId"
                       triggers="click blur"
                       placement="bottom"
                       title="Share filters">
                <p class="mb-2 text-justify">
                    <small>
                        Anyone with this URL and permission to view this
                        assignment's analytics dashboard will get the current
                        view.
                    </small>
                </p>

                <b-input-group class="flex-row" style="flex-wrap: nowrap;">
                    <div class="form-control text-truncate">
                        <small>
                            {{ currentUrl }}
                        </small>
                    </div>

                    <template #append>
                        <b-button @click="copyUrlToClipboard">
                            <icon name="clipboard" />
                        </b-button>
                    </template>
                </b-input-group>
            </b-popover>

            <div class="icon-button reset danger"
                 @click="resetFilters()"
                 v-b-popover.hover.top="'Clear all'">
                <icon name="reply" />
            </div>

            <description-popover class="icon-button pl-0"
                                 placement="bottom"
                                 :scale="1">
                <p class="mb-2">
                    With filters you can select the data you want to visualize.
                    A filter takes the set of all submissions for this
                    assignment and produces the subset of those submissions
                    that satisfy all the filter's requirements.
                </p>

                <p>
                    See
                    <a href="https://docs.codegra.de/user/analytics-dashboard.html#filters"
                       target="_blank"
                        >the documentation</a>
                    for more details.
                </p>
            </description-popover>
        </div>
    </template>

    <div class="row">
        <div v-for="filter, filterIndex in filters"
             :key="filterIndex"
             class="filter col-12 col-xl-6 mb-3">
            <b-card header-class="d-flex">
                <template #header>
                    <div class="flex-grow-1">
                        {{ filter.toString() }}
                    </div>

                    <div class="d-flex flex-grow-0">
                        <div class="icon-button clone"
                             @click="duplicateFilter(filterIndex)"
                             v-b-popover.hover.top="'Duplicate'">
                            <icon name="copy" />
                        </div>

                        <div class="icon-button split"
                             :class="{
                                 active: isSplitting === filterIndex,
                                 'text-muted': isSplittingOther(filterIndex),
                             }"
                             @click="toggleSplitFilter(filterIndex)"
                             v-b-popover.hover.top="
                                isSplittingOther(filterIndex) ? 'Already splitting another filter' : 'Split'
                            ">
                            <icon name="scissors" />
                        </div>

                        <div class="icon-button delete danger"
                             :class="{ 'text-muted': deleteDisabled }"
                             @click="deleteFilter(filterIndex)"
                             v-b-popover.hover.top="
                                deleteDisabled ?  'You cannot delete the only filter' : 'Delete'
                             ">
                            <icon name="times" />
                        </div>
                    </div>
                </template>

                <div class="controls">
                    <div class="filter-controls"
                        :class="{ active: isSplitting !== filterIndex }">
                        <b-input-group>
                            <template #prepend>
                                <b-input-group-text>
                                    Latest

                                    <description-popover hug-text placement="top">
                                        Keep only the latest submission by each student.
                                    </description-popover>
                                </b-input-group-text>
                            </template>

                            <div class="form-control pl-2">
                                <b-form-checkbox :checked="filter.onlyLatestSubs"
                                                 @input="updateFilter(filterIndex, 'onlyLatestSubs', $event)"
                                                 class="d-inline-block">
                                    Only use latest submissions
                                </b-form-checkbox>
                            </div>
                        </b-input-group>

                        <b-input-group>
                            <template #prepend>
                                <b-input-group-text>
                                    Min. grade

                                    <description-popover hug-text placement="top">
                                        Keep only submissions with a grade equal to
                                        or greater than this value.
                                    </description-popover>
                                </b-input-group-text>
                            </template>

                            <input :value="filter.minGrade"
                                   @input="updateFilter(filterIndex, 'minGrade', $event.target.value)"
                                   class="form-control"
                                   type="number"
                                   placeholder="0"
                                   min="0"
                                   :max="filter.maxGrade"
                                   step="0.5" />

                            <template #append>
                                <b-button variant="warning"
                                          :disabled="filter.minGrade == null"
                                          @click="updateFilter(filterIndex, 'minGrade', null)">
                                    <icon name="reply" />
                                </b-button>
                            </template>
                        </b-input-group>

                        <b-input-group>
                            <template #prepend>
                                <b-input-group-text>
                                    Max. grade

                                    <description-popover hug-text placement="top">
                                        Keep only submissions with a grade less
                                        than this value.
                                    </description-popover>
                                </b-input-group-text>
                            </template>

                            <input :value="filter.maxGrade"
                                   @input="updateFilter(filterIndex, 'maxGrade', $event.target.value)"
                                   class="form-control"
                                   type="number"
                                   :placeholder="assignmentMaxGrade"
                                   :min="filter.minGrade"
                                   :max="assignmentMaxGrade"
                                   step="0.5" />

                            <template #append>
                                <b-button variant="warning"
                                        :disabled="filter.maxGrade == null"
                                        @click="updateFilter(filterIndex, 'maxGrade', null)">
                                    <icon name="reply" />
                                </b-button>
                            </template>
                        </b-input-group>

                        <b-input-group>
                            <template #prepend>
                                <b-input-group-text>
                                    Submitted after

                                    <description-popover hug-text placement="top">
                                        Keep only submissions that were submitted
                                        on or after this date.
                                    </description-popover>
                                </b-input-group-text>
                            </template>

                            <datetime-picker :value="formatDate(filter.submittedAfter)"
                                             @input="updateFilter(filterIndex, 'submittedAfter', $event)"
                                             :placeholder="formatDate(firstSubmissionDate)"
                                             :config="{
                                                 minDate: firstSubmissionDate.toISOString(),
                                                 maxDate: lastSubmissionDate.toISOString(),
                                                 defaultHour: 0,
                                                 defaultMinute: 0,
                                             }"/>

                            <template #append>
                                <b-button variant="warning"
                                          :disabled="filter.submittedAfter == null"
                                          @click="updateFilter(filterIndex, 'submittedAfter', null)">
                                    <icon name="reply" />
                                </b-button>
                            </template>
                        </b-input-group>

                        <b-input-group>
                            <template #prepend>
                                <b-input-group-text>
                                    Submitted before

                                    <description-popover hug-text placement="top">
                                        Keep only submissions that were submitted
                                        before this date.
                                    </description-popover>
                                </b-input-group-text>
                            </template>

                            <datetime-picker :value="formatDate(filter.submittedBefore)"
                                             @input="updateFilter(filterIndex, 'submittedBefore', $event)"
                                             :placeholder="formatDate(lastSubmissionDate)"
                                             :config="{
                                                 minDate: firstSubmissionDate.toISOString(),
                                                 maxDate: lastSubmissionDate.toISOString(),
                                                 defaultHour: 23,
                                                 defaultMinute: 59,
                                             }"/>

                            <template #append>
                                <b-button variant="warning"
                                          :disabled="filter.submittedBefore == null"
                                          @click="updateFilter(filterIndex, 'submittedBefore', null)">
                                    <icon name="reply" />
                                </b-button>
                            </template>
                        </b-input-group>

                        <!-- Must have a z-index otherwise the reset buttons of the
                             other options are visible over the multiselect popup -->
                        <b-input-group class="flex-wrap-0">
                            <template #prepend>
                                <b-input-group-text>
                                    Graders

                                    <description-popover hug-text placement="top">
                                        Keep only submissions assigned to the
                                        selcted graders.
                                    </description-popover>
                                </b-input-group-text>
                            </template>

                            <multiselect
                                class="d-flex rounded-0"
                                :max-height="150"
                                :value="filter.assignees"
                                @input="updateFilter(filterIndex, 'assignees', $event)"
                                :options="assignees"
                                multiple
                                searchable
                                open-direction="top"
                                track-by="id"
                                label="name"
                                :close-on-select="false"
                                placeholder="Select graders"
                                internal-search
                                :disabled="assignees.length === 0"
                                v-b-popover.top.hover="graderPopoverText"/>

                            <template #append>
                                <b-button variant="warning"
                                          :disabled="filter.assignees.length === 0"
                                          @click="updateFilter(filterIndex, 'assignees', [])">
                                    <icon name="reply" />
                                </b-button>
                            </template>
                        </b-input-group>

                        <analytics-general-stats
                            :base-workspace="results[filterIndex]"
                            class="mb-0" />
                    </div>

                    <div class="split-controls"
                         :class="{ active: isSplitting === filterIndex }">
                        <b-input-group>
                            <b-input-group-prepend is-text>
                                Latest

                                <description-popover hug-text placement="top">
                                    Splitting on latest will generate two new
                                    filters: one that selects all submissions
                                    for this assignment, and another one that
                                    selects only the latest submission per
                                    student.
                                </description-popover>
                            </b-input-group-prepend>

                            <b-form-checkbox v-model="splitLatest"
                                             class="form-control"
                                             style="padding-left: 2.25rem;">
                                Split on latest
                            </b-form-checkbox>
                        </b-input-group>

                        <b-input-group>
                            <b-input-group-prepend is-text>
                                Grade

                                <description-popover hug-text placement="top">
                                    Splitting on grade will generate two new
                                    filters: one that selects all submissions
                                    with a grade less than this value, and
                                    another one that selects all submissions
                                    with a grade equal to or greater than this
                                    value.
                                </description-popover>
                            </b-input-group-prepend>

                            <input v-model="splitGrade"
                                   class="form-control placeholder-left"
                                   type="number"
                                   :min="0"
                                   :max="assignmentMaxGrade"
                                   :placeholder="`Avg. of filter = ${filterAvgGrade(filter)}`" />
                        </b-input-group>

                        <b-input-group>
                            <b-input-group-prepend is-text>
                                Submitted on

                                <description-popover hug-text placement="top">
                                    Splitting on submission date will generate
                                    two new filters: one that selects all
                                    submissions before the given date, and
                                    another one that selects all submissions
                                    exactly on or after the given date.
                                </description-popover>
                            </b-input-group-prepend>

                            <datetime-picker v-model="splitDate"
                                             placeholder="Date"
                                             :config="{
                                                 minDate: nthFirstSubmissionDate(filterIndex),
                                                 maxDate: nthLastSubmissionDate(filterIndex),
                                             }"/>
                        </b-input-group>

                        <b-input-group class="flex-wrap-0">
                            <b-input-group-prepend is-text>
                                Grader

                                <description-popover hug-text placement="top">
                                    Splitting on grader will generate a new
                                    filter for every selected grader.
                                </description-popover>
                            </b-input-group-prepend>

                            <multiselect
                                class="d-flex rounded-left-0"
                                :max-height="150"
                                :value="splitAssignees"
                                @input="updateSplitAssignees"
                                :options="assigneesOrAll"
                                multiple
                                searchable
                                open-direction="top"
                                track-by="id"
                                label="name"
                                :close-on-select="false"
                                placeholder="Select graders"
                                internal-search>
                                <span slot="noResult">
                                    No graders with this name.
                                </span>
                            </multiselect>
                        </b-input-group>

                        <b-alert v-if="splitFiltersFailed"
                                 show
                                 variant="warning">
                            {{ $utils.getErrorMessage(splitFilters) }}
                        </b-alert>

                        <template v-for="split in splitResults"
                                  v-else>
                            <small class="pl-2 text-muted">
                                {{ split.filter.toString() }}
                            </small>
                            <analytics-general-stats
                                :base-workspace="split"
                                class="mb-0" />
                        </template>

                        <div class="mt-3"
                             v-b-popover.top.hover="splitFiltersFailed ? 'The split parameters are invalid' : ''">
                            <submit-button class="float-right"
                                           variant="primary"
                                           :disabled="splitFiltersFailed"
                                           :submit="() => splitFilter(filterIndex)"
                                           @after-success="afterSplitFilter">
                                <icon name="check" />
                            </submit-button>
                        </div>
                    </div>
                </div>
            </b-card>
        </div>
    </div>

    <div ref="copyContainer" />
</b-card>
</template>

<script>
import { mapGetters } from 'vuex';

import Multiselect from 'vue-multiselect';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/reply';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/unlink';
import 'vue-awesome/icons/scissors';
import 'vue-awesome/icons/copy';
import 'vue-awesome/icons/share-alt';
import 'vue-awesome/icons/clipboard';

import { Workspace, WorkspaceFilter } from '@/models/analytics';
import SubmitButton from '@/components/SubmitButton';
import DatetimePicker from '@/components/DatetimePicker';
import DescriptionPopover from '@/components/DescriptionPopover';
import AnalyticsGeneralStats from '@/components/AnalyticsGeneralStats';

export default {
    name: 'analytics-filters',

    props: {
        workspace: {
            type: Workspace,
            required: true,
        },
        value: {
            type: Array,
            default: [],
        },
    },

    data() {
        const id = this.$utils.getUniqueId();

        return {
            filters: this.defaultFilters(this.value),
            isSplitting: null,
            splitAssignees: [],
            splitLatest: false,
            splitGrade: '',
            splitDate: '',

            shareBtnId: `analytics-filters-share-btn-${id}`,
        };
    },

    computed: {
        ...mapGetters('users', ['getUser']),

        currentUrl() {
            // We can't get an actual URL from a $route, but we want this to
            // be updated whenever $route changes.
            // eslint-disable-next-line
            const route = this.$route;
            return window.location.href;
        },

        assignment() {
            return this.workspace.assignment;
        },

        assignmentMaxGrade() {
            return this.assignment.maxGrade;
        },

        firstSubmissionDate() {
            const { firstSubmissionDate } = this.workspace.submissions;
            if (firstSubmissionDate == null) {
                return this.assignment.createdAt;
            } else {
                return firstSubmissionDate;
            }
        },

        lastSubmissionDate() {
            const { lastSubmissionDate } = this.workspace.submissions;
            if (lastSubmissionDate == null) {
                return this.assignment.deadline;
            } else {
                return lastSubmissionDate;
            }
        },

        results() {
            return this.workspace.filter(this.filters);
        },

        deleteDisabled() {
            return this.filters.length === 1;
        },

        splitFiltersFailed() {
            return this.splitFilters instanceof Error;
        },

        splitFilters() {
            // The new filters produced by the current split.

            if (this.isSplitting == null) {
                return [];
            }

            try {
                return this.filters[this.isSplitting].split({
                    assignees: this.splitAssignees,
                    latest: this.splitLatest,
                    grade: this.splitGrade,
                    date: this.splitDate,
                });
            } catch (e) {
                return e;
            }
        },

        splitResults() {
            if (this.splitFiltersFailed) {
                return [];
            } else {
                return this.workspace.filter(this.splitFilters);
            }
        },

        assignees() {
            const ids = this.workspace.submissions.assigneeIds;
            return [...ids].map(id => this.getUser(id));
        },

        assigneesOrAll() {
            return [
                {
                    name: 'All',
                    allAssignees: true,
                },
                ...this.assignees,
            ];
        },

        graderPopoverText() {
            if (this.assignees.length === 0) {
                let msg = 'No graders are assigned to any submission.';
                if (!this.assignment.course.permissions.can_see_assignee) {
                    msg +=
                        ' You probably cannot see them because you do not have permission to ' +
                        ' see the  assignee.';
                }
                return msg;
            } else {
                return '';
            }
        },
    },

    methods: {
        defaultFilters(filters) {
            if (filters == null || filters.length === 0) {
                return [WorkspaceFilter.emptyFilter];
            } else {
                return filters.map(f => WorkspaceFilter.deserialize(f));
            }
        },

        resetFilters() {
            this.filters = this.defaultFilters();
            this.resetSplitParams();
        },

        resetSplitParams() {
            this.isSplitting = null;
            this.splitAssignees = [];
            this.splitLatest = false;
            this.splitGrade = '';
            this.splitDate = '';
        },

        updateFilter(idx, key, value) {
            const filter = this.filters[idx].update(key, value);
            this.$set(this.filters, idx, filter);
        },

        addFilter() {
            this.filters = [WorkspaceFilter.emptyFilter, ...this.filters];
        },

        toggleSplitFilter(idx) {
            if (this.isSplitting == null) {
                this.isSplitting = idx;
            } else if (this.isSplitting === idx) {
                this.resetSplitParams();
            }
        },

        replaceFilter(idx, ...newFilters) {
            const fs = this.filters;
            this.filters = [...fs.slice(0, idx), ...newFilters, ...fs.slice(idx + 1)];
        },

        deleteFilter(idx) {
            if (!this.deleteDisabled) {
                this.replaceFilter(idx);
            }
        },

        duplicateFilter(idx) {
            // Replace the filter with two copies of itself.
            const f = this.filters[idx];
            this.replaceFilter(idx, f, f);
        },

        async splitFilter(idx) {
            // Replace the filter with the result of splitting it.
            this.replaceFilter(idx, ...this.splitFilters);
        },

        afterSplitFilter() {
            this.$afterRerender(() => {
                this.$root.$emit('bv::hide::popover');
                this.resetSplitParams();
            });
        },

        updateSplitAssignees(assignees) {
            if (assignees.some(a => a.allAssignees)) {
                this.splitAssignees = this.assignees;
            } else {
                this.splitAssignees = assignees;
            }
        },

        isSplittingOther(idx) {
            return this.isSplitting != null && this.isSplitting !== idx;
        },

        nthFirstSubmissionDate(idx) {
            return this.maybeToISOString(this.results[idx].submissions.firstSubmissionDate);
        },

        nthLastSubmissionDate(idx) {
            return this.maybeToISOString(this.results[idx].submissions.lastSubmissionDate);
        },

        filterAvgGrade(filter) {
            let { minGrade, maxGrade } = filter;
            if (minGrade == null) {
                minGrade = 0;
            }
            if (maxGrade == null) {
                maxGrade = this.assignment.maxGrade;
            }
            return (minGrade + maxGrade) / 2;
        },

        formatDate(d) {
            return d == null ? null : this.$utils.readableFormatDate(d);
        },

        to2Dec(x) {
            return this.$utils.toMaxNDecimals(x, 2);
        },

        copyUrlToClipboard(event) {
            // TODO: Handle possible errors.
            const url = window.location.href;
            this.$copyText(url, this.$refs.copyContainer);
            event.target.blur();
        },

        maybeToISOString(d) {
            return d == null ? null : d.toISOString();
        },
    },

    watch: {
        workspace() {
            this.resetFilters();
        },

        filters: {
            immediate: true,
            handler() {
                this.isSplitting = null;
                this.$emit('input', this.filters.map(f => f.serialize()));
            },
        },

        results: {
            immediate: true,
            handler() {
                this.$emit('results', this.results);
            },
        },
    },

    components: {
        Icon,
        Multiselect,
        SubmitButton,
        DatetimePicker,
        DescriptionPopover,
        AnalyticsGeneralStats,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.controls {
    overflow: hidden;
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
}

.filter-controls,
.split-controls {
    flex: 0 0 100%;
    margin-right: 1rem;
}

.filter-controls {
    margin-left: calc(-100% - 1rem);
    transition: margin-left @transition-duration;

    &.active {
        margin-left: 0;
    }
}

.flex-wrap-0 {
    flex-wrap: nowrap;
}
</style>

<style lang="less">
.analytics-filters {
    .multiselect {
        flex: 1 1 auto;
        width: auto;

        .multiselect__tags {
            width: 100%;
        }

        &.rounded-left-0 .multiselect__tags {
            border-top-left-radius: 0;
            border-bottom-left-radius: 0;
        }

        &.rounded-0 .multiselect__tags {
            border-top-left-radius: 0;
            border-bottom-left-radius: 0;
            border-top-right-radius: 0;
            border-bottom-right-radius: 0;
        }
    }
}
</style>
