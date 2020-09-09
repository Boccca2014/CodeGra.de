<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="feedback-area">
    <div class="replies-wrapper"
         :style="{ 'pb-2': showReply }">
        <transition-group name="fade"
                          tag="div">
            <div :key="reply.trackingId"
                 class="reply-wrapper"
                 v-if="shouldShowReply(idx, reply)"
                 :class="{ editing: isEditing(reply) }"
                 v-for="reply, idx in nonDeletedReplies">
                <a v-if="hiddenReplies.has(reply.trackingId) && idx === 1"
                   href="#"
                   @click.prevent="showAllReplies"
                   class="inline-link mx-auto mt-n1 mb-n3">
                    Show {{ amountHiddenReplies }} more repl{{ amountHiddenReplies > 1 ? 'ies' : 'y' }}
                </a>
                <template v-else>
                    <div v-if="idx !== 0"
                        class="pr-1 reply-gutter"
                        :class="{ faded: fadedReplies.has(reply.trackingId) }">
                        <icon name="caret-right" class="reply-icon" />
                    </div>
                    <feedback-reply
                        class="d-block"
                        :class="{ faded: fadedReplies.has(reply.trackingId) }"
                        :can-use-snippets="canUseSnippets"
                        :reply="reply"
                        :feedback-line="feedback"
                        :force-snippets-above="forceSnippetsAbove"
                        :total-amount-lines="totalAmountLines"
                        @updated="replyUpdated"
                        @deleted="replyDeleted"
                        @editing="onEditingEvent(reply, $event)"
                        :submission="submission"
                        :non-editable="nonEditable"/>
                </template>
            </div>
        </transition-group>
    </div>
    <div @click.prevent="addReply"
         class="add-reply text-muted p-2 border rounded mt-2 border-top"
         v-if="showReply">
        Click to reply&hellip;
    </div>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';
import { Getter, Action } from 'vuex-class';

// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/caret-right';

import { FeedbackLine, FeedbackReply as FeedbackReplyModel } from '@/models/feedback';

import { Assignment } from '@/models/assignment';
// @ts-ignore
import { Submission } from '@/models/submission';

import FeedbackReply from './FeedbackReply';

/**
 * Get the tracking ids of which replies to hide.
 *
 * @param replies - A list of non deleted to replies for which we should find
 *   the replies you want to hide.
 * @param base - If not null this is should be a set of tracking ids. This will
 *   be used as base for the returned set, i.e. the resulting set will be equal to
 *   or a subset of this base.
 */
function getRepliesToHide(replies: FeedbackReplyModel[], base: Set<number> | null): Set<number> {
    let trackingIds = replies.slice(1, -1).map(r => r.trackingId);
    if (base != null) {
        trackingIds = trackingIds.filter(id => base.has(id));
    }
    return new Set(trackingIds);
}

@Component({
    components: {
        FeedbackReply,
        Icon,
    },
})
export default class FeedbackArea extends Vue {
    @Getter('user/id') myUserId!: number;

    @Action('feedback/addFeedbackLine') addFeedbackLine!: any;

    @Prop({ required: true }) readonly feedback!: FeedbackLine;

    @Prop({ required: true }) readonly canUseSnippets!: boolean;

    @Prop({ required: true }) readonly submission!: Submission;

    @Prop({ required: true }) readonly totalAmountLines!: number;

    @Prop({ default: false }) readonly nonEditable!: boolean;

    @Prop({ default: false }) readonly forceSnippetsAbove!: boolean;

    // A function that receives a thread and a reply as arguments, and returns
    // a boolean value indicating whether a reply within a thread should be
    // faded.
    @Prop({ default: () => false })
    readonly shouldFadeReply!: (thread: FeedbackLine, reply: FeedbackReplyModel) => boolean;

    editingReplies: Record<string, boolean> = {};

    /*
     * This is not a computed property on purpose. By having this as a normal
     * property we can make sure we never start hiding certain replies that were
     * visible before. For example if a user adds a new reply we do not want to
     * start hiding the previous last reply, as this reply is probably useful
     * for the message the user is writing.
     */
    hiddenReplies: Set<number> = getRepliesToHide(this.nonDeletedReplies, null);

    get nonDeletedReplies(): FeedbackReplyModel[] {
        return this.feedback.replies.filter(r => !r.deleted);
    }

    get amountHiddenReplies(): number {
        return this.hiddenReplies.size;
    }

