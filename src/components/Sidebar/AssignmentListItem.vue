<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<li :class="{ 'light-selected': selected, 'small-item': small }"
    class="sidebar-list-item assignment-list-item">
    <router-link class="sidebar-item overflow-hidden flex-grow-1"
                 :class="{ selected: submissionsSelected || (small && selected) }"
                 :to="submissionsRoute(assignment)">
        <div class="d-flex flex-row align-items-center" v-if="small">
            <assignment-name
                :assignment="assignment"
                :badge-variant="examBadgeVariant" />
            <assignment-date
                :assignment="assignment"
                relative />
        </div>

        <template v-else>
            <div class="d-flex flex-row">
                <assignment-name
                    :assignment="assignment"
                    :badge-variant="examBadgeVariant" />
                <assignment-state
                    :assignment="assignment"
                    :editable="false"
                    size="sm" />
            </div>

            <small v-if="showCourseName"
                   class="course text-truncate">
                <course-name :course="assignment.course" />
            </small>

            <assignment-date
                :assignment="assignment"
                relative />
        </template>
    </router-link>

    <router-link class="sidebar-item manage-link"
                 v-if="assignment.canManage && !small"
                 v-b-popover.topleft.hover.window="noPopover ? '' : 'Manage assignment'"
                 :class="{ selected: manageSelected }"
                 :to="manageRoute(assignment)">
        <icon name="gear" />
    </router-link>
</li>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/gear';

import { mapGetters } from 'vuex';

import CourseName from '@/components/CourseName';
import AssignmentDate from '@/components/AssignmentDate';
import AssignmentName from '@/components/AssignmentName';
import AssignmentState from '@/components/AssignmentState';

export default {
    name: 'assignment-list-item',

    props: {
        assignment: {
            type: Object,
            required: true,
        },

        small: {
            type: Boolean,
            default: false,
        },

        currentId: {
            type: Number,
            default: null,
        },

        showCourseName: {
            type: Boolean,
            default: true,
        },

        sbloc: {
            default: undefined,
        },

        noPopover: {
            type: Boolean,
            default: false,
        },
    },

    computed: {
        ...mapGetters('pref', ['darkMode']),

        selected() {
            return this.assignment.id === this.currentId;
        },

        submissionsSelected() {
            return this.selected && this.$route.name === 'assignment_submissions';
        },

        manageSelected() {
            return this.selected && this.$route.name === 'manage_assignment';
        },

        examBadgeVariant() {
            if (this.darkMode) {
                // This primary will be overridden by our own css.
                return this.selected ? 'primary' : 'light';
            }
            return this.selected ? 'light' : 'primary';
        },

        isNotStartedExam() {
            return this.$utils.getProps(this.assignment, false, 'isNotStartedExam');
        },
    },

    methods: {
        submissionsRoute(assignment) {
            return {
                name: 'assignment_submissions',
                params: {
                    courseId: assignment.course.id,
                    assignmentId: assignment.id,
                },
                query: {
                    sbloc: this.sbloc,
                },
            };
        },

        manageRoute(assignment) {
            return {
                name: 'manage_assignment',
                params: {
                    courseId: assignment.course.id,
                    assignmentId: assignment.id,
                },
                query: {
                    sbloc: this.sbloc,
                },
            };
        },
    },

    components: {
        Icon,
        AssignmentDate,
        AssignmentName,
        AssignmentState,
        CourseName,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.manage-link {
    flex: 0 0 auto;
    padding-top: 4px;

    .fa-icon {
        transform: translateY(-5px) !important;

        body.cg-edge & {
            transform: translateY(-6px) !important;
        }
    }
}

a {
    text-decoration: none;
    color: inherit;
}

.assignment-name {
    display: flex;
    flex: 1 1 auto;
    min-width: 0;
}

.assignment-state.fa-icon {
    transform: translateY(0) !important;
}

.assignment-list-item.small-item {
    .assignment-name {
        line-height: 1.1;
    }

    .assignment-date {
        flex: 0 0 auto;
    }
}

@{dark-mode} {
    .light-selected .badge {
        color: white;
        background-color: @color-primary;
    }
}
</style>
