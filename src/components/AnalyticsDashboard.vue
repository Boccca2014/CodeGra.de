<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="analytics-dashboard row">
    <div v-if="workspaceIds.length === 0"
         class="col-12">
        <b-alert show
                 variant="danger"
                 class="col-12">
            You do not have permission to view the Analytics Dashboard.
        </b-alert>
    </div>

    <div v-else-if="error"
         class="col-12">
        <b-alert show
                 variant="danger">
            {{ $utils.getErrorMessage(error) }}
        </b-alert>
    </div>

    <loader page-loader v-else-if="loading" />

    <div v-else-if="totalSubmissionCount === 0"
         class="col-12">
        <h3 class="border rounded p-5 text-center text-muted font-italic">
            There are no submissions yet.
        </h3>
    </div>

    <template v-else>
        <div class="col-12">
            <catch-error capture>
                <template slot-scope="scope">
                    <b-alert show variant="danger" class="general-stats-error" v-if="scope.error">
                        An unexpected error occurred:
                        {{ $utils.getErrorMessage(scope.error) }}
                    </b-alert>

                    <analytics-general-stats
                        v-else
                        large
                        :base-workspace="baseWorkspace"
                        :grade-workspace="latestSubmissionsWorkspace"
                        :feedback-workspace="latestSubmissionsWorkspace" />
                </template>
            </catch-error>
        </div>

        <div class="col-12 mt-3">
            <catch-error capture>
                <template slot-scope="scope">
                    <b-alert show variant="danger" class="filters-error" v-if="scope.error">
                        An unexpected error occurred:
                        {{ $utils.getErrorMessage(scope.error) }}
                    </b-alert>

                    <analytics-filters
                        v-else
                        :workspace="baseWorkspace"
                        v-model="filters"
                        @results="filterResults = $event" />
                </template>
            </catch-error>
        </div>

        <loader page-loader :scale="4" v-if="filterResults.length === 0" />

        <div v-else-if="filteredSubmissionCount === 0"
             class="col-12 mt-3">
            <h3 class="border rounded p-5 text-center text-muted font-italic">
                No submissions within the specified filter parameters.
            </h3>
        </div>

        <template v-else>
            <div class="col-12 mt-3">
                <catch-error capture>
                    <template slot-scope="scope">
                        <b-alert show variant="danger" class="submission-date-error" v-if="scope.error">
                            An unexpected error occurred:
                            {{ $utils.getErrorMessage(scope.error) }}
                        </b-alert>

                        <analytics-submission-date
                            v-else
                            v-model="submissionDateSettings"
                            :filter-results="filterResults" />
                    </template>
                </catch-error>
            </div>

            <div class="col-12 mt-3">
                <catch-error capture>
                    <template slot-scope="scope">
                        <b-alert show variant="danger" class="submission-count-error" v-if="scope.error">
                            An unexpected error occurred:
                            {{ $utils.getErrorMessage(scope.error) }}
                        </b-alert>

                        <analytics-submission-count
                            v-else
                            v-model="submissionCountSettings"
                            :filter-results="filterResults" />
                    </template>
                </catch-error>
            </div>

            <div class="col-12 mt-3">
                <catch-error capture>
                    <template slot-scope="scope">
                        <b-alert show variant="danger" class="grade-stats-error" v-if="scope.error">
                            An unexpected error occurred:
                            {{ $utils.getErrorMessage(scope.error) }}
                        </b-alert>

                        <analytics-grade-stats
                            v-else
                            v-model="gradeSettings"
                            :filter-results="filterResults" />
                    </template>
                </catch-error>
            </div>

            <div v-if="hasRubricSource != null"
                 class="col-12 mt-3">
                <catch-error capture>
                    <template slot-scope="scope">
                        <b-alert show variant="danger" class="rubric-stats-error" v-if="scope.error">
                            An unexpected error occurred:
                            {{ $utils.getErrorMessage(scope.error) }}
                        </b-alert>

                        <analytics-rubric-stats
                            v-else
                            v-model="rubricSettings"
                            :filter-results="filterResults" />
                    </template>
                </catch-error>
            </div>
        </template>
    </template>
</div>
</template>

<script>
import { mapActions } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/percent';

import * as models from '@/models';

import { WorkspaceFilter } from '@/models/analytics';
import { BarChart, ScatterPlot } from '@/components/Charts';
import Loader from '@/components/Loader';
import CatchError from '@/components/CatchError';
import DatetimePicker from '@/components/DatetimePicker';
import AnalyticsFilters from '@/components/AnalyticsFilters';
import DescriptionPopover from '@/components/DescriptionPopover';
import AnalyticsGeneralStats from '@/components/AnalyticsGeneralStats';
import AnalyticsSubmissionDate from '@/components/AnalyticsSubmissionDate';
import AnalyticsSubmissionCount from '@/components/AnalyticsSubmissionCount';
import AnalyticsRubricStats from '@/components/AnalyticsRubricStats';
import AnalyticsGradeStats from '@/components/AnalyticsGradeStats';
import { deepEquals, filterObject } from '@/utils';

