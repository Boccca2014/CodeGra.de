<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="sso-providers">
    <b-alert variant="danger" class="mt-3 mb-0" show v-if="error">
        {{ $utils.getErrorMessage(error) }}
    </b-alert>
    <div v-else-if="providers != null">
        <template v-if="providers.length > 0">
            <slot  />
        </template>

        <ul class="mb-0 list-group">
            <li v-for="provider in providers" :key="provider.id"
                :class="{ 'clickable': !adminMode }"
                class="list-group-item sso-provider-list-item p-0">
                <a :href="adminMode ? undefined : provider.loginUrl"
                   class="sso-link d-block"
                   @click.prevent="() => !adminMode && $emit('saml-login', provider)">
                    <div class="d-flex flex-row">
                        <img :src="provider.logoUrl"
                             class="d-block pr-3"
                             :style="`max-width: ${minWidth / 2}px;`"
                             :alt="`Logo for ${provider.name}`"
                             height="auto"
                             width="auto" />
                        <div>
                            <h4>{{ provider.name }}</h4>

                            <p>{{ provider.description }}</p>

                            <p v-if="adminMode">
                                <b>SP metadata URL:</b>
                                <a :href="provider.metadataUrl" v-if="adminMode">{{ provider.metadataUrl }}</a>
                            </p>
                        </div>
                    </div>
                </a>
            </li>
        </ul>
        <div v-if="adminMode">
            <hr v-if="providers && providers.length > 0" />
            <h6>Create a new SSO Identity Provider</h6>
            <b-form>
                <b-form-group label="Metadata URL">
                    <input type="text"
                           class="form-control"
                           placeholder="Enter metadata url"
                           v-model="newProviderMetadataUrl"
                           @keyup.enter="() => $refs.create.onClick()"/>
                </b-form-group>

                <b-form-group label="Backup name"
                              description="If no name can be found in the metadata of the IdP this will be displayed to the user.">
                    <input type="text"
                           class="form-control"
                           placeholder="Enter name"
                           v-model="newProviderMetadataName"
                           @keyup.enter="() => $refs.create.onClick()"/>
                </b-form-group>

                <b-form-group label="Backup description"
                              description="If no description can be found in the metadata of the IdP this will be displayed to the user.">
                    <input type="text"
                           class="form-control"
                           placeholder="Enter description"
                           v-model="newProviderMetadataDescription"
                           @keyup.enter="() => $refs.create.onClick()"/>
                </b-form-group>

                <b-form-group
                    label="Logo URL"
                    description="If no logo can be found in the metadata of the IdP this will be displayed instead.">
                    <multiple-files-uploader
                        disable-multiple-files
                        v-model="newProviderLogo"
                        class="rounded" />
                </b-form-group>


                <div class="text-right">
                    <cg-submit-button
                        ref="create"
                        :submit="createNew"
                        @after-success="afterCreate" />
                </div>
            </b-form>
        </div>
    </div>
    <cg-loader v-else-if="adminMode" />
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop } from 'vue-property-decorator';
import { AxiosResponse } from 'axios';

// @ts-ignore
import MultipleFilesUploader from '@/components/MultipleFilesUploader';

import * as api from '@/api/v1';
import * as models from '@/models';

@Component({ components: { MultipleFilesUploader } })
export default class SSOProviders extends Vue {
    providers: null | models.SSOProvider[] = null;

    error: Error | null = null;

    @Prop({ default: false })
    adminMode!: boolean;

    private newProviderMetadataUrl: string = '';

    private newProviderMetadataName: string = '';

    private newProviderMetadataDescription: string = '';

    private newProviderLogo: readonly any[] = [];

    mounted() {
        this.loadData();
    }

    async loadData() {
        this.providers = null;
        this.error = null;

        try {
            this.providers = await api.ssoProviders.get();
        } catch (e) {
            this.error = e;
        }
    }

    createNew() {
        if (this.newProviderLogo.length !== 1) {
            return Promise.reject(new Error('You should upload exactly one logo'));
        }
        const json = {
            metadata_url: this.newProviderMetadataUrl,
            name: this.newProviderMetadataName,
            description: this.newProviderMetadataDescription,
        };
        const data = new FormData();
        data.append('logo', this.newProviderLogo[0]);
        data.append(
            'json',
            new Blob(
                [JSON.stringify(json)],
                { type: 'application/json' },
            ),
        );
        return this.$http.post('/api/v1/sso_providers/', data);
    }

    afterCreate(response: AxiosResponse<models.Saml2ProviderServerData>) {
        if (this.providers == null) {
            this.providers = [];
        }
        this.providers.push(models.makeSSOProvider(response.data));
    }

    get minWidth(): number {
        if (this.providers == null || this.providers.length === 0) {
            return 0;
        }

        let min = 200;
        this.providers.forEach(prov => {
            if (prov.logo == null) {
                return;
            }
            min = Math.min(min, prov.logo.width);
        });
        return min;
    }
}
</script>

<style lang="less" scoped>
@import '~mixins.less';

.sso-providers .sso-provider-list-item {
    // We style the dark mode to be light too, as the logo's we're provided
    // probably don't work with a dark background.
    @{dark-mode} {
        background-color: white;
        .sso-link {
            color: @text-color !important;
        }

        &.clickable:hover {
            background-color: darken(white, 7.5) !important;
        }
    }

    &.clickable:hover {
        background-color: rgba(0, 0, 0, 0.075) !important;
        cursor: pointer;
    }
    img {
        margin: auto 1rem;
        object-fit: scale-down;
    }

    .sso-link {
        padding: 0.75rem 1.25rem;
    }
}
</style>
