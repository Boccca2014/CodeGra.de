<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div v-if="error != null" class="mt-3">
    <cg-error :error="error" />
</div>
<loader center class="submission-page-loader" v-else-if="loadingPage"/>
<div class="page submission outer-container" id="submission-page" v-else>
    <local-header :back-route="submissionsRoute"
                  back-popover="Go back to submissions list"
                  always-show-extra-slot
                  :force-extra-drawer="!$root.$isLargeWindow">
        <submission-nav-bar
            :current-submission="submission"
            :latest-submissions="latestSubmissions"
            :not-latest="!currentSubmissionIsLatest"
            :group-of-user="groupOfCurrentUser"
            :show-user-buttons="canGrade"
            :assignment="assignment"/>

        <b-button-group class="submission-header-buttons">
            <preference-manager in-popover
                                container="#submission-page"
                                :file-id="prefFileId"
                                :show-context-amount="showPrefContextAmount"
                                :show-language="selectedCat === 'code'"
                                @whitespace="whitespaceChanged"
                                @language="languageChanged"
                                @inline-feedback="inlineFeedbackChanged" />

            <general-feedback-area v-if="editable"
                                   in-popover
                                   container="#submission-page"
                                   :assignment="assignment"
                                   :submission="submission"
                                   editable/>

            <b-button v-if="canSeeGradeHistory"
                      id="codeviewer-grade-history"
                      v-b-popover.hover.top="'Show grade history'">
                <icon name="history"/>

                <b-popover target="codeviewer-grade-history"
                           title="Grade history"
                           triggers="click blur"
                           container="submission-page"
                           placement="bottom"
                           custom-class="p-0"
                           @show="$root.$emit('bv::hide::popover')">
                    <grade-history style="width: 30rem;"
                                   :submission-id="submission && submission.id"
                                   :isLTI="assignment && assignment.course.isLTI"/>
                </b-popover>
            </b-button>

            <b-button v-if="!submission.user.is_test_student && canEmailStudents"
                      id="codeviewer-email-student"
                      v-b-popover.top.hover="`Email the author${submission.user.isGroup ? 's' : ''} of this submission`"
                      v-b-modal.codeviewer-email-student-modal>
                <icon name="envelope"/>
            </b-button>

            <b-modal v-if="canEmailStudents"
                     id="codeviewer-email-student-modal"
                     ref="contactStudentModal"
                     size="xl"
                     hide-footer
                     no-close-on-backdrop
                     no-close-on-esc
                     hide-header-close
                     title="Email authors"
                     @show="() => $root.$emit('bv::hide::popover')"
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
                            :initial-users="submission.user.getContainedUsers()"
                            :course="assignment.course"
                            :default-subject="defaultEmailSubject"
                            no-everybody-email-option
                            @hide="() => $refs.contactStudentModal.hide()"
                            @emailed="() => $refs.contactStudentModal.hide()"
                            :can-use-snippets="canUseSnippets"
                            class="p-3"/>
                    </template>
                </cg-catch-error>
            </b-modal>

            <b-button v-b-popover.hover.top="'Download assignment or feedback'"
                      id="codeviewer-download-toggle">
                <icon name="download"/>

                <b-popover target="codeviewer-download-toggle"
                           triggers="click blur"
                           placement="bottom"
                           container="submission-page"
                           custom-class="p-0"
                           @show="$root.$emit('bv::hide::popover')">
                    <table style="width: 10rem;"
                           class="table table-hover mb-0 text-left">
                        <tbody>
                            <tr @click="downloadType('zip')">
                                <td><b>Archive</b></td>
                            </tr>
                            <tr v-if="canSeeGrade || canSeeUserFeedback || canSeeLinterFeedback"
                                @click="downloadType('feedback')">
                                <td><b>Feedback</b></td>
                            </tr>
                        </tbody>
                    </table>
                </b-popover>
            </b-button>

            <submit-button v-if="canDeleteSubmission"
                           variant="danger"
                           confirm="By deleting all information about this submission, including files, will be lost forever! So are you really sure?"
                           confirm-in-modal
                           v-b-popover.hover.top="'Delete submission'"
                           :submit="deleteSubmission"
                           @after-success="afterDeleteSubmission">
                <icon name="times"/>
            </submit-button>
        </b-button-group>

        <template slot="extra" v-if="!loadingInner">
            <category-selector slot="extra"
                               :default="defaultCat"
                               v-model="selectedCat"
                               :categories="categories"/>
        </template>
    </local-header>

    <loader page-loader
            class="submission-page-inner-loader"
            v-if="loadingInner"/>
    <template v-else>
        <div class="cat-wrapper"
             :class="{ hidden: selectedCat !== 'code' }">
            <rs-panes v-if="!hiddenCats.has('code')"
                      allow-resize
                      :split-to="$root.$isLargeWindow ? 'columns' : 'rows'"
                      @update:size="splitRatio = $event"
                      :on-drag-started="() => { resizingFileViewer = true; }"
                      :on-drag-finished="() => { resizingFileViewer = false; }"
                      :size="splitRatio"
                      :step="25"
                      units="percents"
                      class="code-wrapper"
                      id="submission-page-inner"
                      :min-size="30"
                      :max-size="85">
                <file-viewer
                    slot="firstPane"
                    :assignment="assignment"
                    :submission="submission"
                    :file="currentFile"
                    :revision="revision"
                    :editable="canSeeUserFeedback && canGiveLineFeedback"
                    :can-use-snippets="canUseSnippets"
                    :show-whitespace="showWhitespace"
                    :show-inline-feedback="selectedCat === 'code' && showInlineFeedback && revision === 'student'"
                    :language="selectedLanguage"
                    @language="languageChanged"
                    :resizing="resizingFileViewer"/>

                <div v-if="course.isStudent"
                     slot="secondPane"
                     class="h-100 w-100 overflow-hidden">
                    <div class="file-tree-container border rounded overflow-auto">
                        <file-tree
                            :assignment="assignment"
                            :submission="submission"
                            :revision="revision"/>
                    </div>
                </div>

                <b-tabs v-else
                        class="submission-sidebar"
                        slot="secondPane"
                        nav-class="border-bottom-0"
                        no-fade
                        v-model="currentSidebarTab">
                    <b-tab title="Files"
                           class="border rounded-bottom rounded-right">
                        <file-tree
                            :assignment="assignment"
                            :submission="submission"
                            :revision="revision" />
                    </b-tab>

                    <b-tab title="Feedback"
                           class="border rounded overflow-hidden">
                        <course-feedback
                            v-if="!hiddenSidebarTabs.has('feedback')"
                            :course="course"
                            :user="submission.user"
                            :exclude-submission="submission" />
                    </b-tab>
                </b-tabs>
            </rs-panes>
        </div>

        <div class="cat-wrapper"
             :class="{ hidden: selectedCat !== 'feedback-overview' }">
            <feedback-overview v-if="!hiddenCats.has('feedback-overview')"
                               :assignment="assignment"
                               :submission="submission"
                               :context-lines="contextAmount"
                               :show-whitespace="showWhitespace"
                               :show-inline-feedback="selectedCat === 'feedback-overview'" />
        </div>

        <div class="cat-wrapper"
             :class="{ hidden: selectedCat !== 'teacher-diff' }">
            <diff-overview v-if="!hiddenCats.has('teacher-diff')"
                           :assignment="assignment"
                           :submission="submission"
                           :show-whitespace="showWhitespace"/>
        </div>

        <div class="cat-wrapper"
             :class="{ hidden: selectedCat !== 'auto-test' }"
             v-if="autoTestId">
            <div class="cat-scroller border rounded">
                <auto-test :assignment="assignment"
                           :submission-id="submissionId" />
            </div>
        </div>

        <div class="cat-wrapper"
             :class="{ hidden: selectedCat !== 'peer-feedback'}"
             v-if="showPeerFeedback">
            <peer-feedback-by-user
                v-if="!hiddenCats.has('peer-feedback')"
                :assignment="assignment"
                :context-lines="contextAmount"
                :show-whitespace="showWhitespace"
                :show-inline-feedback="selectedCat === 'peer-feedback'"
                :user="submission.user"/>
        </div>
    </template>

    <grade-viewer :assignment="assignment"
                  :submission="submission"
                  :not-latest="!currentSubmissionIsLatest"
                  :group-of-user="groupOfCurrentUser"
                  :editable="canSeeGrade && editable"
                  :rubric-start-open="rubricStartOpen"
                  v-if="!loadingInner"
                  class="mb-3"/>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/download';
