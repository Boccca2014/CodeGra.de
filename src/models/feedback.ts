/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';
import axios, { AxiosResponse } from 'axios';

// @ts-ignore-next
import DiffMatchPatch from 'diff-match-patch';

// @ts-ignore
import { setProps, coerceToString, getUniqueId, htmlEscape, withSentry, Maybe } from '@/utils';
import { NEWLINE_CHAR } from '@/utils/diff';
import { Assignment, Submission } from '@/models';

import { CoursePermission as CPerm } from '@/permissions';

import { store, PeerFeedbackStore } from '@/store';
import * as assignmentState from '@/store/assignment-states';
import { SubmitButtonResult } from '../interfaces';

import { User, AnyUser, UserServerData, NormalUser } from './user';

type ReplyTypes = 'plain_text' | 'markdown';

/* eslint-disable camelcase */
interface FeedbackReplyEditServerData {
    id: number;
    editor: UserServerData;
    old_text: string;
    new_text: string;
    created_at: string;
}

export interface FeedbackReplyServerData {
    id: number;
    comment: string;
    author_id: number | null;
    in_reply_to_id: number | null;
    last_edit: string | null;
    created_at: string;
    updated_at: string;
    reply_type: ReplyTypes;
    comment_type: 'normal' | 'peer_feedback';
    approved: boolean;

    author?: UserServerData;
}

export interface FeedbackLineServerData {
    id: number;
    file_id: string;
    work_id: number;
    line: number;
    replies: FeedbackReplyServerData[];
}

type LinterFeedbackServerData = Record<string, Record<string, [string, Record<string, any>][]>>;

export interface FeedbackServerData {
    general: string | null;
    linter: LinterFeedbackServerData;
    user: Array<FeedbackLine | FeedbackLineServerData>;
    authors: UserServerData[];
}
/* eslint-enable camelcase */

export class FeedbackReplyEdit {
    constructor(
        public readonly id: number,
        public readonly editorId: number,
        public readonly oldText: string,
        public readonly newText: string,
        public readonly createdAt: moment.Moment,
    ) {
        Object.freeze(this);
    }

    static fromServerData(data: FeedbackReplyEditServerData) {
        store.dispatch('users/addOrUpdateUser', { user: data.editor });
        return new FeedbackReplyEdit(
            data.id,
            data.editor.id,
            data.old_text,
            data.new_text,
            moment.utc(data.created_at, moment.ISO_8601),
        );
    }

    get editor(): AnyUser | null {
        return User.findUserById(this.editorId);
    }

    getDiffHtml(): string {
        const dmp = new DiffMatchPatch();
        const diff = dmp.diff_main(this.oldText, this.newText);
        dmp.diff_cleanupSemantic(diff);

        return diff
            .map(([state, txt]: [-1 | 0 | 1, string]) => {
                let cls: '' | 'removed' | 'added' = '';
                if (state === -1) {
                    cls = 'removed';
                } else if (state === 1) {
                    cls = 'added';
                }

                let innerTxt = txt;
                if (cls !== '') {
                    const innerReplace = (match: string) =>
                        match.replace(/\n/g, `${NEWLINE_CHAR}\n`);

                    innerTxt = txt.replace(/^\n+/, innerReplace).replace(/\n+$/, innerReplace);
                }

                return `<span class="${cls}">${htmlEscape(innerTxt)}</span>`;
            })
            .join('');
    }
}

// This should really be kept track of in the store, but that isn't really
// possible for now without rewriting that entire store unfortunately.
// This contains a mapping between serverId and trackingId.
const trackingIdLookup: Map<number, number> = new Map();

export class FeedbackReply {
    public readonly trackingId: number;

