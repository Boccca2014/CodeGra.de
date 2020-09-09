<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader v-if="loading" page-loader/>
<div class="permissions-manager" v-else>
    <input class="form-control mb-2"
           placeholder="Type to search permissions"
           :value="filter"
           v-debounce="newFilter => { filter = newFilter }" />
    <table class="table table-striped"
           :class="{ 'mb-0': !showAddRole }">
        <thead>
            <tr>
                <th>Name</th>
                <th v-for="field in fields"
                    class="text-center">
                    {{ field.label }}
                </th>
            </tr>
        </thead>

        <tbody>
            <tr v-for="perm, i in items"
                v-if="filteredIndices.has(i)"
                :class="{ 'table-danger': perm.warning }">
                <td>
                    {{ perm.name }}

                    <description-popover
                        hug-text
                        :icon="perm.warning ? 'exclamation-triangle' : undefined"
                        placement="right">
                        <p>
                            {{ perm.description }}
                        </p>

                        <p v-if="perm.warning">
                            <b class="text-danger">Warning:</b>
                            {{ perm.warning }}
                        </p>
                    </description-popover>
                </td>

                <td v-for="field in fields"
                    class="text-center align-middle"
                    v-b-popover.hover.top="perm.value === fixedPermission && field.own ? 'You cannot disable this permission for yourself.' : ''">
                    <loader v-if="perm[field.key] === 'loading'"
                            :scale="1" />

                    <b-form-checkbox v-else
                                     :class="`role-${field.key}`"
                                     :checked="perm[field.key]"
                                     :disabled="perm.value === fixedPermission && field.own"
                                     @change="changeButton(i, field)"/>
                </td>
            </tr>

            <tr v-if="showDeleteRole">
                <td/>
                <td v-for="field, i in fields"
                    class="text-center">
                    <submit-button variant="danger"
                                   :submit="() => removeRole(i)"
                                   @after-success="afterRemoveRole(i)"
                                   v-b-popover.hover.top="'Delete this role'">
                        Delete
                    </submit-button>
                </td>
            </tr>
        </tbody>
    </table>

    <b-form-fieldset v-if="showAddRole"
                     class="add-role">
        <b-input-group>
            <input v-model="newRoleName"
                   class="form-control"
                   placeholder="Name of new role"
                   @keyup.ctrl.enter="$refs.addUserBtn.onClick"/>

            <submit-button label="Add"
                           class="rounded-left-0"
                           ref="addUserBtn"
                           :submit="addRole"
                           @after-success="afterAddRole"/>
        </b-input-group>
    </b-form-fieldset>

    <b-toast v-if="$inLTI"
             :visible="showChangedMessage"
             toaster="b-toaster-top-right"
             title="Permissions have changed"
             no-auto-hide
             solid>
           Reload CodeGrade to apply the changes.
    </b-toast>
    <b-toast v-else
             :visible="showChangedMessage"
             toaster="b-toaster-top-right"
             title="Permissions have changed"
             no-auto-hide
             solid
             href="javascript:window.location.reload()">
           Click here to reload the page and apply the changes.
    </b-toast>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/exclamation-triangle';
import 'vue-awesome/icons/times';

import { waitAtLeast } from '@/utils';
import { CoursePermission, GlobalPermission } from '@/permissions';

import DescriptionPopover from './DescriptionPopover';
import Loader from './Loader';
import SubmitButton from './SubmitButton';

