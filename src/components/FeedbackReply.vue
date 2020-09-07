<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="feedback-reply" :id="componentId" v-b-visible="onVisible"
     :class="{ focus: showFocus && replyIdToFocus === reply.id, editing, }">
    <b-card no-body v-if="editing" class="mt-0">
        <b-tabs card
                class="border-bottom">
            <b-tab title="Edit" active>
                <div>
                    <snippetable-input
                        :course="assignment.course"
                        :value="internalReply.message"
                        @input="onInput"
                        :min-initial-height="100"
                        :force-snippets-above="forceSnippetsAbove"
                        :total-amount-lines="totalAmountLines"
                        :feedback-disabled="inputDisabled"
                        :can-use-snippets="canUseSnippets"
                        :max-initial-height="300"
                        :line="feedbackLine.line"
                        ref="inputField"
                        @ctrlEnter="doSubmit"/>
                </div>
            </b-tab>
            <b-tab title="Preview"
                   lazy
                   :disabled="internalReply.replyType !== 'markdown' || internalReply.isEmpty">
                <div class="p-2">
                    <inner-markdown-viewer
                        :markdown="internalReply.message"
                        class="markdown-message" />
                </div>
            </b-tab>

            <template v-slot:tabs-end>
                <div class="snippet-toolbar-wrapper"
                     style="margin-top: -.75rem">
                    <b-dropdown toggle-class="p-0 border-0 bg-transparent"
                                no-caret
                                class="snippet-dropdown"
                                ref="snippetDropdown"
                                v-b-popover.top.hover="'Use, search and add snippets'"
                                style="max-height: 70vh;"
                                dropleft>
                        <template v-slot:button-content>
                            <icon name="snippet" />
                        </template>

                        <b-dropdown-group header="Search snippet" class="rounded-top">
                            <b-input-group>
                                <input class="form-control" placeholder="Search snippets"
                                       v-model="snippetsFilter"/>
                            </b-input-group>
                        </b-dropdown-group>

                        <b-dropdown-divider />

                        <b-dropdown-group header="Existing snippets"
                                          style="max-height: 40vh; overflow-y: auto;">
                            <template v-if="sortedSnippets.length === 0">
                                <b-dropdown-item
                                    href="#"
                                    class="py-2"
                                    disabled>
                                    <span class="text-muted font-italic">You have no snippets yet</span>
                                </b-dropdown-item>
                            </template>
                            <template v-else-if="filteredSnippets.length === 0">
                                <b-dropdown-item
                                    class="py-2"
                                    href="#"
                                    disabled>
                                    <span class="text-muted font-italic">No snippets found</span>
                                </b-dropdown-item>
                            </template>
                            <template v-else>
                                <li v-for="snippet in filteredSnippets"
                                    :key="snippet.key">
                                    <div class="dropdown-item cursor-pointer"
                                         @click="selectSnippet(snippet)">
                                        <icon :scale="0.9" :name="snippet.course ? 'book' : 'user-circle-o'" />
                                        <b class="snippet-key">{{ snippet.key }}</b>
                                        <div class="snippet-value">{{ snippet.value }}</div>
                                    </div>
                                </li>
                            </template>
                        </b-dropdown-group>


                        <b-dropdown-divider />

                        <b-dropdown-group header="Add current text as snippet">
                            <li :id="`${componentId}-add-snippet-wrapper`">
                                <b-input-group class="input-snippet-group m-0">
                                    <input class="input form-control"
                                           placeholder="Snippet key"
                                           ref="snippetAddInput"
                                           v-model="snippetKey"
                                           :disabled="inputDisabled"
                                           @keydown.ctrl.enter="() => addSnippetButton.onClick()"/>
                                    <b-input-group-append>
                                        <cg-submit-button ref="addSnippetButton"
                                                          class="add-snippet-btn"
                                                          :submit="addSnippet"
                                                          :confirm="addSnippetConfirm"
                                                          :container="`#${componentId}-add-snippet-wrapper`"
                                                          @after-success="afterAddSnippet"
                                                          @error="inputDisabled = false">
                                            <icon :scale="1" name="check"/>
                                        </cg-submit-button>
                                    </b-input-group-append>
                                </b-input-group>
                            </li>
                        </b-dropdown-group>
                    </b-dropdown>
                </div>
            </template>
        </b-tabs>

        <div class="save-button-wrapper">
            <cg-submit-button
                ref="deleteButton"
                variant="danger"
                name="delete-feedback"
                :submit="deleteFeedback"
                @error="inputDisabled = false"
                :confirm="(reply.isEmpty && internalReply.isEmpty) ?  '' : 'Are you sure you want to delete this comment?'"
                @after-success="afterDeleteFeedback"
                label="Delete" />

            <cg-submit-button :submit="cancelEditing"
                              :wait-at-least="0"
                              @after-success="afterCancel"
                              @after-error="afterCancel"
                              :duration="0"
                              :confirm="cancelEditingConfirmMessage"
                              variant="outline-primary"
                              label="Cancel"/>

            <cg-submit-button :submit="submitFeedback"
                              @after-success="afterSubmitFeedback"
                              @error="inputDisabled = false"
                              ref="submitButton"
                              name="submit-feedback"
                              label="Save"  />
        </div>
    </b-card>

    <div v-else>
        <div class="d-flex justify-content-between header-line">
            <div class="info-text-wrapper">
                <span>
                    <b-badge v-if="reply.isPeerFeedback"
                             class="text-small-uppercase align-middle mt-n1">
                        peer feedback
                    </b-badge>

                    <cg-user :user="reply.author"
                             :show-you="true"
                             v-if="reply.author"/>
                    <i v-else
                       title="You do not have the permission to see the authors of feedback">
                        A grader
                    </i>

                    <span class="text-muted">
                        <cg-relative-time
                            :date="reply.createdAt"/>

                        <template v-if="reply.lastEdit != null">
                            <sup :title="`Edited on ${$utils.readableFormatDate(reply.lastEdit)}`">*</sup>
                        </template>
                    </span>
                </span>
            </div>
            <div v-if="showApprovalToggle || editable || canSeeEdits || hasExternalImages" class="d-flex edit-buttons-wrapper">
                <peer-feedback-assessment
                    v-if="showApprovalToggle"
                    :disabled="nonEditable || !canApprove"
                    :reply="reply"
                    @updated="emitUpdated" />

                <b-btn v-if="canSeeEdits && reply.lastEdit"
                       class="state-default"
                       :id="`${componentId}-history-btn`">
                    <icon name="history" />
                </b-btn>

                <b-popover :target="`${componentId}-history-btn`"
                           v-if="canSeeEdits && reply.lastEdit"
                           triggers="click blur"
                           title="Edit history"
                           custom-class="feedback-reply-edit-history-popover p-0"
                           :container="componentId"
                           placement="leftbottom">
                    <feedback-reply-history :reply="reply"/>
                </b-popover>

                <b-btn @click="showExternalImages = !showExternalImages"
                       class="state-default"
                       v-b-popover.top.hover="externalImagesTogglePopover"
                       v-if="hasExternalImages">
                    <icon name="picture-o"
                          v-if="showExternalImages"
                          class="enabled"/>
                    <span v-else class="strikethrough disabled">
                            <icon name="picture-o" />
                    </span>
                </b-btn>

                <template v-if="!nonEditable">
                    <cg-submit-button
                        v-if="editable"
                        ref="deleteButton"
                        variant="secondary"
                        name="delete-feedback"
                        :submit="deleteFeedback"
                        confirm="Are you sure you want to delete this comment?"
                        invert-colors
                        @error="inputDisabled = false"
                        @success="onDeleteFeedback"
                        @after-success="afterDeleteFeedback">
                        <icon name="times" class="delete-icon"/>
                    </cg-submit-button>

                    <b-btn @click="startEdit"
                           v-if="editable"
                           class="state-default"
                           name="edit-feedback">
                        <icon name="pencil"/>
                    </b-btn>
                </template>
            </div>
        </div>
        <transition name="fade">
            <b-card class="feedback-reply-message-wrapper m-0">

                <div v-html="newlines($utils.htmlEscape(internalReply.message))"
                     class="plain-text-message p-2"
                     v-if="internalReply.replyType === 'plain_text'"  />
                <inner-markdown-viewer
                    :block-external-images="!showExternalImages"
                    :markdown="internalReply.message"
                    @blocked-external="onExternalBlocked"
                    class="markdown-message py-2 px-3"
                    v-else />

            </b-card>
        </transition>
    </div>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop, Ref, Watch } from 'vue-property-decorator';

// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/reply';
import 'vue-awesome/icons/gear';
import 'vue-awesome/icons/user-circle-o';
import 'vue-awesome/icons/book';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/pencil';
import 'vue-awesome/icons/history';
import 'vue-awesome/icons/picture-o';
import 'vue-awesome/icons/ban';

import { mapActions, mapGetters } from 'vuex';

// @ts-ignore
import { Submission } from '@/models/submission';

import { Snippet, CourseSnippet } from '@/interfaces';

import { FeedbackReply as FeedbackReplyModel, FeedbackLine, Assignment, User as UserModel } from '@/models';
// @ts-ignore
import SubmitButton from './SubmitButton';
// @ts-ignore
import InnerMarkdownViewer from './InnerMarkdownViewer';
// @ts-ignore
import SnippetableInput from './SnippetableInput';

import FeedbackReplyHistory from './FeedbackReplyHistory';
import PeerFeedbackAssessment from './PeerFeedbackAssessment';

@Component({
    computed: {
        ...mapGetters({
            snippets: 'user/snippets',
        }),

    },
    methods: {
        ...mapActions('user', {
            addSnippetToStore: 'addSnippet',
            updateSnippetInStore: 'updateSnippet',
        }),
    },
    components: {
        Icon,
        SnippetableInput,
        InnerMarkdownViewer,
        FeedbackReplyHistory,
        PeerFeedbackAssessment,
    },
})
export default class FeedbackReply extends Vue {
    snippets!: Record<string, Snippet>;

