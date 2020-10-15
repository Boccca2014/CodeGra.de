/* SPDX-License-Identifier: AGPL-3.0-only */
import { CreateElement, VNode } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

import * as models from '@/models';
import * as types from '@/types';
import * as utils from '@/utils';

export default tsx.component({
    name: 'gutter-comment',
    functional: true,

    props: {
        comments: p.ofType<ReadonlyArray<models.QualityComment>>().required,
        width: p(String).required,
    },

    render(h, { props }) {
        const id = `gutter-comment-${utils.getUniqueId()}`;

        const renderComment = (comment: models.QualityComment): VNode => (
            <tr>
                <td class="pr-2 font-weight-bold">{comment.origin}</td>

                <td class="text-left">
                    {/* Severity can be null for old linter comments */}
                    {utils.ifOrEmpty(
                        comment.severity !== models.QualityCommentSeverity.old_linter,
                        () => (
                            <b-badge variant={comment.badgeVariant}>{comment.severity}</b-badge>
                        ),
                    )}{' '}
                    {comment.code ? `[${comment.code}] ` : ''}
                    {comment.msg}
                </td>
            </tr>
        );

        const popover = (
            <b-popover placement="topright" triggers="hover" boundary="window" target={id}>
                <table class="gutter-comments-table">{props.comments.map(renderComment)}</table>
            </b-popover>
        );

        const toggle = (
            <div
                id={id}
                class="linter-toggle"
                style={{
                    position: 'absolute',
                    top: 0,
                    right: '100%',
                    width: props.width,
                    height: '100%',
                }}
            />
        );

        return (
            <div class="gutter-comment d-inline">
                {popover}
                {toggle}
            </div>
        );
    },
});