export default {
    name: 'permissions-manager',

    props: {
        courseId: {
            type: Number,
            default: null,
        },
        fixedPermission: {
            default: 'can_edit_course_roles',
            type: String,
        },
        showDeleteRole: {
            type: Boolean,
            default: true,
        },
        showAddRole: {
            type: Boolean,
            default: true,
        },
        getRetrieveUrl: {
            type: Function,
            default: courseId => `/api/v1/courses/${courseId}/roles/?with_roles=true`,
        },
        getChangePermUrl: {
            type: Function,
            default: (courseId, roleId) => `/api/v1/courses/${courseId}/roles/${roleId}`,
        },
        getDeleteRoleUrl: {
            type: Function,
            default: (courseId, roleId) => `/api/v1/courses/${courseId}/roles/${roleId}`,
        },
    },

    data() {
        return {
            loading: true,
            fields: [],
            items: [],
            newRoleName: '',
            hideChanged: false,
            changed: {},
            filter: this.$route.query.filterPermissions || '',
        };
    },

    computed: {
        permissionLookup() {
            const res = {};
            Object.values(CoursePermission).forEach(v => {
                res[v.value] = v;
            });
            Object.values(GlobalPermission).forEach(v => {
                res[v.value] = v;
            });
            return res;
        },

        filteredIndices() {
            const filter = (this.filter || '').toLocaleLowerCase();
            return this.items.reduce((acc, perm, i) => {
                if (
                    perm.value.toLocaleLowerCase().indexOf(filter) >= 0 ||
                    perm.name.toLocaleLowerCase().indexOf(filter) >= 0 ||
                    perm.description.toLocaleLowerCase().indexOf(filter) >= 0 ||
                    (perm.warning && perm.warning.toLocaleLowerCase().indexOf(filter) >= 0)
                ) {
                    acc.add(i);
                }
                return acc;
            }, new Set());
        },

        showChangedMessage() {
            return !this.hideChanged && Object.values(this.changed).some(x => x);
        },
    },

    watch: {
        courseId(newVal, oldVal) {
            if (newVal !== oldVal) {
                this.hideChanged = false;
                this.changed = {};
            }
            this.loadData();
        },

        filter() {
            const newQuery = Object.assign({}, this.$route.query);
            newQuery.filterPermissions = this.filter || undefined;

            this.$router.replace({
                query: newQuery,
                hash: this.$route.hash,
            });
        },
    },

    methods: {
        hideWarning() {
            this.hideChanged = true;
        },

        async loadData() {
            this.loading = true;
            await this.getAllPermissions();
            this.loading = false;
        },

        getAllPermissions() {
            return this.$http.get(this.getRetrieveUrl(this.courseId)).then(({ data }) => {
                const fields = [];

                this.items = [];

                data.forEach(item => {
                    fields.push({
                        key: item.name,
                        label: item.name,
                        id: item.id,
                        own: item.own,
                    });

                    let i = 0;
                    Object.entries(item.perms).forEach(([name, value]) => {
                        if (!this.items[i]) {
                            this.items[i] = Object.assign(
                                { name },
                                this.permissionLookup[name]);
                        }
                        this.items[i][item.name] = value;
                        i += 1;
                    });
                });

                this.fields = fields;
            });
        },

        changeButton(i, field) {
            const item = this.items[i];
            const newValue = !item[field.key];
            item[field.key] = 'loading';
            this.$set(this.items, i, item);
            const req = this.$http.patch(this.getChangePermUrl(this.courseId, field.id), {
                value: newValue,
                permission: item.value,
            });
            waitAtLeast(500, req).then(() => {
                this.hideChanged = false;
                const key = `${this.courseId}-${field.id}-${item.name}`;
                this.$set(this.changed, key, !this.changed[key]);
                item[field.key] = newValue;
                this.$set(this.items, i, item);
            });
        },

        removeRole(index) {
            const perm = this.fields[index];
            return this.$http
                .delete(this.getDeleteRoleUrl(this.courseId, perm.id))
                .then(() => index);
        },

        afterRemoveRole(index) {
            this.fields.splice(index, 1);
        },

        addRole() {
            if (this.newRoleName === '') {
                throw new Error('The name cannot be empty!');
            }

            return this.$http.post(`/api/v1/courses/${this.courseId}/roles/`, {
                name: this.newRoleName,
            });
        },

        afterAddRole() {
            this.getAllPermissions().then(() => {
                this.newRole = '';
                this.newRoleName = '';
            });
        },
    },

    mounted() {
        this.loadData();
    },

    components: {
        Icon,
        Loader,
        SubmitButton,
        DescriptionPopover,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.add-role {
    margin-top: 1rem;
}

.perm-warning {
    position: fixed;
    bottom: 0;
    right: 1rem;
    z-index: 8;
    width: max-content;
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

<style lang="less">
.permissions-manager {
    .custom-checkbox {
        padding: 0 !important;

        label {
            display: block;
            text-align: center;

            &::before,
            &::after {
                left: 50%;
                transform: translateX(-50%);
            }
        }
    }
}
</style>