    addSnippetToStore!: any;

    updateSnippetInStore!: any;

    @Prop({ required: true }) reply!: FeedbackReplyModel

    @Prop({ required: true }) feedbackLine!: FeedbackLine

    @Prop({ default: false }) forceSnippetsAbove!: boolean

    @Prop({ required: true }) totalAmountLines!: number

    @Prop({ required: true }) submission!: Submission

    @Prop({ required: true }) canUseSnippets!: boolean

    @Prop({ default: false }) readonly nonEditable!: boolean;

    get assignment(): Assignment {
        return this.submission.assignment;
    }

    internalReply: FeedbackReplyModel = this.reply;

    @Watch('reply')
    onReplyUpdate() {
        this.internalReply = this.reply;
    }

    get componentId(): string {
        if (this.reply.id == null) {
            return `feedback-reply-tracking-id-${this.reply.trackingId}`;
        }
        return `feedback-reply-id-${this.reply.id}`;
    }

    get replyIdToFocus(): number {
        const replyId = this.$route.query?.replyToFocus;
        return parseInt(replyId ?? '', 10);
    }

    get externalImagesTogglePopover() {
        if (this.showExternalImages) {
            return 'Hide external images.';
        }
        return 'Show external images, this might leak information to third parties.';
    }

    snippetKey: string = '';

    snippetDisabled: boolean = false;

    showSnippetDialog: boolean = false

    inputDisabled: boolean = false;

    wasClicked: boolean = false;

    showFocus: boolean = false;

    snippetsFilter: string = '';

    showExternalImages: boolean = false;

    hasExternalImages: boolean = false;

    onVisible(nowVisible: boolean) {
        if (nowVisible) {
            this.showFocus = true;
        }
    }

    startEdit() {
        this.wasClicked = true;
    }

    get canSeeEdits(): boolean {
        return this.reply.canSeeEdits(this.assignment);
    }

    get editable(): boolean {
        return this.reply.canEdit(this.assignment);
    }

