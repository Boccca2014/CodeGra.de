<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader center v-if="loading"/>

<div class="submissions d-flex flex-column"
     :class="{ 'is-student': isStudent }"
     v-else>
    <local-header always-show-extra-slot
                  :back-route="headerBackRoute">
        <template #title
                  v-if="assignment">
            <assignment-name
                :assignment="assignment" />

            <assignment-date
                :assignment="assignment"
                class="text-muted" />
        </template>

        <template #title
                  v-else>
            <small class="text-muted font-italic">
                Unknown assignment...
            </small>
        </template>

        <template #extra
                  v-show="!isStudent">
            <category-selector slot="extra"
                               default=""
                               v-model="selectedCat"
                               :disabled="loadingInner"
                               :categories="categories"/>
        </template>

        <b-input-group v-if="assignment != null">
            <b-button v-if="isStudent"
                      class="mr-2"
                      v-b-modal="`submissions-page-course-feedback-modal-${id}`">
                Course feedback
            </b-button>

            <b-button-group>
                <b-button :to="manageAssignmentRoute"
                          variant="secondary"
                          v-if="canManageAssignment"
                          v-b-popover.bottom.hover="'Manage assignment'"
                          class="manage-assignment-button">
                    <icon name="gear"/>
                </b-button>

                <b-button v-if="canEmailStudents"
                          v-b-popover.top.hover="`Email the authors of the visible submissions`"
                          v-b-modal="`submissions-page-email-students-modal-${id}`"
                          id="submissions-page-email-students-button">
                    <icon name="envelope"/>
                </b-button>

                <b-button-group v-b-popover.bottom.hover="'Reload submissions'">
                    <submit-button :wait-at-least="500"
                                   name="refresh-button"
                                   :submit="submitForceLoadSubmissions">
                        <icon name="refresh"/>
                        <icon name="refresh" spin slot="pending-label"/>
                    </submit-button>
                </b-button-group>
            </b-button-group>
        </b-input-group>

        <cg-logo v-if="isStudent"
                 :inverted="!darkMode" />
    </local-header>

    <b-modal v-if="canEmailStudents"
             :id="`submissions-page-email-students-modal-${id}`"
             ref="contactStudentModal"
             size="xl"
             hide-footer
             no-close-on-backdrop
             no-close-on-esc
             hide-header-close
             title="Email authors"
             body-class="p-0"
             dialog-class="auto-test-result-modal">
        <cg-catch-error capture>
            <template slot-scope="{ error }">
                <b-alert v-if="error"
                         show
                         variant="danger">
                    {{ $utils.getErrorMessage(error) }}
                </b-alert>

                <student-contact
                    v-else
                    :initial-users="visibleStudents"
                    :course="assignment.course"
                    :default-subject="defaultEmailSubject"
                    reset-on-email
                    @hide="() => $refs.contactStudentModal.hide()"
                    @emailed="() => $refs.contactStudentModal.hide()"
                    :can-use-snippets="canUseSnippets"
                    class="p-3"/>
            </template>
        </cg-catch-error>
    </b-modal>

    <div class="cat-container d-flex flex-column">
        <div v-if="error != null">
            <b-alert variant="danger" show>
                {{ $utils.getErrorMessage(error) }}
            </b-alert>
        </div>

        <loader center page-loader v-else-if="loadingInner" />

        <template v-else>
            <b-modal v-if="isStudent"
                     :id="`submissions-page-course-feedback-modal-${id}`"
                     title="Course feedback"
                     size="xl"
                     body-class="p-0"
                     hide-footer>
                <course-feedback :course="assignment.course"
                                 :user="loggedInUser" />
            </b-modal>

            <div v-if="selectedCat === 'student-start'"
                 class="wizard-buttons flex-grow-1 d-flex flex-wrap">
                <template v-if="canUploadForSomeone">
                    <cg-wizard-button
                        class="latest-submission"
                        :icon="latestSubmissionGrade == null ? 'history' : 'file-o'"
                        :is-file-icon="latestSubmissionGrade == null"
                        :size="wizardButtonSize"
                        :variant="latestSubmissionAfterDeadline ? 'danger' : ''"
                        :disabled="!!latestSubmissionDisabled"
                        :popover="latestSubmissionDisabled"
                        @click="openLatestUserSubmission()">
                        Latest submission

                        <late-submission-icon
                            v-if="latestSubmission"
                            :assignment="assignment"
                            :submission="latestSubmission"/>

                        <div v-if="latestSubmission">
                            Submitted <cg-relative-time :date="latestSubmission.createdAt" />
                        </div>

                        <b-badge v-if="latestSubmissionGrade != null"
                                 class="center-in-file"
                                 :variant="latestSubmissionAfterDeadline ? 'danger' : 'dark'"
                                 style="font-size: 112.5%;"
                                 title="Your grade for this assignment">
                            {{ latestSubmissionGrade }}
                        </b-badge>
                    </cg-wizard-button>

                    <cg-wizard-button
                        class="upload-files"
                        label="Upload files"
                        icon="plus"
                        is-file-icon
                        :size="wizardButtonSize"
                        :disabled="!!uploadDisabledMessage"
                        :popover="uploadDisabledMessage"
                        @click="openCategory('hand-in')"/>

                    <cg-wizard-button
                        v-if="webhookUploadEnabled"
                        label="Set up Git"
                        icon="code-fork"
                        :size="wizardButtonSize"
                        :disabled="!!webhookDisabledMessage"
                        :popover="webhookDisabledMessage"
                        @click="openCategory('git'); loadGitData()"/>
                </template>

                <cg-wizard-button
                    v-if="rubric != null"
                    label="Rubric"
                    icon="th"
                    :size="wizardButtonSize"
                    @click="openCategory('rubric')" />

                <cg-wizard-button
                    v-if="assignment.group_set != null"
                    label="Groups"
                    icon="users"
                    :size="wizardButtonSize"
                    @click="openCategory('groups')" />

                <cg-wizard-button
                    v-if="assignment.peer_feedback_settings != null"
                    label="Peer feedback"
                    icon="comments-o"
                    :size="wizardButtonSize"
                    :disabled="!!peerFeedbackDisabled"
                    :popover="peerFeedbackDisabled"
                    @click="openCategory('peer-feedback')" />
            </div>

            <!-- We can't use v-if here because the <submission-list> MUST
                 always be rendered so we can get the filtered list of
                 submissions. Because v-show doesn't add an !important to its
                 style rule, but d-flex does, we must disable the d-flex class
                 when the element isn't shown. -->
            <div class="flex-grow-1 flex-column"
                 :class="selectedCat === 'hand-in' ? 'd-flex' : 'd-none'">
                <submission-list v-if="!isStudent"
                                 :assignment="assignment"
                                 :rubric="rubric"
                                 :graders="graders"
                                 :can-see-assignee="canSeeAssignee"
                                 :can-assign-grader="canAssignGrader"
                                 :can-see-others-work="canSeeOthersWork"
                                 @filter="filteredSubmissions = $event.submissions"
                                 class="mb-3" />

                <b-card v-else-if="assigHandinReqs"
                        class="mb-3"
                        no-body>
                        <b-card-header>
                            Hand-in instructions
                        </b-card-header>

                        <c-g-ignore-file :assignment="assignment"
                                         :editable="false"
                                         summary-mode />
                    </collapse>
                </b-card>

                <template>
                    <b-alert show
                             variant="info"
                             class="group-assignment-alert assignment-alert"
                             v-if="assignment.group_set">
                        This is a group assignment.

                        <template v-if="assignment.group_set.minimum_size > 1">
                            To submit you have to be in a group with at least
                            {{ assignment.group_set.minimum_size }} members.
                        </template>

                        <template v-else>
                            You don't have to be member of group to submit.
                        </template>

                        You can create or join groups
                        <router-link :to="{ hash: '#groups' }"
                                     class="inline-link">here</router-link>.
                        When submitting you will always submit for your entire
                        group.
                    </b-alert>

                    <submission-uploader :assignment="assignment"
                                         :for-others="canUploadForOthers"
                                         :can-list-users="canListUsers"
                                         :maybe-show-git-instructions="!isStudent"
                                         @created="goToSubmission"
                                         :class="isStudent ? 'flex-grow-1' : ''" />
                </template>
            </div>

            <div v-if="selectedCat === 'rubric'"
                 class="flex-grow-1">
                <rubric-editor :assignment="assignment"
                               grow />
            </div>

            <div v-if="selectedCat === 'hand-in-instructions'"
                 class="flex-grow-1">
                <c-g-ignore-file class="border rounded mb-3"
                                 :assignment="assignment"
                                 :editable="false"
                                 summary-mode/>
            </div>

            <div v-if="selectedCat === 'git'"
                 class="flex-grow-1">
                <template v-if="gitData == null">
                    <cg-loader page-loader />
                    <p class="mt-3 text-center text-muted">Loading webhook data&#8230;</p>
                </template>

                <webhook-instructions v-else
                                      :data="gitData"
                                      :style="{ margin: '0 auto', maxWidth: '42rem' }" />
            </div>

            <div v-if="selectedCat === 'groups'"
                 class="flex-grow-1">
                <groups-management :assignment="assignment"
                                   :course="assignment.course"
                                   :group-set="assignment.group_set"
                                   :show-lti-progress="showGroupLTIProgress"
                                   :show-add-button="showAddGroupButton" />
            </div>

            <div v-show="selectedCat === 'export'"
                 class="flex-grow-1">
                <submissions-exporter :get-submissions="getExportedSubmissions"
                                      :assignment-id="assignment.id"
                                      :filename="exportFilename" />
            </div>

            <div v-if="selectedCat === 'analytics'"
                 class="flex-grow-1">
                <cg-catch-error>
                    <template slot-scope="scope">
                        <b-alert show variant="danger" v-if="scope.error">
                            An unexpected error occurred:
                            {{ $utils.getErrorMessage(scope.error) }}

                            <pre class="text-wrap-pre">{{ scope.error.stack }}</pre>
                        </b-alert>

                        <analytics-dashboard v-else
                                             :assignment="assignment" />
                    </template>
                </cg-catch-error>
            </div>

            <div v-if="selectedCat === 'peer-feedback'"
                 class="overflow-hidden"
                 style="max-height: 100%;">
                <peer-feedback-overview :assignment="assignment"
                                        class="mb-3" />
            </div>
        </template>
    </div>
