/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';

import { AnyUser } from './user';
import { Assignment } from './assignment';
import { Feedback } from './feedback';
import { FileTree } from './fileTree';

/* eslint-disable camelcase */
export class Submission {
    public id: number;

    public user: AnyUser;

    public origin: 'github' | 'gitlab' | 'files';

    public comment: string | null;

    public grade_overridden: string | null;

    public assignmentId: number;

    public assignment: Assignment;

    public extra_info: Record<string, Object> | null;

    public assignee: AnyUser;

    public comment_author: AnyUser | null;

    public feedback?: Feedback;

    public fileTree?: FileTree;

    public createdAt: moment.Moment;
}
/* eslint-enable camelcase */
