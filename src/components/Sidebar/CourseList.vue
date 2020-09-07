<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="course-list sidebar-list-wrapper" v-b-visible="maybeLoadFirstCourses">
    <div class="sidebar-filter">
        <input class="form-control"
               placeholder="Filter courses"
               v-model="filter"
               ref="filter">
    </div>

    <ul class="sidebar-list"
        v-if="sortedCourses.length > 0 || loading > 0">
        <template v-if="currentCourse">
            <li class="sidebar-list-section-header text-muted">
                <small>Current course</small>
            </li>
            <li>
                <course-list-item :course="currentCourse"
                                  :route-name="$route.name"
                                  :current-id="currentCourse.id"
                                  @open-menu="$emit('open-menu', $event)"/>
            </li>
            <li>
                <hr class="separator"/>
            </li>
        </template>
        <li v-if="loading > 0">
            <cg-loader :scale="1" />
        </li>
        <template v-else>
            <course-list-item v-for="course in filteredCourses.slice(0, visibleCourses)"
                              :key="`sorted-course-${course.id}`"
                              :route-name="$route.name"
                              :course="course"
                              :current-id="currentCourse && currentCourse.id"
                              @open-menu="$emit('open-menu', $event)"/>

            <li class="d-flex mx-2 my-1" v-if="moreCoursesAvailable">
                <b-btn class="flex-grow"
                       @click="showMoreCourses()">
                    <cg-loader v-if="renderingMoreCourses > 0" :scale="1" class="py-1"/>
                    <span v-else v-b-visible="visible => visible && showMoreCourses()">
                        Load more courses
                    </span>
                    <infinite-loading @infinite="showMoreCourses" :distance="150">
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
        You don't have any courses yet.
    </span>

    <hr class="separator"
        v-if="showAddButton">

    <b-button-group class="sidebar-footer">
        <b-btn class="add-course-button sidebar-footer-button"
               :id="addButtonId"
               v-if="showAddButton"
               v-b-popover.hover.top="'Add new course'">
            <icon name="plus" style="margin-right: 0;"/>
            <b-popover :target="addButtonId"
                       :id="popoverId"
                       triggers="click"
                       placement="top"
                       custom-class="no-max-width">
                <submit-input style="width: 18rem;"
                              placeholder="New course name"
                              @create="createNewCourse"
                              @after-submit="afterCreateNewCouse"
                              @cancel="closePopover"/>
            </b-popover>
        </b-btn>
    </b-button-group>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/plus';

import InfiniteLoading from 'vue-infinite-loading';

import { INITIAL_COURSES_AMOUNT } from '@/constants';

import SubmitInput from '../SubmitInput';
import CourseListItem from './CourseListItem.tsx';

let idNum = 0;

const EXTRA_COURSES = INITIAL_COURSES_AMOUNT / 2;

export default {
    name: 'course-list',

    props: {
        data: {
            type: Object,
            default: null,
        },
    },

    data() {
        const id = idNum++;
        return {
            filter: '',
            addButtonId: `course-add-btn-${id}`,
            popoverId: `course-add-popover-${id}`,
            loading: false,
            showAddButton: false,
            renderingMoreCourses: 0,
            visibleCourses: EXTRA_COURSES,
        };
    },

    computed: {
        ...mapGetters('courses', ['sortedCourses', 'getCourse', 'retrievedAllCourses']),

        filteredCourses() {
            const base = this.sortedCourses;
            if (!this.filter) {
                return base;
            }

            const filterParts = this.filter.toLocaleLowerCase().split(' ');

            return base.filter(course =>
                filterParts.every(part => course.name.toLocaleLowerCase().indexOf(part) > -1),
            );
        },

        currentCourseId() {
            return this.$routeParamAsId('courseId');
        },

        currentCourse() {
            return this.getCourse(this.currentCourseId).extract();
        },

        currentCourse() {
            return this.getCourse(this.currentCourseId).extract();
        },

        moreCoursesAvailable() {
            if (!this.retrievedAllCourses) {
                return true;
            }
            return this.visibleCourses <= this.sortedCourses.length;
        },
    },

    watch: {
        currentCourseId() {
            this.loadCurrentCourse();
        },

        moreCoursesAvailable() {
            if (!this.retrievedAllCourses) {
                return true;
            }
            return this.visibleCourses <= this.sortedCourses.length;
        },
    },

    watch: {
        currentCourseId() {
            this.loadCurrentCourse();
        },
    },

    async mounted() {
        this.$root.$on('sidebar::reload', this.reload);

        this.$hasPermission('can_create_courses').then(create => {
            this.showAddButton = create;
        });

        await this.asLoader(this.loadCurrentCourse());
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

    destroyed() {
        this.$root.$off('sidebar::reload', this.reload);
    },

    methods: {
        ...mapActions('courses', ['loadFirstCourses', 'loadSingleCourse', 'loadAllCourses', 'reloadCourses', 'createCourse']),

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

        maybeLoadFirstCourses(doLoad) {
            if (doLoad) {
                this.asLoader(this.loadFirstCourses());
            }
        },

        reload() {
            const fullReload = this.visibleCourses > INITIAL_COURSES_AMOUNT;
            this.asLoader(this.reloadCourses({ fullReload }).then(
                () => this.loadCurrentCourse(),
            ));
        },

        createNewCourse(name, resolve, reject) {
            return this.createCourse({ name }).then(resolve, reject);
        },

        afterCreateNewCouse({ data: course }) {
            this.$router.push({
                name: 'manage_course',
                params: { courseId: course.id },
            });
        },

        closePopover() {
            this.$root.$emit('bv::hide::popover', this.popoverId);
        },

        async showMoreCourses(state = null) {
            this.renderingMoreCourses += 1;
            this.visibleCourses += EXTRA_COURSES;
            if (!this.retrievedAllCourses && this.visibleCourses > INITIAL_COURSES_AMOUNT) {
                await this.loadAllCourses();
            } else if (this.visibleCourses <= INITIAL_COURSES_AMOUNT) {
                await this.loadFirstCourses();
            }
            this.renderingMoreCourses -= 1;
            if (state) {
                if (this.moreCoursesAvailable) {
                    state.loaded();
                } else {
                    state.complete();
                }
            }
        },


        loadCurrentCourse() {
            if (this.currentCourseId) {
                return this.loadSingleCourse({ courseId: this.currentCourseId });
            }
            return null;
        },
    },

    components: {
        CourseListItem,
        Icon,
        SubmitInput,
        InfiniteLoading,
    },
};
</script>
