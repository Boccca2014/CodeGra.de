/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';
import axios from 'axios';

import { SubmitButtonResult } from '@/interfaces';

import { store, AssignmentsStore } from '@/store';
import { FeedbackReplyServerData, FeedbackReply } from '@/models/feedback';
import { Assignment } from '@/models/assignment';
import { Maybe } from '@/utils';

import { Submission } from './submission';

export type NotificationReason = 'author' | 'replied' | 'assignee';

/* eslint-disable camelcase */
export interface CommentNotificationServerData {
    id: number;
    type: 'comment_notification';
    created_at: string;
    comment_base_id: number;
    work_id: number;
    assignment_id: number;
    comment_reply: FeedbackReplyServerData;
    read: boolean;
    file_id: number;
    reasons: [NotificationReason, string][];
}
/* eslint-enable camelcase */

export class CommentNotification {
    constructor(
        public readonly id: number,
        public readonly commentReply: FeedbackReply,
        public readonly submissionId: number,
        public readonly assignmentId: number,
        public readonly createdAt: moment.Moment,
        public readonly read: boolean,
        public readonly fileId: string,
        private readonly reasons: [NotificationReason, string][],
    ) {
        Object.freeze(this.reasons);
        Object.freeze(this);
    }

    static fromServerData(data: CommentNotificationServerData) {
        return new CommentNotification(
            data.id,
            FeedbackReply.fromServerData(data.comment_reply, data.comment_base_id),
            data.work_id,
            data.assignment_id,
            moment.utc(data.created_at, moment.ISO_8601),
            data.read,
            `${data.file_id}`,
            data.reasons,
        );
    }

    async markAsRead(): Promise<SubmitButtonResult<Notification>> {
        const response = await axios.patch(`/api/v1/notifications/${this.id}`, {
            read: true,
        });

        return {
            ...response,
            cgResult: CommentNotification.fromServerData(response.data),
        };
    }

    get assignment(): Maybe<Assignment> {
        return AssignmentsStore.getAssignment()(this.assignmentId);
    }

    get submission(): Submission | undefined {
        return store.getters['submissions/getSingleSubmission'](
            this.assignmentId,
            this.submissionId,
        );
    }
}

export type Notification = CommentNotification;
