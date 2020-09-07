<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<li :class="{ 'light-selected': selected }"
    class="sidebar-list-item assignment-list-item">
    <router-link class="sidebar-item name"
                 :class="{ selected: submissionsSelected || (small && selected) }"
                 :to="submissionsRoute(assignment)">
        <div class="assignment-wrapper">
            <span :title="assignment.name" class="assignment text-truncate">{{ assignment.name }}</span>
            <div class="flex-grow-1 text-small-uppercase mx-2 d-flex align-self-center">
                <b-badge class="exam-badge" v-if="assignment.kind === 'exam'" :variant="examBadgeVariant">
                    exam
                </b-badge>
            </div>

            <assignment-state :assignment="assignment"
                              :editable="false"
                              v-if="!small"
                              size="sm"/>
            <small v-else-if="isNotStartedExam" class="deadline">
                Starts <cg-relative-time :date="assignment.availableAt" />
            </small>
            <small v-else-if="assignment.hasDeadline" class="deadline">
                Due <cg-relative-time :date="assignment.deadline" />
            </small>

            <small v-else class="deadline text-muted">
                <i>No deadline</i>
            </small>
        </div>

        <template v-if="!small">
            <small v-if="showCourseName"
                class="course text-truncate"
                :title="assignment.course.name">{{ assignment.course.name }}</small>

            <small v-if="isNotStartedExam" class="deadline">
                Starts <cg-relative-time :date="assignment.availableAt" />
            </small>
            <small v-else-if="assignment.hasDeadline" class="deadline">
                Due <cg-relative-time :date="assignment.deadline" />
            </small>
            <small v-else class="deadline text-muted">
                <i>No deadline</i>
            </small>
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

import { AssignmentKind } from '@/models';
import AssignmentState from '../AssignmentState';

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
            const { assignment } = this;

            if (assignment == null) {
                return false;
            }

            return (
                assignment.kind === AssignmentKind.exam &&
                assignment.availableAt.isAfter(this.$root.$epoch)
            );
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
        AssignmentState,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.name {
    flex: 1 1 auto;
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
}

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

.assignment-wrapper {
    display: flex;
    max-width: 100%;
    text-overflow: ellipsis;
    align-items: baseline;
    margin-bottom: 2px;

    .deadline {
        padding-left: 2px;
    }

    .assignment {
        line-height: 1.1;
    }
}

@{dark-mode} {
    .light-selected .exam-badge {
        color: white;
        background-color: @color-primary;
    }
}
</style>
