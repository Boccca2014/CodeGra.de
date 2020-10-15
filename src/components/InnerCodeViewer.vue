<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-alert v-if="!confirmedLines && (computedEndLine - computedStartLine) > maxLines"
         show
         variant="warning"
         class="mb-0 rounded">
    This file has {{ innerCodeLines.length - (hasMissingNewline ? 0 : 1) }} lines. Rendering it may
    cause the page to freeze or other issues. Do you want to render this file?

    <b-button-toolbar justify class="mt-2">
        <b-button @click.prevent.stop="renderNextLines(innerCodeLines.length)"
                  variant="warning"
                  class="d-block">
            Render all lines
        </b-button>

        <b-button @click.prevent.stop="renderNextLines(maxLines)"
                  variant="primary"
                  class="d-block">
            Render first {{ maxLines }} lines
        </b-button>
    </b-button-toolbar>
</b-alert>

<div v-else class="inner-code-viewer">
    <ol :class="{
            'lint-whitespace': lintWhitespace,
            'show-whitespace': showWhitespace,
         }"
        :start="computedStartLine"
        :style="{
            paddingLeft: lineNumberWidth,
            listStyle: noLineNumbers ? 'none' : null,
            fontSize: `${fontSize}px`,
            cursor: canGiveFeedback ? cursorType : 'text',
        }"
        class="hljs lines"
        @mousedown="dragStart"
        @mouseup="dragStop">

        <li v-for="i in computedEndLine"
            v-if="i - 1 >= computedStartLine - 1 && (i < innerCodeLines.length || innerCodeLines[i - 1] !== '')"
            :key="i"
            class="line"
            :class="{
                'pb-1': hasFeedback(i - 1),
                'normal-cursor': hasFeedback(i - 1),
                'hover': canGiveFeedback && !hasFeedback(i - 1),
                'gutter-comments-outer': gutterComments[i - 1 + lineFeedbackOffset],
                [gutterCommentVariant(i - 1)]: true,
            }"
            :data-line="i">

            <code class="d-block px-2" v-html="innerCodeLines[i - 1]" />

            <span v-if="addingInlineFeedback[i - 1]"
                  class="add-feedback-loader-wrapper">
                <cg-loader :scale="1" v-if="addingInlineFeedback[i - 1] === true" />

                <span v-else>
                    <icon name="times" class="text-danger" :id="`add-feedback-line-error-${i}`"/>
                    <b-popover :target="`add-feedback-line-error-${i}`"
                               show>
                        <icon name="times"
                                class="hide-button"
                                @click.native="$delete(addingInlineFeedback, i - 1)"/>
                        Error adding inline feedback: {{ $utils.getErrorMessage(addingInlineFeedback[i - 1]) }}
                    </b-popover>
                </span>
            </span>

            <gutter-comment :comments="gutterComments[i - 1]"
                            :width="lineNumberWidth"
                            v-if="gutterComments[i - 1] != null"/>

            <feedback-area
                class="border-top border-bottom py-2 px-3 mt-1"
                :key="feedback[i - 1 + lineFeedbackOffset].id"
                :feedback="feedback[i - 1 + lineFeedbackOffset]"
                :total-amount-lines="computedEndLine"
                :can-use-snippets="canUseSnippets"
                :submission="submission"
                :non-editable="nonEditable"
                :should-fade-reply="shouldFadeReply"
                v-if="hasFeedback(i - 1) && shouldRenderThread(feedback[i - 1 + lineFeedbackOffset])"/>
        </li>
        <li class="empty-file px-2"
            v-if="innerCodeLines.length === 1 && innerCodeLines[0] === ''">
            {{ emptyFileMessage }}
        </li>
        <li class="missing-newline px-2"
            v-if="showMissingNewline">
            <icon name="level-up" class="missing-newline-icon"/> Missing newline at the end of file.
        </li>
    </ol>

    <div class="render-next-lines"
         v-if="confirmedLines && !atEndOfFile">
        <div class="left"
             :style="{ flex: `0 0 ${lineNumberWidth}`, fontSize: `${fontSize}px` }">
            <loader class="float-right" :scale="1" v-if="showLinesLoader" />
        </div>
        <b-button-toolbar class="right py-1 justify-content-center">
            <b-button class="mr-2"
                      size="sm"
                      :variant="remainingLines > nextRenderedLines ? 'warning' : 'primary'"
                      :disabled="showLinesLoader"
                      @click="renderNextLines(innerCodeLines.length - confirmedLines)">
                Show remaining {{ remainingLines }} line{{ remainingLines === 1 ? '' : 's' }}
            </b-button>
            <b-button size="sm"
                      variant="primary"
                      :disabled="showLinesLoader"
                      @click="renderNextLines(maxLines)"
                      v-if="remainingLines > nextRenderedLines">
                Show next {{ nextRenderedLines }} line{{ nextRenderedLines === 1 ? '' : 's' }}
            </b-button>
        </b-button-toolbar>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/level-up';
import { FeedbackLine } from '@/models';

