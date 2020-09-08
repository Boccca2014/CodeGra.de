/* SPDX-License-Identifier: AGPL-3.0-only */
import { NotificationState } from './modules/notification';
import { CoursesState } from './modules/courses';
import { AssignmentState } from './modules/assignments';
import { FeedbackState } from './modules/feedback';
import { GradersState } from './modules/graders';
import { PeerFeedbackState } from './modules/peer_feedback';

export interface RootState {
    notification: NotificationState;
    courses: CoursesState;
    assignments: AssignmentState;
    feedback: FeedbackState;
    graders: GradersState;
    peer_feedback: PeerFeedbackState;

    submissions: any;
    user: any;
    pref: any;
}
