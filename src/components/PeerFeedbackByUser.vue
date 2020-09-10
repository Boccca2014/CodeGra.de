<template>
<div v-if="!assignment.deadlinePassed()"
     class="p-3 border rounded text-muted font-italic">
    <p>
        Peer feedback will be available once the deadline for this assignment has
        passed.
    </p>

    <p class="mb-0">
        After the deadline you have
        {{ assignment.peer_feedback_settings.time / (24 * 60 * 60) }}
        days to give feedback to your peers.
    </p>
</div>
<cg-loader class="peer-feedback-by-user" v-else-if="loading" page-loader :scale="2" />
<rs-panes class="peer-feedback-by-user" v-else
          allow-resize
          :split-to="$root.$isMediumWindow ? 'columns' : 'rows'"
          :size="75"
          :step="25"
          units="percents"
          :min-size="30"
          :max-size="85">
    <div class="scroller-wrapper rounded border p-0"
         slot="firstPane">
        <div class="scroller"
             @scroll.passive="onScroll"
             ref="scroller">
            <div v-for="subId, idx in sortedSubmissionIds"
                 class="border-top-not-first"
                 :key="subId"
                 :id="getDivIdForOption(subId, 'sub')">
                <b-alert v-if="errors[subId]" show variant="danger">
                    Error when retrieving the submission:
                    {{ $utils.getErrorMessage(errors[subId]) }}
                </b-alert>
                <template v-else>
                    <div v-for="sub in [submissionById.orDefault({})[subId]]"
                         :key="subId"
                         class="mb-2">
                        <div no-body v-if="sub == null || sub.feedback == null || sub.fileTree == null">
                            <div class="text-muted p-3 border-bottom text-center">
                                &hellip;
                            </div>
                            <div class="p-3">
                                <cg-loader :scale="2" />
                            </div>
                        </div>
                        <div v-else
                             class="submission-wrapper">
                            <div class="font-weight-bold p-3 border-bottom text-center">
                                <cg-user :user="sub.user" />
                                <fa-icon name="exclamation-triangle"
                                         class="text-warning ml-1"
                                         v-b-popover.top.hover="'This is not the latest submission'"
                                         v-if="!isLatest(sub)"/>
                            </div>
                            <feedback-overview
                                :assignment="sub.assignment"
                                :submission="sub"
                                :context-lines="contextLines"
                                :show-whitespace="showWhitespace"
                                :show-inline-feedback="showInlineFeedback"
                                :should-render-general="false"
                                :should-render-thread="shouldRenderThread"
                                :should-fade-reply="shouldFadeReply"
                                :on-file-visible="(fileId, visible) => onVisible(getDivIdForOption(fileId, 'file'), visible)" />
                        </div>
                    </div>
                </template>
            </div>
            <div v-if="missingPeerFeedbackSubjects.orDefault([]).length > 0"
                 v-b-visible="visible => onVisible(getDivIdForOption(null, 'missing-wrapper'), visible)"
                 class="border-top-not-first"
                 :id="getDivIdForOption(null, 'missing-wrapper')">
                <div class="font-weight-bold p-3 mb-3 text-center border-bottom">
                    Missing students
                </div>
                <div class="px-3">
                    <p>
                        The following student(s) were assigned to
                        <cg-user :user="user" />, but did not receive any
                        feedback:
                    </p>

                    <ul>
                        <li v-for="subject, idx in missingPeerFeedbackSubjects.orDefault([])"
                            :id="getDivIdForOption(subject.id, 'subject')"
                            :key="subject.id">
                            <cg-user :user="subject" />
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    <div class="scroller-wrapper"
         slot="secondPane">
        <div class="scroller">
            <outline-viewer :options="outlineOptions"
                            @goto-option="gotoOption"
                            :selected-option="selectedOption" >
                <template #option="{ option, open }">
                    <component :is="open ? 'b' : 'span'"
                               class="outline-option">
                        <code v-if="option.data.typ === 'file'">{{ option.data.name }}</code>
                        <template v-else-if="option.data.sub != null">
                            <cg-user :user="option.data.sub.user" />
                            <fa-icon name="exclamation-triangle"
                                     class="text-warning ml-1"
                                     v-b-popover.top.hover="'This is not the latest submission'"
                                     v-if="!isLatest(option.data.sub)"/>
                        </template>
                        <template v-else-if="option.data.typ == 'missing-subject'">
                            <cg-user :user="option.data.user" />
                        </template>
                        <template v-else-if="option.data.typ == 'wrapper'">
                            <span>{{ option.data.text }}</span>
                        </template>
                        <span v-else>&hellip;</span>
                    </component>
                </template>
            </outline-viewer>
        </div>
    </div>
