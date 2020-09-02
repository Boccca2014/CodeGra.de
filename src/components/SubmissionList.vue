<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="submission-list d-flex flex-column">
    <b-form-fieldset>
        <b-input-group class="search-wrapper">
            <input v-model="filter"
                   class="form-control"
                   name="submissions-filter"
                   placeholder="Type to Search"
                   @keyup.enter="submit"
                   @keyup="submitDelayed"/>

            <b-input-group-append is-text
                                  class="assigned-to-me-option"
                                  v-if="canSeeOthersWork && !assigneeCheckboxDisabled"
                                  v-b-popover.bottom.hover="'Show only submissions assigned to me.'">
                <b-form-checkbox v-model="mineOnly"
                                 @change="submit">
                    Assigned to me
                </b-form-checkbox>
            </b-input-group-append>
        </b-input-group>
    </b-form-fieldset>

    <b-table striped
             hover
             class="mb-0 border-bottom submissions-table"
             primary-key="id"
             :id="tableId"
             show-empty
             :fields="fields"
             :items="filteredSubmissions"
             :sort-by="this.$route.query.sortBy || 'user'"
             :sort-desc="!parseBool(this.$route.query.sortAsc, true)"
             :sort-compare="(a, b, sortBy) => sortSubmissions(a.sub, b.sub, sortBy)"
             @sort-changed="sortChanged"
             :per-page="perPage"
             :current-page="currentPage"
             @row-clicked="gotoSubmission">
        <template #cell(user)="item">
            <router-link class="invisible-link"
                         :to="submissionRoute(item.item.sub)">
                <user :user="item.item.sub.user"/>
                <webhook-name :submission="item.item.sub" />
                <icon name="exclamation-triangle"
                      class="text-warning ml-1"
                      v-b-popover.top.hover="getOtherSubmissionPopover(item.item.sub)"
                      v-if="!!getOtherSubmissionPopover(item.item.sub)"/>
            </router-link>
        </template>

        <template #cell(grade)="item">
            <span class="submission-grade">
                {{ item.item.sub.grade || '-' }}
            </span>
        </template>

        <template #cell(formattedCreatedAt)="item">
            {{item.item.sub.formattedCreatedAt }}

            <late-submission-icon :submission="item.item.sub"
                                  :assignment="assignment" />
        </template>

        <template #cell(assignee)="item" >
            <span class="assigned-to-grader">
                <span v-if="!canAssignGrader || graders == null">
                    <user :user="item.item.sub.assignee"
                          v-if="item.item.sub.assignee"/>
                    <span v-else>-</span>
                </span>
                <loader :scale="1"
                        v-else-if="assigneeUpdating[item.item.sub.id]"/>
                <div v-else
                     v-b-popover.top.hover="graderDisabledMessage(item.item.sub)">
                    <b-form-select :options="assignees"
                                   :disabled="!!graderDisabledMessage(item.item.sub)"
                                   :value="item.item.sub.assigneeId || null"
                                   @input="updateAssignee($event, item.item.sub)"
                                   @click.native.stop
                                   class="user-form-select"/>
                </div>
            </span>
        </template>

        <template #empty>
            <div class="text-center font-italic text-muted">
                <template v-if="!canSeeOthersWork && submissions.length === 0">
                    You have no submissions yet.
                </template>
                <template v-else-if="submissions.length === 0">
                    There are no submissions yet.
                </template>
                <template v-else>
                    No submissions found with the given filters.
                </template>
            </div>
        </template>

        <template #custom-foot
                  v-if="canSeeOthersWork">
            <tr>
                <td colspan="4"
                    class="submission-count">
                    Showing {{ numFilteredStudents }} out of {{ numStudents }} students.
                </td>
            </tr>
        </template>
    </b-table>

    <b-pagination
        class="mt-3 mb-0"
        v-if="showPagination"
        v-model="currentPage"
        :limit="10"
        :total-rows="numFilteredStudents"
        :per-page="perPage"
        :aria-controls="tableId" />
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/exclamation-triangle';

import { waitAtLeast, formatGrade, parseBool, nameOfUser } from '@/utils';
import { filterSubmissions, sortSubmissions } from '@/utils/FilterSubmissionsManager';

import Loader from './Loader';
import User from './User';
import LateSubmissionIcon from './LateSubmissionIcon';
import WebhookName from './WebhookName';