    constructor(
        oldTrackingId: number,
        public readonly id: number | null,
        public readonly inReplyToId: number | null,
        public readonly message: string,
        public readonly authorId: number | null,
        public readonly lastEdit: moment.Moment | null,
        public readonly replyType: ReplyTypes,
        public readonly createdAt: moment.Moment,
        private readonly feedbackLineId: number,
        public readonly commentType: 'normal' | 'peer_feedback',
        public readonly approved: boolean,
        public readonly deleted = false,
    ) {
        const foundTrackingId = trackingIdLookup.get(id ?? -1);
        if (foundTrackingId != null) {
            this.trackingId = foundTrackingId;
        } else {
            if (this.id != null) {
                trackingIdLookup.set(this.id, oldTrackingId);
            }
            this.trackingId = oldTrackingId;
        }
        Object.freeze(this);
    }

    static fromServerData(
        serverData: FeedbackReplyServerData,
        feedbackLineId: number,
        trackingId: number = getUniqueId(),
    ): FeedbackReply {
        if (serverData.author != null) {
            store.dispatch('users/addOrUpdateUser', { user: serverData.author });
        }

        return new FeedbackReply(
            trackingId,
            serverData.id,
            serverData.in_reply_to_id,
            serverData.comment,
            serverData.author_id,
            serverData.last_edit == null ? null : moment.utc(serverData.last_edit, moment.ISO_8601),
            serverData.reply_type,
            moment.utc(serverData.created_at, moment.ISO_8601),
            feedbackLineId,
            serverData.comment_type,
            serverData.approved,
        );
    }

    async fetchEdits(): Promise<SubmitButtonResult<FeedbackReplyEdit[]>> {
        if (this.id == null) {
            return Promise.reject(
                new Error("Cannot get edits of feedback that hasn't been saved."),
            );
        }
        const url = `/api/v1/comments/${this.feedbackLineId}/replies/${this.id}/edits/`;
        const response: AxiosResponse<FeedbackReplyEditServerData[]> = await axios.get(url);

        return {
            ...response,
            cgResult: response.data.map(d => FeedbackReplyEdit.fromServerData(d)),
        };
    }

    get isPeerFeedback() {
        return this.commentType === 'peer_feedback';
    }

    canSeeEdits(assignment: Assignment): boolean {
        const author = this.author;
        if (author?.isEqualOrMemberOf(NormalUser.getCurrentUser()) ?? false) {
            return true;
        }
        return assignment.hasPermission(CPerm.canViewOthersCommentEdits);
    }

    canEdit(assignment: Assignment): boolean {
        const author = this.author;
        if (author?.isEqualOrMemberOf(NormalUser.getCurrentUser()) ?? false) {
            return true;
        }
        return assignment.hasPermission(CPerm.canEditOthersComments);
    }

    canApprove(assignment: Assignment): boolean {
        if (this.commentType === 'normal') {
            return false;
        }
        return assignment.hasPermission(CPerm.canApproveInlineComments);
    }

    updateFromServerData(serverData: FeedbackReplyServerData): FeedbackReply {
        return FeedbackReply.fromServerData(serverData, this.feedbackLineId, this.trackingId);
    }

    get author(): AnyUser | null {
        return User.findUserById(this.authorId);
    }

    get isEmpty(): boolean {
        return !this.message;
    }

    _update(props: { message?: string; deleted?: boolean; approved?: boolean }): FeedbackReply {
        return new FeedbackReply(
            this.trackingId,
            this.id,
            this.inReplyToId,
            props?.message ?? this.message,
            this.authorId,
            this.lastEdit,
            this.replyType,
            this.createdAt,
            this.feedbackLineId,
            this.commentType,
            props?.approved ?? this.approved,
            props?.deleted ?? this.deleted,
        );
    }

    update(message: string): FeedbackReply {
        return this._update({ message });
    }

    approveAndSave(approved: boolean): Promise<SubmitButtonResult<FeedbackReply>> {
        let meth = axios.post;
        if (!approved) {
            meth = axios.delete;
        }
        if (this.id == null) {
            return Promise.reject(
                new Error("Cannot change approval of feedback that hasn't been saved."),
            );
        }
        return meth(`/api/v1/comments/${this.feedbackLineId}/replies/${this.id}/approval`).then(
            response => ({
                ...response,
                cgResult: FeedbackReply.fromServerData(
                    response.data,
                    this.feedbackLineId,
                    this.trackingId,
                ),
            }),
        );
    }

