<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-alert class="error" variant="danger" show v-if="error">
    <div>{{ $utils.getErrorMessage(error) }}</div>
</b-alert>

<div v-else-if="loading">
    <loader page-loader :scale="2" />
</div>

<div v-else-if="!feedbackAvailable"
     class="feedback-overview p-3 border rounded font-italic text-muted">
    The feedback is not yet available.
</div>

<div v-else
     class="feedback-overview border rounded">
    <div class="scroller">
        <b-card header="General feedback"
                class="general-feedback inline-feedback-scroll-part"
                v-if="shouldRenderGeneral">
            <pre v-if="generalFeedback"
                 class="text-wrap-pre mb-0">{{ generalFeedback }}</pre>
            <span v-else class="text-muted font-italic">
                No general feedback given.
            </span>
        </b-card>

        <inner-feedback-overview :file-wrapper-props="{ is: 'div', class: 'inline-feedback-scroll-part' }"
                                 parts-wrapper-component="b-card-body"
                                 :on-file-visible="onFileVisible"
                                 :assignment="assignment"
                                 :context-lines="contextLines"
                                 :submission="submission"
                                 :feedback="feedback"
                                 :file-tree="fileTree"
                                 :should-render-thread="shouldRenderThread">
            <template #no-feedback>
                <b-card-header>Inline feedback</b-card-header>
                <b-card-body class="text-muted font-italic">
                    <slot name="no-inline-feedback">
                        This submission has no inline feedback.
                    </slot>
                </b-card-body>
            </template>

            <template #header="{ file }">
                <b-card-header>
                    <router-link slot="header"
                                 :to="file.link"
                                 :target="openFilesInNewTab ? '_blank' : undefined"
                                 :title="openFilesInNewTab ? 'Open file in a new tab' : 'Go to file'">
                        {{ file.name }}
                        <fa-icon v-if="openFilesInNewTab"
                                 name="share-square-o"
                                 class="ml-1"/>
                    </router-link>
                </b-card-header>
            </template>

            <template #disabled-file="{ file, fileType, userFeedback }">
                Overview mode is not available for {{ file.disabled.name }}. Click
                <router-link class="inline-link" :to="file.link">here</router-link>
                to see the entire file.

                <feedback-area v-if="fileType.singleLine && showInlineFeedback"
                               class="pt-2"
                               :can-use-snippets="false"
                               :line="0"
                               :feedback="userFeedback[0]"
                               :total-amount-lines="0"
                               :assignment="assignment"
                               :submission="submission"
                               :non-editable="nonEditable"
                               :should-fade-reply="shouldFadeReply"/>
            </template>

            <template #code="{ file, userFeedback, linterFeedback, chunk, part }">
                <hr v-if="chunk.idx !== 0">

                <inner-code-viewer class="border rounded p-0"
                                   :assignment="assignment"
                                   :submission="submission"
                                   :code-lines="chunk.content"
                                   :feedback="showInlineFeedback ? userFeedback : {}"
                                   :linter-feedback="linterFeedback"
                                   :file-id="file.id"
                                   :start-line="chunk.start"
                                   :end-line="chunk.end"
                                   :show-whitespace="showWhitespace"
                                   :non-editable="nonEditable"
                                   :should-render-thread="shouldRenderThread"
                                   :should-fade-reply="shouldFadeReply"/>
            </template>
        </inner-feedback-overview>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import { Assignment, Submission } from '@/models';

import Loader from './Loader';
import InnerCodeViewer from './InnerCodeViewer';
import FeedbackArea from './FeedbackArea';
import InnerFeedbackOverview from './InnerFeedbackOverview';

