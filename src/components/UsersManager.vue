<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader v-if="loading" page-loader/>
<div class="users-manager" v-else>
    <div ref="copyContainer" />
    <b-card class="registration-link-wrapper mb-3" v-if="course.permissions.can_edit_course_users && !course.is_lti">
        <template #header>
            Course enroll links
            <cg-description-popover>
                With these links users can join this course as the role you specify.
                <template v-if="courseRegister">
                    If users do not already have an account they can also register with this link.
                </template>
            </cg-description-popover>
        </template>

        <table class="registration-table table mb-0">
            <thead>
                <tr>
                    <th />
                    <th>
                        Link
                        <description-popover hug-text>
                            This is the link users can use to enroll in this
                            course.
                        </description-popover>
                    </th>
                    <th>
                        Expiration date
                        <description-popover hug-text>
                            After this date the link will no longer work.
                        </description-popover>
                    </th>
                    <th>
                        Role
                        <description-popover hug-text>
                            The role users will get in the course after
                            registering with this link.
                        </description-popover>
                    </th>
                    <th v-if="courseRegister">
                        Allow registration
                        <cg-description-popover hug-text>
                            Should users be allowed to register using this link.
                        </cg-description-popover>
                    </th>
                    <th class="shrink" />
                </tr>
            </thead>
            <tbody>
                <tr v-for="link in registrationLinks"
                    :key="link.trackingId"
                    v-if="!link.deleted"
                    class="registration-links">
                    <template v-if="link.id == null">
                        <td  />
                        <td class="align-middle text-muted font-italic">
                            This link has not been saved yet
                        </td>
                    </template>
                    <template v-else>
                        <td>
                            <div v-b-popover.top.hover="isLinkExpired(link) ? 'This link has expired, therefore it cannot be copied anymore.' : ''">
                                <submit-button :submit="() => copyLink(link)" class="mr-3"
                                               :disabled="isLinkExpired(link)"
                                               variant="secondary">
                                    Copy
                                </submit-button>
                            </div>
                        </td>
                        <td class="align-middle">
                            <div class="d-flex">
                                <code style="word-break: break-all"
                                      :style="{ textDecoration: isLinkExpired(link) ? 'line-through' : 'none' }"
                                      >{{ getRegistrationLinkUrl(link) }}</code>
                            </div>
                        </td>
                    </template>
                    <td>
                        <datetime-picker v-model="link.expiration_date"
                                         placeholder="None set"/>
                    </td>
                    <td class="shrink">
                        <b-dropdown :text="link.role.name"
                                    class="w-100 role-dropdown"
                                    menu-class="w-100">
                            <b-dropdown-header>Select a default role</b-dropdown-header>
                            <b-dropdown-item v-for="role in roles"
                                             @click="$set(link, 'role', role)"
                                             :key="role.id">
                                {{ role.name }}
                            </b-dropdown-item>
                        </b-dropdown>
                    </td>
                    <td v-if="courseRegister">
                        <cg-toggle v-model="link.allow_register"
                                   label-on="Yes"
                                   label-off="No" />
                    </td>
                    <td class="shrink">
                        <div class="save-link-wrapper">
                            <submit-button :submit="() => saveLink(link)" label="Save"
                                           :disabled="link.role.id == null || link.expiration_date == null"
                                           class="mr-1"/>
                            <submit-button :submit="() => deleteLink(link)"
                                           @after-success="$set(link, 'deleted', true)"
                                           label="Delete"
                                           :confirm="link.id ? 'Are you sure you want to delete this link? This invalidates the link.' : ''"
                                           variant="danger"
                                           />
                        </div>
                    </td>
                </tr>

                <tr v-if="registrationLinks.filter(x => !x.deleted).length === 0">
                    <td :colspan="courseRegister ? 6 : 5" class="text-center text-muted font-italic">
                        There are no registration links yet.
                    </td>
                </tr>

                <tr>
                    <td :colspan="courseRegister ? 6 : 5" class="pb-0">
                        <b-btn @click="addRegistrationLink"
                               class="float-right"
                               name="add-registration-link"
                               variant="primary">
                            Add new
                        </b-btn>
                    </td>
                </tr>
            </tbody>
        </table>
    </b-card>

    <b-card header="Course members" no-body>
        <div class="m-2">
            <input class="form-control"
                   placeholder="Type to search users"
                   :value="filter"
                   v-debounce="newFilter => { filter = newFilter }" />
        </div>
        <template v-if="canListUsers">
            <b-table striped
                     ref="table"
                     class="users-table"
                     :id="tableId"
                     :fields="fields"
                     :items="filteredUsers"
                     :sort-compare="sortTable"
                     sort-by="User"
                     :per-page="perPage"
                     :current-page="currentPage"
                     show-empty>

                <template #cell(User)="item">
                    <span class="username">{{item.value.name}} ({{item.value.username}})</span>
                </template>

                <template #cell(CourseRole)="item">
                    <b-dropdown class="role-dropdown"
                                menu-class="w-100"
                                v-b-popover.top.hover="item.item.User.id === loggedInUserId ? 'You cannot change your own role' : ''"
                                :disabled="updating[item.item.User.id] || item.item.User.id === loggedInUserId">

                        <template slot="button-content"
                                  v-if="updating[item.item.User.id]">
                            <loader class="d-inline" :scale="1" />
                        </template>
                        <template slot="button-content"
                                  v-else>
                            {{ item.value.name }}
                        </template>

                        <b-dropdown-header>Select the new role</b-dropdown-header>
                        <b-dropdown-item v-for="role in roles"
                                         @click="changed(item.item, role)"
                                         :key="role.id">
                            {{ role.name }}
                        </b-dropdown-item>
                    </b-dropdown>
                </template>

                <template #empty>
                    <div class="text-center font-italic text-muted">
                        No users found.
                    </div>
                </template>
            </b-table>

            <b-pagination
                v-if="showPagination"
                v-model="currentPage"
                :limit="10"
                :total-rows="totalRows"
                :per-page="perPage"
                :aria-controls="tableId" />
        </template>
        <b-alert show variant="info" class="mx-3" v-else>
            You can only actually manage users when you also have the 'list course
            users' ('can_list_course_users') permission
        </b-alert>

        <b-popover class="new-user-popover"
                   :triggers="course.isLTI ? 'hover' : ''"
                   target="new-users-input-field">
            You cannot add users to a lti course.
        </b-popover>
        <b-form-fieldset class="add-student mx-3"
                         id="new-users-input-field">
            <b-input-group>
                <user-selector v-model="newStudentUsername"
                               placeholder="New student"
                               :use-selector="canListUsers && canSearchUsers"
                               :extra-params="{ exclude_course: course.id }"
                               :disabled="course.isLTI"/>

                <template slot="append">
                    <b-dropdown dropup
                                class="role-dropdown"
                                toggle-class="h-100 border"
                                :text="newRole ? newRole.name : 'Role'"
                                :disabled="course.isLTI">
                        <b-dropdown-header>Select the new role</b-dropdown-header>
                        <b-dropdown-item v-for="role in roles"
                                         v-on:click="() => {newRole = role; error = '';}"
                                         :key="role.id">
                            {{ role.name }}
                        </b-dropdown-item>
                    </b-dropdown>
                    <submit-button class="add-user-button"
                                   label="Add"
                                   :submit="addUser"
                                   @success="afterAddUser"
                               :disabled="course.isLTI"/>
                </template>
            </b-input-group>
        </b-form-fieldset>
    </b-card>