    markAsDeleted() {
        return this._update({ deleted: true });
    }

    delete(): Promise<object> {
        if (this.id == null) {
            return Promise.resolve({});
        }
        return axios.delete(`/api/v1/comments/${this.feedbackLineId}/replies/${this.id}`);
    }

    save(): Promise<object> {
        if (this.id == null) {
            return axios.post(`/api/v1/comments/${this.feedbackLineId}/replies/`, {
                comment: this.message,
                in_reply_to_id: this.inReplyToId,
                reply_type: this.replyType,
            });
        } else {
            return axios.patch(`/api/v1/comments/${this.feedbackLineId}/replies/${this.id}`, {
                comment: this.message,
            });
        }
    }

    static createEmpty(
        userId: number,
        feedbackLineId: number,
        isPeerFeedback: boolean = false,
    ): FeedbackReply {
        return new FeedbackReply(
            getUniqueId(),
            null,
            null,
            '',
            userId,
            null,
            'markdown',
            moment(),
            feedbackLineId,
            isPeerFeedback ? 'peer_feedback' : 'normal',
            isPeerFeedback,
        );
    }
}

export class FeedbackLine {
    constructor(
        public readonly id: number,
        public readonly fileId: string,
        public readonly line: number,
        public readonly replies: ReadonlyArray<FeedbackReply>,
        public readonly workId: number,
    ) {
        Object.freeze(this);
    }

    get isEmpty(): boolean {
        return !this.replies.some(reply => !reply.deleted);
    }

    get lineNumber(): number {
        return this.line;
    }

    static fromServerData(data: FeedbackLineServerData): FeedbackLine {
        const replies = Object.freeze(
            data.replies.map(r => FeedbackReply.fromServerData(r, data.id)),
        );
        return new FeedbackLine(
            data.id,
            coerceToString(data.file_id),
            data.line,
            replies,
            data.work_id,
        );
    }

    deleteReply(updatedReply: FeedbackReply): FeedbackLine {
        const replies = this.replies.map(r => {
            if (r.trackingId === updatedReply.trackingId) {
                return r.markAsDeleted();
            }
            return r;
        });
        return new FeedbackLine(
            this.id,
            this.fileId,
            this.line,
            Object.freeze(replies),
            this.workId,
        );
    }

    updateReply(updatedReply: FeedbackReply): FeedbackLine {
        const replies = this.replies.map(r => {
            if (r.trackingId === updatedReply.trackingId) {
                return updatedReply;
            }
            return r;
        });
        return new FeedbackLine(
            this.id,
            this.fileId,
            this.line,
            Object.freeze(replies),
            this.workId,
        );
    }

    static canAddReply(submission: Submission, now: moment.Moment) {
        const assignment: Assignment = submission.assignment;

        const currentUser: Maybe<NormalUser> = store.getters['user/currentUser'];
        // @ts-ignore
        const author: AnyUser = submission.user;
        const perms = [CPerm.canGradeWork];

        if (author.isEqualOrMemberOf(NormalUser.getCurrentUser())) {
            perms.push(CPerm.canAddOwnInlineComments);
        }
        if (perms.some(x => assignment.hasPermission(x))) {
            return true;
        }

        const submissionIsOwn = currentUser.map(u => submission.user.isEqualOrMemberOf(u));
        if (submissionIsOwn.orDefault(false)) {
            return false;
        }

        if (assignment.peer_feedback_settings != null) {
            const userId = store.getters['user/id'];
            const connections = PeerFeedbackStore.getConnectionsForUser()(assignment.id, userId);

            connections.ifNothing(() => {
                withSentry(sentry => {
                    sentry.captureMessage('Peer feedback connections were not yet loaded');
                });
                PeerFeedbackStore.loadConnectionsForUser({
                    userId,
                    assignmentId: assignment.id,
                });
            });

            const hasConnection = connections
                .map(conns => conns.some(user => user.id === author.id))
                .orDefault(true);

            if (!hasConnection) {
                return false;
            }

            if (!assignment.deadlinePassed(now)) {
                return false;
            }
            if (assignment.peerFeedbackDeadlinePassed(now)) {
                return false;
            }

            if (assignment.state === assignmentState.DONE) {
                return false;
            }

            return true;
        }

        return false;
    }

