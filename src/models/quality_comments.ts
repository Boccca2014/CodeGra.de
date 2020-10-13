/* SPDX-License-Identifier: AGPL-3.0-only */
import * as models from '@/models';
import * as utils from '@/utils';
import { makeCache } from '@/utils/cache';
import { DefaultMap } from '@/utils/defaultdict';

export enum QualityCommentSeverity {
    fatal = 'fatal',
    error = 'error',
    warning = 'warning',
    info = 'info',
}

export interface LineRange {
    start: number;
    end: number;
}

export interface ColumnRange {
    start: number;
    end: number | null;
}

interface IQualityCommentBase {
    severity: QualityCommentSeverity;
    code: string | null;
    origin: string;
    msg: string;
    line: LineRange;
    column: ColumnRange;
}

export interface IQualityCommentData extends IQualityCommentBase {
    // eslint-disable-next-line camelcase
    step_id: number;
    // eslint-disable-next-line camelcase
    result_id: number;
    // eslint-disable-next-line camelcase
    file_id: string;
}

export interface IQualityComment extends IQualityCommentBase {
    // eslint-disable-next-line camelcase
    stepId: number;
    // eslint-disable-next-line camelcase
    resultId: number;
    // eslint-disable-next-line camelcase
    fileId: string;
}

export class QualityComment implements IQualityComment {
    static fromServerData(data: IQualityCommentData): QualityComment {
        return new QualityComment(
            Object.assign(
                {
                    stepId: data.step_id,
                    resultId: data.result_id,
                    fileId: data.file_id,
                },
                data,
            ),
        );
    }

    public stepId: number;

    public resultId: number;

    public fileId: string;

    public severity: QualityCommentSeverity;

    public code: string | null;

    public origin: string;

    public msg: string;

    public line: LineRange;

    public column: ColumnRange;

    constructor(data: IQualityComment) {
        this.stepId = data.stepId;
        this.resultId = data.resultId;
        this.fileId = data.fileId;
        this.severity = data.severity;
        this.code = data.code;
        this.origin = data.origin;
        this.msg = data.msg;
        this.line = data.line;
        this.column = data.column;
        Object.freeze(this);
    }
}

export class QualityComments {
    static fromServerData(
        data: IQualityCommentData[],
        result: models.AutoTestResult,
    ): QualityComments {
        const comments = data.map(QualityComment.fromServerData);
        return new QualityComments(comments, result);
    }

    public result: models.AutoTestResult;

    constructor(comments: QualityComment[], result: models.AutoTestResult) {
        this.result = result;
        this._comments = Object.freeze(comments);
        Object.freeze(this);
    }

    private _comments: ReadonlyArray<QualityComment>;

    private _cache = makeCache('commentsPerFile', 'commentsPerStep');

    get commentsPerFile(): DefaultMap<string, QualityComment[]> {
        return this._cache.get('commentsPerFile', () =>
            utils.groupBy(this._comments, comment => comment.fileId),
        );
    }

    get commentsPerStep(): DefaultMap<number, QualityComment[]> {
        return this._cache.get('commentsPerStep', () =>
            utils.groupBy(this._comments, comment => comment.stepId),
        );
    }

    get assignmentId(): number {
        return this.result.autoTest.assignment_id;
    }

    get submissionId(): number {
        return this.result.submissionId;
    }
}
