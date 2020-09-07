<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader v-if="loading"/>
<div v-else class="groups">
    <local-header :back-route="$utils.getProps(getPreviousRoute(), null, 'name') && getPreviousRoute()"
                  :back-popover="backPopover">
        <template slot="title">
            <span v-if="groupSet.assignment_ids.length === 0">
                Unused group set
            </span>
            <span v-else>
                Group set used by
                <span v-for="(assig, index) in groupAssignments">
                    <router-link
                        :to="getAssignmentLink(assig)"
                        class="inline-link"
                        >{{ assig.name }}</router-link
                                                      ><template
                                                           v-if="index + 1 < groupAssignments.length"
                                                           >,
                    </template>
                </span>
            </span>
        </template>
        <b-form-fieldset class="filter-input">
            <input v-model="filter"
                   class="form-control"
                   placeholder="Type to search"/>
        </b-form-fieldset>

        <submit-button :submit="reload"
                       variant="secondary"
                       v-b-popover.bottom.hover="'Reload groups'">
            <icon name="refresh"/>
            <icon name="refresh" spin slot="pending-label"/>
        </submit-button>
    </local-header>

    <div class="content">
        <groups-management :group-set="groupSet"
                           :course="course"
                           ref="groups"
                           :filter="filterGroup"/>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/refresh';

import { getPreviousRoute } from '@/router';

import { nameOfUser } from '@/utils';

import GroupsManagement from '@/components/GroupsManagement';
import LocalHeader from '@/components/LocalHeader';
import Loader from '@/components/Loader';
import SubmitButton from '@/components/SubmitButton';

export default {
    name: 'groups-page',

    data() {
        return {
            filter: '',
            getPreviousRoute,
        };
    },

    watch: {
        groupSetId: {
            immediate: true,
            handler() {
                this.loadData();
            },
        },

        groupSet(newVal) {
            if (newVal == null) {
                this.loadData();
            }
        },

        groupAssignmentIds: {
            immediate: true,
            handler(newVal) {
                newVal.forEach(assignmentId => {
                    this.loadSingleAssignment({ assignmentId });
                });
            },
        },
    },

    computed: {
        ...mapGetters('courses', ['getCourse']),
        ...mapGetters('assignments', ['getAssignment']),

        backPopover() {
            const prev = this.getPreviousRoute();
            if (prev == null || prev.name == null) {
                return '';
            }
            return `Go back to the ${prev.name.replace(/_/g, ' ')} page`;
        },

        course() {
            return this.getCourse(this.courseId).extract();
        },

        courseId() {
            return Number(this.$route.params.courseId);
        },

        groupSetId() {
            return Number(this.$route.params.groupSetId);
        },

        groupSet() {
            if (!this.course) {
                return null;
            }
            const set = this.course.groupSets.filter(s => this.groupSetId === s.id);
            return set.length > 0 ? set[0] : null;
        },

        groupAssignmentIds() {
            return this.$utils.getProps(this.groupSet, [], 'assignment_ids');
        },

        groupAssignments() {
            return this.$utils.filterMap(
                this.groupAssignmentIds,
                id => this.getAssignment(id),
            );
        },

        loading() {
            return this.course == null;
        },
    },

    methods: {
        ...mapActions('courses', ['loadSingleCourse']),
        ...mapActions('assignments', ['loadSingleAssignment']),

        getAssignmentLink(assig) {
            return {
                name: 'assignment_submissions',
                params: {
                    courseId: this.courseId,
                    assignmentId: assig.id,
                },
            };
        },

        loadData({ force = false } = {}) {
            this.loadSingleCourse({
                courseId: this.courseId,
                force,
            });
        },

        reload() {
            this.$refs.groups.loadData({ force: true });
        },

        filterGroup(group) {
            if (!this.filter) return true;

            const terms = [
                group.name,
                ...group.members.map(nameOfUser),
                ...group.members.map(u => u.username),
            ].map(t => t.toLowerCase());

            return this.filter
                .toLowerCase()
                .split(' ')
                .every(word => terms.some(term => term.indexOf(word) >= 0));
        },
    },

    components: {
        Icon,
        GroupsManagement,
        LocalHeader,
        Loader,
        SubmitButton,
    },
};
</script>

<style lang="less">
@import '~mixins.less';

.filter-input {
    flex: 1 1 auto;
    margin-bottom: 0;
}
</style>
