/* SPDX-License-Identifier: AGPL-3.0-only */
import { VNode } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

import * as comp from '@/components';
import * as models from '@/models';
import * as utils from '@/utils';
import { DefaultMap } from '@/utils/defaultdict';
import { store } from '@/store';

type MessageGroup = {
    comments: ReadonlyArray<models.QualityComment>;
    origin: string;
    msg: string;
    severity: models.QualityCommentSeverity;
};

type Penalties = {
    [K in models.QualityCommentSeverity]: number;
};

const groupComments = (
    comments: ReadonlyArray<models.QualityComment>,
): ReadonlyArray<MessageGroup> => {
    const nested = comments.reduce(
        (acc, comment) => {
            acc.get(comment.origin)
                .get(comment.msg)
                .get(comment.severity)
                .comments.push(comment);
            return acc;
        },
        new DefaultMap(
            (origin: string) =>
                new DefaultMap(
                    (msg: string) =>
                        new DefaultMap((severity: models.QualityCommentSeverity) => ({
                            comments: [] as models.QualityComment[],
                            origin,
                            msg,
                            severity,
                        })),
                ),
        ),
    );
    const res = [];
    for (const perOrigin of nested.values()) {
        for (const perMsg of perOrigin.values()) {
            for (const perSev of perMsg.values()) {
                res.push(perSev);
            }
        }
    }
    return res;
};

export default tsx.component({
    name: 'quality-comments',
    functional: true,

    props: {
        comments: p.ofRoArray<models.QualityComment>().required,
        courseId: p(Number).required,
        assignmentId: p(Number).required,
        submissionId: p(Number).required,
        renderLinks: p(Boolean).default(false),
        penalties: p.ofType<Penalties>().default(() => ({
            fatal: 8,
            error: 4,
            warning: 2,
            info: 1,
            old_linter: 0,
        })),
    },

    render(h, ctx) {
        const { data, props } = ctx;
        const fileTree: models.FileTree = store.getters['fileTrees/getFileTree'](
            props.assignmentId,
            props.submissionId,
        );

        if (fileTree == null) {
            return <comp.Loader />;
        }

        const getFileRoute = (file: models.BaseFile<string>) => ({
            name: 'submission_file',
            params: {
                courseId: props.courseId,
                assignmentId: props.assignmentId,
                submissionId: props.submissionId,
                fileId: file.id,
            },
            query: ctx.parent.$route.query,
            hash: '#code',
        });

        const renderLocation = (line: models.LineRange): VNode => {
            const lStart = line.start;
            const lEnd = line.end;

            const lineText = utils.ifExpr(
                lStart === lEnd,
                () => (
                    <span>
                        line <b>{lStart}</b>
                    </span>
                ),
                () => (
                    <span>
                        line <b>{lStart}</b> to line <b>{lEnd}</b>
                    </span>
                ),
            );

            return <small class="text-muted">{lineText}</small>;
        };

        const renderComment = (comment: models.QualityComment): VNode => {
            // TODO: Handle case when AutoTest is run on teacher revision
            const file = utils.Maybe.fromNullable(fileTree.search('student', comment.fileId));
            const name = <code>{file.map(f => f.getFullName()).orDefault('…')}</code>;
            const loc = renderLocation(comment.line);

            return utils.ifExpr(
                props.renderLinks,
                () => (
                    <router-link to={file.map(getFileRoute).extract()} class="d-block inline-link">
                        {name} {loc}
                    </router-link>
                ),
                () => (
                    <div class="d-block">
                        {name} {loc}
                    </div>
                ),
            );
        };

        const renderCommentGroup = (group: MessageGroup): VNode => (
            <div class="mt-3 p-3 border rounded">
                <div class="d-flex align-items-center">
                    <b-badge
                        class="mr-1"
                        variant={models.QualityComment.getBadgeVariant(group.severity)}
                    >
                        {group.severity}
                    </b-badge>
                    <span class="mr-1">
                        <b>{group.origin}</b>:
                    </span>
                    <span>{group.msg}</span>
                </div>
                <div style={{ 'max-height': '12rem', overflow: 'auto' }}>
                    {group.comments.map(renderComment)}
                </div>
            </div>
        );

        const renderComments = (comments: ReadonlyArray<models.QualityComment>): VNode => {
            const grouped = groupComments(comments);
            const sorted = utils.sortBy(
                grouped,
                group => [
                    props.penalties[group.severity] * group.comments.length,
                    group.comments.length,
                    group.origin,
                    group.msg,
                ],
                {
                    reversePerKey: [
                        // With highest penalty first.
                        true,
                        // Comments with highest impact per comment next.
                        false,
                        // Next sort keys are here to make sure sorting is
                        // stable even if input data isn't sorted.
                        false,
                        false,
                    ],
                },
            );

            return (
                <div class={`quality-comments mt-n3 ${data.class ?? ''} ${data.staticClass ?? ''}`}>
                    {sorted.map(renderCommentGroup)}
                </div>
            );
        };

        return renderComments(props.comments);
    },
});
