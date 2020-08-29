<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div v-if="error"
     class="plagiarism-overview">
    <b-alert show
             variant="danger"
             style="margin-top: 1rem;">
        {{ error }}
    </b-alert>
</div>
<loader v-else-if="loadingData || assignment == null || run == null"/>
<div class="plagiarism-overview" v-else>
    <local-header :back-route="{ name: 'manage_assignment', hash: '#plagiarism' }"
                  back-popover="Go back to manage assignment page">
        <template slot="title">
            Plagiarism overview for assignment &quot;{{assignment.name}}&quot; of &quot;{{assignment.course.name}}&quot;
        </template>

        <b-button class="download-btn"
                  variant="secondary"
                  @click="downloadLog">
            Download log
        </b-button>

        <input v-model="filter"
               class="filter-input form-control"
               placeholder="Filter students"/>
    </local-header>

    <div v-if="run.state === 'crashed'"
         class="text-muted text-center">
        The run crashed. Please check the logs for more details.
    </div>
    <infinite-plagiarism-case-list
        v-else
        :filter="filter"
        :run="run">
        <b-table :fields="tableFields"
                 hover
                 striped
                 slot-scope="{ cases }"
                 show-empty
                 :sort-compare="sortCompareTable"
                 sort-by="match_avg"
                 sort-desc
                 :items="cases"
                 @row-clicked="rowClicked"
                 @row-hovered="rowHovered"
                 @mouseleave.native="rowHovered(null)"
                 class="overview-table">
            <template v-slot:cell(user1)="row">
                <user :user="row.item.users[0]"/>
            </template>

            <template v-slot:cell(user2)="row">
                <span>
                    <user :user="row.item.users[1]"/>
                    <sup v-b-popover.hover.top="getOtherAssignmentPlagiarismDesc(row.item, 1)"
                         class="description"
                         v-if="row.item.assignments[1].id != run.assignment.id"
                         >*</sup>
                </span>
            </template>

            <template v-slot:empty>
                <div style="text-align: center;">
                    <span v-if="run.cases.length == 0">No plagiarism found</span>
                <span v-else>No results found</span>
            </div>
        </template>
    </b-table>
    </infinite-plagiarism-case-list>

    <b-popover v-if="disabledPopoverRowId"
               :target="disabledPopoverRowId"
               ref="disabledPopover"
               placement="top"
               show>
        {{ disabledPopoverContent }}
    </b-popover>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import {
    SubmitButton,
    Loader,
    LocalHeader,
    DescriptionPopover,
    User,
    InfinitePlagiarismCaseList,
} from '@/components';
import { downloadFile, getOtherAssignmentPlagiarismDesc, nameOfUser } from '@/utils';