export default {
    name: 'submission-list',

    props: {
        assignment: {
            type: Object,
            default: null,
        },
        rubric: {
            default: null,
        },
        graders: {
            default: null,
            type: Array,
        },
        canSeeAssignee: {
            type: Boolean,
            required: true,
        },
        canAssignGrader: {
            type: Boolean,
            required: false,
        },
        canSeeOthersWork: {
            type: Boolean,
            required: false,
        },
    },

    data() {
        return {
            mineOnly: parseBool(this.$route.query.mine, null),
            sortAsc: parseBool(this.$route.query.sortAsc, true),
            sortBy: this.$route.query.sortBy || 'user',
            filter: this.$route.query.q || '',
            assignees: [],
            assigneeUpdating: [],
            // For use in v-b-popover directives.
            quote: '"',
            currentPage: parseInt(this.$route.query.page, 10) || 1,
            tableId: `submissions-table-${this.$utils.getUniqueId()}`,
        };
    },

    computed: {
        ...mapGetters('user', {
            userId: 'id',
            userName: 'name',
        }),

        ...mapGetters('submissions', ['getLatestSubmissions', 'getGroupSubmissionOfUser']),

        submissions() {
            return this.getLatestSubmissions(this.assignment.id);
        },

        fields() {
            const fields = [
                {
                    key: 'user',
                    label: 'User',
                    sortable: true,
                },
                {
                    key: 'grade',
                    label: 'Grade',
                    sortable: true,
                },
                {
                    key: 'formattedCreatedAt',
                    label: 'Created at',
                    sortable: true,
                },
            ];
            if (this.canSeeAssignee) {
                fields.push({
                    key: 'assignee',
                    label: 'Assigned to',
                    sortable: true,
                });
            }
            return fields;
        },

        filteredSubmissions() {
            // WARNING: We need to access all, do not change!
            if (
                [this.submissions, this.mineOnly, this.userId, this.filter].indexOf(undefined) !==
                -1
            ) {
                return [];
            }

            return filterSubmissions(this.submissions, this.mineOnly, this.userId, this.filter).map(
                sub => {
                    let variant = null;
                    if (sub.isLate()) {
                        variant = 'danger';
                    } else if (this.getGroupSubmissionOfUser(this.assignment.id, sub.userId)) {
                        variant = 'warning';
                    }

                    return {
                        id: sub.id,
                        sub,
                        _rowVariant: variant,
                    };
                },
            );
        },

        numStudents() {
            return this.submissions.length;
        },

        numFilteredStudents() {
            return this.filteredSubmissions.length;
        },

        assigneeCheckboxDisabled() {
            if (this.submissions == null) {
                return true;
            }

            return !this.submissions.find(
                s => this.$utils.getProps(s, null, 'assignee', 'id') === this.userId,
            );
        },

        perPage() {
            return 15;
        },

        showPagination() {
            return this.numFilteredStudents > this.perPage || this.currentPage !== 1;
        },
    },

    watch: {
        filteredSubmissions: {
            immediate: true,
            handler(newVal, oldVal) {
                this.$emit('filter', {
                    submissions: this.filteredSubmissions.map(s => s.sub),
                });

                // This is null on the immediate call of this wachter.
                if (oldVal != null) {
                    this.currentPage = 1;
                }
            },
        },

        graders(graders) {
            if (graders == null) return;

            this.updateGraders(graders);
        },

        assigneeCheckboxDisabled: {
            immediate: true,
            handler(newVal) {
                if (newVal && this.mineOnly) {
                    this.mineOnly = false;
                    this.submit();
                }
            },
        },

        currentPage() {
            this.submitDelayed();
        },
    },

    created() {
        if (this.graders) {
            this.updateGraders(this.graders);
        }
        if (this.mineOnly == null) {
            this.mineOnly = this.submissions.some(
                s => s.userId === this.userId || (s.assignee && s.assigneeId === this.userId),
            );
        }
    },

    mounted() {
        if (!this.mineOnly) {
            this.submit();
        }
    },

    methods: {
        ...mapActions('submissions', {
            updateSubmission: 'updateSubmission',
        }),

        updateGraders(graders) {
            const assignees = graders.map(g => ({
                value: g.user.id,
                text: nameOfUser(g.user),
                data: g.user,
            }));
            assignees.unshift({ value: null, text: '-', data: null });
            this.assignees = assignees;
        },

        sortChanged(context) {
            this.$nextTick().then(() => {
                const { sortBy, sortDesc } = context;
                this.sortBy = sortBy;
                // Fuck you bootstrapVue (sortDesc should've been sortAsc)
                this.sortAsc = !sortDesc;
                this.$router.replace({
                    query: Object.assign({}, this.$route.query, {
                        sortBy,
                        sortAsc: !sortDesc,
                    }),
                    hash: this.$route.hash,
                });
            });
        },

        submissionRoute(submission) {
            return {
                name: 'submission',
                params: { submissionId: submission.id },
                query: {
                    mine: this.mineOnly == null ? undefined : this.mineOnly,
                    search: this.filter || undefined,
                    sortBy: this.sortBy,
                    sortAsc: this.sortAsc,
                    page: this.currentPage,
                },
            };
        },

        gotoSubmission({ sub: submission }) {
            this.submit();
            this.$router.push(this.submissionRoute(submission));
        },

        submitDelayed() {
            if (this.submitTimeout != null) {
                clearTimeout(this.submitTimeout);
            }

            this.submitTimeout = setTimeout(() => {
                this.submitTimeout = null;
                this.submit();
            }, 200);
        },

        async submit() {
            await this.$nextTick();

            this.$router.replace({
                query: Object.assign({}, this.$route.query, {
                    mine: this.mineOnly,
                    q: this.filter || undefined,
                    page: this.currentPage,
                }),
                hash: this.$route.hash,
            });
        },

        updateAssignee(newId, submission) {
            const oldId = submission.assigneeId || null;
            if (oldId === newId) {
                return;
            }

            this.$set(this.assigneeUpdating, submission.id, true);

            let res;
            if (newId != null) {
                res = this.$http.patch(`/api/v1/submissions/${submission.id}/grader`, {
                    user_id: newId,
                });
            } else {
                res = this.$http.delete(`/api/v1/submissions/${submission.id}/grader`);
            }

            waitAtLeast(250, res).then(
                () => {
                    this.$set(this.assigneeUpdating, submission.id, false);
                    let newAssignee;
                    for (let i = 0; i < this.assignees.length; i += 1) {
                        if (this.assignees[i].data && this.assignees[i].data.id === newId) {
                            newAssignee = this.assignees[i].data;
                            break;
                        }
                    }
                    this.updateSubmission({
                        assignmentId: this.assignment.id,
                        submissionId: submission.id,
                        submissionProps: { assignee: newAssignee },
                    });
                },
                err => {
                    this.$set(this.assigneeUpdating, submission.id, false);
                    this.$bvToast.toast(err.response.data.message, {
                        title: 'Error',
                        toaster: 'b-toaster-top-right',
                        variant: 'danger',
                        noAutoHide: true,
                        solid: true,
                    });
                },
            );
        },

        parseBool,
        formatGrade,
        sortSubmissions,

        getOtherSubmissionPopover(sub) {
            const otherSub = this.getGroupSubmissionOfUser(this.assignment.id, sub.userId);
            if (otherSub) {
                return `This user is member of the group "${
                    otherSub.user.group.name
                }", which also created a submission.`;
            }
            return null;
        },

        graderDisabledMessage(sub) {
            const msg = 'You cannot assign graders to';

            if (sub.user.is_test_student) {
                return `${msg} test students.`;
            }

            const otherSub = this.getGroupSubmissionOfUser(this.assignment.id, sub.userId);
            if (otherSub) {
                return `${msg} students that also have a group submission.`;
            }

            return null;
        },
    },

    components: {
        Icon,
        User,
        Loader,
        WebhookName,
        LateSubmissionIcon,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.submission-list {
    position: relative;
}

.submission-count,
.no-submissions-found {
    padding: 0.75rem;
}

.user-form-select {
    max-width: 20em;
    margin: -0.35rem 0;
    cursor: pointer;

    &[disabled] {
        cursor: not-allowed;
    }
}
</style>

<style lang="less">
@import '~mixins.less';

.submissions-table {
    td,
    th {
        vertical-align: middle;

        // student
        &:nth-child(1) {
            width: 30em;
        }

        // grade
        // created at
        // assignee
        &:nth-child(2),
        &:nth-child(3),
        &:nth-child(4) {
            width: 1px;
            white-space: nowrap;
        }

        .loader {
            padding: 0.33rem;
        }
    }
}

.submission-list {
    .fa-icon {
        transform: translateY(-2px);
    }
}
</style>
