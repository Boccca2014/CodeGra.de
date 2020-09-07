<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<tr class="user-notification"
    :class="{ read: notification.read }"
    v-b-visible="onVisible">
    <template>
        <td class="notification-icon-wrapper pl-4">
            <icon name="commenting" class="notification-icon"/>
        </td>

        <td v-if="loading" class="loader-wrapper">
            <cg-loader :scale="1" />
        </td>
        <td v-else>
            <div class="text-muted">
                Submission by <cg-user :user="notification.submission.user" text-when-you="you" />
                for
                <router-link :to="assignmentToLink"
                             @click.native.stop>
                    "{{ assignment.extract().name }}"
                </router-link>
            </div>

            <div>
                <template v-if="notification.commentReply.author">
                    <cg-user :user="notification.commentReply.author" />
                </template>
                <template v-else>
                    Someone
                </template>
                commented on an inline feedback thread you are following.
            </div>
        </td>

        <td class="text-right badge-wrapper">
            <b-badge v-for="[reason, explanation] in notification.reasons"
                     class="px-2 py-1"
                     :title="$utils.capitalize(explanation)"
                     :key="reason">
                {{ reason }}
            </b-badge>
        </td>

        <td class="created-at-wrapper shrink pr-4"
             :class="{ submitting: submitting, 'created-at-only': notification.read }">
            <cg-relative-time class="created-at"
                              :date="notification.createdAt" />
            <cg-submit-button :submit="markAsRead"
                              @after-error="afterSubmit"
                              class="px-2"
                              ref="submitButton"
                              v-b-popover.top.hover="'Mark as read'"
                              @after-success="afterDismmissNotification">
                <icon name="eye" />
            </cg-submit-button>
        </td>
    </template>
</tr>
</template>

<script lang="ts">
// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/eye';
import 'vue-awesome/icons/commenting';

import { Vue, Component, Prop, Watch } from 'vue-property-decorator';

import * as models from '@/models';
import { NotificationStore } from '@/store/modules/notification';
import { AssignmentsStore } from '@/store/modules/assignments';
import { SubmitButtonResult } from '@/interfaces';
import { Maybe } from '@/utils';

@Component({
    components: {
        Icon,
    },
})
export default class UserNotification extends Vue {
    @Prop({ required: true }) notification!: models.Notification;

    get submission(): models.Submission | undefined {
        return this.notification.submission;
    }

    get assignment(): Maybe<models.Assignment> {
        return this.notification.assignment;
    }

    get loading(): boolean {
        return this.assignment == null || this.submission == null;
    }

    public submitting = false;

    @Watch('notification')
    onNewNotification() {
        this.submitting = false;
    }

    markAsRead() {
        this.submitting = true;
        return this.notification.markAsRead();
    }

    afterSubmit() {
        this.submitting = false;
    }

    get whyNotification(): string {
        const me = models.NormalUser.getCurrentUser();
        if (this.submission == null) {
            return '';
        }

        const author = this.submission.user;
        const assignee = this.submission.assignee;

        if (me.isEqualOrMemberOf(author)) {
            if (author?.isGroup) {
                return 'one of the authors of the submission';
            } else {
                return 'author of the submission';
            }
        } else if (assignee != null && me.isEqualOrMemberOf(assignee)) {
            return 'the assignee of the submission';
        } else {
            return '';
        }
    }

    get assignmentToLink() {
        return this.assignment.mapOrDefault(
            assignment => ({
                name: 'assignment_submissions',
                params: {
                    courseId: assignment.courseId,
                    assignmentId: assignment.id,
                },
                query: {},
                hash: undefined,
            }),
            undefined,
        );
    }

    onVisible(isVisible: boolean) {
        if (this.loading && isVisible) {
            AssignmentsStore.loadSingleAssignment({
                assignmentId: this.notification.assignmentId,
            });
            this.$store.dispatch('submissions/loadSingleSubmission', {
                assignmentId: this.notification.assignmentId,
                submissionId: this.notification.submissionId,
            });
        }
    }

    // eslint-disable-next-line class-methods-use-this
    afterDismmissNotification(result: SubmitButtonResult<models.Notification>): void {
        this.submitting = false;
        NotificationStore.commitUpdateNotifications({ notifications: [result.cgResult] });
    }
}
</script>

<style lang="less" scoped>
@import '~mixins.less';

.badge-wrapper,
.loader-wrapper,
.created-at-wrapper,
.notification-icon-wrapper {
    vertical-align: middle;
}

@media @media-medium {
    .badge-wrapper {
        white-space: nowrap;
        .badge:not(:first-child) {
            margin-left: 0.25rem;
        }
    }
}

.user-notification.read {
    color: @text-color-muted;
}
.user-notification:not(.read) .notification-icon {
    color: @color-warning-dark;
}

.created-at-wrapper {
    position: relative;
    text-align: right;
    vertical-align: middle;

    .created-at, .submit-button {
        transition: opacity 0ms;
    }

    .created-at {
        opacity: 1;
    }

    &:not(.created-at-only).submitting,
    .user-notification:hover &:not(.created-at-only) {
        .created-at {
            opacity: 0;
        }

        .submit-button {
            opacity: 1;
        }
    }

    .submit-button {
        opacity: 0;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);

        &, &:hover {
            border: none;
            padding: 0;
        }
    }
}

.badge {
    text-transform: uppercase;
    font-size: 70%;
}
</style>
