/* SPDX-License-Identifier: AGPL-3.0-only */
import { VNode, CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import { Moment } from 'moment';
import * as models from '@/models';
import { Variant, isVariant } from '@/types';
import * as utils from '@/utils';

function renderAvailableAt(
    h: CreateElement,
    assignment: models.Assignment,
    relative: boolean,
) {
    if (relative) {
        return ['Starts ', <cg-relative-time date={assignment.availableAt} />];
    } else {
        return ['Starts on ', assignment.getFormattedAvailableAt()];
    }
}

function renderDeadline(
    h: CreateElement,
    assignment: models.Assignment,
    relative: boolean,
) {
    if (relative) {
        return ['Due ', <cg-relative-time date={assignment.deadline} />];
    } else {
        return ['Due at ', assignment.getFormattedDeadline()];
    }
}

const AssignmentDate = tsx.component({
    functional: true,

    props: {
        assignment: p.ofType<models.Assignment>().required,
        now: p.ofType<Moment>().required,
        relative: p(Boolean).default(false),
        Tag: p(String).default('small'),
    },

    render(h, { data, props }) {
        const { assignment, now, relative, Tag } = props;

        let content;
        if (assignment.isNotStartedExam(now)) {
            content = renderAvailableAt(h, assignment, relative);
        } else if (assignment.hasDeadline) {
            content = renderDeadline(h, assignment, relative);
        } else {
            content = <i class="text-muted">No deadline</i>;
        }

        return <Tag class={['assignment-deadline', data.staticClass, data.class]}>
            {content}
        </Tag>;
    }
});

export default AssignmentDate;
