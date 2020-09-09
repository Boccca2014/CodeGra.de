<template>
<b-alert
    v-if="error != null"
    variant="danger"
    show>
    {{ $utils.getErrorMessage(this.error) }}
</b-alert>
<cg-loader page-loader v-else-if="loading" />
<div v-else
     class="peer-feedback-overview">
    <table class="table table-striped table-hover">
        <thead>
            <tr>
                <th>User</th>
                <th class="shrink"># Comments</th>
            </tr>
        </thead>

        <tbody>
            <tr v-for="sub in latestSubmissions" :key="sub.id"
                @click="gotoSubmission(sub)">
                <td>
                    <cg-user :user="sub.user" />
                </td>
                <td class="text-center shrink">
                    <b-badge :variant="getBadgeVariant(commentsPerStudent[sub.user.id])"
                             v-b-popover.hover.top="getBadgePopover(commentsPerStudent[sub.user.id])">
                        {{ commentsPerStudent[sub.user.id].latest }}
                    </b-badge>
                </td>
            </tr>
        </tbody>

        <tfoot>
            <tr>
                <td colspan="2">
                    This lists all the students that you have been assigned to
                    give peer feedback.

                    <template v-if="peerFeedbackDeadline != null">
                        You have until {{ peerFeedbackDeadline }} to complete
                        your feedback.
                    </template>
                </td>
            </tr>
        </tfoot>
    </table>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';
import { mapActions, mapGetters } from 'vuex';
import * as models from '@/models';
import { defaultdict } from '@/utils/defaultdict';

import { FeedbackStore } from '@/store/modules/feedback';

type PeerFeedbackCommentCount = {
    all: number;
    latest: number;
    nonLatest: number;
} | {
    all: '-';
    latest: '-';
    nonLatest: '-';
};

@Component({
    methods: {
        ...mapActions('submissions', ['loadGivenSubmissions']),
    },
    computed: {
        ...mapGetters('user', { userId: 'id', userPerms: 'permissions' }),
        ...mapGetters('submissions', ['getLatestSubmissions', 'getSubmissionsByUser']),
    },
})
export default class PeerFeedbackOverview extends Vue {
    @Prop({ required: true })
    assignment!: models.Assignment;

    userId!: number;

    userPerms!: Record<number, boolean>;

    loadGivenSubmissions!: (args: {
        assignmentId: number;
        submissionIds: number[];
    }) => Promise<unknown>;

    getLatestSubmissions!: (assignmentId: number) => models.Submission[];

    getSubmissionsByUser!: (assignmentId: number, userId: number) => models.Submission[];

    error: Error | null = null;

    get assignmentId() {
        return this.assignment.id;
    }

    @Watch('assignmentId', { immediate: true })
    onAssignmentIdChanged() {
        this.loadData();
    }

    get loading() {
        return this.latestSubmissions == null;
    }

    // eslint-disable-next-line class-methods-use-this
    get latestSubmissions() {
        return this.$utils.sortBy(
            this.getLatestSubmissions(this.assignmentId).filter(
                s => s.user.id !== this.userId,
            ),
            sub => [sub.user.readableName],
        );
    }

    get commentsPerSubmission() {
        return FeedbackStore.getSubmissionWithFeedbackByUser()(
            this.assignmentId,
            this.userId,
        );
    }

    get commentsPerStudent(): Record<number, PeerFeedbackCommentCount> {
        const fb = this.commentsPerSubmission;

        if (fb == null) {
            return defaultdict(() => ({ all: '-', latest: '-', nonLatest: '-' }));
        }

        return this.$utils.mapToObject(this.latestSubmissions, sub => {
            const user = sub.user;
            const subs = this.getSubmissionsByUser(this.assignmentId, user.id);

            const onLatest = fb[sub.id] ?? 0;
            const onAllSubs = subs.reduce((acc, s) => acc + (fb[s.id] ?? 0), 0);

            return [user.id, {
                latest: onLatest,
                nonLatest: onAllSubs - onLatest,
                all: onAllSubs,
            }];
        });
    }

    get peerFeedbackDeadline() {
        if (this.assignment.peerFeedbackDeadline == null) {
            return null;
        }
        return this.$utils.readableFormatDate(this.assignment.peerFeedbackDeadline);
    }

    loadData() {
        return FeedbackStore.loadInlineFeedbackByUser({
            assignmentId: this.assignmentId,
            userId: this.userId,
        }).then(() => {
            this.error = null;
            // For some reason the commentsPerSubmission mapping contains a Symbol as key...
            const subIds = Object.keys(this.commentsPerSubmission || {})
                .map(x => parseInt(x, 10))
                .filter(x => !Number.isNaN(x));
            return this.loadGivenSubmissions({
                assignmentId: this.assignmentId,
                submissionIds: subIds,
            });
        }).catch(err => {
            this.error = err;
        });
    }

    gotoSubmission(sub: models.Submission) {
        this.$router.push({
            name: 'submission',
            params: { submissionId: sub.id.toString(10) },
            query: {
                peerFeedback: 'true',
            },
        });
    }

    // eslint-disable-next-line class-methods-use-this
    getBadgeVariant(comments: PeerFeedbackCommentCount) {
        const { latest, nonLatest } = comments;

        if (typeof latest !== 'number' || typeof nonLatest !== 'number') {
            return 'secondary';
        }

        if (comments.nonLatest > 0) {
            return 'warning';
        } else if (comments.latest > 0) {
            return 'primary';
        } else {
            return 'secondary';
        }
    }

    // eslint-disable-next-line class-methods-use-this
    getBadgePopover(comments: PeerFeedbackCommentCount) {
        if (typeof comments.nonLatest !== 'number') {
            return '';
        } else if (comments.nonLatest > 0) {
            return `You have also given ${comments.nonLatest} comments on older submissions.`;
        } else {
            return '';
        }
    }
}
</script>
