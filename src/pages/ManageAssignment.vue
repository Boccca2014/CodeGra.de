<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="manage-assignment loading" v-if="loading">
    <local-header>
        <template slot="title" v-if="assignment && Object.keys(assignment).length">
            <span>{{ assignment.name }}</span>
            <small v-if="formattedDeadline">- {{ formattedDeadline }}</small>
            <small v-else class="text-muted"><i>- No deadline</i></small>
        </template>
        <loader :scale="1"/>
    </local-header>
    <loader page-loader/>
</div>
<div class="manage-assignment" v-else>
    <local-header always-show-extra-slot
                  class="header">
        <template slot="title">
            <span>{{ assignment.name }}</span>
            <small v-if="formattedDeadline">- {{ formattedDeadline  }}</small>
            <small v-else class="text-muted"><i>- No deadline</i></small>
        </template>
        <assignment-state :assignment="assignment"
                          :key="assignmentId"
                          class="assignment-state"
                          :editable="canEditState"
                          size="sm"/>
        <template slot="extra">
            <category-selector default="general"
                               v-model="selectedCat"
                               :categories="categories"/>
        </template>
    </local-header>

    <div class="page-content" v-if="loadingInner">
        <loader page-loader />
    </div>

    <div class="page-content"
         :key="assignmentId"
         v-show="!loadingInner">
        <div :class="{hidden: selectedCat !== 'general'}"
             v-if="visibleCats.general"
             class="row cat-wrapper">
            <div class="col-xl-6">
                <assignment-general-settings
                    v-if="permissions.canEditSomeGeneralSettings"
                    :assignment="assignment" />
            </div>

            <div class="col-xl-6">
                <assignment-submission-settings
                    v-if="permissions.canEditSubmissionSettings"
                    :assignment="assignment" />

                <b-card v-if="canSubmitWork"
                        no-body>
                    <template #header>
                        Upload submission

                        <description-popover>
                            Upload work for this assignment. With the author
                            field you can select who should be the author. This
                            function can be used to submit work for a student.
                        </description-popover>
                    </template>

                    <submission-uploader :assignment="assignment"
                                         for-others
                                         no-border
                                         maybe-show-git-instructions
                                         :can-list-users="canListCourseUsers" />
                </b-card>
            </div>

            <div class="col-xl-6">
                <b-card v-if="canEditPeerFeedbackSettings">
                    <template #header>
                        Peer feedback

                        <description-popover>
                            Enable peer feedback for this assignment. When
                            enabled you can set the amount of days that
                            students have after the deadline of the assignment
                            to give feedback to their peers. You can also set
                            the number of students that each student must
                            review.
                        </description-popover>
                    </template>

                    <peer-feedback-settings :assignment="assignment" />
                </b-card>
            </div>

            <div class="col-xl-6">
                <b-card v-if="canEditGroups" no-body>
                    <span slot="header">
                        Group assignment

                        <description-popover>
                            <span slot="description">
                                Determine if this assignment should be a group
                                assignment. Select a group set for this
                                assignment to make it a group assignment. To
                                learn more about how groups work on CodeGrade,
                                you can read more
                                <a class="inline-link"
                                   href="https://docs.codegra.de/"
                                   target="_blank">here</a>.
                            </span>
                        </description-popover>
                    </span>
                    <assignment-group :assignment="assignment"/>
                </b-card>
            </div>

            <div class="col-xl-12">
                <b-card v-if="canEditIgnoreFile"
                        class="ignore-card"
                        body-class="p-0">
                    <span slot="header">
                        Hand-in requirements
                        <description-popover>
                            This allows you to set hand-in requirement for
                            students, making sure their submission follows
                            a certain file and directory structure. Students
                            will be able to see these requirements before
                            submitting and will get a warning if their
                            submission does not follow the hand-in
                            requirements.
                        </description-popover>
                    </span>

                    <c-g-ignore-file class="m-3"
                                     :assignment="assignment"/>
                </b-card>

                <b-card header="Blackboard zip"
                        v-if="canSubmitBbZip">
                    <b-popover placement="top"
                               v-if="assignment.is_lti"
                               :target="`file-uploader-assignment-${assignment.id}`"
                               triggers="hover">
                        Not available for LTI assignments
                    </b-popover>
                    <file-uploader class="blackboard-zip-uploader"
                                   :url="`/api/v1/assignments/${assignment.id}/submissions/`"
                                   :disabled="assignment.is_lti"
                                   @response="() => forceLoadSubmissions({ assignmentId: assignment.id, courseId: assignment.courseId })"
                                   :id="`file-uploader-assignment-${assignment.id}`"/>
                </b-card>

                <b-card header="Danger zone"
                        class="danger-zone-wrapper"
                        border-variant="danger"
                        header-text-variant="danger"
                        header-border-variant="danger"
                        v-if="canDeleteAssignments">
                    <div class="d-flex justify-content-between">
                        <div>
                            <strong class="d-block">Delete assignment</strong>

                            <small>
                                Delete this assignment, including all its
                                submissions.
                            </small>
                        </div>
                        <div>
                            <submit-button :submit="deleteAssignment"
                                           @after-success="afterDeleteAssignment"
                                           confirm="Deleting this assignment cannot be reversed, and all submissions will be lost."
                                           confirm-in-modal
                                           variant="danger">
                                Delete assignment
                            </submit-button>
                        </div>
                    </div>
                </b-card>
            </div>
        </div>

        <div class="cat-wrapper"
             :class="{hidden: selectedCat !== 'graders'}">
            <assignment-grader-settings :assignment="assignment"
                                        v-if="visibleCats.graders"/>
        </div>

        <div class="cat-wrapper" :class="{hidden: selectedCat !== 'linters'}">
            <b-card v-if="canUseLinters && visibleCats.linters"
                    header="Linters"
                    :course-id="assignment.course.id">
                <linters :assignment="assignment"/>
            </b-card>

        </div>

        <div class="cat-wrapper" :class="{hidden: selectedCat !== 'plagiarism'}">
            <b-card v-if="canUsePlagiarism && visibleCats.plagiarism" no-body>
                <span slot="header">
                    Plagiarism checking
                    <description-popover>
                        Run a plagiarism checker or view the results.
                    </description-popover>
                </span>
                <plagiarism-runner :class="{ 'mb-3': canManagePlagiarism }"
                                   :assignment="assignment"
                                   :hidden="selectedCat !== 'plagiarism'"
                                   :can-manage="canManagePlagiarism"
                                   :can-view="canViewPlagiarism"/>
            </b-card>
        </div>

        <div class="cat-wrapper" :class="{hidden: selectedCat !== 'rubric'}">
            <b-card header="Rubric" v-if="canUseRubrics && visibleCats.rubric">
                <!-- TODO: Proper fix instead of :key hack -->
                <rubric-editor :key="assignment.id"
                               :hidden="selectedCat !== 'rubric'"
                               editable
                               :assignment="assignment" />
            </b-card>
        </div>

        <div class="cat-wrapper" :class="{hidden: selectedCat !== 'auto-test'}">
            <!-- TODO: Proper fix instead of :key hack -->
            <auto-test :key="assignment.id"
                       v-if="visibleCats['auto-test']"
                       :assignment="assignment"
                       :hidden="selectedCat !== 'auto-test'"
                       editable />
        </div>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import 'vue-awesome/icons/reply';

