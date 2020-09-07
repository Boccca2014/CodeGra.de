<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="groups-management">
    <b-alert variant="error" show v-if="error != null">
        {{ $utils.getErrorMessage(error) }}
    </b-alert>
    <loader v-else-if="loading"/>
    <div v-else>
        <transition-group v-if="filteredVirtualUsers.length > 0"
                          :name="doAnimations ? 'fade' : ''"
                          tag="div">
            <group-management v-for="virtualUser, i in filteredVirtualUsers"
                              :virtual-user="virtualUser"
                              v-if="filter == null || filter(virtualUser.group, i, virtualUser)"
                              :show-lti-progress="showLtiProgress(virtualUser.group, i)"
                              :can-edit-own="canEdit.own"
                              :can-edit-others="canEdit.others"
                              :selected-members="selectedMembers"
                              :key="`assignment-group-${virtualUser.id}`"
                              :assignment="assignment"
                              :course="course"
                              :group-set="groupSet"/>
        </transition-group>

        <p class="mb-0 text-muted font-italic">
            <span v-if="groups.length === 0">
                There are no groups yet.
            </span>

            <span v-if="!showAddButton || !canCreate">
                <span v-if="currentUserInGroup">
                    You cannot create any new groups because you are already in a group.
                </span>
                <span v-else>
                    You are currently not in a group and you don't have the permission to create any.
                </span>
                Please ask your instructor to create a group if needed.

                <span v-if="groupSet.minimum_size > 1">
                    To submit work it is mandatory that you are in a group of at least
                    {{ groupSet.minimum_size }} members.
                </span>
                <span v-else>
                    You are not required to be part of a group to submit work for this assignment.
                </span>
            </span>
        </p>

        <div class="button-wrapper" v-if="showAddButton && canCreate">
            <submit-button label="Create new group"
                           :submit="addGroup" />
        </div>
    </div>
</div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex';

import UserSelector from '@/components/UserSelector';
import GroupManagement from '@/components/GroupManagement';
import PermissionsManager from '@/components/PermissionsManager';
import LocalHeader from '@/components/LocalHeader';
import Loader from '@/components/Loader';
import Toggle from '@/components/Toggle';
import SubmitButton from '@/components/SubmitButton';

export default {
    name: 'groups-management',

    props: {
        groupSet: {
            type: Object,
            required: true,
        },

        course: {
            type: Object,
            required: true,
        },

        assignment: {
            type: Object,
            default: null,
        },

        filter: {
            type: Function,
            default: null,
        },

        showLtiProgress: {
            type: Function,
            default: () => false,
        },

        showAddButton: {
            type: Boolean,
            default: true,
        },
    },

    data() {
        return {
            loading: true,
            doAnimations: false,
            error: null,
            canEdit: {
                own: false,
                others: false,
            },
            canCreate: false,
        };
    },

    computed: {
        ...mapGetters('user', { myId: 'id' }),
        ...mapGetters('users', ['getGroupsOfGroupSet', 'getGroupInGroupSetOfUser']),

        virtualUsers() {
            return this.getGroupsOfGroupSet(this.groupSet.id);
        },

        filteredVirtualUsers() {
            if (this.filter == null && this.course.isStudent && this.currentUserInGroup) {
                return [this.currentUsersGroup];
            }
            return this.virtualUsers;
        },

        groups() {
            return this.virtualUsers.map(user => user.group);
        },

        selectedMembers() {
            const res = new Set();
            this.groups.forEach(group => group.memberIds.forEach(id => res.add(id)));
            return res;
        },

        currentUsersGroup() {
            return this.getGroupInGroupSetOfUser(this.groupSet.id, this.myId);
        },

        currentUserInGroup() {
            return this.currentUsersGroup != null;
        },
    },

    watch: {
        groupSet: {
            immediate: true,
            handler(newVal, oldVal) {
                if (!newVal || !oldVal || oldVal.id !== newVal.id) {
                    this.loadData();
                }
            },
        },

        async filter() {
            this.doAnimations = false;
            await this.$nextTick();
            this.doAnimations = true;
        },
    },

    methods: {
        ...mapActions('users', ['loadGroupsOfGroupSet', 'createNewGroup']),

        loadData() {
            this.doAnimations = false;
            this.loading = true;
            this.error = null;

            return Promise.all([
                this.loadGroupsOfGroupSet({ groupSetId: this.groupSet.id, force: true }),
                this.getPermissions(),
            ])
                .then(() => {
                    this.loading = false;
                    this.$nextTick(() => {
                        this.doAnimations = true;
                    });
                })
                .catch(err => {
                    this.error = err;
                    throw err;
                });
        },

        addGroup() {
            return this.createNewGroup({ groupSetId: this.groupSet.id });
        },

        getPermissions() {
            this.canEdit = {
                own: this.course.hasPermission('can_edit_own_groups'),
                others: this.course.hasPermission('can_edit_others_groups'),
            };
            this.canCreate = this.course.hasPermission('can_create_groups');
        },
    },

    components: {
        GroupManagement,
        UserSelector,
        PermissionsManager,
        LocalHeader,
        Loader,
        Toggle,
        SubmitButton,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.group-management {
    margin-bottom: 1rem;
}

.button-wrapper {
    margin-top: 1rem;
    .btn {
        float: right;
    }
}

.fade-enter-active,
.fade-leave-active {
    transition: opacity @transition-duration;
}
.fade-enter,
.fade-leave-to {
    opacity: 0;
}
</style>
