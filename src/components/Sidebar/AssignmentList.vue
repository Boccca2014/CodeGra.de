<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="assignment-list sidebar-list-wrapper">
    <div class="sidebar-filter">
        <input class="form-control"
               placeholder="Filter assignments"
               v-model="filter"
               ref="filter">
    </div>

    <ul class="sidebar-list"
        v-if="assignments.length > 0">
        <li class="sidebar-list-section-header text-muted"
            v-if="showTopAssignments">
            <small>Closest deadlines</small>
        </li>

        <assignment-list-item v-for="assignment in topAssignments"
                              small
                              :key="`top-assignment-${assignment.id}`"
                              v-if="showTopAssignments"
                              :current-id="currentAssignment && currentAssignment.id"
                              :sbloc="sbloc"
                              :assignment="assignment"/>

        <li v-if="showTopAssignments">
            <hr class="separator">
        </li>

        <assignment-list-item v-for="assignment in (filteredAssignments || sortedAssignments)"
                              :key="`sorted-assignment-${assignment.id}`"
                              :assignment="assignment"
                              :current-id="currentAssignment && currentAssignment.id"
                              :show-course-name="currentCourse == null"
                              :sbloc="sbloc"/>
    </ul>
    <span v-else class="sidebar-list no-items-text">
        You don't have any assignments yet.
    </span>

    <hr class="separator"
        v-if="showAddButton || showManageButton">

    <div class="sidebar-footer">
        <b-btn class="add-assignment-button sidebar-footer-button"
               :id="addButtonId"
               v-if="showAddButton"
               v-b-popover.hover.top="addAssignmentPopover">
            <icon name="plus" style="margin-right: 0;"/>
            <b-popover :target="addButtonId"
                       :id="popoverId"
                       triggers="click"
                       placement="top"
                       custom-class="no-max-width">
                <submit-input style="width: 18rem;"
                              :confirm="addAssignmentConfirm"
                              placeholder="New assignment name"
                              @create="createNewAssignment"
                              @cancel="closePopover"/>
            </b-popover>
        </b-btn>
        <router-link class="btn  sidebar-footer-button"
                     :class="{ active: manageButtonActive }"
                     v-b-popover.hover.top="'Manage course'"
                     v-if="showManageButton"
                     :to="manageCourseRoute(currentCourse.id)">
            <icon name="gear"/>
        </router-link>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/gear';
import 'vue-awesome/icons/plus';

import { cmpNoCase } from '@/utils';

import SubmitInput from '../SubmitInput';
import AssignmentListItem from './AssignmentListItem';

let idNum = 0;

export default {
    name: 'assignment-list',

    props: {
        data: {
            type: Object,
            default: null,
        },
    },

    computed: {
        ...mapGetters('courses', {
            allAssignments: 'assignments',
            allCourses: 'courses',
        }),

        sbloc() {
            return this.currentCourse ? undefined : 'a';
        },

        currentAssignment() {
            return this.allAssignments[this.$route.params.assignmentId];
        },

        currentCourse() {
            if (this.data && this.data.course) {
                return this.allCourses[this.data.course.id];
            } else {
                return null;
            }
        },

        showAddButton() {
            const course = this.currentCourse;
            return !!(course && course.canCreateAssignments);
        },

        showManageButton() {
            const course = this.currentCourse;
            return !!(course && course.canManage);
        },

        manageButtonActive() {
            const course = this.currentCourse;
            return !!(
                this.$route.params.courseId &&
                course &&
                this.$route.params.courseId.toString() === course.id.toString() &&
                !this.currentAssignment
            );
        },

        assignments() {
            return this.currentCourse
                ? this.currentCourse.assignments
                : Object.values(this.allAssignments);
        },

        topAssignments() {
            const lookup = this.assignments.reduce((res, cur) => {
                if (cur.hasDeadline) {
                    res[cur.id] = Math.abs(cur.deadline.diff(this.$root.$now));
                }
                return res;
            }, {});

            return this.assignments
                .filter(a => lookup[a.id] != null)
                .sort((a, b) => lookup[a.id] - lookup[b.id])
                .slice(0, 3);
        },

        showTopAssignments() {
            return !this.filter && this.sortedAssignments.length >= this.topAssignments.length + 2;
        },

        sortedAssignments() {
            return this.assignments.slice().sort((a, b) => cmpNoCase(a.name, b.name));
        },

        filteredAssignments() {
            if (!this.filter) {
                return null;
            }

            const filterParts = this.filter.toLocaleLowerCase().split(' ');

            return this.sortedAssignments.filter(assig =>
                filterParts.every(
                    part =>
                        assig.name.toLocaleLowerCase().indexOf(part) > -1 ||
                        assig.course.name.toLocaleLowerCase().indexOf(part) > -1,
                ),
            );
        },

        addAssignmentPopover() {
            const course = this.currentCourse;
            if (!course || !course.is_lti) {
                return 'Add a new assignment';
            }
            return 'Add a new assignment that is not connected to your LMS.';
        },

        addAssignmentConfirm() {
            if (!this.$utils.getProps(this.currentCourse, false, 'is_lti')) {
                return '';
            }
            const lms = this.currentCourse.lti_provider.name;
            return `You are about to create an assignment that is not connected to ${lms}. This means that students will not be able to navigate to this assignment inside ${lms} and grades will not be synced. Are you sure?`;
        },
    },

    async mounted() {
        this.$root.$on('sidebar::reload', this.reloadAssignments);

        const res = this.loadCourses();
        if (res != null) {
            this.$emit('loading');
            await res;
            this.$emit('loaded');
        }

        await this.$nextTick();
        const activeEl = document.activeElement;
        if (
            !activeEl ||
            !activeEl.matches('input, textarea') ||
            activeEl.closest('.sidebar .submenu')
        ) {
            this.$refs.filter.focus();
        }
    },

    data() {
        const id = idNum++;
        return {
            filter: '',
            addButtonId: `assignment-add-btn-${id}`,
            popoverId: `assignment-add-popover-${id}`,
        };
    },

    destroyed() {
        this.$root.$off('sidebar::reload', this.reloadAssignments);
    },

    methods: {
        ...mapActions('courses', ['loadCourses', 'reloadCourses']),

        reloadAssignments() {
            if (this.currentCourse) {
                return Promise.resolve();
            }
            this.$emit('loading');
            return this.reloadCourses().then(() => {
                this.$emit('loaded');
            });
        },

        manageCourseRoute(courseId) {
            return {
                name: 'manage_course',
                params: { courseId },
            };
        },

        createNewAssignment(name, resolve, reject) {
            this.$http
                .post(`/api/v1/courses/${this.currentCourse.id}/assignments/`, {
                    name,
                })
                .then(
                    res => {
                        const assig = res.data;
                        res.onAfterSuccess = () => {
                            this.$emit('loading');
                            this.reloadCourses().then(() => {
                                this.$emit('loaded');
                                this.$router.push({
                                    name: 'manage_assignment',
                                    params: {
                                        courseId: this.currentCourse.id,
                                        assignmentId: assig.id,
                                    },
                                });
                            });
                        };
                        resolve(res);
                    },
                    err => {
                        reject(err);
                    },
                );
        },

        closePopover() {
            this.$root.$emit('bv::hide::popover', this.popoverId);
        },
    },

    components: {
        AssignmentListItem,
        Icon,
        SubmitInput,
    },
};
</script>
