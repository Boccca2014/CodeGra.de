<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<component :is="useRsPanes ? 'rs-panes' : 'div'"
           :class="{ 'add-space': addSpace, 'without-hover': visibleWithoutHover }"
           class="floating-feedback-button p-relative"
           :size="initialSize"
           units="percents"
           :step="50"
           :min-size="20"
           :max-size="90"
           allow-resize
           :on-drag-started="() => {resizingFeedback = true;}"
           :on-drag-finished="() => {resizingFeedback = false;}"
           split-to="rows">
    <div class="content" slot="firstPane"
         key="content">
        <div class="content-wrapper">
            <slot :resizing="resizingFeedback"/>
        </div>

        <submit-button class="feedback-button"
                       :class="buttonClasses"
                       :submit="addFeedback"
                       @success="afterAddFeedback"
                       variant="secondary"
                       v-b-popover.window.top.hover="`Edit feedback for this ${slotDescription}`"
                       v-if="canEditFeedback && !hasFeedback">
            <icon name="edit"/>
        </submit-button>
    </div>

    <div class="feedback-area-wrapper" v-if="showFeedback"
         slot="secondPane">
            <feedback-area
                class="py-1"
                @updated="updateSize"
                @editing="updateSize"
                ref="feedbackArea"
                :feedback="feedback"
                :total-amount-lines="1"
                :force-snippets-above="forceSnippetsAbove"
                :can-use-snippets="canUseSnippets"
                :submission="submission" />
        </div>
    </component>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import { FeedbackLine } from '@/models';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/edit';

import ResSplitPane from 'vue-resize-split-pane';

import FeedbackArea from './FeedbackArea';
import SubmitButton from './SubmitButton';

export default {
    name: 'floating-feedback-button',

    props: {
        fileId: {
            type: String,
            required: true,
        },
        line: {
            type: Number,
            required: true,
        },
        feedback: {
            type: FeedbackLine,
            default: null,
        },
        canUseSnippets: {
            type: Boolean,
            default: false,
        },
        slotDescription: {
            type: String,
            default: 'cell',
        },
        alwaysShowButton: {
            type: Boolean,
            default: false,
        },
        disabled: {
            type: Boolean,
            default: false,
        },
        forceSnippetsAbove: {
            type: Boolean,
            default: false,
        },
        assignment: {
            type: Object,
            required: true,
        },
        submission: {
            type: Object,
            required: true,
        },
        addSpace: {
            type: Boolean,
            default: false,
        },
        visibleWithoutHover: {
            type: Boolean,
            default: false,
        },
        buttonPosition: {
            type: String,
            default: 'top-right',
        },
        noResize: {
            type: Boolean,
            default: false,
        },
    },

    computed: {
        ...mapGetters('user', {
            myId: 'id',
        }),

        hasFeedback() {
            return this.feedback != null && !this.feedback.isEmpty;
        },

        showFeedback() {
            return this.hasFeedback && !this.disabled;
        },

        canEditFeedback() {
            return (
                !this.disabled &&
                FeedbackLine.canAddReply(this.submission, this.$root.$now)
            );
        },

        buttonClasses() {
            const res = { hide: this.hasFeedback && !this.alwaysShowButton };
            this.buttonPosition.split('-').forEach(pos => {
                res[pos] = true;
            });
            return res;
        },

        useRsPanes() {
            return this.showFeedback && !this.noResize;
        },
    },

    data() {
        return {
            resizingFeedback: false,
            initialSize: 65,
        };
    },

    async mounted() {
        await this.$afterRerender();
        this.updateSize();
    },

    watch: {
        noResize: 'updateSize',

        showFeedback() {
            this.updateSize();
            this.$emit('feedback-shown', {
                shown: this.showFeedback,
            });
        },
    },

    methods: {
        ...mapActions('feedback', {
            storeAddFeedbackLine: 'addFeedbackLine',
        }),

        async updateSize() {
            if (!this.showFeedback && this.noResize) {
                return;
            }
            await this.$nextTick();

            let height;
            for (let i = 0; i < 10; ++i) {
                const fbEl = this.$refs.feedbackArea;
                if (!fbEl) {
                    return;
                }
                height = fbEl.$el.scrollHeight;
                if (height !== 0) {
                    break;
                }

                // eslint-disable-next-line no-await-in-loop
                await this.$afterRerender();
            }

            const totalHeight = this.$el.scrollHeight;
            this.initialSize = Math.max(20, 100 - ((height + 10) / totalHeight) * 100);
        },

        addFeedback() {
            return FeedbackLine.createFeedbackLine(
                parseInt(this.fileId, 10),
                this.line,
                this.myId,
            );
        },

        afterAddFeedback({ cgResult }) {
            this.storeAddFeedbackLine({
                assignmentId: this.assignment.id,
                submissionId: this.submission.id,
                line: cgResult,
            });
        },
    },

    components: {
        Icon,
        FeedbackArea,
        SubmitButton,
        'rs-panes': ResSplitPane,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.floating-feedback-button {
    display: flex;
    flex-direction: column;
    max-height: 100%;

    @media @media-no-large {
        height: 100%;
    }
}

.content {
    position: relative;
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    min-height: 0;

    .pane-rs & {
        height: 100%;
    }
}

.content-wrapper {
    width: 100%;
    height: 100%;
    overflow: auto;
    max-height: 100%;
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
}

.feedback-area-wrapper {
    height: 100%;
    width: 100%;
}

.feedback-button.btn {
    position: absolute;

    &.top {
        top: 0;
    }
    &.bottom {
        bottom: 0;
    }
    &.right {
        right: 0;
    }
    &.left {
        left: 0;
    }

    .add-space & {
        margin: 1rem;
    }

    transition-property: opacity, transform;
    transition-duration: @transition-duration;
    transform: scale(0);
    opacity: 0;

    .floating-feedback-button:hover &:not(.hide),
    .floating-feedback-button.without-hover &:not(.hide) {
        transform: scale(1);
        opacity: 1;
    }
}
</style>

<style lang="less">
.floating-feedback-button .feedback-area {
    padding: 0.5rem;
}
.floating-feedback-button.pane-rs > .Pane.row {
    margin: 0;
    overflow: auto;
}
</style>
