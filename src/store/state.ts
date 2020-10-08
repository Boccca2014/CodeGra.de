/* SPDX-License-Identifier: AGPL-3.0-only */
import { NotificationState } from './modules/notification';
import { CoursesState } from './modules/courses';
import { AssignmentState } from './modules/assignments';
import { FeedbackState } from './modules/feedback';
import { GradersState } from './modules/graders';
import { PeerFeedbackState } from './modules/peer_feedback';
import { UIPrefsState } from './modules/ui_prefs';

export interface RootState {
    notification: NotificationState;
    courses: CoursesState;
    assignments: AssignmentState;
    feedback: FeedbackState;
    graders: GradersState;
    // eslint-disable-next-line camelcase
    peer_feedback: PeerFeedbackState;
    // eslint-disable-next-line camelcase
    ui_prefs: UIPrefsState;

    submissions: any;
    user: any;
    pref: any;
}