</div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/gear';
import 'vue-awesome/icons/history';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/refresh';
import 'vue-awesome/icons/th';
import 'vue-awesome/icons/users';
import 'vue-awesome/icons/code-fork';
import 'vue-awesome/icons/envelope';
import 'vue-awesome/icons/comments-o';
import 'vue-awesome/icons/file-o';

import { NONEXISTENT } from '@/constants';
import { GradersStore } from '@/store/modules/graders';
import GroupsManagement from '@/components/GroupsManagement';
import {
    CgLogo,
    Loader,
    Collapse,
    LocalHeader,
    CGIgnoreFile,
    RubricEditor,
    SubmitButton,
    CourseFeedback,
    SubmissionList,
    CategorySelector,
    LateSubmissionIcon,
    SubmissionUploader,
    SubmissionsExporter,
    WebhookInstructions,
    PeerFeedbackOverview,
    AssignmentDate,
    AssignmentName,
} from '@/components';
import StudentContact from '@/components/StudentContact';

import { setPageTitle, pageTitleSep } from './title';

export default {
    name: 'submissions-page',

    data() {
        return {
            id: this.$utils.getUniqueId(),
            loading: true,
            loadingInner: true,
            wrongFiles: [],
            selectedCat: '',
            filteredSubmissions: [],
            gitData: null,
            error: null,
            showCourseFeedback: false,
        };
    },

    computed: {
        ...mapGetters('user', {
            userId: 'id',
            userPerms: 'permissions',
        }),
        ...mapGetters('pref', ['darkMode']),
        ...mapGetters('assignments', ['getAssignment']),
        ...mapGetters('rubrics', { allRubrics: 'rubrics' }),
        ...mapGetters('submissions', ['getSubmissionsByUser', 'getLatestSubmissions']),
        ...mapGetters('users', ['getUser', 'getGroupInGroupSetOfUser']),

        loggedInUser() {
            return this.getUser(this.userId);
        },

        categories() {
            return [
                {
                    id: 'student-start',
                    name: '',
                    enabled: this.isStudent,
                },
                {
                    id: 'hand-in',
                    name: !this.isStudent ? 'Submissions' : 'Hand in',
                    enabled: true,
                },
                {
                    id: 'git',
                    name: 'Git instructions',
                    enabled: this.isStudent && this.webhookUploadEnabled,
                },
                {
                    id: 'rubric',
                    name: 'Rubric',
                    enabled: true,
                },
                {
                    id: 'hand-in-instructions',
                    name: 'Hand-in instructions',
                    enabled: !this.isStudent && this.assigHandinReqs,
                },
                {
                    id: 'groups',
                    name: 'Groups',
                    enabled: this.assigGroupSet,
                },
                {
                    id: 'export',
                    name: 'Export',
                    enabled: !this.isStudent,
                },
                {
                    id: 'analytics',
                    name: 'Analytics',
                    badge: { label: 'beta' },
                    enabled: this.analyticsWorkspaceIds.length > 0,
                },
                {
                    id: 'peer-feedback',
                    name: 'Peer Feedback',
                    enabled: this.isStudent,
                },
            ];
        },

        defaultCat() {
            return this.isStudent ? 'student-start' : 'hand-in';
        },

        manageAssigURL() {
            return {
                name: 'manage_assignment',
                params: {
                    courseId: this.courseId,
                    assignmentId: this.assignmentId,
                },
            };
        },

        groupSetPageLink() {
            return {
                name: 'manage_groups',
                params: {
                    courseId: this.assignment.course.id,
                    groupSetId: this.assignment.group_set && this.assignment.group_set.id,
                },
                query: { sbloc: 'g' },
            };
        },

        assignment() {
            return this.getAssignment(this.assignmentId).extract();
        },

        submissions() {
            return this.getSubmissionsByUser(this.assignmentId, this.userId, {
                includeGroupSubmissions: true,
            });
        },

        latestSubmissions() {
            return this.getLatestSubmissions(this.assignmentId);
        },

        rubric() {
            const rubric = this.allRubrics[this.assignmentId];
            return rubric === NONEXISTENT ? null : rubric;
        },

        graders() {
            return GradersStore.getGraders()(this.assignmentId);
        },

        assignmentId() {
            return Number(this.$route.params.assignmentId);
        },

        courseId() {
            return this.$route.params.courseId;
        },

        webhookUploadEnabled() {
            return this.$utils.getProps(this.assignment, false, 'webhook_upload_enabled');
        },

        analyticsWorkspaceIds() {
            return this.$utils.getProps(this.assignment, [], 'analytics_workspace_ids');
        },

        canManageAssignment() {
            return this.$utils.getProps(this.assignment, false, 'canManage');
        },

        wizardButtonSize() {
            return this.$root.$isMediumWindow ? 'large' : 'medium';
        },

        uploadDisabledMessage() {
            const reasons = this.assignment.getSubmitDisabledReasons(this.$root.$now);

            if (!this.assignment.files_upload_enabled) {
                reasons.unshift('file uploads are disabled for this assignment.');
            }

            if (reasons.length === 0) {
                return '';
            }

            return `You cannot upload work because ${this.$utils.readableJoin(reasons)}.`;
        },

        webhookDisabledMessage() {
            const reasons = this.assignment.getSubmitDisabledReasons(this.$root.$now);

            if (reasons.length === 0) {
                return '';
            }

            return `You cannot view the webhook instructions because ${this.$utils.readableJoin(reasons)}.`;
        },

        latestSubmissionDisabled() {
            if (this.submissions.length === 0) {
                return 'You have not yet submitted your work';
            } else {
                return '';
            }
        },

        latestSubmissionAfterDeadline() {
            if (this.latestSubmission == null) {
                return false;
            }

            return this.latestSubmission.isLate();
        },

        peerFeedbackDisabled() {
            const assig = this.assignment;

            if (assig.deadline == null) {
                return 'Peer feedback is disabled because the deadline has not been set yet.';
            } else if (assig.deadlinePassed(this.$root.$now)) {
                return '';
            } else {
                const pfSettings = assig.peer_feedback_settings;
                return (
                    'Peer feedback is disabled until the deadline has passed, which is at' +
                    ` ${assig.getFormattedDeadline()}. After the deadline you have` +
                    ` ${pfSettings.amount} days to give peer feedback.`
                );
            }
        },

        // It should not be possible that `assignment` is null. Still we use getProps below just in
        // case it ever is.

        assigHandinReqs() {
            return this.$utils.getProps(this.assignment, null, 'cgignore');
        },

        assigGroupSet() {
            return this.$utils.getProps(this.assignment, null, 'group_set');
        },

        isStudent() {
            return this.$utils.getProps(this.assignment, true, 'course', 'isStudent');
        },

        manageAssignmentRoute() {
            return {
                name: 'manage_assignment',
                params: {
                    courseId: this.assignment.course.id,
                    assignmentId: this.assignment.id,
                },
            };
        },

        latestSubmission() {
            if (this.submissions.length === 0) {
                return null;
            }
            return this.$utils.last(this.submissions);
        },

        latestSubmissionGrade() {
            return this.$utils.getProps(this.latestSubmission, null, 'grade');
        },

        exportFilename() {
            return this.assignment
                ? `${this.assignment.course.name}-${this.assignment.name}.csv`
                : null;
        },

        headerBackRoute() {
            if (!this.isStudent || this.selectedCat === 'student-start') {
                return null;
            } else {
                return Object.assign({}, this.$route, { hash: '' });
            }
        },

        actionIconFactor() {
            return this.$root.$isSmallWindow ? 0.75 : 1;
        },

        coursePermissions() {
            return this.$utils.getProps(this.assignment, {}, 'course', 'permissions');
        },

        canSeeAssignee() {
            return this.coursePermissions.can_see_assignee;
        },

        canAssignGrader() {
            return this.coursePermissions.can_assign_graders;
        },

        canUploadForSelf() {
            return this.coursePermissions.can_submit_own_work;
        },

        canUploadForOthers() {
            return this.coursePermissions.can_submit_others_work;
        },

        canUploadForSomeone() {
            return this.canUploadForSelf || this.canUploadForOthers;
        },

        canListUsers() {
            return this.coursePermissions.can_list_course_users;
        },

        canSeeOthersWork() {
            return this.coursePermissions.can_see_others_work;
        },

        currentGroup() {
            const groupSetId = this.$utils.getProps(this.assignment, null, 'group_set', 'id');
            return this.getGroupInGroupSetOfUser(groupSetId, this.userId);
        },

        showAddGroupButton() {
            if (this.currentGroup == null) {
                return true;
            }
            // When there is a group, only show the add button if you are not a student.
            return !this.isStudent;
        },

        visibleStudents() {
            const seen = new Set();
            return this.filteredSubmissions.reduce((acc, s) => {
                s.user.getContainedUsers().forEach(u => {
                    if (u.is_test_student || seen.has(u.id)) {
                        return;
                    }

                    seen.add(u.id);
                    acc.push(u);
                });

                return acc;
            }, []);
        },

        defaultEmailSubject() {
            return `[CodeGrade - ${this.assignment.course.name}/${this.assignment.name}] …`;
        },

        canUseSnippets() {
            return !!this.userPerms.can_use_snippets;
        },

        canEmailStudents() {
            return (UserConfig.features.email_students &&
                    this.$utils.getProps(this.coursePermissions, false, 'can_email_students'));
        },
    },

    watch: {
        userId: {
            immediate: true,
            handler() {
                this.loadData();
            },
        },

        assignment(newValue) {
            if (newValue == null) {
                this.loadData();
            }
        },

        assignmentId: {
            immediate: true,
            handler() {
                this.gitData = null;
                this.loadData();
            },
        },
    },

    methods: {
        ...mapActions('assignments', ['loadSingleAssignment']),

        ...mapActions('submissions', {
            loadSubmissions: 'loadSubmissions',
            forceLoadSubmissions: 'forceLoadSubmissions',
        }),

        ...mapActions('rubrics', {
            storeLoadRubric: 'loadRubric',
        }),

        async loadData() {
            this.error = null;

            // Don't set loading if we already have the assignment data to
            // prevent the LocalHeader from disappearing for a fraction of
            // a second.
            if (this.assignment == null) {
                this.loading = true;
                await this.loadSingleAssignment({
                    assignmentId: this.assignmentId,
                    courseId: this.courseId,
                }).catch(() => null);
                await this.$nextTick();
            }

            // Always set loading to false, otherwise you'd get an infinite
            // when the page/component is reloaded in dev mode.
            this.loading = false;

            if (this.assignment == null) {
                this.error = new ReferenceError(
                    'The requested assignment does not exist or you do not have permission to' +
                    ' view it. This is probably because the assignment is still hidden.',
                );
                return;
            }

            const promises = [
                this.loadSubmissions({
                    assignmentId: this.assignmentId,
                    courseId: this.courseId,
                }),
                this.loadRubric(),
                this.$afterRerender(),
            ];

            // This uses the hash because this.selectedCat may still be unset on page load.
            if (this.$route.hash === '#git') {
                promises.push(this.loadGitData());
            }

            setPageTitle(`${this.assignment.name} ${pageTitleSep} Submissions`);

            this.loadInner(Promise.all(promises));
        },

        loadGitData() {
            if (!this.webhookUploadEnabled) {
                return Promise.reject(new Error('Webhooks are not enabled for this assignment'));
            } else if (this.gitData != null) {
                return Promise.resolve();
            }

            return this.$http
                .post(`/api/v1/assignments/${this.assignment.id}/webhook_settings?webhook_type=git`)
                .then(
                    res => {
                        this.gitData = res.data;
                        return res;
                    },
                    err => {
                        this.gitData = null;
                        throw err;
                    },
                );
        },

        loadRubric() {
            return this.storeLoadRubric({
                assignmentId: this.assignmentId,
            }).catch(err => {
                if (this.$utils.getProps(err, 500, 'response', 'status') !== 404) {
                    throw err;
                }
            });
        },

        submitForceLoadSubmissions() {
            this.$root.$emit('cg::submissions-page::reload');
            return this.loadInner(
                this.forceLoadSubmissions({ assignmentId: this.assignmentId }),
            );
        },

        loadInner(promise) {
            this.loadingInner = true;

            return promise.then(
                res => {
                    this.loadingInner = false;
                    return res;
                },
                err => {
                    this.loadingInner = false;
                    this.error = err;
                    throw err;
                },
            );
        },

        goToSubmission(submission) {
            this.$router.push({
                name: 'submission',
                params: { submissionId: submission.id },
            });
        },

        openLatestUserSubmission() {
            const sub = this.latestSubmission;

            if (sub != null) {
                this.goToSubmission(sub);
            }
        },

        openCategory(cat) {
            this.$router.push(
                Object.assign({}, this.$route, {
                    hash: `#${cat}`,
                }),
            );
        },

        showGroupLTIProgress(group) {
            if (this.assignment.is_lti && this.currentGroup && this.currentGroup.isGroup) {
                return this.currentGroup.group.id === group.id;
            }
            return false;
        },

        getExportedSubmissions(filter) {
            if (filter) {
                return this.filteredSubmissions;
            } else {
                return this.latestSubmissions;
            }
        },
    },

    mounted() {
        this.$root.$on('sidebar::reload', this.submitForceLoadSubmissions);
    },

    destroyed() {
        this.$root.$off('sidebar::reload', this.submitForceLoadSubmissions);
    },

    components: {
        Icon,
        CgLogo,
        Loader,
        Collapse,
        LocalHeader,
        CGIgnoreFile,
        RubricEditor,
        SubmitButton,
        CourseFeedback,
        SubmissionList,
        CategorySelector,
        GroupsManagement,
        SubmissionUploader,
        SubmissionsExporter,
        WebhookInstructions,
        LateSubmissionIcon,
        StudentContact,
        PeerFeedbackOverview,
        AssignmentDate,
        AssignmentName,
        AnalyticsDashboard: () => ({
            component: import('@/components/AnalyticsDashboard'),
            loading: Loader,
        }),
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.loader {
    padding-top: 3.5em;
}

.cg-logo {
    height: 1.5rem;
    width: auto;
}

.cat-container {
    margin: -1rem -15px 0;
    padding: 1rem 15px 0;
    background-color: white;
    flex: 1 1 auto;

    @{dark-mode} {
        background-color: @color-primary;
    }
}

.cat-wrapper,
.submission-list {
    flex: 1 1 auto;
}

.wizard-buttons {
    max-width: 48rem;
    width: 100%;
    margin: 0 auto;
    justify-content: center;

    @media @media-no-small {
        align-content: center;
        align-items: center;
    }

    @media @media-small {
        align-content: flex-start;
        align-items: flex-start;
    }

    .wizard-button-container {
        margin: 0.5rem;
    }
}
</style>

<style lang="less">
.page.submissions.is-student {
    // Hide the "extra" slot in the LocalHeader when a student is logged in
    // because we need to render the CategorySelector so it responds to
    // changes in the URL.
    .local-header .always-extra-header {
        display: none;
    }
}
</style>