import Loader from './Loader';
import FeedbackArea from './FeedbackArea';
import GutterComment from './GutterComment';

export default {
    name: 'inner-code-viewer',

    props: {
        assignment: {
            type: Object,
            default: null,
        },
        submission: {
            type: Object,
            default: null,
        },
        codeLines: {
            type: Array,
            required: true,
        },
        feedback: {
            type: Object,
            required: true,
        },
        gutterComments: {
            type: Object,
            default: () => ({}),
        },
        showWhitespace: {
            type: Boolean,
            default: true,
        },
        showInlineFeedback: {
            type: Boolean,
            default: true,
        },
        fileId: {
            type: String,
            required: true,
        },
        canUseSnippets: {
            type: Boolean,
            default: false,
        },
        startLine: {
            type: Number,
            default: 0,
        },
        endLine: {
            type: Number,
            default: null,
        },
        warnNoNewline: {
            type: Boolean,
            default: true,
        },
        lineFeedbackOffset: {
            type: Number,
            default: 0,
        },
        noLineNumbers: {
            type: Boolean,
            default: false,
        },
        emptyFileMessage: {
            type: String,
            default: 'File is empty.',
        },
        maxLines: {
            type: Number,
            default: UserConfig.maxLines,
        },
        nonEditable: {
            type: Boolean,
            default: false,
        },
        shouldRenderThread: {
            type: Function,
            default: () => true,
        },
        shouldFadeReply: {
            type: Function,
            default: () => false,
        },
    },

    data() {
        return {
            dragEvent: null,
            confirmedLines: false,
            showLinesLoader: false,
            innerCodeLines: [],
            cursorType: 'pointer',
            addingInlineFeedback: {},
        };
    },

    watch: {
        fileId() {
            this.confirmedLines = false;
        },

        codeLines: {
            immediate: true,
            handler() {
                this.addingInlineFeedback = {};
                this.innerCodeLines = Object.freeze(
                    Object.preventExtensions(this.codeLines.map(x => x)),
                );
            },
        },

        canGiveFeedback() {
            if (this.canGiveFeedback) {
                this.cursorType = 'pointer';
            }
        },
    },

    computed: {
        ...mapGetters('user', {
            myId: 'id',
        }),

        ...mapGetters('pref', ['fontSize']),

        computedStartLine() {
            return Math.max(this.startLine + 1, 1);
        },

        computedEndLine() {
            let end = this.innerCodeLines.length;

            if (this.confirmedLines !== false) {
                end = Math.min(end, this.confirmedLines);
            }

            if (this.endLine !== null) {
                end = Math.min(end, this.endLine);
            }

            return end;
        },

        lintWhitespace() {
            return this.assignment && this.assignment.whitespace_linter;
        },

        canGiveFeedback() {
            return (
                !this.nonEditable &&
                this.showInlineFeedback &&
                this.submission &&
                FeedbackLine.canAddReply(this.submission, this.$root.$now)
            );
        },

        showFeedback() {
            return this.assignment != null && this.submission != null && this.showInlineFeedback;
        },

        atEndOfFile() {
            return this.computedEndLine >= this.innerCodeLines.length;
        },

        hasMissingNewline() {
            return this.innerCodeLines[this.innerCodeLines.length - 1] !== '';
        },

        showMissingNewline() {
            return this.warnNoNewline && this.atEndOfFile && this.hasMissingNewline;
        },

        remainingLines() {
            let remaining = this.innerCodeLines.length - this.confirmedLines;

            if (!this.hasMissingNewline) {
                remaining -= 1;
            }

            return remaining;
        },

        nextRenderedLines() {
            return Math.min(this.maxLines, this.remainingLines);
        },

        lineNumberWidth() {
            return this.noLineNumbers
                ? 0
                : `${3 + Math.log10(this.innerCodeLines.length) * 2 / 3}em`;
        },
    },

    components: {
        Icon,
        Loader,
        FeedbackArea,
        GutterComment,
    },

    destroyed() {
        this.removeDragHandler();
    },

    methods: {
        ...mapActions('feedback', {
            storeAddFeedbackLine: 'addFeedbackLine',
        }),

        removeDragHandler() {
            this.$el.removeEventListener('mousemove', this.dragMove);
        },

        async addFeedback(event) {
            if (!this.canGiveFeedback) {
                return;
            }

            const el = event.target.closest('li.line');
            if (!el) {
                return;
            }

            const line = Number(el.getAttribute('data-line')) - 1;
            if (!this.hasFeedback(line) && this.canGiveFeedback) {
                this.$set(this.addingInlineFeedback, line, true);

                FeedbackLine.createFeedbackLine(
                    parseInt(this.fileId, 10),
                    line + this.lineFeedbackOffset,
                    this.myId,
                ).then(({ cgResult }) => {
                    this.$delete(this.addingInlineFeedback, line);
                    const args = {
                        assignmentId: this.assignment.id,
                        submissionId: this.submission.id,
                        line: cgResult,
                    };
                    this.storeAddFeedbackLine(args);
                }, err => {
                    this.$set(this.addingInlineFeedback, line, err);
                });
            }
        },

        dragStart(event) {
            if (event.button === 0 && this.canGiveFeedback) {
                this.dragEvent = event;
                this.$el.addEventListener('mousemove', this.dragMove);
            }
        },

        dragMove(event) {
            this.cursorType = this.movedTooFar(event) ? 'text' : 'cursor';
        },

        movedTooFar(currentEvent) {
            const firstEvent = this.dragEvent;
            if (!firstEvent) {
                return false;
            }

            let dx = 0;
            let dy = 0;

            if (firstEvent.clientX != null) {
                dx = Math.abs(currentEvent.clientX - firstEvent.clientX);
            }
            if (firstEvent.clientY != null) {
                dy = Math.abs(currentEvent.clientY - firstEvent.clientY);
            }

            return dx + dy >= 1;
        },

        dragStop(event) {
            // Only add a new comment if a) a drag event was started _inside_ the code viewer,
            // b) the button used is the primary mouse button, and c) The mouse didn't move more
            // than a few pixels. Expanding the file tree often leads to the mouse cursor being
            // over the code viewer when the mouse button is released, triggering the creation of
            // a new reply if any of these conditions weren't there.

            if (this.dragEvent != null && event.button === 0 && !this.movedTooFar(event)) {
                this.addFeedback(event);
            }

            this.dragEvent = null;
            this.cursorType = 'pointer';
            this.removeDragHandler();
        },

        async renderNextLines(nLines) {
            this.showLinesLoader = true;

            await this.$afterRerender();

            this.confirmedLines += nLines;
            this.showLinesLoader = false;
        },

        hasFeedback(i) {
            return (
                this.showFeedback &&
                this.$utils.getProps(this.feedback, null, i + this.lineFeedbackOffset) != null
            );
        },

        gutterCommentVariant(line) {
            if (this.gutterComments[line] == null) {
                return '';
            }

            const variants = new Set(
                this.gutterComments[line].map(comm => comm.badgeVariant),
            );
            if (variants.has('danger')) {
                return 'text-danger';
            } else if (variants.has('warning')) {
                return 'text-warning';
            } else if (variants.has('info')) {
                return 'text-info';
            } else {
                return '';
            }
        },
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.inner-code-viewer {
    background-color: @linum-bg;

    @{dark-mode} {
        background-color: @color-primary-darkest;
    }
}

ol {
    margin: 0;
    padding: 0;
    overflow-x: visible;
    background: transparent;

    @{dark-mode} {
        color: @color-secondary-text-lighter !important;
    }
}

li {
    position: relative;

    background-color: lighten(@linum-bg, 1%);
    border-left: 1px solid darken(@linum-bg, 5%);

    code, &.empty-file, &.missing-newline {
        font-family: monospace;
    }

    @{dark-mode} {
        background-color: @color-primary-darker;
        border-color: darken(@color-primary-darkest, 5%);
    }

    &.hover:hover {
        background-color: rgba(0, 0, 0, 0.025);
    }

    &.normal-cursor {
        cursor: initial;
    }

    &.gutter-comments-outer {
        font-weight: bold;

        .bg-colors(@base, @op-base, @op-hover) {
            background-color: fade(@base, @op-base) !important;

            &.hover:hover {
                background-color: fade(@base, @op-hover) !important;
            }
        }

        &.text-danger {
            .bg-colors(red, 2.5%, 7.5%);

            @{dark-mode} {
                .bg-colors(red, 7.5%, 15%);
            }
        }

        &.text-warning {
            .bg-colors(@color-warning, 10%, 25%);

            @{dark-mode} {
                .bg-colors(@color-warning-dark, 15%, 25%);
            }
        }

        &.text-info {
            .bg-colors(@color-info, 5%, 12.5%);

            @{dark-mode} {
                .bg-colors(@color-info, 15%, 25%);
            }
        }

        > * {
            font-weight: normal;
        }
    }

    &.missing-newline,
    &.empty-file {
        list-style-type: none;
        cursor: default;
        user-select: none;

        .fa-icon {
            transform: rotate(90deg);

            &.missing-newline-icon {
                transform: translateY(-2px) rotate(90deg);
            }
        }
    }
}

code {
    color: @color-secondary-text;
    white-space: pre-wrap;
    font-size: 100%;

    word-wrap: break-word;
    word-break: break-word;
    -ms-word-break: break-all;

    -webkit-hyphens: auto;
    -moz-hyphens: auto;
    -ms-hyphens: auto;
    hyphens: auto;

    @{dark-mode} {
        color: rgb(131, 148, 150);
    }
}

.render-next-lines {
    display: flex;

    .left {
        align-self: stretch;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    .right {
        flex: 1 1 auto;
        border-top: 1px solid darken(@linum-bg, 5%);

        @{dark-mode} {
            border-top: 1px solid darken(@color-primary-darkest, 5%);
        }
    }
}

.feedback-area {
    font-size: 110%;
    .default-background;
}

.add-feedback-loader-wrapper {
    position: absolute;
    right: 5px;
    top: 1px;
}
</style>
