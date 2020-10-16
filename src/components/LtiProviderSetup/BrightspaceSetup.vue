<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="brightspace-setup">
    <cg-wizard-wrapper
        v-model="wizardPage"
        use-local-header
        :get-next-page-disabled-popover="nextPageDisabled">
        <template #header-wrapper="{ position }"
                  v-if="showLogo">
            <cg-logo :inverted="!darkMode"
                     :style="{ opacity: position === 'prepend' ? 0 : 1 }" />
        </template>
        <template #title="{ page, totalPages }">
            Connect CodeGrade to Brightspace {{ page }} / {{ totalPages }}

        </template>

        <template #page-1="{ nextPage }">
            <p>
                To connect CodeGrade to Brightspace first open Brightspace and
                click on the gear icon on the top right of your screen. A
                dropdown should appear, in which you should select the "Manage
                Extensibility" option. A new page should load, in which you
                should select the "LTI Advantage" tab.
            </p>

            <p>
                You should now be presented with an overview of all the
                registered tools in your Brightspace environment. To add
                CodeGrade click on the "Register Tool" button. If you
                are presented with a screen to register a new LTI tool,
                <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
            </p>
        </template>

        <template #page-2="{ nextPage }">
            <p>
                On the page in Brightspace we need to fill in the information to
                register a new tool. We need to go through each option presented
                by Brightspace, and if it is present in the table below please
                copy the value, if it is not present please keep the default
                value in Brightspace.
            </p>

            <table class="table table-sm">
                <thead>
                    <tr>
                        <th>
                            Option name
                        </th>
                        <th>
                            Value
                        </th>
                    </tr>
                </thead>

                <tbody>
                    <tr class="table-secondary">
                    </tr>
                    <tr>
                        <td>Name</td>
                        <td>CodeGrade</td>
                    </tr>

                    <tr>
                        <td>Description</td>
                        <td>{{ cgDescription }}</td>
                    </tr>

                    <tr>
                        <td>Domain</td>
                        <td><code>{{ $utils.getExternalUrl() }}</code></td>
                    </tr>

                    <tr>
                        <td>
                            Redirect URLs
                            <cg-description-popover>
                                You need to click the "Add Redirect URL" link to
                                add the second url present in this list.
                            </cg-description-popover>
                        </td>
                        <td>
                            <ul class="pl-3">
                                <li v-for="url in redirectUrls">
                                    <code>{{ url }}</code>
                                </li>
                            </ul>
                        </td>
                    </tr>

                    <tr>
                        <td>OpenID Connect Login URL</td>
                        <td><code>{{ loginUrl }}</code></td>
                    </tr>

                    <tr>
                        <td>Keyset URL</td>
                        <td><code>{{ jwksUrl }}</code></td>
                    </tr>

                    <tr>
                        <td>Extensions</td>
                        <td><i>All items should be checked</i></td>
                    </tr>

                    <tr>
                        <td>Roles</td>
                        <td>Send Institution Role should be enabled</td>
                    </tr>
                </tbody>
            </table>

            <p>
                After inputting all these values please click "Save" in
                Brightspace and
                <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
            </p>
        </template>

        <template #page-3="{ nextPage }">
            <p>
                After clicking "Save" in Brightspace the page should reload and
                and the bottom of the page some information should appear under
                the header "Brightspace Registration Details". Please copy that
                information into the inputs below.
            </p>

            <b-form-group class="mb-3">
                <b-input-group prepend="Client Id">
                    <input class="form-control"
                           v-model="clientId" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="Brightspace Keyset URL">
                    <input class="form-control"
                           v-model="keySetUrl" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="Brightspace OAuth2 Access Token URL">
                    <input class="form-control"
                           v-model="authTokenUrl" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="OpenID Connect Authentication Endpoint">
                    <input class="form-control"
                           v-model="authLoginUrl" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="Brightspace OAuth2 Audience">
                    <input class="form-control"
                           v-model="authAudience" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="Issuer">
                    <input class="form-control"
                           v-model="iss" />
                </b-input-group>
            </b-form-group>

            <div class="text-right">
                <cg-submit-button :submit="submitInitialInformation"
                                  label="Submit" />
            </div>

            <p v-if="ltiProvider.client_id">
                You can
                <a href="#" class="inline-link"
                   @click.prevent="nextPage">continue to the next step</a>.
            </p>
        </template>

        <template #page-4="{ nextPage }">
            <p>
                Now we need to create a deployment for CodeGrade. Please click
                the "View Deployments" link at the bottom of the page in
                Brightspace. This should navigate you to a new page which should
                display all the current LTI Advantage deployments for you
                Brightspace instance.
            </p>
            <p>
                Click the "New Deployment" button, after
                which you should be presented with a page to create the new
                deployment. Please go through each option presented by
                Brightspace again, and copy the value from the table below, if it is
                not present please keep the default value in Brightspace.
            </p>

            <table class="table">
                <thead>
                    <tr>
                        <th>
                            Option name
                        </th>
                        <th>
                            Value
                        </th>
                    </tr>
                </thead>

                <tbody>
                    <tr>
                        <td>Tool</td>
                        <td>CodeGrade</td>
                    </tr>

                    <tr>
                        <td>Name</td>
                        <td>CodeGrade</td>
                    </tr>

                    <tr>
                        <td>Description</td>
                        <td>{{ cgDescription }}</td>
                    </tr>

                    <tr>
                        <td>Extensions</td>
                        <td><i>All items should be checked</i></td>
                    </tr>

                    <tr>
                        <td>Security Settings</td>
                        <td><i>Select all items except "Anonymous"</i></td>
                    </tr>

                    <tr>
                        <td>Make tool available to:</td>
                        <td>
                            Select all parts of your organization that should be
                            able to use CodeGrade
                        </td>
                    </tr>
                </tbody>
            </table>

            <p>
                After inputting all these values please click "Save" in
                Brightspace and
                <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
            </p>
        </template>

        <template #page-5="{ nextPage }">
            <p>
                We're almost finished now, we just need to create a "Link" for
                CodeGrade. To do this click on the "View Links" link in
                Brightspace. The page this link will load should contain a "New
                Link" button, please click it. This will open up a screen to
                create a new link. Please copy the information from the table
                below into the inputs in Brightspace, again ignoring information
                not present in the table below.
            </p>

            <table class="table">
                <thead>
                    <tr>
                        <th>Option name</th>
                        <th>Value</th>
                    </tr>
                </thead>

                <tbody>
                    <tr>
                        <td>Name</td>
                        <td>CodeGrade</td>
                    </tr>

                    <tr>
                        <td>URL</td>
                        <td><code>{{ launchUrl }}</code></td>
                    </tr>

                    <tr>
                        <td>Description</td>
                        <td>{{ cgDescription }}</td>
                    </tr>

                    <tr>
                        <td>Type</td>
                        <td>Deep Linking Quicklink</td>
                    </tr>

                    <tr>
                        <td>Substitution Parameters</td>
                        <td>
                            The following pairs should be inputted, please
                            ignore any pair for which you cannot find the value
                            in the dropdown in Brightspace.
                            <table class="table mt-1">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Value</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="[key, value] in customParameters">
                                        <td><code>{{ key }}</code></td>
                                        <td><code>{{ value }}</code></td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                    </tr>
                </tbody>
            </table>

            <p>
                After inputting all these values please click "Save" in Brightspace
                and click the finalize registration button below.
            </p>

            <cg-submit-button
                confirm="After finalizing your configuration you cannot edit it anymore. Are you sure you want to finalize your configuration?"
                class="float-right"
                label="Finalize"
                :submit="finalizeProvider"
                @after-success="afterFinalizeProvider" />
        </template>

        <template #page-6>
            <p class="text-center">
                Your Brightspace integration has been finalized, and is now ready to use!
            </p>
        </template>
    </cg-wizard-wrapper>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop } from 'vue-property-decorator';

// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/list';

import { mapGetters } from 'vuex';
import * as api from '@/api/v1';

@Component({
    components: {
        Icon,
    },
    computed: {
        ...mapGetters('pref', ['darkMode']),
    },
})
export default class BrightspaceSetup extends Vue {
    @Prop({ required: true }) ltiProvider!: api.lti.NonFinalizedLTI1p3ProviderServerData;

    @Prop({ required: true }) secret!: string | null;

    wizardPage: number = 1;

    readonly darkMode!: boolean;

    clientId: string | null = this.ltiProvider.client_id;

    keySetUrl: string | null = this.ltiProvider.key_set_url;

    authTokenUrl: string | null = this.ltiProvider.auth_token_url;

    authLoginUrl: string | null = this.ltiProvider.auth_login_url;

    authAudience: string | null = this.ltiProvider.auth_audience;

    iss: string | null = this.ltiProvider.iss;

    // eslint-disable-next-line class-methods-use-this
    get cgDescription(): string {
        return 'The complete feedback environment for computer science.';
    }

    get showLogo(): boolean {
        return (this.$root as any).$isMediumWindow;
    }

    get redirectUrls(): readonly string[] {
        return [
            this.launchUrl,
            this.$utils.buildUrl(
                ['api', 'v1', 'lti1.3', 'launch_to_latest_submission'],
                {
                    baseUrl: this.$utils.getExternalUrl(),
                },
            ),
        ];
    }