export default {
    name: 'feedback-overview',

    props: {
        assignment: {
            type: Assignment,
            required: true,
        },
        submission: {
            type: Submission,
            required: true,
        },
        showWhitespace: {
            type: Boolean,
            default: true,
        },
        showInlineFeedback: {
            type: Boolean,
            default: true,
        },
        nonEditable: {
            type: Boolean,
            default: false,
        },
        contextLines: {
            type: Number,
            default: 3,
        },
        // Boolean indicating whether the general feedback should be rendered
        // or not.
        shouldRenderGeneral: {
            type: Boolean,
            default: true,
        },
        // A function that determines whether a given feedback thread should be
        // rendered. The function is given a FeedbackLine model as its only
        // argument and should return a boolean indicating whether the thread
        // should be rendered or not.
        shouldRenderThread: {
            type: Function,
            default: () => true,
        },
        // A function that receives a thread and a reply as arguments, and
        // returns a boolean value indicating whether a reply within a thread
        // should be faded.
        shouldFadeReply: {
            type: Function,
            default: () => false,
        },
        openFilesInNewTab: {
            type: Boolean,
            default: false,
        },

        onFileVisible: {
            type: Function,
            default: () => false,
        },
    },

    data() {
        return {
            error: null,
        };
    },

    computed: {
        ...mapGetters('pref', ['fontSize']),

        loading() {
            const feedback = this.feedback;
            const fileTree = this.fileTree;

            return feedback == null || fileTree == null || feedback.user == null;
        },

        fileTree() {
            return this.submission && this.submission.fileTree;
        },

        feedback() {
            return this.$utils.getProps(this.submission, {}, 'feedback');
        },

        generalFeedback() {
            return this.feedback.general;
        },

        submissionId() {
            return this.submission.id;
        },

        canSeeFeedback() {
            return this.assignment.canSeeUserFeedback();
        },

        hasUserFeedback() {
            return !this.$utils.isEmpty(this.feedback.user);
        },

        hasFeedback() {
            return this.feedback.general || this.hasUserFeedback;
        },

        feedbackAvailable() {
            return this.canSeeFeedback || this.hasFeedback;
        },
    },

    watch: {
        submissionId: {
            immediate: true,
            handler() {
                this.loadData();
            },
        },
    },

    methods: {
        ...mapActions('feedback', {
            storeLoadSubmissionFeedback: 'loadFeedback',
        }),
        ...mapActions('fileTrees', {
            storeLoadSubmissionFileTree: 'loadFileTree',
        }),

        async loadData() {
            Promise.all([
                this.storeLoadSubmissionFeedback({
                    assignmentId: this.assignment.id,
                    submissionId: this.submission.id,
                }),
                this.storeLoadSubmissionFileTree({
                    assignmentId: this.assignment.id,
                    submissionId: this.submission.id,
                }),
            ]).catch(err => {
                this.error = this.$utils.getErrorMessage(err);
            });
        },
    },

    components: {
        Loader,
        FeedbackArea,
        InnerCodeViewer,
        InnerFeedbackOverview,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.feedback-overview {
    max-height: 100%;
    overflow: hidden;
    display: flex;
}

.scroller {
    width: 100%;
    flex: 1 1 auto;
    overflow: auto;
}

.inner-code-viewer {
    overflow: hidden;
}

.general-feedback pre {
    @{dark-mode} {
        color: @text-color-dark;
    }
}
</style>

<style lang="less">
@import '~mixins.less';

.feedback-overview > .scroller .inner-feedback-viewer,
.feedback-overview > .scroller .inline-feedback-scroll-part {
    border: 1px solid @border-color;
    border-left-width: 0px;
    border-right-width: 0px;

    @{dark-mode} {
        border-color: @color-primary-darkest;
    }

    &:first-child {
        border-top-width: 0px;
    }

    &:last-child {
        border-bottom-width: 0px;
    }

    &:not(:first-child) {
        &,
        & > .card-header {
            border-top-left-radius: 0;
            border-top-right-radius: 0;
        }
    }

    &:not(:last-child) {
        margin-bottom: -1px;
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
    }

    > .card-header {
        position: sticky;
        top: -1px;
        border-top-width: 1px;
        border-top-style: solid;
        border-top-color: inherit;
        border-radius: 0;
        margin-top: -1px;
        z-index: 100;
        background-color: rgb(247, 247, 247);

        @{dark-mode} {
            background-color: @color-primary-darker;
            border-top-color: @color-primary-darkest;
        }
    }
}
</style>