</div>
</template>

<script>
import moment from 'moment';

import { mapGetters } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/pencil';
import 'vue-awesome/icons/floppy-o';
import 'vue-awesome/icons/ban';

import { cmpNoCase, cmpOneNull, waitAtLeast } from '@/utils';
import Loader from './Loader';
import SubmitButton from './SubmitButton';
import UserSelector from './UserSelector';
import DatetimePicker from './DatetimePicker';

import DescriptionPopover from './DescriptionPopover';

export default {
    name: 'users-manager',
    props: {
        course: {
            type: Object,
            required: true,
        },
    },

    data() {
        return {
            roles: [],
            users: [],
            loading: true,
            updating: {},
            newStudentUsername: null,
            canListUsers: false,
            canSearchUsers: false,
            tableId: `users-table-${this.$utils.getUniqueId()}`,
            newRole: '',
            error: '',
            fields: [
                {
                    label: 'Name',
                    key: 'User',
                    sortable: true,
                },
                {
                    label: 'Role',
                    key: 'CourseRole',
                    sortable: true,
                },
            ],

            registrationLinks: [],
            UserConfig,
            currentPage: 1,
            filter: this.$route.query.filterUsers || '',
        };
    },

    computed: {
        ...mapGetters('user', {
            loggedInUserId: 'id',
        }),

        courseRegister() {
            return this.$userConfig.features.course_register;
        },

        totalRows() {
            return this.$utils.getProps(this.filteredUsers, 0, 'length');
        },

        perPage() {
            return 15;
        },

        courseId() {
            return this.course.id;
        },

        filteredUsers() {
            return this.users.filter(this.filterFunction);
        },

        showPagination() {
            return this.totalRows > this.perPage;
        },
    },

    watch: {
        course(newVal, oldVal) {
            if (newVal.id !== oldVal.id) {
                this.loadData();
            }
        },

        users() {
            this.currentPage = 1;
        },

        filter() {
            this.currentPage = 1;

            const newQuery = Object.assign({}, this.$route.query);
            newQuery.filterUsers = this.filter || undefined;

            this.$router.replace({
                query: newQuery,
                hash: this.$route.hash,
            });
        },
    },

    mounted() {
        this.loadData();
    },

    methods: {
        filterFunction(item) {
            if (!this.filter) {
                return true;
            }

            const terms = [item.User.name, item.User.username, item.CourseRole.name];
            return (this.filter || '')
                .toLowerCase()
                .split(' ')
                .every(word => terms.some(t => t.toLowerCase().indexOf(word) >= 0));
        },

        async loadData() {
            this.loading = true;

            [
                ,
                ,
                this.canSearchUsers,
                this.registrationLinks,
            ] = await Promise.all([
                this.getAllUsers(),
                this.getAllRoles(),
                this.$hasPermission('can_search_users'),
                this.getRegistrationLinks(),
            ]);
            this.canListUsers = this.course.hasPermission('can_list_course_users');

            this.loading = false;

            const tableRef = await this.$waitForRef('table');
            if (tableRef != null) {
                this.$refs.table.sortBy = 'User';
            }
        },

        getRegistrationLinks() {
            return this.$http.get(`/api/v1/courses/${this.course.id}/registration_links/`).then(
                ({ data }) =>
                    data.map(link => {
                        link.expiration_date = this.$utils.formatDate(link.expiration_date);
                        link.trackingId = this.$utils.getUniqueId();

                        return link;
                    }),
                () => [],
            );
        },

        sortTable(a, b, sortBy) {
            if (typeof a[sortBy] === 'number' && typeof b[sortBy] === 'number') {
                return a[sortBy] - b[sortBy];
            } else if (sortBy === 'User') {
                const first = a[sortBy];
                const second = b[sortBy];

                const ret = cmpOneNull(first, second);

                return ret === null ? cmpNoCase(first.name, second.name) : ret;
            } else if (sortBy === 'CourseRole') {
                const first = a.CourseRole;
                const second = b.CourseRole;

                const ret = cmpOneNull(first, second);

                return ret === null ? cmpNoCase(first.name, second.name) : ret;
            }
            return 0;
        },

        getAllUsers() {
            return this.$http.get(`/api/v1/courses/${this.courseId}/users/`).then(
                ({ data }) => {
                    this.users = data;
                },
                () => [],
            );
        },

        getAllRoles() {
            return this.$http.get(`/api/v1/courses/${this.courseId}/roles/`).then(({ data }) => {
                this.roles = data;
            });
        },

        changed(user, role) {
            this.$set(this.updating, user.User.id, true);
            const req = this.$http.put(`/api/v1/courses/${this.courseId}/users/`, {
                user_id: user.User.id,
                role_id: role.id,
            });

            waitAtLeast(250, req).then(
                () => {
                    for (let i = 0, len = this.users.length; i < len; i += 1) {
                        if (this.users[i].User.id === user.User.id) {
                            this.$set(user, 'CourseRole', role);
                            this.$set(this.users, i, user);
                            break;
                        }
                    }
                },
                err => {
                    this.$bvToast.toast(err.response.data.message, {
                        title: 'Error',
                        toaster: 'b-toaster-top-right',
                        variant: 'danger',
                        noAutoHide: true,
                        solid: true,
                    });
                },
            ).then(() => {
                this.$set(this.updating, user.User.id, false);
                delete this.updating[user.User.id];
            });
        },

        addUser() {
            if (this.newRole === '') {
                throw new Error('You have to select a role!');
            } else if (this.newStudentUsername == null || this.newStudentUsername.username === '') {
                throw new Error('You have to add a non-empty username!');
            }

            return this.$http.put(`/api/v1/courses/${this.courseId}/users/`, {
                username: this.newStudentUsername.username,
                role_id: this.newRole.id,
            });
        },

        afterAddUser(response) {
            this.newRole = '';
            this.newStudentUsername = null;
            this.users.push(response.data);
        },

        addRegistrationLink() {
            this.registrationLinks.push({
                id: undefined,
                role: {
                    name: 'Select a default role',
                },
                expiration_date: null,
                trackingId: this.$utils.getUniqueId(),
            });
        },

        saveLink(link) {
            if (link.role == null) {
                throw new Error('You have to select a default role');
            }
            return this.$http
                .put(`/api/v1/courses/${this.course.id}/registration_links/`, {
                    id: link.id,
                    role_id: link.role.id,
                    expiration_date: this.$utils.convertToUTC(link.expiration_date),
                    allow_register: link.allow_register,
                })
                .then(response => {
                    response.data.expiration_date = link.expiration_date;
                    Object.assign(link, response.data);
                    return response;
                });
        },

        deleteLink(link) {
            if (link.id == null) {
                return null;
            }
            return this.$http.delete(
                `/api/v1/courses/${this.course.id}/registration_links/${link.id}`,
            );
        },

        getRegistrationLinkUrl(link) {
            const { host, protocol } = window.location;
            return this.$utils.buildUrl(
                ['courses', this.courseId, 'enroll', link.id],
                { protocol, host },
            );
        },

        copyLink(link) {
            return this.$copyText(this.getRegistrationLinkUrl(link), this.$refs.copyContainer);
        },

        isLinkExpired(link) {
            if (link.expiration_date == null) {
                return false;
            }
            return this.$root.$now.isAfter(moment(link.expiration_date, moment.ISO_8601).local());
        },
    },

    components: {
        Icon,
        Loader,
        SubmitButton,
        UserSelector,
        DatetimePicker,
        DescriptionPopover,
    },
};
</script>

<style lang="less">
.users-manager {
    .users-table,
    .registration-table {
        th,
        td {
            &:last-child {
                width: 1px;
            }
        }
    }

    .users-table {
        td {
            vertical-align: middle;
        }

        .dropdown-toggle {
            padding-top: 3px;
            padding-bottom: 4px;
        }
    }

    .username {
        word-wrap: break-word;
        word-break: break-word;
        -ms-word-break: break-all;

        -webkit-hyphens: auto;
        -moz-hyphens: auto;
        -ms-hyphens: auto;
        hyphens: auto;
    }

    .role-dropdown {
        .dropdown-toggle {
            min-width: 10rem;
            padding-right: 1.5rem;

            &::after {
                position: absolute;
                top: 50%;
                right: 0.5rem;
                transform: translateY(-50%);
            }
        }

        .dropdown-menu {
            overflow-y: auto;
        }
    }

    .save-link-wrapper {
        display: flex;
    }

    .registration-links td {
        vertical-align: middle;
    }
}
</style>
