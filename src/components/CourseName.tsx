/* SPDX-License-Identifier: AGPL-3.0-only */
import { VNode, CreateElement } from 'vue';
import * as models from '@/models';
import * as tsx from 'vue-tsx-support';
import { CoursesStore } from '@/store';
import { emptyVNode } from '@/utils';
import p from 'vue-strict-prop';

const maybeMakeBadge = (h: CreateElement, course: models.Course) => {
    const state = course.state;
    const cls = "text-small-uppercase align-middle ml-2";

    switch (state) {
        case models.CourseState.visible:
            return emptyVNode();
        case models.CourseState.archived:
            return <b-badge class={cls} variant="primary">archived</b-badge>;
        case models.CourseState.deleted:
            return <b-badge class={cls} variant="primary">deleted</b-badge>;
    }
};

const CourseName = tsx.component({
    functional: true,

    props: {
        course: p(models.Course).required,
        bold: p(Boolean).default(false),
    },

    render(h, { props }): VNode {
        const { course, bold } = props;

        const counts = CoursesStore.getCourseCounts()(course);
        // XXX: This has a problem: we don't load all courses at once, so we
        // don't actually know if these counts are correct. However with
        // archiving it might be way more clear which course is which. We could
        // also simply add the year to the course unconditionally (maybe check
        // if it isn't already in the name?).
        let extra;
        if (counts.total.length > 1 && counts.byYear.get(course.createdAt.year()).length > 1) {
            extra = ` (${course.createdAt.format('YYYY-MM-DD')})`;
        } else if (counts.total.length > 1) {
            extra = ` (${course.createdAt.format('YYYY')})`;
        }

        const badge = maybeMakeBadge(h, course);
        const title = `${course.name}${extra ?? ''}${course.isArchived ? ' [archived]' : ''}`;

        return <span title={title} class="course-name">
            <span class="align-middle" class={bold ? 'font-weight-bold' : ''}>
                {course.name}
            </span>
            {extra && <i class="align-middle">{extra}</i>}
            {badge}
        </span>

    },
});


export default CourseName;
