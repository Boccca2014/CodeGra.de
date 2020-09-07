<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="user-notifications">
    <b-collapse :visible="showSettings">
        <div class="border-bottom notification-settings-wrapper">
            <notification-settings class="px-3 pt-3" />
        </div>
    </b-collapse>

    <cg-loader v-if="loading"
               :scale="1"
               class="p-3"/>
    <div v-else class="p-3">
        <div v-if="!hasUnreadNotifications"
             class="text-muted">
            You are all caught up!
            <hr v-if="hasReadNotifications"  />
        </div>

        <div class="border rounded" v-if="notifications.length > 0">
            <table class="table table-hover table-borderless mb-0"
                   :class="{ disabled }">
                <transition-group :name="goingToSubmission != null ? '' : 'fade'" tag="tbody">
                    <template v-for="notification in notifications">
                        <tr v-if="goingToSubmission === notification.id"
                            :class="{ disabled }"
                            :key="notification.id">
                            <td colspan="4">
                                <cg-loader :scale="1"/>
                            </td>
                        </tr>
                        <user-notification :notification="notification"
                                           v-else
                                           :key="notification.id"
                                           @click.native="gotoNotification(notification)"
                                           :class="{ read: notification.read, disabled }" />
                    </template>
                </transition-group>
            </table>
        </div>

        <div v-if="hasReadNotifications && !showRead"
             class="d-flex justify-content-center mt-3">
            <b-btn @click="showRead = true">
                Show read notifications
            </b-btn>
        </div>
    </div>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop } from 'vue-property-decorator';

import { Location } from 'vue-router';
import { NotificationStore } from '@/store/modules/notification';
import { AssignmentsStore } from '@/store/modules/assignments';

import * as models from '@/models';

import UserNotification from './UserNotification';
import NotificationSettings from './NotificationSettings';

@Component({
    components: {
        UserNotification,
        NotificationSettings,
    },
})
export default class UserNotifications extends Vue {
    @Prop({ required: true }) showSettings!: boolean;

    // eslint-disable-next-line
    get allNotifications(): ReadonlyArray<models.Notification> {
        return NotificationStore.getAllNotifications();
    }

    // eslint-disable-next-line
    get unreadNotifications(): ReadonlyArray<models.Notification> {
        return NotificationStore.getAllUnreadNotifications();
    }

    // eslint-disable-next-line
    get hasUnreadNotifications(): boolean {
        return NotificationStore.getHasUnreadNotifications();
    }

    get hasReadNotifications() {
        return this.allNotifications.length > this.unreadNotifications.length;
    }

    get notifications() {
        return this.showRead ? this.allNotifications : this.unreadNotifications;
    }

    get disabled(): boolean {
        return this.goingToSubmission != null;
    }

    loading: boolean = true;

    disableAnimations: boolean = false;

    goingToSubmission: number | null = null;

    showRead: boolean = false;

    isDestroyed: boolean = false;

    destroyed() {
        this.$root.$loadFullNotifications = false;
        this.isDestroyed = true;
    }

    async created() {
        this.loading = true;
        this.$root.$loadFullNotifications = true;
        await NotificationStore.dispatchLoadNotifications();
        this.loading = false;
    }

    // eslint-disable-next-line class-methods-use-this
    getNotificationRoute(notification: models.Notification): Location | null {
        return notification.assignment.mapOrDefault(
            assig => ({
                name: 'submission_file',
                params: {
                    courseId: assig.courseId.toString(),
                    assignmentId: assig.id.toString(),
                    submissionId: `${notification.submission?.id}`,
                    fileId: notification.fileId,
                },
                query: {
                    replyToFocus: `${notification.commentReply?.id}`,
                },
                hash: '#code',
            }),
            null,
        );
    }

    async gotoNotification(notification: models.Notification): Promise<void> {
        const assignmentId = notification.assignmentId;
        const submissionId = notification.submissionId;
        this.goingToSubmission = notification.id;

        notification.markAsRead().then(({ cgResult }) => {
            NotificationStore.commitUpdateNotifications({
                notifications: [cgResult],
            });
        });

        await Promise.all([
            AssignmentsStore.loadSingleAssignment({
                assignmentId: notification.assignmentId,
            }),
            this.$store.dispatch('feedback/loadFeedback', {
                assignmentId,
                submissionId,
                force: true,
            }).catch(() => null),
        ]);

        const location = this.getNotificationRoute(notification);
        if (location == null) {
            this.$utils.withSentry(Sentry => {
                Sentry.captureMessage('Could not create link to notification');
            });
        } else {
            this.$router.push(location);
            this.$root.$emit('cg::sidebar::close');
        }
    }
}
</script>

<style lang="less" scoped>
@import '~mixins.less';

.notification-settings-wrapper {
    background-color: @footer-color;
}

.list-group-item:hover {
    background-color: @color-lightest-gray;
}

.list-group-item.read {
    background-color: @color-lighter-gray;
    &:hover {
        background-color: darken(@color-lighter-gray, 5%);
    }
}

.fade-enter-active,
.fade-leave-active {
    transition: opacity @transition-duration;
}
.fade-enter,
.fade-leave-to {
    opacity: 0;
}

.disabled {
    cursor: not-allowed;
}

tr {
    cursor: pointer;
    &.disabled {
        cursor: not-allowed;
        pointer-events: none;
    }
}
</style>