    get launchUrl(): string {
        return this.$utils.buildUrl(
            ['api', 'v1', 'lti1.3', 'launch'],
            {
                baseUrl: this.$utils.getExternalUrl(),
            },
        );
    }

    get loginUrl(): string {
        return this.$utils.buildUrl(
            ['api', 'v1', 'lti1.3', 'login'],
            {
                baseUrl: this.$utils.getExternalUrl(),
            },
        );
    }

    get jwksUrl(): string {
        return this.$utils.buildUrl(
            ['api', 'v1', 'lti1.3', 'providers', this.ltiProvider.id, 'jwks'], {
                baseUrl: this.$utils.getExternalUrl(),
            },
        );
    }

    get secureIconUrl(): string {
        return this.$utils.buildUrl(
            ['static', 'favicon', 'android-chrome-512x512.png'],
            {
                baseUrl: this.$utils.getExternalUrl(),
            },
        );
    }

    get customParameters(): [string, string][] {
        return Object.entries(this.ltiProvider.custom_fields)
            .sort(([a], [b]) => a.localeCompare(b));
    }

    // eslint-disable-next-line class-methods-use-this
    nextPageDisabled(currentPage: number): string | null {
        if (currentPage === 3 && !this.ltiProvider.client_id) {
            return 'Please fill in the required information';
        } else if (currentPage === 5) {
            return 'Please finalize the provider';
        }
        return null;
    }

    submitInitialInformation() {
        if (!this.clientId || !this.authTokenUrl || !this.authLoginUrl ||
            !this.keySetUrl || !this.authAudience || !this.iss) {
            throw new Error('Please provide a value for every input.');
        }

        return api.lti.updateLti1p3Provider(this.ltiProvider, this.secret, {
            client_id: this.clientId,
            auth_token_url: this.authTokenUrl,
            auth_login_url: this.authLoginUrl,
            key_set_url: this.keySetUrl,
            auth_audience: this.authAudience,
            iss: this.iss,
        }).then(response => {
            this.$emit('update-provider', response.data);
            return response;
        });
    }

    finalizeProvider() {
        return api.lti.updateLti1p3Provider(this.ltiProvider, this.secret, {
            finalize: true,
        });
    }

    afterFinalizeProvider() {
        this.wizardPage = 6;
    }
}
</script>

<style lang="less" scoped>
@import '~mixins.less';

.cg-logo {
    height: 1.5rem;
    width: auto;
}

pre {
    display: block;
    margin-bottom: 0;
    code {
        color: @color-code;
    }
}
.copy-btn {
    position: absolute;
    top: 0.25rem;
    right: 0.25rem;

    transition-property: opacity, transform;
    transition-duration: @transition-duration;
    transform: scale(0);
    opacity: 0;

    .add-space & {
        margin: 1rem;
    }

    .copy-wrapper:hover &,
    &.fixed {
        transform: scale(1);
        opacity: 1;
    }
}
</style>