export default {
    name: 'plagiarism-overview',

    data() {
        return {
            getOtherAssignmentPlagiarismDesc,
            filter: '',
            tableFields: [
                {
                    key: 'user1',
                    sortable: true,
                    label: 'Student 1',
                },
                {
                    key: 'user2',
                    sortable: true,
                    label: 'Student 2',
                },
                {
                    key: 'match_max',
                    sortable: true,
                    label: 'Maximum score',
                    formatter: item => item.toFixed(2),
                },
                {
                    key: 'match_avg',
                    sortable: true,
                    label: 'Average score',
                    formatter: item => item.toFixed(2),
                },
            ],
            loadingData: true,
            error: '',
            disabledPopoverRowId: '',
            disabledPopoverContent: '',
        };
    },

    computed: {
        ...mapGetters('assignments', ['getAssignment']),
        ...mapGetters('plagiarism', ['runs']),

        run() {
            return this.runs[this.plagiarismRunId];
        },

        plagiarismRunId() {
            return `${this.$route.params.plagiarismRunId}`;
        },

        courseId() {
            return this.$routeParamAsId('courseId');
        },

        assignmentId() {
            return this.$routeParamAsId('assignmentId');
        },

        assignment() {
            return this.getAssignment(this.assignmentId).extract();
        },
    },

    watch: {
        $route(newRoute, oldRoute) {
            if (
                newRoute.params.assignmentId !== oldRoute.params.assignmentId ||
                newRoute.params.plagiarismRunId !== oldRoute.params.plagiarismRunId
            ) {
                this.loadRun();
            }
        },

        assignment(assignment) {
            if (assignment == null) {
                this.loadSingleAssignment({
                    assignmentId: this.assignmentId,
                    courseId: this.courseId,
                });
            }
        },

        assignmentId: {
            immediate: true,
            handler(assignmentId) {
                this.loadSingleAssignment({ assignmentId, courseId: this.courseId });
            },
        },
    },

    methods: {
        ...mapActions('assignments', ['loadSingleAssignment']),
        ...mapActions('plagiarism', {
            loadPlagiarismRun: 'loadRun',
        }),

        downloadLog() {
            const filename = `Plagiarism log for ${this.assignment.name}.txt`;
            downloadFile(this.run.log, filename, 'text/plain');
        },

        rowClicked(item) {
            if (!item.canView) {
                return;
            }

            this.$router.push({
                name: 'plagiarism_detail',
                params: Object.assign(this.$route.params, {
                    plagiarismCaseId: item.id,
                }),
            });
        },

        rowHovered(item, _, event) {
            this.disabledPopoverRowId = '';

            if (item == null || item.canView) {
                return;
            }

            if (!event.target.id) {
                event.target.id = `row-${item.id}`;
            }

            const index = item.assignments[0].id === this.assignmentId ? 1 : 0;

            this.disabledPopoverContent = `You don't have the permission
            "View plagiarism" for the course
            "${item.assignments[index].course.name}" which is necessary to view
            this case.`;

            this.$nextTick(() => {
                this.disabledPopoverRowId = event.target.id;
            });
        },

        sortCompareTable(a, b, key) {
            if (key === 'user1' || key === 'user2') {
                const index = key === 'user1' ? 0 : 1;
                return nameOfUser(a.users[index]).localeCompare(
                    nameOfUser(b.users[index]),
                    undefined,
                    {
                        numeric: true,
                    },
                );
            }
            if (typeof a[key] === 'number' && typeof b[key] === 'number') {
                // If both compared fields are native numbers
                return a[key] - b[key];
            } else {
                // Stringify the field data and use String.localeCompare
                return a[key].localeCompare(b[key], undefined, {
                    numeric: true,
                });
            }
        },

        loadRun() {
            this.loadingData = true;

            this.loadPlagiarismRun(this.plagiarismRunId).then(
                () => {
                    this.loadingData = false;
                },
                err => {
                    this.error = this.$utils.getErrorMessage(err);
                },
            );
        },
    },

    mounted() {
        this.loadRun();
    },

    components: {
        SubmitButton,
        LocalHeader,
        DescriptionPopover,
        User,
        Loader,
        InfinitePlagiarismCaseList,
    },
};
</script>

<style lang="less" scoped>
.filter-input {
    flex: 1;
    width: auto;
}

.download-btn,
.filter-input {
    margin-top: 0.2rem;
    margin-bottom: 0.2rem;
    word-wrap: nowrap;
}

.description {
    font-size: 100%;
    cursor: help;
}
</style>

<style lang="less">
@import '~mixins.less';

.plagiarism-overview .modal-dialog {
    .default-text-colors;
    width: 75vw;
    margin-left: 12.5vw;
    margin-right: 12.5vw;

    .modal-content {
        width: 75vw;
    }

    pre {
        color: inherit;
    }
}

.plagiarism-overview .overview-table {
    .table-warning {
        cursor: not-allowed;
        color: @color-secondary-text-lighter;
        background-color: transparent !important;

        @{dark-mode} {
            color: @text-color-muted;
        }

        td {
            background-color: transparent !important;
            border-color: @border-color;

            @{dark-mode} {
                border-color: @color-primary-darker;
            }
        }

        &:nth-of-type(odd) {
            background-color: rgba(0, 0, 0, 0.05) !important;
        }
    }
}
</style>