</rs-panes>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';
import { mapActions, mapGetters } from 'vuex';

// @ts-ignore
import ResSplitPane from 'vue-resize-split-pane';

import 'vue-awesome/icons/exclamation-triangle';

import * as models from '@/models';
import { Maybe } from '@/utils';

import { FeedbackStore } from '@/store/modules/feedback';
import { PeerFeedbackStore } from '@/store/modules/peer_feedback';

// @ts-ignore
import FeedbackOverview from './FeedbackOverview';

// @ts-ignore
import LateSubmissionIcon from './LateSubmissionIcon';

import OutlineViewer, { OutlineOption } from './OutlineViewer';

@Component({
    methods: {
        ...mapActions('submissions', ['loadGivenSubmissions']),
        ...mapActions('fileTrees', ['loadFileTree']),
    },
    computed: {
        ...mapGetters('submissions', ['getSingleSubmission', 'getIsLatestSubmissionByUser']),
    },
    components: {
        FeedbackOverview,
        LateSubmissionIcon,
        OutlineViewer,
        'rs-panes': ResSplitPane,
    },
})
export default class PeerFeedbackByUser extends Vue {
    @Prop({ required: true }) assignment!: models.Assignment;

    @Prop({ required: true }) user!: models.User;

    @Prop({ required: true }) contextLines!: number;

    @Prop({ required: true }) showWhitespace!: boolean;

    @Prop({ required: true }) showInlineFeedback!: boolean;

    private loadGivenSubmissions!: (d: {
        assignmentId: number,
        submissionIds: ReadonlyArray<number>,
        onError?: (err: Error, subId: number) => void,
    }) => Promise<void>;

    private loadFileTree!: (d: { assignmentId: number, submissionId: number, force?: boolean }) =>
        Promise<void>;

    private getSingleSubmission!: (submissionId: number) => models.Submission | null;

    private getIsLatestSubmissionByUser!: (submission: models.Submission) => boolean;

    private errors: Record<number, Error> = {};

    private visibleDivs: Record<string, boolean> = {};

    private scrollTop: number = 0;

    private scrollDirection: 'up' | 'down' = 'up';

    private uniqueId: number = this.$utils.getUniqueId();

    get assignmentId(): number {
        return this.assignment.id;
    }

    get userId(): number {
        return this.user.id;
    }

    @Watch('assignmentId', { immediate: true })
    onAssignmentIdChanged() {
        this.loadData();
    }

    @Watch('userId')
    onUserIdChanged() {
        this.loadData();
    }

    loadData() {
        Promise.all([
            FeedbackStore.loadInlineFeedbackByUser(
                { assignmentId: this.assignmentId, userId: this.userId },
            ),
            PeerFeedbackStore.loadConnectionsForUser(
                { assignmentId: this.assignmentId, userId: this.userId },
            ),
        ]);
    }

    get peerFeedbackConnections(): Maybe<readonly models.AnyUser[]> {
        return PeerFeedbackStore.getConnectionsForUser()(
            this.assignmentId, this.userId,
        );
    }

    get missingPeerFeedbackSubjects(): Maybe<readonly models.AnyUser[]> {
        return this.submissionById.map(
            subsById => new Set(Object.values(subsById).map(sub => sub?.user.id)),
        ).chain(
            usersWithFeedback => this.peerFeedbackConnections.map(
                users => users.filter(u => !usersWithFeedback.has(u.id)),
            ),
        );
    }

    onScroll() {
        const referenceNode = this.$refs.scroller as any;
        const newScrollTop = referenceNode.scrollTop;
        const diff = newScrollTop - this.scrollTop;

        if (diff === 0) {
            return;
        } else if (diff < 0) {
            this.scrollDirection = 'up';
        } else if (diff > 0) {
            this.scrollDirection = 'down';
        }
        this.scrollTop = newScrollTop;
    }

    get submissionIds(): Maybe<ReadonlyArray<number>> {
        const ids = FeedbackStore.getSubmissionWithFeedbackByUser()(
            this.assignmentId, this.userId,
        );
        if (ids == null) {
            return this.$utils.Nothing;
        }
        return this.$utils.Just(Object.keys(ids).map(x => parseInt(x, 10)).filter(subId => {
            const sub = this.getSingleSubmission(subId);
            return sub == null || !this.user.isEqualOrMemberOf(sub.user);
        }));
    }

