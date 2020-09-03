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
        v-if="assignments.length > 0 || loading > 0">
        <template v-if="currentAssignment.isJust() && !currentIsInTop">
            <li class="sidebar-list-section-header text-muted">
                <small>Current assignment</small>
            </li>
            <assignment-list-item
                small
                :key="`current-assignment-${currentAssignment.extract().id}`"
                :current-id="currentAssignment.extract().id"
                no-popover
                :sbloc="sbloc"
                :show-course-name="currentCourse == null"
                :assignment="currentAssignment.extract()"/>
            <li>
                <hr class="separator" />
            </li>
        </template>
        <li v-if="loading > 0">
            <cg-loader :scale="1" />
        </li>
        <template v-else>
            <li class="sidebar-list-section-header text-muted"
                v-if="showTopAssignments">
                <small>Closest deadlines</small>
            </li>

            <assignment-list-item v-for="assignment in topAssignments"
                                small
                                :key="`top-assignment-${assignment.id}`"
                                v-if="showTopAssignments"
                                :current-id="currentAssignment.mapOrDefault(a => a.id, null)"
                                no-popover
                                :sbloc="sbloc"
                                :show-course-name="currentCourse == null"
                                :assignment="assignment"/>

            <li v-if="showTopAssignments">
                <hr class="separator">
            </li>

            <assignment-list-item v-for="assignment in filteredAssignments.slice(0, visibleAssignments)"
                                :key="`sorted-assignment-${assignment.id}`"
                                :assignment="assignment"
                                no-popover
                                :current-id="currentAssignment.mapOrDefault(a => a.id, null)"
                                :show-course-name="currentCourse == null"
                                :sbloc="sbloc"/>

            <li class="d-flex mx-2 my-1" v-if="moreAssignmentsAvailable">
                <b-btn class="flex-grow"
                    @click="showMoreAssignments">
                    <cg-loader v-if="renderingMoreAssignments > 0" :scale="1" class="py-1"/>
                    <span v-else v-b-visible="visible => visible && showMoreAssignments()">
                        Load more assignments
                    </span>
                    <infinite-loading @infinite="showMoreAssignments" :distance="150">
                        <div slot="spinner"></div>
                        <div slot="no-more"></div>
                        <div slot="no-results"></div>
                        <div slot="error" slot-scope="err">
                            {{ err }}
                        </div>
                    </infinite-loading>
                </b-btn>
            </li>
        </template>
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
import InfiniteLoading from 'vue-infinite-loading';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/gear';
import 'vue-awesome/icons/plus';

import { cmpNoCase } from '@/utils';

import SubmitInput from '../SubmitInput';
import AssignmentListItem from './AssignmentListItem';

const EXTRA_ASSIGNMENTS = 15;
const TOP_ASSIGNMENTS_LENGTH = 7;

export default {
    name: 'assignment-list',

    props: {
        data: {
            type: Object,
            default: null,
        },
    },

    computed: {
        ...mapGetters('courses', ['getCourse']),
        ...mapGetters('assignments', ['getAssignment', 'allAssignments']),

        sbloc() {
            return this.currentCourse ? undefined : 'a';
        },

        currentAssignment() {
            return this.getAssignment(this.$route.params.assignmentId);
        },

        currentCourse() {
            if (this.data && this.data.course) {
                return this.getCourse(this.data.course.id).extract();
            } else {
                return null;
            }
        },

        showAddButton() {
            const course = this.currentCourse;
            return !!(this.loading === 0 && course && course.canCreateAssignments);
        },

        showManageButton() {
            const course = this.currentCourse;
            return !!(this.loading === 0 && course && course.canManage);
        },

        manageButtonActive() {
            const course = this.currentCourse;
            return !!(
                this.$route.name === 'manage_course' &&
                course &&
                this.$route.params.courseId.toString() === course.id.toString()
            );
        },

        assignments() {
            return this.currentCourse
                ? this.currentCourse.assignments
                : this.allAssignments;
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
                .slice(0, TOP_ASSIGNMENTS_LENGTH);
        },

        showTopAssignments() {
            return !this.filter && this.assignments.length >= TOP_ASSIGNMENTS_LENGTH + 2;
        },

        currentIsInTop() {
            if (!this.showTopAssignments) {
                return false;
            }
            return this.currentAssignment.mapOrDefault(
                cur => this.topAssignments.some(a => a.id === cur.id),
                false,
            );
        },

        sortedAssignments() {
            return this.assignments.slice().sort((a, b) => cmpNoCase(a.name, b.name));
        },

        filteredAssignments() {
            if (!this.filter) {
                return this.sortedAssignments;
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
            if (!course || !course.isLTI) {
                return 'Add a new assignment';
            }
            return 'Add a new assignment that is not connected to your LMS.';
        },

        addAssignmentConfirm() {
            if (!this.currentCourse) {
                return '';
            }
            return this.currentCourse.ltiProvider.mapOrDefault(prov => {
                const lms = prov.lms;
                return `You are about to create an assignment that is not connected to ${lms}. This means that students will not be able to navigate to this assignment inside ${lms} and grades will not be synced. Are you sure?`;
            }, '');
        },

        moreAssignmentsAvailable() {
            return this.visibleAssignments <= this.assignments.length;
        },
    },

    async mounted() {
        this.$root.$on('sidebar::reload', this.reloadAssignments);

        if (this.currentCourse == null) {
            await this.asLoader(this.loadAllCourses());
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
        const id = this.$utils.getUniqueId();
        return {
            filter: '',
            loading: 0,
            renderingMoreAssignments: 0,
            visibleAssignments: EXTRA_ASSIGNMENTS * 4,
            addButtonId: `assignment-add-btn-${id}`,
            popoverId: `assignment-add-popover-${id}`,
        };
    },

    destroyed() {
        this.$root.$off('sidebar::reload', this.reloadAssignments);
    },

    methods: {
        ...mapActions('courses', ['loadAllCourses', 'reloadCourses']),

        async asLoader(promise) {
            if (this.loading === 0) {
                this.$emit('loading');
            }

            this.loading += 1;
            await promise;
            this.loading = Math.max(0, this.loading - 1);

            if (this.loading === 0) {
                this.$emit('loaded');
            }
        },

        reloadAssignments() {
            if (this.currentCourse) {
                return Promise.resolve();
            }
            return this.asLoader(this.reloadCourses({ fullReload: true }));
        },

        manageCourseRoute(courseId) {
            return {
                name: 'manage_course',
                params: { courseId },
            };
        },

        createNewAssignment(name, resolve, reject) {
            const url = this.$utils.buildUrl(
                ['api', 'v1', 'courses', this.currentCourse.id, 'assignments'],
                {
                    query: { no_course_in_assignment: true },
                    addTrailingSlash: true,
                },
            );
            this.$http
                .post(url, { name })
                .then(
                    res => {
                        const assig = res.data;
                        res.onAfterSuccess = () => {
                            this.asLoader(this.reloadCourses).then(() => {
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

        showMoreAssignments(state = null) {
            this.renderingMoreAssignments += 1;
            this.visibleAssignments += EXTRA_ASSIGNMENTS;
            this.renderingMoreAssignments -= 1;
            if (state) {
                if (this.moreAssignmentsAvailable) {
                    state.loaded();
                } else {
                    state.complete();
                }
            }
        },
    },

    components: {
        AssignmentListItem,
        Icon,
        SubmitInput,
        InfiniteLoading,
    },
};
</script>
