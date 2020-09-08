/* SPDX-License-Identifier: AGPL-3.0-only */
import { VNode, CreateElement, RenderContext } from 'vue';
import { mapGetters } from 'vuex';
import * as models from '@/models';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import { store } from '@/store';
import CourseName from '@/components/CourseName';

// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/gear';

function maybeEmit(ctx: RenderContext<{ course: models.Course }>) {
    if (ctx.listeners['open-menu']) {
        const { course } = ctx.props;
        let listeners = ctx.listeners['open-menu'];
        if (!Array.isArray(listeners)) {
            listeners = [listeners];
        }

        listeners.forEach(listener => listener({
            header: course.name,
            component: 'assignment-list',
            data: { course },
            reload: true,
        }));
    }
};

export default tsx.component({
    name: 'course-list-item',
    functional: true,

    props: {
        course: p(models.Course).required,
        currentId: p(Number).optional,
        routeName: p(String).required,
    },

    render(h, ctx): VNode {
        const { course, routeName, currentId } = ctx.props;
        const selected = course.id === currentId;
        const manageSelected = selected && routeName === 'manage_course';

        const manageRoute = {
            name: 'manage_course',
            params: { courseId: course.id },
            query: { sbloc: 'c' },
        };

        const classes = {
            selected: selected && !manageSelected,
            'light-selected': selected,
            'sidebar-list-item': true,
            'course-list-item': true,
        }

        const aStyle = {
            'text-decoration': 'none',
            'color': 'inherit',
        };

        let badgeVariant;
        if (store.getters['pref/darkMode']) {
            badgeVariant = selected ? 'dark' : 'light';
        } else {
            badgeVariant = selected ? 'light' : 'primary';
        }

        let manageLink;
        if (course.canManage) {
            manageLink = (
                <router-link style={aStyle}
                             class={['sidebar-item manage-link', { selected: manageSelected }]}
                             to={manageRoute}>
                    <Icon name="gear" style="transform: translateY(-3px)" />
                </router-link>
            );
        }

        return <li class={classes}>
            <a class="sidebar-item course-name flex-grow-1 text-truncate"
               style={aStyle}
               onClick={() => maybeEmit(ctx)}>
                <CourseName course={course} badge-variant={badgeVariant} />
            </a>
            {manageLink}
        </li>;
    },
});