import {
    AssignmentState,
    AssignmentGeneralSettings,
    AssignmentGraderSettings,
    AssignmentSubmissionSettings,
    FileUploader,
    Linters,
    Loader,
    SubmitButton,
    RubricEditor,
    CGIgnoreFile,
    DescriptionPopover,
    LocalHeader,
    SubmissionUploader,
    PlagiarismRunner,
    AssignmentGroup,
    CategorySelector,
    AutoTest,
    PeerFeedbackSettings,
} from '@/components';

import { CoursePermission as CPerm } from '@/permissions';
import * as models from '@/models';

export default {
    name: 'manage-assignment',

    data() {
        return {
            UserConfig,
            loadingInner: true,
            selectedCat: '',
            visibleCats: {},
        };
    },

    computed: {
        ...mapGetters('assignments', ['getAssignment']),

        formattedDeadline() {
            return (this.assignment && this.assignment.getFormattedDeadline()) || '';
        },

        courseId() {
            return Number(this.$route.params.courseId);
        },

        assignment() {
            return this.getAssignment(this.assignmentId).extract();
        },

        assignmentId() {
            return Number(this.$route.params.assignmentId);
        },

        ltiProvider() {
            return this.$utils.getPropMaybe(this.assignment, 'ltiProvider');
        },

        permissions() {
            return new models.AssignmentCapabilities(this.assignment);
        },

        canEditState() {
            return this.assignment.hasPermission(CPerm.canEditAssignmentInfo);
        },

        canEditInfo() {
            return this.permissions.canEditSomeGeneralSettings;
        },

        canEditIgnoreFile() {
            return this.assignment.hasPermission(CPerm.canEditCgignore);
        },

        canEditGroups() {
            return UserConfig.features.groups &&
                this.assignment.hasPermission(CPerm.canEditGroupAssignment);
        },

        canEditPeerFeedbackSettings() {
            return UserConfig.features.peer_feedback &&
                this.assignment.hasPermission(CPerm.canEditPeerFeedbackSettings);
        },

        canSubmitWork() {
            return this.assignment.hasPermission(CPerm.canSubmitOthersWork);
        },

        canSubmitBbZip() {
            return UserConfig.features.blackboard_zip_upload &&
                this.assignment.hasPermission(CPerm.canUploadBbZip);
        },

        canAssignGraders() {
            return this.assignment.hasPermission(CPerm.canAssignGraders);
        },

        canUpdateCourseNotifications() {
            return this.assignment.hasPermission(CPerm.canUpdateCourseNotifications);
        },

        canUseLinters() {
            return UserConfig.features.linters && this.assignment.hasPermission(CPerm.canUseLinter);
        },

        canManagePlagiarism() {
            return this.assignment.hasPermission(CPerm.canManagePlagiarism);
        },

        canViewPlagiarism() {
            return this.assignment.hasPermission(CPerm.canViewPlagiarism);
        },

        canUsePlagiarism() {
            return this.canManagePlagiarism || this.canViewPlagiarism;
        },

        canUseRubrics() {
            return UserConfig.features.rubrics &&
                this.assignment.hasPermission(CPerm.manageRubrics);
        },

        canUseAutoTest() {
            return UserConfig.features.auto_test && (
                this.assignment.hasPermission(CPerm.canRunAutotest) ||
                this.assignment.hasPermission(CPerm.canEditAutotest) ||
                this.assignment.hasPermission(CPerm.canDeleteAutotestRun)
            );
        },

        canListCourseUsers() {
            return this.assignment.hasPermission(CPerm.canListCourseUsers);
        },

        canDeleteAssignments() {
            return this.assignment.hasPermission(CPerm.canDeleteAssignments);
        },

        categories() {
            return [
                {
                    id: 'general',
                    name: 'General',
                    enabled:
                        this.canEditInfo ||
                        this.canEditIgnoreFile ||
                        this.canEditGroups ||
                        this.canSubmitWork ||
                        this.canSubmitBbZip,
                },
                {
                    id: 'graders',
                    name: 'Graders',
                    enabled:
                        this.canAssignGraders ||
                        this.permissions.canUpdateGraderStatus ||
                        this.canUpdateCourseNotifications,
                },
                {
                    id: 'linters',
                    name: 'Linters',
                    enabled: this.canUseLinters,
                },
                {
                    id: 'plagiarism',
                    name: 'Plagiarism',
                    enabled: this.canUsePlagiarism,
                },
                {
                    id: 'rubric',
                    name: 'Rubric',
                    enabled: this.canUseRubrics,
                },
                {
                    id: 'auto-test',
                    name: 'AutoTest',
                    enabled: this.canUseAutoTest,
                },
            ];
        },

        manageGroupLink() {
            return {
                name: 'manage_course',
                params: {
                    course_id: this.assignment.course.id,
                },
                hash: '#groups',
            };
        },

        loading() {
            return this.assignment == null;
        },
    },

    watch: {
        assignmentId: {
            immediate: true,
            handler() {
                this.loadData();
            },
        },

        assignment(newVal) {
            if (newVal == null) {
                this.loadData();
            }
        },

        selectedCat: {
            immediate: true,
            handler(newVal) {
                this.$set(this.visibleCats, newVal, true);
            },
        },
    },

    methods: {
        ...mapActions('courses', ['loadSingleCourse']),
        ...mapActions('submissions', ['forceLoadSubmissions']),

        async loadData() {
            this.loadingInner = true;

            await this.loadSingleCourse({ courseId: this.courseId });
            this.visibleCats = {
                [this.selectedCat]: true,
            };
            await this.$afterRerender();
            this.loadingInner = false;
        },

        deleteAssignment() {
            return this.$http.delete(`/api/v1/assignments/${this.assignment.id}`);
        },

        afterDeleteAssignment() {
            this.loadSingleCourse({ courseId: this.courseId, force: true });
            this.$router.push({ name: 'home' });
        },
    },

    components: {
        AssignmentState,
        AssignmentGeneralSettings,
        AssignmentGraderSettings,
        AssignmentSubmissionSettings,
        FileUploader,
        Linters,
        Loader,
        SubmitButton,
        RubricEditor,
        CGIgnoreFile,
        DescriptionPopover,
        LocalHeader,
        SubmissionUploader,
        PlagiarismRunner,
        AssignmentGroup,
        CategorySelector,
        AutoTest,
        PeerFeedbackSettings,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.manage-assignment.loading {
    display: flex;
    flex-direction: column;
}

.cat-wrapper {
    transition: opacity 0.25s ease-out;

    &.hidden {
        padding: 0;
        transition: none;
        opacity: 0;
        max-height: 0;
        overflow-y: hidden;
    }
}
</style>

<style lang="less">
.manage-assignment .card {
    margin-bottom: 1rem;
}
</style>