export default {
    name: 'analytics-dashboard',

    props: {
        assignment: {
            type: models.Assignment,
            required: true,
        },
    },

    data() {
        const { analytics } = this.$route.query;
        const settings = analytics == null ? {} : JSON.parse(analytics);

        return {
            id: this.$utils.getUniqueId(),
            loading: true,
            error: null,

            baseWorkspace: null,
            filterResults: [],

            ...this.fillSettings(settings),
        };
    },

    computed: {
        workspaceIds() {
            return this.$utils.getProps(this.assignment, [], 'analytics_workspace_ids');
        },

        currentWorkspaceId() {
            return this.$utils.getProps(this.workspaceIds, null, 0);
        },

        totalSubmissionCount() {
            return this.baseWorkspace.submissions.submissionCount;
        },

        filteredSubmissionCount() {
            return this.filterResults.reduce((acc, result) => {
                result.submissions.submissionIds.forEach(id => acc.add(id));
                return acc;
            }, new Set()).size;
        },

        latestSubmissionsWorkspace() {
            return this.baseWorkspace.filter([new WorkspaceFilter({ onlyLatestSubs: true })])[0];
        },

        hasRubricSource() {
            return (
                this.assignment.rubric &&
                this.assignment.rubric.rows &&
                this.baseWorkspace &&
                this.baseWorkspace.hasSource('rubric_data')
            );
        },

        settings() {
            const defaults = this.fillSettings({});
            const settings = {
                filters: this.$utils.getProps(this, [], 'filters'),
                submissionDateSettings: this.submissionDateSettings,
                submissionCountSettings: this.submissionCountSettings,
                rubricSettings: this.rubricSettings,
                gradeSettings: this.gradeSettings,
            };

            return filterObject(settings, (val, key) => !deepEquals(val, defaults[key]));
        },
    },

    methods: {
        ...mapActions('analytics', ['loadWorkspace', 'clearAssignmentWorkspaces']),

        fillSettings(settings) {
            if (settings.filters == null) {
                settings.filters = [{}];
            }
            return Object.assign(
                {
                    gradeSettings: {},
                    rubricSettings: {},
                    submissionDateSettings: {},
                    submissionCountSettings: {},
                },
                settings,
            );
        },

        reset() {
            Object.assign(this, this.fillSettings({}));
        },

        loadWorkspaceData() {
            if (this.currentWorkspaceId == null) {
                return Promise.resolve(null);
            }

            this.loading = true;
            this.baseWorkspace = null;
            return this.loadWorkspace({
                workspaceId: this.currentWorkspaceId,
            }).then(
                res => {
                    const ws = res.data;
                    if (ws.id === this.currentWorkspaceId) {
                        this.baseWorkspace = ws;
                        this.error = null;
                        this.loading = false;
                    }
                    return res;
                },
                err => {
                    this.loading = false;
                    this.error = err;
                    throw err;
                },
            );
        },

        reloadWorkspace() {
            this.clearAssignmentWorkspaces(this.assignment.id).then(this.loadWorkspaceData);
        },
    },

    watch: {
        currentWorkspaceId: {
            immediate: true,
            handler(newVal, oldVal) {
                this.loadWorkspaceData().then(() => {
                    // Reset all configuration only when we are changing
                    // to another workspace, but not when loading the
                    // component for the first time.
                    if (newVal !== oldVal && oldVal != null) {
                        this.reset();
                    }
                });
            },
        },

        settings() {
            this.$router.replace({
                query: {
                    ...this.$route.query,
                    analytics: JSON.stringify(this.settings),
                },
                hash: this.$route.hash,
            });
        },
    },

    mounted() {
        this.$root.$on('cg::submissions-page::reload', this.reloadWorkspace);
    },

    destroyed() {
        this.$root.$off('cg::submissions-page::reload', this.reloadWorkspace);
    },

    components: {
        Icon,
        Loader,
        BarChart,
        ScatterPlot,
        AnalyticsFilters,
        DescriptionPopover,
        AnalyticsGeneralStats,
        AnalyticsSubmissionDate,
        AnalyticsSubmissionCount,
        AnalyticsRubricStats,
        AnalyticsGradeStats,
        DatetimePicker,
        CatchError,
    },
};
</script>

<style lang="less">
@import '~mixins.less';

.analytics-dashboard {
    .col-12 {
        display: flex;
        flex-direction: column;
    }

    .card {
        flex: 1 1 auto;

        .input-group:not(:last-child) {
            margin-bottom: 1rem;
        }
    }

    .card-header {
        .btn,
        .custom-select,
        .form-control {
            height: 2rem;
            margin: -0.25rem 0;
            padding-top: 0.25rem;
        }

        .btn {
            padding: 0.25rem 0.5rem;
            box-shadow: none !important;
        }
    }

    .card-body.center {
        display: flex;
        justify-content: center;
        align-items: center;
    }

    // TODO: Define the .icon-button globally so we can use it
    // in other components as well.
    .icon-button {
        margin: -0.5rem 0;
        padding: 0.5rem;
        cursor: pointer;
        transition: background-color @transition-duration;

        &:last-child {
            margin-right: -0.5rem;
        }

        &:focus,
        &.active {
            color: lighten(@color-secondary, 15%);

            &.danger {
                color: @color-danger;
            }
        }

        &.text-muted {
            cursor: not-allowed;
        }

        &:not(.text-muted):hover {
            color: lighten(@color-secondary, 5%);

            &.danger {
                color: darken(@color-danger, 10%);
            }
        }
    }
}
</style>