    get canApprove(): boolean {
        return this.reply.canApprove(this.assignment);
    }

    get editing(): boolean {
        return this.editable && (this.reply.id == null || this.wasClicked);
    }

    @Watch('editing', { immediate: true })
    onEditingChange(): void {
        this.showSnippetDialog = false;
        this.$emit('editing', { reply: this.reply, isEditing: this.editing });
    }

    get line(): number {
        return this.feedbackLine.line;
    }

    get author(): UserModel | null {
        return this.reply.author;
    }

    get addSnippetConfirm() {
        if (this.snippetKey in this.snippets) {
            return `There is already a snippet with key "${this.snippetKey}".
Do you want to overwrite it?`;
        } else {
            return '';
        }
    }

    get gearId(): string {
        return `feedback-edit-gear-${this.reply.trackingId}`;
    }

    get courseSnippets(): CourseSnippet[] {
        return (this.assignment.course.snippets || []).map(
            (s: CourseSnippet) => Object.assign({}, s, { course: true }),
        );
    }

    get sortedSnippets(): Snippet[] {
        return Object.values(this.snippets).concat(this.courseSnippets).sort(
            (a, b) => a.key.localeCompare(b.key),
        );
    }

    get filteredSnippets(): Snippet[] {
        if (this.snippetsFilter === '') {
            return this.sortedSnippets;
        }
        const terms = this.snippetsFilter.toLocaleLowerCase().split(' ');

        return this.sortedSnippets.filter(snip => {
            const key = snip.key.toLocaleLowerCase();
            const value = snip.value.toLocaleLowerCase();
            const course = snip.course ? 'course' : '';

            return terms.every(
                term => key.indexOf(term) >= 0 ||
                    value.indexOf(term) >= 0 ||
                    course.indexOf(term) >= 0,
            );
        });
    }

    get cancelEditingConfirmMessage(): string {
        if (this.internalReply.message !== this.reply.message || this.internalReply.id == null) {
            return 'Are you sure you want to discard your changes?';
        }
        return '';
    }

    get showApprovalToggle() {
        return this.reply.isPeerFeedback || !this.reply.approved;
    }

    @Ref() readonly inputField: SnippetableInput | null;

    @Ref() readonly submitButton: SubmitButton | null;

    @Ref() readonly deleteButton: SubmitButton | null;

    @Ref() readonly addSnippetButton: SubmitButton | null;

    @Ref() readonly snippetAddInput: any | null;

    @Ref() readonly snippetDropdown: any | null;

    onInput(event: string) {
        this.internalReply = this.internalReply.update(event);
    }

    async focusInput(): Promise<void> {
        await this.$nextTick();

        let el = this.inputField;
        if (el == null) {
            await this.$afterRerender();
            el = this.inputField;
        }

        if (el != null) {
            el.focusInput();
        }
    }

    // eslint-disable-next-line class-methods-use-this
    cancelEditing(): Promise<{}> {
        return this.$nextTick().then(() => ({}));
    }

    afterCancel(): void {
        this.internalReply = this.reply;
        if (this.reply.isEmpty) {
            this.afterDeleteFeedback();
        }
        this.inputDisabled = false;
        this.wasClicked = false;
    }

    submitFeedback(): Promise<object> {
        if (this.internalReply.isEmpty) {
            return this.deleteFeedback();
        }

        this.inputDisabled = true;

        return this.internalReply.save();
    }

    emitUpdated(reply: FeedbackReplyModel) {
        this.$emit('updated', reply);
    }

    afterSubmitFeedback(response: any): void {
        if (this.internalReply.isEmpty) {
            this.$emit('deleted', this.internalReply);
        } else {
            this.emitUpdated(this.internalReply.updateFromServerData(response.data));
        }
        this.inputDisabled = false;
        this.wasClicked = false;
    }

    afterDeleteFeedback(): void {
        this.$emit('deleted', this.internalReply);
    }

    onDeleteFeedback(): void {
        if (this.internalReply.id == null) {
            this.afterDeleteFeedback();
        }
    }

