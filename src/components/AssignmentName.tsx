/* SPDX-License-Identifier: AGPL-3.0-only */
import { CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import * as models from '@/models';
import { Variant, isVariant } from '@/types';
import * as utils from '@/utils';

const examBadge = (h: CreateElement, assignment: models.Assignment, variant: string) =>
    utils.ifOrEmpty(assignment.isExam, () => (
        <b-badge variant={variant} class="mr-2 text-small-uppercase align-self-center">
            exam
        </b-badge>
    ));

const AssignmentName = tsx.component({
    functional: true,

    props: {
        assignment: p.ofType<models.Assignment>().required,
        badgeVariant: p
            .ofType<Variant>()
            .validator(isVariant)
            .default('primary'),
    },

    render(h, { data, props }) {
        const { assignment, badgeVariant } = props;

        return (
            <div
                class={['assignment-name', 'text-nowrap', data.class, data.staticClass]}
                style={[data.style, data.staticStyle]}
                title={assignment.name}
            >
                <span class="mr-2 text-truncate">{assignment.name}</span>
                {examBadge(h, assignment, badgeVariant)}
            </div>
        );
    },
});

export default AssignmentName;
