/* SPDX-License-Identifier: AGPL-3.0-only */
import { NotificationState } from './modules/notification';

export interface RootState {
    notification: NotificationState;
    submissions: any;
}