    addReply(newReply: FeedbackReply): FeedbackLine {
        return new FeedbackLine(
            this.id,
            this.fileId,
            this.line,
            Object.freeze(this.replies.concat(newReply)),
            this.workId,
        );
    }

    static async createFeedbackLine(
        fileId: number,
        line: number,
        userId: number,
    ): Promise<SubmitButtonResult<FeedbackLine>> {
        const response = await axios.put('/api/v1/comments/', {
            file_id: fileId,
            line,
        });
        const feedbackLine = FeedbackLine.fromServerData(response.data);

        return {
            ...response,
            cgResult: feedbackLine.addReply(FeedbackReply.createEmpty(userId, feedbackLine.id)),
        };
    }
}

export class Feedback {
    readonly userLines: ReadonlyArray<FeedbackLine>;

    readonly user: { [key: string]: { [key: number]: FeedbackLine } };

    constructor(
        public readonly general: string,
        public readonly linter: LinterFeedbackServerData,
        userLines: FeedbackLine[],
    ) {
        this.userLines = Object.freeze(userLines);

        this.user = Object.freeze(
            this.userLines.reduce((acc, line) => {
                setProps(acc, line, line.fileId, line.lineNumber);
                return acc;
            }, {}),
        );

        Object.freeze(this);
    }

    static fromServerData(feedback?: FeedbackServerData): Feedback {
        if (feedback?.authors != null) {
            feedback.authors.forEach(author => {
                store.dispatch('users/addOrUpdateUser', { user: author });
            });
        }

        const general = feedback?.general ?? '';
        const linter = feedback?.linter ?? {};

        const userLines =
            feedback?.user.map((line: FeedbackLine | any) => {
                if (line instanceof FeedbackLine) {
                    return line;
                } else {
                    return FeedbackLine.fromServerData(line);
                }
            }) ?? [];

        return new Feedback(general, linter, userLines);
    }

    addFeedbackBase(line: FeedbackLine): Feedback {
        if (!(line instanceof FeedbackLine)) {
            throw new Error(
                // @ts-ignore
                `The given line is not the correct class, got ${line.constructor.name}`,
            );
        }

        const newLines = [...this.userLines];
        const oldLineIndex = this.userLines.findIndex(
            l => l.lineNumber === line.lineNumber && l.fileId === line.fileId,
        );

        if (oldLineIndex < 0) {
            newLines.push(line);
        } else {
            newLines[oldLineIndex] = line;
        }

        return new Feedback(this.general, this.linter, newLines);
    }

    removeFeedbackBase(line: FeedbackLine): Feedback {
        return new Feedback(
            this.general,
            this.linter,
            this.userLines.filter(
                l => !(l.lineNumber === line.lineNumber && l.fileId === line.fileId),
            ),
        );
    }

    getFeedbackLine(fileId: string, lineNumber: number): FeedbackLine {
        return this.user[fileId][lineNumber];
    }

    updateGeneralFeedback(general: string) {
        return new Feedback(general, this.linter, [...this.userLines]);
    }

    countEntries(): number {
        return Object.values(this.user).reduce(
            (acc, file) =>
                Object.values(file).reduce((innerAcc, feedback) => {
                    if (!feedback.isEmpty && feedback.replies.some(r => !r.isEmpty)) {
                        return innerAcc + 1;
                    }
                    return innerAcc;
                }, acc),
            this.general.length > 0 ? 1 : 0,
        );
    }
}