    doSubmit() {
        if (this.internalReply.isEmpty) {
            this.deleteButton.onClick();
        } else {
            this.submitButton.onClick();
        }
    }

    submitFeedabckError() {
        this.inputDisabled = false;
    }

    // eslint-disable-next-line
    newlines(value: string): string {
        return value.replace(/\n/g, '<br>');
    }

    deleteFeedback(): Promise<object> {
        this.inputDisabled = true;
        this.snippetKey = '';
        return this.internalReply.delete();
    }

    onDropDownHide(bvEvent: any): void {
        if (this.deleteButton.state !== 'default') {
            bvEvent.preventDefault();
        }
    }

    // eslint-disable-next-line
    deleteFilter<T extends Record<string, Record<string, number>>>(err: T): T {
        if (err.response && err.response.status === 404) {
            return err;
        } else {
            throw err;
        }
    }

    deleteFeedbackError() {
        this.inputDisabled = false;
    }

    async onShowSnippetDialog(): Promise<void> {
        this.showSnippetDialog = true;
        this.findSnippet();
        await this.$afterRerender();
        if (this.snippetAddInput) {
            this.snippetAddInput.focus();
        }
    }

    addSnippet() {
        const key = this.snippetKey;
        const value = this.internalReply.message;

        if (key.match(/\s/)) {
            throw new Error('No spaces allowed!');
        } else if (!key) {
            throw new Error('Snippet key cannot be empty');
        } else if (!value) {
            throw new Error('Snippet value cannot be empty');
        }

        this.inputDisabled = true;

        if (key in this.snippets) {
            const { id } = this.snippets[key];
            return this.$http.patch(`/api/v1/snippets/${id}`, { key, value }).then(response => {
                this.updateSnippetInStore({ id, key, value });
                return response;
            });
        } else {
            return this.$http
                .put('/api/v1/snippet', { key, value })
                .then(response => {
                    this.addSnippetToStore(response.data);
                    return response;
                });
        }
    }

    async afterAddSnippet() {
        this.inputDisabled = false;
        if (this.snippetDropdown) {
            this.snippetDropdown.hide();
        }
    }

    findSnippet() {
        if (this.snippetKey !== '') {
            return;
        }

        const keys = Object.keys(this.snippets);
        for (let i = 0, len = keys.length; i < len; i += 1) {
            if (this.internalReply.message === this.snippets[keys[i]].value) {
                this.snippetKey = keys[i];
                return;
            }
        }
    }

    async selectSnippet(snippet: Snippet) {
        let base = this.internalReply.message;
        if (/[^\s]$/.test(base)) {
            base += '\n';
        }
        this.internalReply = this.internalReply.update(base + snippet.value);
        this.focusInput();
    }

    onExternalBlocked(event: { blocked: boolean }) {
        if (event.blocked) {
            this.hasExternalImages = true;
        } else if (!this.showExternalImages) {
            this.hasExternalImages = false;
        }
    }
}
</script>

<style lang="less" scoped>
@import '~mixins.less';

.feedback-reply-message-wrapper {
    min-height: 1em;
    max-height: 15rem;
    margin-top: 0;
    overflow-y: auto;
    padding: 0;
}

.feedback-reply {
    .default-text-colors;
    .default-background;

    display: flex;
    align-items: top;

    @media @media-small {
        flex-direction: column-reverse;
    }

    font-size: 1.1em;

    .feedback-reply-message-wrapper {
        @{dark-mode} {
            background-color: @color-primary;
            border-color: @color-primary-darkest;
            color: @text-color-dark;
        }

        .plain-text-message {
            font-family: monospace;
            white-space: pre-wrap;
            word-break: break-word;
        }

    }

    &.edit {
        position: relative;
    }
}

.editable-feedback-reply {
    position: relative;
    min-height: 7em;
    font-size: 1em;
}

.snippet-icon {
    display: inline-block;
    width: 1rem;

    .fa-icon {
        vertical-align: middle;
        margin-top: -3px;
    }
}

.save-button-wrapper {
    text-align: right;
    padding: 0.5rem 1.25rem;
    background-color: rgba(0, 0, 0, 0.03);
}