    get replyIdToFocus(): number {
        const replyId = this.$route.query?.replyToFocus;
        return parseInt(replyId ?? '', 10);
    }

    @Watch('replyIdToFocus', { immediate: true })
    async onReplyToFocus() {
        if (!Number.isNaN(this.replyIdToFocus)) {
            if (this.feedback.replies.some(r => r.id === this.replyIdToFocus)) {
                this.showAllReplies();
            }
        }
    }

    showAllReplies() {
        this.hiddenReplies = new Set([]);
    }

    shouldShowReply(idx: number, reply: FeedbackReplyModel): boolean {
        if (reply.deleted) {
            return false;
        }
        if (!this.hiddenReplies.has(reply.trackingId)) {
            return true;
        }
        return idx === 1;
    }

    isLastNonDeletedReply(r: FeedbackReplyModel): boolean {
        const replies = this.nonDeletedReplies;
        return (
            !r.deleted &&
                replies.length > 0 &&
                replies[replies.length - 1].trackingId === r.trackingId
        );
    }

    getReplyIndex(r: FeedbackReplyModel): number | null {
        const replies = this.nonDeletedReplies;
        for (let i = 0, len = replies.length; i < len; ++i) {
            if (replies[i].trackingId === r.trackingId) {
                return i;
            }
        }
        return null;
    }

    get showReply(): boolean {
        const replies = this.nonDeletedReplies;
        return (
            !this.nonEditable &&
            FeedbackLine.canAddReply(this.submission) &&
            replies.length > 0 && !replies[replies.length - 1].isEmpty
        );
    }

    get assignment(): Assignment {
        return this.submission.assignment;
    }

    get replies(): ReadonlyArray<FeedbackReplyModel> {
        return this.feedback.replies;
    }

    get fadedReplies() {
        return new Set(
            this.nonDeletedReplies.filter(reply =>
                this.shouldFadeReply(this.feedback, reply),
            ).map(reply => reply.trackingId),
        );
    }

    @Watch('fadedReplies', { immediate: true })
    onFadedReplies() {
        const hasFaded = this.fadedReplies.size > 0;
        const unfadedHidden = [...this.hiddenReplies].filter(r => !this.fadedReplies.has(r));
        if (hasFaded && unfadedHidden.length > 0) {
            this.showAllReplies();
        }
    }

    isEditing(reply: FeedbackReplyModel): boolean {
        return this.editingReplies[reply.trackingId] ?? false;
    }

    updateLine(newLine: FeedbackLine): Promise<void> {
        // Make sure we don't display that a comment was placed in the future.
        this.$root.$emit('cg::root::update-now');
        this.$emit('updated');

        return this.addFeedbackLine({
            assignmentId: this.assignment.id,
            submissionId: (this.submission as any).id,
            fileId: this.feedback.fileId,
            line: newLine,
        });
    }

    replyUpdated(newReply: FeedbackReplyModel): void {
        const line = this.feedback.updateReply(newReply);
        this.updateLine(line);
    }

    async replyDeleted(deletedReply: FeedbackReplyModel): Promise<void> {
        await this.updateLine(this.feedback.deleteReply(deletedReply));
        await this.$afterRerender();
        this.hiddenReplies = getRepliesToHide(this.nonDeletedReplies, this.hiddenReplies);
    }

    addReply(): void {
        const line = this.feedback.addReply(
            FeedbackReplyModel.createEmpty(this.myUserId, this.feedback.id),
        );
        this.updateLine(line);
    }

    onEditingEvent(reply: FeedbackReplyModel, event: any): void {
        this.$emit('editing');
        this.$set(this.editingReplies, reply.trackingId, event.isEditing);
    }
}
</script>

<style lang="less" scoped>
@import '~mixins.less';

.reply-wrapper {
    transition: margin @transition-duration;
    &:not(:first-child) {
        margin-top: 1rem;
    }

    &.editing .reply-gutter {
        opacity: 0;
    }

    .faded {
        opacity: 0.5;
    }
}

.add-reply {
    cursor: text;
}

.fade-enter-active,
.fade-leave-active {
    transition: opacity @transition-duration;
}
.fade-enter,
.fade-leave-to {
    opacity: 0;
}

.reply-wrapper {
    display: flex;
    flex-direction: row;

    .feedback-reply {
        flex: 1 1 auto;
    }
}

.reply-icon {
    .default-text-colors;
}
</style>
