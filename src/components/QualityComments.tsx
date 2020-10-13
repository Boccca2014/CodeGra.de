/* SPDX-License-Identifier: AGPL-3.0-only */
import { CreateElement, VNode } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

import * as models from '@/models';
import * as types from '@/types';
import * as utils from '@/utils';
import { DefaultMap } from '@/utils/defaultdict';
import { store, AssignmentsStore } from '@/store';

type SeverityGroup = Map<
    models.QualityCommentSeverity,
    ReadonlyArray<models.QualityComment>
>;

type MessageGroup = Map<string, SeverityGroup>;

const groupComments = (
    comments: ReadonlyArray<models.QualityComment>,
): MessageGroup =>
    utils.groupBy(comments, comment => {
        if (comment.code != null) {
            return `${comment.origin} (${comment.code}): ${comment.msg}`;
        } else {
            return `${comment.origin}: ${comment.msg}`;
        }
    }).map(group =>
        utils.groupBy(group, comment => comment.severity).map(x => x),
    );

export default tsx.component({
    name: 'quality-comments',
    functional: true,

    props: {
        comments: p.ofType<models.QualityComments>().required,
        stepId: p(Number).required,
    },

    render(h, ctx) {
        const { data, props } = ctx;
        const { assignmentId, submissionId } = props.comments;
        const courseId = AssignmentsStore.getAssignment()(assignmentId).mapOrDefault(
            assig => assig.courseId,
            null,
        );
        const fileTree = store.getters['fileTrees/getFileTree'](assignmentId, submissionId);

        const getFileRoute = (file: models.BaseFile) => ({
            name: 'submission_file',
            params: {
                courseId,
                assignmentId,
                submissionId,
                fileId: file.id,
            },
            query: ctx.parent.$route.query,
            hash: '#code',
        });

        const qualityBadge = (severity: models.QualityCommentSeverity): VNode => {
            let variant: types.Variant;

            switch (severity) {
            case models.QualityCommentSeverity.fatal:
            case models.QualityCommentSeverity.error:
                variant = 'danger';
                break;
            case models.QualityCommentSeverity.warning:
                variant = 'warning';
                break;
            case models.QualityCommentSeverity.info:
                variant = 'info';
                break;
            default:
                utils.AssertionError.assertNever(severity);
            }

            return <b-badge variant={variant}>
                {severity}
            </b-badge>;
        };

        const renderLocation = (
            line: models.LineRange,
            column: models.ColumnRange,
        ): VNode => {
            const lStart = line.start;
            const lEnd = line.end;
            const cStart = column.start;
            const cEnd = column.end;

            const lineText = utils.ifExpr(
                lStart === lEnd,
                () => <span>line <b>{lStart}</b></span>,
                () => <span>line <b>{lStart}</b> to line <b>{lEnd}</b></span>,
            );

            const columnText = utils.ifExpr(
                cEnd == null || cStart === cEnd,
                () => <span>column <b>{cStart}</b></span>,
                () => <span>column <b>{cStart}</b> to column <b>{cEnd}</b></span>,
            );

            return <span class="text-muted">
                {lineText}, {columnText}
            </span>;
        };

        const renderComment = (
            comment: models.QualityComment,
        ): VNode => {
            {/* TODO: Handle case when AutoTest is run on teacher revision */}
            const file = fileTree.search('student', comment.fileId);

            return <router-link to={getFileRoute(file)}
                                class="d-block inline-link">
                <code>{file.name}</code>
                {' '}
                <small>{renderLocation(comment.line, comment.column)}</small>
            </router-link>;
        };

        const renderSeverityGroup = (
            severity: models.QualityCommentSeverity,
            comments?: ReadonlyArray<models.QualityComment>,
        ): VNode => {
            if (comments != null && comments.length > 0) {
                return <div class="mt-2">
                    {qualityBadge(comments[0].severity)} messages
                    {comments.map(renderComment)}
                </div>;
            } else {
                return utils.emptyVNode();
            }
        };

        const renderCommentGroup = (
            [message, comments]: [string, SeverityGroup],
        ): VNode => {
            return <div class="mt-3 p-3 border rounded">
                {message}

                {[
                    models.QualityCommentSeverity.fatal,
                    models.QualityCommentSeverity.error,
                    models.QualityCommentSeverity.warning,
                    models.QualityCommentSeverity.info,
                ].map(severity =>
                    renderSeverityGroup(severity, comments.get(severity)),
                )}
            </div>;
        };

        const renderComments = (
            comments: ReadonlyArray<models.QualityComment>,
        ): VNode => {
            const grouped = groupComments(comments);
            const sorted = utils.sortBy(
                [...grouped],
                ([msg, group]) => [
                    group.get(models.QualityCommentSeverity.fatal)?.length ?? 0,
                    group.get(models.QualityCommentSeverity.error)?.length ?? 0,
                    group.get(models.QualityCommentSeverity.warning)?.length ?? 0,
                    group.get(models.QualityCommentSeverity.info)?.length ?? 0,
                    msg,
                ],
                { reversePerKey: [true, true, true, true, false] },
            );

            return <div class={`quality-comments mt-n3 ${data.class || ''} ${data.staticClass || ''}`}>
                {sorted.map(renderCommentGroup)}
            </div>;
        }

        const stepComments = props.comments.commentsPerStep.get(props.stepId);

        return utils.ifOrEmpty(
            stepComments != null,
            () => renderComments(stepComments),
        );
    },
});