    @Watch('submissionIds', { immediate: true })
    onChangedSubmissionIds(): void {
        this.submissionIds.ifJust(submissionIds => {
            this.errors = {};

            Promise.all([
                this.loadGivenSubmissions({
                    assignmentId: this.assignmentId,
                    submissionIds,
                    onError: (err, subId) => {
                        this.$utils.vueSet(this.errors, subId, err);
                    },
                }),
                ...submissionIds.map(
                    subId => Promise.all([
                        this.loadFileTree({
                            submissionId: subId,
                            assignmentId: this.assignmentId,
                        }),
                        FeedbackStore.loadFeedback({
                            submissionId: subId,
                            assignmentId: this.assignmentId,
                        }),
                    ]).catch(err => {
                        this.$utils.vueSet(this.errors, subId, err);
                    }),
                ),
            ]);
        });
    }

    get submissionById(): Maybe<Record<number, models.Submission | null>> {
        return this.submissionIds.map(
            ids => this.$utils.mapToObject(
                ids,
                subId => [subId, this.getSingleSubmission(subId)],
                {} as Record<number, models.Submission | null>,
            ),
        );
    }

    get sortedSubmissionIds(): ReadonlyArray<number> {
        const lookup = this.submissionById.orDefault({});
        const epoch = this.$utils.epoch();

        return this.$utils.sortBy(
            this.submissionIds.orDefault([]),
            subId => {
                const sub = lookup[subId];
                const err = this.errors[subId];
                return [
                    err != null,
                    sub != null,
                    sub?.user.readableName ?? '',
                    sub?.createdAt ?? epoch,
                    sub?.assignment.id ?? 0,
                ];
            },
            {
                reversePerKey: [false, false, false, true, false],
            },
        );
    }

    get loading(): boolean {
        if (this.peerFeedbackConnections.isNothing()) {
            return true;
        }

        return this.submissionIds.map(
            subIds => subIds.some(subId => subId == null),
        ).orDefault(false);
    }

    isLatest(sub: models.Submission) {
        return this.getIsLatestSubmissionByUser(sub);
    }

    onVisible(divId: string, visible: boolean) {
        const existing = this.visibleDivs[divId];
        if (visible !== existing) {
            this.$utils.vueSet(this.visibleDivs, divId, visible);
        }
    }

    getAmountDivVisible(div: HTMLElement | null) {
        if (div == null) {
            return 0;
        }
        const referenceNode = this.$refs.scroller as any;
        const pos = div.getBoundingClientRect();
        const referencePos = referenceNode.getBoundingClientRect();

        return Math.min(
            div.clientHeight,
            referencePos.top + referenceNode.clientHeight - pos.top,
            div.clientHeight - (referencePos.top - pos.top),
        );
    }

    get selectedOption(): string | null {
        if (!this.completelyLoaded) {
            return null;
        }
        // eslint-disable-next-line
        this.scrollTop;

        const iter = <T, Y>(
            arr: ReadonlyArray<T>,
            cb: (item: T) => boolean | undefined,
        ): boolean => {
            const len = arr.length;
            switch (this.scrollDirection) {
            case 'up': {
                for (let i = 0; i < len; ++i) {
                    const res = cb(arr[i]);
                    if (res) {
                        return true;
                    }
                }
                break;
            }
            case 'down': {
                for (let i = len - 1; i >= 0; --i) {
                    const res = cb(arr[i]);
                    if (res) {
                        return true;
                    }
                }
                break;
            }
            default: {
                this.$utils.AssertionError.assertNever(this.scrollDirection);
            }
            }
            return false;
        };

        let found = null;
        let foundHeight = -Infinity;

        const processOption = (option: OutlineOption): boolean => {
            const divId = option.data.divId;
            if (this.visibleDivs[divId]) {
                const div = document.getElementById(divId);
                const divHeight = this.getAmountDivVisible(div);
                // If we have a div that is completely visible we always prefer it.
                if (div != null && divHeight === div.clientHeight) {
                    found = option.id;
                    return true;
                }
                if (divHeight - 200 > foundHeight) {
                    found = option.id;
                    foundHeight = divHeight;
                }
            }
            return false;
        };

        iter(this.outlineOptions, (outlineOption: OutlineOption): boolean => {
            if (outlineOption.children != null) {
                return iter(
                    outlineOption.children,
                    option => processOption(option),
                );
            } else {
                return processOption(outlineOption);
            }
        });

        return found;
    }