.snippetable-input {
    font-family: monospace;
}

.info-text-wrapper {
    display: flex;
    align-items: center;
}

.snippet-toolbar-wrapper {
    align-self: center;
    margin-left: auto;
    .fa-icon {
        transition: transform @transition-duration;

        &.rotated {
            transform: translateY(-1px) rotate(45deg);
        }
    }
}
</style>

<style lang="less">
@import '~mixins.less';

.feedback-reply .info-text-wrapper .user .group-user,
.feedback-reply .info-text-wrapper .user .name-user {
    font-weight: bold;
}

.feedback-reply .markdown-message {
    & > *:first-child {
        margin-top: 0;
    }

    & > *:last-child {
        margin-bottom: 0;
    }

    p {
        margin-bottom: 0.5em;
    }

    pre.code-block {
        margin-left: 0;
        padding: 1.5rem;
        border-radius: @border-radius;
        background: @color-lightest-gray;
    }
}

.feedback-reply {
    .fade-leave-active,
    .fade-enter-active {
        transition: opacity @transition-duration;
    }

    .fade-leave-to,
    .fade-enter {
        opacity: 0;
    }
}

.feedback-reply-edit-history-popover {
    width: 70%;
    z-index: 10;
}


.feedback-reply .feedback-reply-message-wrapper .card-body {
    padding: 0;
}

.feedback-reply .feedback-reply-message-wrapper {
    transition: box-shadow @transition-duration, border @transition-duration;
}

.feedback-reply.focus .feedback-reply-message-wrapper {
    border: 1px solid @color-warning;
    box-shadow: 0px 0px 15px @color-warning;
    border-radius: @border-radius;
}

.feedback-reply .snippet-dropdown {
    .input-group {
        padding: .5rem;
    }

    .snippet-value {
        overflow: hidden;
        text-overflow: ellipsis;
    }


    .dropdown-divider {
        padding: 0;
        margin: 0;
    }

    .dropdown-header {
        background: @footer-color;
        border-bottom: 1px solid @border-color;

        @{dark-mode} {
            background-color: @color-primary-darker;
            border-color: @color-primary-darkest;
        }
    }

    & > .dropdown-menu {
        width: 30rem;
        max-width: 80vw;
        padding: 0;
    }

    pre {
        margin-bottom: 0;
    }

    &.show > .dropdown-menu {
        max-height: 70vh;
        border-top-left-radius: @border-radius;
        border-top-right-radius: @border-radius;

        .popover {
            max-width: 80% !important;
        }
    }
}

.feedback-reply .edit-buttons-wrapper .btn {
    display: inline-block;
    padding: 0 0.5rem;
    /* margin: -0.25rem; */
    /* margin-top: -0.5rem; */
    border: none;
    margin-left: 0;
    box-shadow: none !important;
    transition: color @transition-duration ease-out;

    &.state-pending,
    &.state-default {
        background-color: transparent !important;
    }

    .strikethrough {
        padding-left: 4px;
        margin-left: -4px;
        padding-right: 4px;
        margin-right: -4px;
        position: relative;
        opacity: 0.65;
    }

    .strikethrough:before {
        position: absolute;
        content: "";
        left: 0;
        top: 40%;
        right: 0;
        z-index: 100;
        border-top: 2px solid;
        border-color: inherit;
        border-color: @color-secondary-text-lighter;

        transform:rotate(-30deg);
    }

    &:hover .strikethrough:before {
        border-color: @color-primary;
        @{dark-mode} {
            border-color: @color-secondary;
        }
    }

    .fa-icon {
        color: @color-secondary-text-lighter;
    }

    .fa-icon.enabled {
        color: @color-primary;
        @{dark-mode} {
            color: @text-color-dark;
        }
    }

    &:hover {
        background-color: transparent !important;
        .fa-icon {
            color: @color-primary;
            @{dark-mode} {
                color: @color-secondary;
            }
        }

        @{dark-mode} .delete-icon,
        .delete-icon {
            color: @color-danger;
        }
    }
}
</style>
