/* SPDX-License-Identifier: AGPL-3.0-only */
import { CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import * as models from '@/models';
import * as components from '@/components';

function renderAvailableAt(h: CreateElement, assignment: models.Assignment, relative: boolean) {
    // We know that this is never `null` (because of the check in `render`) but
    // we cannot guarentee it to typescript.
    if (relative && assignment.availableAt != null) {
        return ['Starts ', <components.RelativeTime date={assignment.availableAt} />];
    } else {
        return ['Starts on ', assignment.getFormattedAvailableAt()];
    }
}

function renderDeadline(h: CreateElement, assignment: models.Assignment, relative: boolean) {
    if (relative) {
        return ['Due ', <components.RelativeTime date={assignment.deadline} />];
    } else {
        return ['Due at ', assignment.getFormattedDeadline()];
    }
}

const AssignmentDate = tsx.component({
    functional: true,

    props: {
        assignment: p.ofType<models.Assignment>().required,
        relative: p(Boolean).default(false),
        Tag: p(String).default('small'),
    },

    render(h, { data, props, parent }) {
        const { assignment, relative, Tag } = props;
        const now = parent.$root.$now;

        let content;
        if (assignment.isNotStartedExam(now)) {
            content = renderAvailableAt(h, assignment, relative);
        } else if (assignment.hasDeadline) {
            content = renderDeadline(h, assignment, relative);
        } else {
            content = <i class="text-muted">No deadline</i>;
        }

        return <Tag class={['assignment-date', data.staticClass, data.class]}>{content}</Tag>;
    },
});

export default AssignmentDate;
