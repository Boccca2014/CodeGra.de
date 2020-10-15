<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="page admin">
    <local-header title="Admin" always-show-extra-slot>
        <template #extra>
            <category-selector
                default="permissions"
                v-model="selectedCat"
                :categories="categories"/>
        </template>
    </local-header>

    <loader v-if="loading"/>
    <div class="row" v-else>
        <div v-if="selectedCat === 'permissions'" class="col-12">
            <div v-if="impersonate">
                <b-card header="Impersonate user">
                    <impersonate-user />
                </b-card>
            </div>

            <div v-if="manage">
                <b-card header="Manage site permissions">
                    <permissions-manager :showAddRole="false"
                                         fixedPermission="can_manage_site_users"
                                         :showDeleteRole="false"
                                         :getChangePermUrl="(_, roleId) => `/api/v1/roles/${roleId}`"
                                         :getRetrieveUrl="() => '/api/v1/roles/'"/>
                </b-card>
            </div>
        </div>

        <div class="col-12" v-if="selectedCat === 'lti'">
            <b-card header="LTI providers">
                <lti-providers />
            </b-card>
        </div>

        <div class="col-12" v-if="selectedCat === 'sso'">
            <b-card header="SSO Providers">
                <sso-providers admin-mode />
            </b-card>
        </div>

        <div class="col-12" v-if="selectedCat === 'settings'">
            <b-card header="Site Settings">
                <site-settings-editor />
            </b-card>
        </div>
    </div>
</div>
</template>

<script>
import { mapGetters } from 'vuex';
import { LocalHeader, PermissionsManager, Loader, ImpersonateUser, LtiProviders, SsoProviders, CategorySelector, SiteSettingsEditor } from '@/components';

import { setPageTitle } from './title';

export default {
    name: 'user-page',

    components: {
        PermissionsManager,
        Loader,
        LocalHeader,
        ImpersonateUser,
        LtiProviders,
        SsoProviders,
        CategorySelector,
        SiteSettingsEditor,
    },

    data() {
        return {
            manage: false,
            impersonate: false,
            manageLtiproviders: false,
            manageSsoproviders: false,
            manageSiteSettings: false,
            loading: true,
            selectedCat: 'general',
        };
    },

    mounted() {
        setPageTitle('Admin page');
        // Do not forget to add new permissions to constants file
        this.$hasPermission(['can_manage_site_users', 'can_impersonate_users', 'can_manage_lti_providers', 'can_manage_sso_providers', 'can_manage_site_settings']).then(
            ([manage, impersonate, ltiProviders, ssoProviders, siteSettings]) => {
                this.manage = manage;
                this.impersonate = impersonate;
                this.manageLtiproviders = ltiProviders;
                this.manageSsoproviders = ssoProviders;
                this.manageSiteSettings = siteSettings;
                this.loading = false;
            },
        );
    },

    computed: {
        ...mapGetters('user', ['loggedIn']),

        categories() {
            return [
                {
                    id: 'permissions',
                    name: 'Permissions',
                    enabled: this.impersonate || this.manage,
                },
                {
                    id: 'lti',
                    name: 'LTI',
                    enabled: this.manageLtiproviders,
                },
                {
                    id: 'sso',
                    name: 'Single Sign-On',
                    enabled: this.manageSsoproviders,
                },
                {
                    id: 'settings',
                    name: 'Site Settings',
                    enabled: this.manageSiteSettings,
                },
            ];
        },
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.row > div:not(.col-12) .card:not(:first-child) {
    margin-top: 15px;

    @media @media-no-medium {
        .card {
            margin-top: 15px;
        }
    }
}

.card {
    margin-bottom: 15px;
}

.permissions-manager {
    margin: -1.25rem;
}
</style>