import 'vue-awesome/icons/edit';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/exclamation-triangle';
import 'vue-awesome/icons/history';
import 'vue-awesome/icons/archive';
import 'vue-awesome/icons/envelope';
import ResSplitPane from 'vue-resize-split-pane';

import { mapGetters, mapActions } from 'vuex';

import { nameOfUser } from '@/utils';

import * as assignmentState from '@/store/assignment-states';

import { setPageTitle } from '@/pages/title';

import {
    AutoTest,
    FeedbackOverview,
    DiffOverview,
    FileTree,
    CategorySelector,
    GradeViewer,
    GradeHistory,
    GeneralFeedbackArea,
    CourseFeedback,
    Loader,
    LocalHeader,
    PreferenceManager,
    SubmissionNavBar,
    SubmitButton,
    Toggle,
    User,
    PeerFeedbackByUser,
} from '@/components';

import FileViewer from '@/components/FileViewer';
import StudentContact from '@/components/StudentContact';

export default {
    name: 'submission-page',

    data() {
        return {
            assignmentState,

            defaultCat: '',
            selectedCat: '',
            hiddenCats: new Set(),

            splitRatio: 75,
            currentSidebarTab: 0,
            hiddenSidebarTabs: new Set(['feedback']),

            showWhitespace: true,
            selectedLanguage: 'Default',
            showInlineFeedback: true,
            currentFile: null,
            resizingFileViewer: false,

            error: null,
        };
    },

    computed: {
        ...mapGetters('pref', ['contextAmount']),
        ...mapGetters('user', {
            userId: 'id',
            userPerms: 'permissions',
        }),
        ...mapGetters('submissions', {
            storeGetLatestSubmissions: 'getLatestSubmissions',
            storeGetSingleSubmission: 'getSingleSubmission',
            storeGetGroupSubmissionOfUser: 'getGroupSubmissionOfUser',
        }),
        ...mapGetters('assignments', ['getAssignment']),
        ...mapGetters('autotest', {
            allAutoTests: 'tests',
        }),
        ...mapGetters('fileTrees', ['getFileTree']),
        ...mapGetters('feedback', ['getFeedback']),

        course() {
            return this.$utils.getProps(this.assignment, null, 'course');
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

        submission() {
            const id = Number(this.$route.params.submissionId);
            return this.storeGetSingleSubmission(this.assignmentId, id);
        },

        submissionId() {
            return this.$utils.getProps(this.submission, null, 'id');
        },

        fileId() {
            return this.$route.params.fileId;
        },

        editable() {
            return !!(
                this.canGrade &&
                this.currentSubmissionIsLatest &&
                this.groupOfCurrentUser == null
            );
        },

        coursePerms() {
            return this.$utils.getProps(this.assignment, {}, 'course', 'permissions');
        },

        canGrade() {
            return this.coursePerms.can_grade_work;
        },

        canSeeGrade() {
            return this.assignment && this.assignment.canSeeGrade();
        },

        canSeeUserFeedback() {
            return this.assignment && this.assignment.canSeeUserFeedback();
        },

        canSeeLinterFeedback() {
            return this.assignment && this.assignment.canSeeLinterFeedback();
        },

        canDeleteSubmission() {
            return this.coursePerms.can_delete_submission;
        },

        canSeeGradeHistory() {
            return this.coursePerms.can_see_grade_history;
        },

        canEmailStudents() {
            return (UserConfig.features.email_students &&
                    this.$utils.getProps(this.coursePerms, false, 'can_email_students'));
        },

        canViewAutoTestBeforeDone() {
            return this.coursePerms.can_view_autotest_before_done;
        },

        canGiveLineFeedback() {
            return this.editable && this.revision === 'student';
        },

        canUseSnippets() {
            return !!this.userPerms.can_use_snippets;
        },

        prefFileId() {
            switch (this.selectedCat) {
            case 'code':
                return this.fileId;
            case 'feedback-overview':
                return `${this.submissionId}-feedback-overview`;
            case 'auto-test':
                return `${this.submissionId}-auto-test`;
            case 'teacher-diff':
                return `${this.submissionId}-teacher-diff`;
            default:
                return '';
            }
        },

        revision() {
            return this.$route.query.revision || 'student';
        },

        latestSubmissions() {
            return this.storeGetLatestSubmissions(this.assignmentId);
        },

        currentSubmissionIsLatest() {
            return !!this.latestSubmissions.find(sub => sub.id === this.submissionId);
        },

        groupOfCurrentUser() {
            const curSub = this.submission;
            if (curSub == null) {
                return null;
            }
            const groupSub = this.storeGetGroupSubmissionOfUser(this.assignmentId, curSub.userId);
            return this.$utils.getProps(groupSub, null, 'user');
        },

        fileTree() {
            return this.getFileTree(this.assignmentId, this.submissionId);
        },

        feedback() {
            return this.getFeedback(this.assignmentId, this.submissionId);
        },

        autoTestId() {
            return this.assignment && this.assignment.auto_test_id;
        },

        autoTest() {
            return this.allAutoTests[this.autoTestId];
        },

        autoTestRun() {
            return this.$utils.getProps(this.autoTest, null, 'runs', 0);
        },

        autoTestResult() {
            return this.autoTestRun && this.autoTestRun.findResultBySubId(this.submissionId);
        },

        loadingPage() {
            return !this.assignment || this.submission == null;
        },

        loadingInner() {
            const {
                canSeeUserFeedback,
                canSeeLinterFeedback,
                feedback,
                fileTree,
                currentFile,
                canViewAutoTest,
                autoTest,
            } = this;

            return (
                ((canSeeUserFeedback || canSeeLinterFeedback) && !feedback) ||
                !fileTree ||
                !currentFile ||
                (canViewAutoTest && !autoTest)
            );
        },

        canViewAutoTest() {
            const { autoTestId, assignmentDone, canViewAutoTestBeforeDone } = this;

            return autoTestId && (assignmentDone || canViewAutoTestBeforeDone);
        },

        showTeacherDiff() {
            return this.fileTree && this.fileTree.hasRevision(this.fileTree.student);
        },

        categories() {
            return [
                {
                    id: 'code',
                    name: 'Code',
                    enabled: true,
                },
                {
                    id: 'feedback-overview',
                    name: 'Feedback Overview',
                    badge: this.numFeedbackItems === 0 ? null : {
                        label: this.numFeedbackItems,
                        variant: 'primary',
                    },
                    enabled: true,
                },
                {
                    id: 'auto-test',
                    name: 'AutoTest',
                    badge: !this.showContinuousBadge ? null : {
                        label: 'CF',
                        variant: 'warning',
                    },
                    enabled: this.autoTestId != null,
                },
                {
                    id: 'teacher-diff',
                    name: 'Teacher Diff',
                    enabled: this.showTeacherDiff,
                },
                {
                    id: 'peer-feedback',
                    name: 'Peer Feedback',
                    enabled: this.showPeerFeedback,
                },
            ];
        },

        sidebarTabs() {
            const tabs = ['files'];
            if (this.canGiveLineFeedback) {
                tabs.push('feedback');
            }
            return tabs;
        },

        hasFeedback() {
            const fb = this.feedback;

            return !!(fb && (fb.general || Object.keys(fb.user).length));
        },

        numFeedbackItems() {
            if (!this.feedback || !this.submission) {
                return 0;
            }
            return this.feedback.countEntries();
        },

        showContinuousBadge() {
            const test = this.autoTest;
            const result = this.autoTestResult;

            // Check that result.isFinal is exactly false, because it may be
            // `undefined` when we haven't received the extended result yet,
            // which would cause the CF badge to flicker on page load.
            return (
                test &&
                test.results_always_visible &&
                ((result && result.isFinal === false) || !this.canSeeGrade)
            );
        },

        assignmentDone() {
            if (this.assignment == null) {
                return false;
            } else {
                return this.assignment.state === assignmentState.DONE;
            }
        },

        rubricStartOpen() {
            const done = this.assignmentDone;
            const editable = this.editable;
            const canSeeGrade = this.canSeeGrade;

            return (editable || done) && canSeeGrade;
        },

        isPeerFeedback() {
            return this.$utils.parseBool(this.$route.query.peerFeedback, false);
        },

        submissionsRoute() {
            return {
                name: 'assignment_submissions',
                params: {
                    courseId: this.courseId,
                    assignmentId: this.assignmentId,
                },
                query: {
                    q: this.$route.query.search || undefined,
                    mine: this.$route.query.mine || false,
                    latest: this.$route.query.latest || false,
                    sortBy: this.$route.query.sortBy,
                    sortAsc: this.$route.query.sortAsc,
                    page: this.$route.query.page || undefined,
                },
                hash: this.isPeerFeedback ? '#peer-feedback' : undefined,
            };
        },

        pageTitle() {
            const assig = this.assignment;
            const sub = this.submission;
            const grade = sub && sub.grade;

            if (!assig) {
                return '';
            }

            let title = this.assignment.name;
            if (sub) {
                title += ` by ${nameOfUser(sub.user)}`;

                if (grade != null) {
                    title += ` (${grade})`;
                }
            }

            return title;
        },

        defaultEmailSubject() {
            return `[CodeGrade - ${this.assignment.course.name}/${this.assignment.name}] …`;
        },

        showPeerFeedback() {
            const pfSettings = this.$utils.getProps(
                this.assignment,
                null,
                'peer_feedback_settings',
            );
            if (pfSettings == null) {
                return false;
            }
            if (this.canGrade) {
                return true;
            }
            if (this.submission != null && this.userId === this.submission.userId) {
                return true;
            }
            return false;
        },

        showPrefContextAmount() {
            const cat = this.selectedCat;
            return cat === 'feedback-overview' || cat === 'teacher-diff' || cat === 'peer-feedback';
        },
    },

    watch: {
        assignment() {
            if (this.assignment == null) {
                this.loadData();
            }
        },

        assignmentId: {
            immediate: true,
            handler() {
                this.loadData();
            },
        },

        autoTestId: {
            immediate: true,
            handler() {
                this.loadAutoTest();
            },
        },

        submissionId: {
            immediate: true,
            handler() {
                this.loadCurrentSubmissionData();
            },
        },

        // We need these watchers (feedback and filetree) as these properties
        // become `null`/`undefined` when the submissions are reloaded (this can
        // be done using the sidebar). So in that case we need to load the data
        // again.
        feedback() {
            if (!this.feedback) {
                this.loadCurrentSubmissionData();
            }
        },

        fileTree() {
            if (!this.fileTree) {
                this.loadCurrentSubmissionData();
            }
        },

        fileId: {
            immediate: true,
            handler() {
                this.openFile();
            },
        },

        revision: {
            immediate: true,
            handler() {
                this.openFile();
            },
        },

        pageTitle: {
            immediate: true,
            handler() {
                setPageTitle(this.pageTitle);
            },
        },

        selectedCat: {
            immediate: true,
            handler() {
                this.hiddenCats.delete(this.selectedCat);
            },
        },

        currentSidebarTab: {
            immediate: true,
            handler(newVal) {
                this.openSidebarTab(newVal);
            },
        },
    },

    methods: {
        ...mapActions('submissions', {
            storeLoadSubmissions: 'loadSubmissions',
            storeLoadSingleSubmission: 'loadSingleSubmission',
            storeDeleteSubmission: 'deleteSubmission',
        }),
        ...mapActions('assignments', {
            storeLoadSingleAssignment: 'loadSingleAssignment',
        }),
        ...mapActions('feedback', {
            storeLoadFeedback: 'loadFeedback',
        }),
        ...mapActions('fileTrees', {
            storeLoadFileTree: 'loadFileTree',
        }),

        ...mapActions('autotest', {
            storeLoadAutoTest: 'loadAutoTest',
            storeLoadAutoTestResult: 'loadAutoTestResult',
        }),

        ...mapActions('peer_feedback', {
            storeLoadPeerFeedbackConnectionsForUser: 'loadConnectionsForUser',
        }),

        loadData() {
            Promise.all([
                this.storeLoadSingleAssignment({
                    assignmentId: this.assignmentId,
                    courseId: this.courseId,
                }),
                this.loadCurrentSubmission(),
                this.storeLoadSubmissions({
                    assignmentId: this.assignmentId,
                    courseId: this.courseId,
                }),
            ]).then(this.loadCurrentSubmissionData, error => {
                this.error = error;
            });
        },

        maybeLoadPeerFeedbackConnections() {
            if (this.userId === this.$utils.getProps(this.submission, null, 'userId')) {
                return Promise.resolve();
            } else if (this.$utils.getProps(this.assignment, null, 'peer_feedback_settings') == null) {
                return Promise.resolve();
            }
            return this.storeLoadPeerFeedbackConnectionsForUser({
                userId: this.userId,
                assignmentId: this.assignmentId,
            });
        },

        loadCurrentSubmission() {
            if (this.assignmentId == null) {
                return Promise.resolve();
            }

            // We need to reset the current file to `null` as changing the
            // current submission reloads the current file, which means we
            // download it again while it is not needed.
            this.currentFile = null;

            // Reset the error so we show a loader and not the old error.
            this.error = null;

            return this.storeLoadSingleSubmission({
                assignmentId: this.assignmentId,
                submissionId: this.$route.params.submissionId,
                courseId: this.courseId,
            }).catch(err => {
                this.error = err;
            });
        },

        loadCurrentSubmissionData() {
            if (this.submissionId == null || this.error != null) {
                return;
            }

            if (!this.$route.query.revision) {
                this.$router.replace(
                    this.$utils.deepExtend({}, this.$route, {
                        query: { revision: 'student' },
                    }),
                );
            }

            this.currentFile = null;
            this.showWhitespace = true;

            this.hiddenCats = new Set(
                this.categories.filter(c => c.id !== this.selectedCat).map(c => c.id),
            );

            // Reset the hidden tabs so the feedback of other submissions will
            // not be loaded until the feedback tab is clicked.
            this.splitRatio = 75;
            this.currentSidebarTab = 0;
            this.hiddenSidebarTabs = new Set(this.sidebarTabs.slice(1));

            const promises = [
                this.storeLoadFileTree({
                    assignmentId: this.assignmentId,
                    submissionId: this.submissionId,
                }),
                this.storeLoadFeedback({
                    assignmentId: this.assignmentId,
                    submissionId: this.submissionId,
                }),
                // We need to know if we are looking at a peer feedback subject
                // of ours, because in that case we can probably give this
                // student feedback.
                //
                // TODO: Don't do this load if it is not needed, e.g. if the
                // current user is the teacher.
                this.maybeLoadPeerFeedbackConnections(),
            ];

            // Load the AutoTest result of this submission. This must happen here because the
            // AutoTest file tree must be loaded for `loadingInner` to become `false` if the
            // file id in the URL refers to a file in the AutoTest file tree, because
            // `loadingInner` waits until `currentFile` is set.
            if (this.autoTestId != null && this.autoTestResult == null) {
                promises.push(
                    this.storeLoadAutoTestResult({
                        autoTestId: this.autoTestId,
                        submissionId: this.submissionId,
                    }).catch(this.$utils.makeHttpErrorHandler({
                        // The user may not have permission to see the results yet.
                        403: () => {},
                        // The AT may not have been run yet.
                        404: () => {},
                        // TODO: storeLoadAutoTestResults mixes the HTTP errors
                        // thrown by axios with standard errors when there are
                        // no AT results...
                        noResponse: () => {},
                    })),
                );
            }

            Promise.all(promises).then(
                () => {
                    this.setDefaultCat();
                    this.openFirstFile();
                },
                err => {
                    this.error = err;
                },
            );
        },

        loadAutoTest() {
            if (this.autoTestId != null) {
                return this.storeLoadAutoTest({
                    autoTestId: this.autoTestId,
                }).catch(this.$utils.makeHttpErrorHandler({
                    // The user may not have permission to see the results yet.
                    403: () => {},
                }));
            } else {
                return Promise.resolve();
            }
        },

        openFirstFile() {
            if (!this.fileTree) {
                return;
            }

            let file;
            if (this.fileId) {
                file = this.fileTree.search(this.revision, this.fileId);

                if (!file && this.currentFile && this.currentFile.revision) {
                    file = this.fileTree.search(this.revision, this.currentFile.revision.id);
                }
            }

            if (!file) {
                file = this.fileTree.getFirstFile(this.revision);
            }

            if (file) {
                const fileId = file.id || file.ids[0] || file.ids[1];
                if (fileId !== this.fileId) {
                    this.$router.replace(
                        this.$utils.deepExtend({}, this.$route, {
                            name: 'submission_file',
                            params: { fileId },
                        }),
                    );
                }
            }

            this.currentFile = file;
        },

        openFile() {
            this.currentFile = this.fileTree && this.fileTree.search(this.revision, this.fileId);
        },

        deleteSubmission() {
            const sub = this.submission;
            return this.$http.delete(`/api/v1/submissions/${this.submissionId}`).then(() => sub);
        },

        afterDeleteSubmission(sub) {
            this.storeDeleteSubmission({
                assignmentId: this.assignmentId,
                submission: sub,
            });
            this.$router.replace({
                name: 'assignment_submissions',
                params: {
                    courseId: this.courseId,
                    assignmentId: this.assignmentId,
                },
            });
        },

        downloadType(type) {
            this.$http
                .get(this.$utils.buildUrl(
                    ['api', 'v1', 'submissions', this.submissionId],
                    { query: { type } },
                ))
                .then(({ data }) => {
                    const url = this.$utils.buildUrl(
                        ['api', 'v1', 'files', data.name, data.output_name],
                        { query: { not_as_attachment: '' } },
                    );
                    window.open(url);
                });
        },

        languageChanged(val) {
            this.selectedLanguage = val;
        },

        whitespaceChanged(val) {
            this.showWhitespace = val;
        },

        inlineFeedbackChanged(val) {
            this.showInlineFeedback = val;
        },

        openSidebarTab(idx) {
            const tab = this.sidebarTabs[idx];
            const wasHidden = this.hiddenSidebarTabs.delete(tab);

            // Only resize the first time, and only if the sidebar is less than
            // half of the width of the page.
            if (wasHidden && tab === 'feedback' && this.splitRatio > 50) {
                this.splitRatio = 50;
            }
        },

        setDefaultCat() {
            this.defaultCat = this.getDefaultCat(
                this.editable,
                this.assignmentDone,
                this.hasFeedback,
                this.autoTestRun,
            );
        },

        getDefaultCat(feedbackEditable, assignmentDone, hasFeedback, autoTestRun) {
            if (assignmentDone) {
                if (hasFeedback) {
                    return 'feedback-overview';
                } else if (autoTestRun) {
                    return 'auto-test';
                } else {
                    return 'feedback-overview';
                }
            } else if (!feedbackEditable && autoTestRun) {
                return 'auto-test';
            } else {
                return 'code';
            }
        },
    },

    components: {
        AutoTest,
        CategorySelector,
        DiffOverview,
        FeedbackOverview,
        FileTree,
        FileViewer,
        GradeViewer,
        GradeHistory,
        GeneralFeedbackArea,
        CourseFeedback,
        Loader,
        LocalHeader,
        PreferenceManager,
        SubmissionNavBar,
        SubmitButton,
        Toggle,
        Icon,
        User,
        StudentContact,
        'rs-panes': ResSplitPane,
        PeerFeedbackByUser,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.outer-container {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    height: 100vh;
    max-height: 100%;
    margin-bottom: 0 !important;
    overflow: hidden;
}

.submission-nav-bar {
    flex: 1 1 auto;
}

.cat-wrapper {
    position: relative;
    flex: 1 1 100%;
    min-height: 0;
    margin: 0 -15px 1rem;
    padding: 0 1rem;
    transition: opacity .25s ease-out, visibility .25s ease-out;
    overflow: hidden;
    visibility: visible;

    &.hidden {
        visibility: hidden;
        padding: 0;
        margin: 0;
        opacity: 0;
        max-height: 0;
        overflow-y: hidden;
    }
}

.cat-scroller {
    max-height: 100%;
    overflow: auto;
}

.code-wrapper {
    display: flex;
    flex-wrap: nowrap;
    min-height: 0;
    height: 100%;

    @media @media-no-large {
        flex-direction: column;
    }
}

.file-viewer {
    position: relative;
    min-height: 0;
    max-height: 100%;

    @media @media-no-large {
        width: 100%;
        height: 100%;
    }
}

.file-tree-container {
    max-height: 100%;
}

.file-tree,
.course-feedback {
    max-height: 100%;
}

.file-tree {
    overflow: auto;
}

.grade-viewer {
    flex: 0 0 auto;
}
</style>

<style lang="less">
@import '~mixins.less';

#submission-page {
    .popover {
        max-width: 45em;
    }

    .code-wrapper.pane-rs {
        position: relative;

        &.rows {
            padding-left: 15px;
            padding-right: 15px;
        }
    }

    .code-wrapper .Resizer {
        z-index: 0;
    }

    .code-wrapper > .Resizer {
        background-color: transparent !important;
        border: none !important;
        margin: 0 !important;
        position: relative;

        &:before,
        &:after {
            content: '';
            display: block;
            width: 3px;
            height: 3px;
            border-radius: 50%;
            background-color: gray;
            position: absolute;
            top: 50%;
            left: 50%;
            z-index: 10;
        }

        &.columnsres {
            width: 1rem !important;

            &:before {
                transform: translate(-2px, -4px);
            }

            &:after {
                transform: translate(-2px, +1px);
            }
        }

        &.rowsres {
            width: 100% !important;
            height: 1rem !important;

            &:before {
                transform: translate(-4px, -2px);
            }

            &:after {
                transform: translate(+1px, -2px);
            }
        }
    }

    .category-selector .badge {
        font-size: 1em !important;
    }

    .submission-sidebar {
        width: 100%;
        max-height: 100%;
        display: flex;
        flex-direction: column;

        .nav-tabs {
            position: relative;
            z-index: 1;
        }

        .tab-content {
            display: flex;
            flex: 1 1 auto;
            min-height: 0;
        }

        .tab-pane {
            flex: 1 1 auto;
            min-height: 0;
            max-width: 100%;
        }

        @media @media-no-large {
            .nav-item .nav-link {
                padding: 0.25rem 0.5rem;
            }
        }
    }
}
</style>