    get outlineOptions() {
        const lookup = this.submissionById.orDefault({});
        const completelyLoaded = this.completelyLoaded;

        return (this.sortedSubmissionIds).map(subId => {
            const sub = lookup[subId];
            const base: OutlineOption = {
                id: `sub-${subId}`,
                data: {
                    typ: 'sub',
                    divId: this.getDivIdForOption(subId, 'sub'),
                },
            };
            if (sub == null) {
                return base;
            }

            base.data.sub = sub;
            const feedback = sub.feedback;
            const fileTree = sub.fileTree;
            if (feedback != null && fileTree != null && completelyLoaded) {
                base.children = Object.keys(feedback.user).map(fileId => ({
                    id: `file-${fileId}`,
                    data: {
                        typ: 'file',
                        name: fileTree.flattened[fileId],
                        divId: this.getDivIdForOption(fileId, 'file'),
                    },
                }));
            }

            return base;
        }).concat(this.missingPeerFeedbackSubjects.map(
            subjects => {
                if (subjects.length > 0 && completelyLoaded) {
                    return [{
                        id: 'missings-wrapper',
                        data: {
                            typ: 'wrapper',
                            divId: this.getDivIdForOption(null, 'missing-wrapper'),
                            text: 'Missing students',
                        },
                    }];
                }
                return [];
            },
        ).orDefault([]));
    }

    get completelyLoaded(): boolean {
        return this.submissionById.chain(
            lookup => this.submissionIds.map(
                subIds => subIds.every(subId => {
                    if (this.errors[subId]) {
                        return true;
                    }
                    const sub = lookup[subId];
                    if (sub == null) {
                        return false;
                    }

                    const feedback = sub.feedback;
                    const fileTree = sub.fileTree;
                    if (feedback == null || fileTree == null) {
                        return false;
                    }

                    return true;
                }),
            ),
        ).orDefault(false);
    }

    // eslint-disable-next-line
    gotoOption(option: OutlineOption) {
        const { divId } = option.data;

        if (divId) {
            const div = document.getElementById(divId);
            if (div) {
                div.scrollIntoView({ block: 'start', behavior: 'smooth' });
            }
        }
    }

    shouldRenderThread(thread: models.FeedbackLine) {
        return thread.replies.some(reply => !this.shouldFadeReply(thread, reply));
    }

    shouldFadeReply(thread: models.FeedbackLine, reply: models.FeedbackReply) {
        const author = reply.author;
        if (author == null) {
            return true;
        }
        return !this.user.isEqualOrMemberOf(author);
    }

    getDivIdForOption(itemId: string | number | null, option: 'file' | 'subject' | 'sub' | 'missing-wrapper') {
        switch (option) {
        case 'file':
            return `inner-feedback-overview-file-${itemId}`;
        case 'sub':
            return `peer-feedback-by-user-sub-${itemId}-${this.uniqueId}`;
        case 'subject':
            return `missing-subject-${itemId}-${this.uniqueId}`;
        case 'missing-wrapper':
            return `missing-wrapper-${this.uniqueId}`;
        default:
            return this.$utils.AssertionError.assertNever(option);
        }
    }
}
</script>


<style lang="less" scoped>
@import "~mixins.less";

.user-card:not(:last-child) {
    margin-bottom: 1rem;
}

.scroller {
    width: 100%;
    overflow: auto;
    flex: 1 1 auto;
}

.scroller-wrapper {
    overflow: hidden;
    position: relative;
    flex: 1 1 auto;
    display: flex;
    width: 100%;
    max-height: 100%;
}

.outline-option:hover {
    text-decoration: underline;
}

.border-top-not-first:not(:first-child) {
    border-top: 1px solid @border-color;

    @{dark-mode} {
        border-top-color: @color-primary-darker;
    }
}
</style>

<style lang="less">
.peer-feedback-by-user .submission-wrapper {
    .feedback-overview {
        border-radius: 0 !important;
        border-left: none !important;
        border-right: none !important;
    }
    &:first-child .feedback-overview {
        border-top: none !important;
    }
    &:last-child .feedback-overview {
        border-bottom: none !important;
    }
}

.peer-feedback-by-user .outline-option:hover .name-user {
    text-decoration: underline;
}


.peer-feedback-by-user {
    &.pane-rs {
        position: relative;

        &.rows {
            padding-left: 15px;
            padding-right: 15px;
        }
    }

    &.pane-rs > .Resizer {
        z-index: 0;
    }

    &.pane-rs > .Resizer {
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
}
</style>
