<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="group-set-manager">
    <table class="range-table table table-striped">
        <thead>
            <th>
                Minimum size
                <description-popover
                    hug-text
                    description="The minimum size a group should be before it
                                 can submit for an assignment. If the value is 1
                                 a user that is not in a group is also able to
                                 submit assignments. The value should be 1 or
                                 higher."/>
            </th>
            <th>
                Maximum size
                <description-popover
                    hug-text
                    description="The maximum size a group can be. This value
                                 should be equal or greater than the minimum
                                 size."/>
            </th>
            <th>
                Assignments
                <description-popover
                    hug-text
                    description="The assignments this group set is used."/>
            </th>
            <th class="shrink">
                Actions
            </th>
        </thead>
        <tbody>
            <tr v-if="groupSets.length === 0">
                <td colspan="4" style="text-align: center;">There are no group sets for this course</td>
            </tr>
            <tr v-else v-for="set in groupSets">
                <template v-if="editing[set.id]">
                    <td>
                        <input class="form-control text-left"
                               type="number"
                               min="1"
                               v-model="editing[set.id].minimum_size"
                               @keyup.ctrl.enter="clickSubmit(set)"/>
                    </td>
                    <td>
                        <input class="form-control text-left"
                               v-model="editing[set.id].maximum_size"
                               type="number"
                               :min="editing[set.id].minimum_size"
                               @keyup.ctrl.enter="clickSubmit(set)"/>
                    </td>
                    <td>
                        <span v-b-popover.top.hover="'Go the assignment management page to use this group set in an assignment'">
                            <input class="form-control text-left"
                                   :value="formattedAssignments(set)"
                                   disabled />
                        </span>
                    </td>
                    <td class="shrink">
                        <b-button-group>
                            <b-button variant="warning"
                                      size="sm"
                                      @click="$set(editing, set.id, null)"
                                      v-b-popover.top.hover="'Revert'">
                                <icon name="reply"/>
                            </b-button>
                            <submit-button size="sm"
                                           :submit="() => submitSet(editing[set.id])"
                                           @after-success="(res) => afterSubmitSet(res, editing[set.id])"
                                           :ref="`saveSet-${set.id}`"
                                           v-b-popover.top.hover="'Save'">
                                <icon name="floppy-o"/>
                            </submit-button>
                        </b-button-group>
                    </td>
                </template>
                <template v-else>
                    <td><span class="txt">{{ set.minimum_size }}</span></td>
                    <td><span class="txt">{{ set.maximum_size }}</span></td>
                    <td><span class="txt assigs">{{ formattedAssignments(set)}}</span></td>
                    <td class="shrink">
                        <b-button-group>
                            <b-button variant="primary"
                                      size="sm"
                                      @click="startEdit(set)"
                                      v-b-popover.top.hover="'Edit group set'">
                                <icon name="pencil"/>
                            </b-button>
                            <submit-button variant="danger"
                                           size="sm"
                                           :submit="() => deleteSet(set)"
                                           @after-success="(res) => afterDeleteSet(res, set)"
                                           confirm="Are you sure you want to delete this group set?"
                                           v-b-popover.top.hover="'Delete group set'">
                                <icon name="times"/>
                            </submit-button>
                        </b-button-group>
                    </td>
                </template>
            </tr>
        </tbody>
    </table>

    <submit-button class="add-btn float-right"
                   label="Add group set"
                   :submit="addGroup"
                   @success="afterAddGroup"/>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/floppy-o';
import 'vue-awesome/icons/reply';
import 'vue-awesome/icons/pencil';

import * as models from '@/models';
import { SubmitButton, DescriptionPopover } from '@/components';

export default {
    name: 'group-set-manager',

    props: {
        course: {
            type: models.Course,
            required: true,
        },
    },

    computed: {
        ...mapGetters('assignments', ['getAssignment']),

        groupSets() {
            return this.course.groupSets;
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

    watch: {
        allAssignmentIds: {
            immediate: true,
            handler() {
                this.loadAssignments();
            },
        },
    },


    methods: {
        ...mapActions('courses', ['updateCourse']),
        ...mapActions('assignments', ['updateAssignment', 'loadSingleAssignment']),

        addGroup() {
            return this.$http.put(`/api/v1/courses/${this.course.id}/group_sets/`, {
                minimum_size: 1,
                maximum_size: 1,
            });
        },

        afterAddGroup(response) {
            this.updateCourse({
                courseId: this.course.id,
                courseProps: {
                    groupSets: [...this.groupSets, response.data],
                },
            });

            this.startEdit(response.data);
        },

        startEdit(groupSet) {
            const copy = Object.assign({}, groupSet);
            copy.assignment_ids = [...groupSet.assignment_ids];
            this.$set(this.editing, groupSet.id, copy);
        },

        formattedAssignments(groupSet) {
            const res = this.$utils.filterMap(
                groupSet.assignment_ids,
                id => this.getAssignment(id).map(a => a.name),
            ).join(', ');
            return res || 'Not used';
        },

        clickSubmit(groupSet) {
            this.$refs[`saveSet-${groupSet.id}`][0].onClick();
        },

        submitSet(groupSet) {
            return this.$http.put(`/api/v1/courses/${this.course.id}/group_sets/`, {
                id: groupSet.id,
                minimum_size: Number(groupSet.minimum_size),
                maximum_size: Number(groupSet.maximum_size),
            });
        },

        afterSubmitSet(response, groupSet) {
            const { data } = response;

            this.updateCourse({
                courseId: this.course.id,
                courseProps: {
                    groupSets: this.groupSets.map(set => (set.id === groupSet.id ? data : set)),
                },
            });

            data.assignment_ids.forEach(id => {
                this.updateAssignment({
                    assignmentId: id,
                    assignmentProps: {
                        group_set: data,
                    },
                });
            });

            this.$set(this.editing, groupSet.id, undefined);
        },

        deleteSet(groupSet) {
            return this.$http.delete(`/api/v1/group_sets/${groupSet.id}`);
        },

        afterDeleteSet(response, groupSet) {
            this.updateCourse({
                courseId: this.course.id,
                courseProps: {
                    groupSets: this.groupSets.filter(set => set.id !== groupSet.id),
                },
            });
        },

        loadAssignments() {
            Promise.all(
                Array.from(
                    this.allAssignmentIds,
                    id => this.loadSingleAssignment({ assignmentId: id }),
                ),
            );
        },
    },

    data() {
        return {
            editing: {},
        };
    },

    components: {
        SubmitButton,
        Icon,
        DescriptionPopover,
    },
};
</script>

<style lang="less" scoped>
td {
    width: 33%;
    vertical-align: middle;

    .txt {
        display: block;

        &:not(.assigs) {
            width: 100%;
        }
    }
}
</style>
