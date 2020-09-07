<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="sidebar-list-wrapper">
    <ul class="sidebar-list"
        v-if="groupSets && groupSets.length > 0">
        <li v-for="groupSet in groupSets"
            :class="{
                      'sidebar-list-item': true,
                      'selected': $route.name === 'manage_groups' && groupSet.id === curGroupSetId,
                    }"
            >
            <router-link
                class="sidebar-item name"
                :to="{ name: 'manage_groups', params: { courseId: course.id, groupSetId: groupSet.id }, query: { sbloc: 'g' } }"
                >
                <span v-if="groupSet.assignment_ids.length === 0">
                    Unused group set
                </span>
                <span v-else>
                    Group set used by
                    {{ getGroupSetUsedIn(groupSet) }}
                </span>
            </router-link>
        </li>
    </ul>
    <span v-else class="sidebar-list no-items-text">
        You don&apos;t have any group sets yet.
    </span>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';

export default {
    name: 'group-list',

    props: {
        data: {
            type: Object,
            default: null,
        },
    },

    computed: {
        ...mapGetters('assignments', ['getAssignment']),

        course() {
            return this.$utils.getProps(this.data, null, 'course');
        },

        courseId() {
            return this.$utils.getProps(this.course, null, 'id');
        },

        curGroupSetId() {
            return Number(this.$route.params.groupSetId);
        },

        groupSets() {
            return this.$utils.getProps(this.course, [], 'groupSets');
        },

        allAssignmentIds() {
            return this.groupSets.reduce(
                (acc, groupSet) => {
                    groupSet.assignment_ids.forEach(id => acc.add(id));
                    return acc;
                },
                new Set(),
            );
        },
    },

    async mounted() {
        this.$root.$on('sidebar::reload', this.reload);
    },

    destroyed() {
        this.$root.$off('sidebar::reload', this.reload);
    },

    watch: {
        allAssignmentIds: {
            immediate: true,
            handler() {
                this.loadAssignments();
            },
        },

        courseId() { this.loadAssignments(); },
    },

    methods: {
        ...mapActions('courses', ['loadSingleCourse']),
        ...mapActions('assignments', ['loadSingleAssignment']),

        getGroupSetUsedIn(groupSet) {
            return this.$utils.filterMap(
                groupSet.assignment_ids,
                id => this.getAssignment(id).map(a => a.name),
            ).join(', ');
        },

        async loadAssignments() {
            // All the assignments ids should be in this course, however new
            // assignment could be added in the meantime so also load
            // them. The `loadSingleAssignment` action does nothing if the
            // assignment is already present.
            if (this.courseId == null) {
                return;
            }
            this.loadSingleCourse({
                courseId: this.courseId,
            }).then(
                () => Promise.all(
                    Array.from(
                        this.allAssignmentIds,
                        id => this.loadSingleAssignment({ assignmentId: id }),
                    ),
                ),
            );
        },

        reload() {
            this.$utils.waitAtLeast(
                250,
                this.loadSingleCourse({ courseId: this.course.id, force: true }),
            ).then(() => {
                this.$emit('loaded');
            });
        },
    },

    components: {
        Icon,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

a {
    text-decoration: none;
    color: inherit;
    width: 100%;
    align-items: baseline;
}
</style>
