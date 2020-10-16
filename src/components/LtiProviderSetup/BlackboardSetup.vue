<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="blackboard-setup">
    <cg-wizard-wrapper v-if="adminSetup">
        <template #title="{ page, totalPages }">
            Initial blackboard setup {{ page }} / {{ totalPages }}
        </template>

        <template #page-1="{ nextPage }">
            <p class="text-muted">
                For Blackboard you need to create the integration
                yourself before you email the instructions to the system admin.

                Please navigate
                to <a href="https://developer.blackboard.com/portal/applications/create"
                      class="inline-link"
                      target="_blank"
                      >https://developer.blackboard.com/portal/applications/create</a>
                and create a new application with the following data.
            </p>

            <table class="table">
                <thead>
                    <tr>
                        <th>Option</th>
                        <th>Value</th>
                    </tr>
                </thead>

                <tbody>
                    <tr>
                        <td>Application name</td>
                        <td>
                            CodeGrade for
                            <template v-if="ltiProvider.intended_use">
                                {{ ltiProvider.intended_use }}
                            </template>
                            <template v-else>&hellip;</template>
                        </td>
                    </tr>

                    <tr>
                        <td>Description</td>
                        <td><i>Anything, but it cannot be empty.</i></td>
                    </tr>

                    <tr>
                        <td>Domain(s)</td>
                        <td><code>{{ externalHostname }}</code></td>
                    </tr>

                    <tr>
                        <td>My Integration supports LTI 1.3</td>
                        <td>Checked (so in the supported state)</td>
                    </tr>

                    <tr>
                        <td>Login Initiation URL</td>
                        <td><code>{{ loginUrl }}</code></td>
                    </tr>

                    <tr>
                        <td>Tool Redirect URL(s)</td>
                        <td><code>{{ redirectUrls.join(',') }}</code></td>
                    </tr>

                    <tr>
                        <td>Tool JWKS URL</td>
                        <td><code>{{ jwksUrl }}</code></td>
                    </tr>
                </tbody>
            </table>

            <p>
                After clicking "Register application and generate API Key" you
                can
                <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
            </p>
        </template>

        <template #page-2>
            <p>
                You should now be presented with data for the new API
                key. Please copy the data into the provided fields below, if no
                field exists for some piece of data simply ignore it.
            </p>

            <b-form-group class="mb-3">
                <b-input-group prepend="Application ID">
                    <input class="form-control"
                           v-model="clientId" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="Public keyset URL">
                    <input class="form-control"
                           v-model="keySetUrl" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="Auth token endpoint">
                    <input class="form-control"
                           v-model="authTokenUrl" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="OIDC auth request endpoint">
                    <input class="form-control"
                           v-model="authLoginUrl" />
                </b-input-group>
            </b-form-group>


            <cg-submit-button
                class="float-right"
                label="Submit"
                :submit="submitAdminData"
                @after-success="$emit('done')" />
        </template>
    </cg-wizard-wrapper>

    <cg-wizard-wrapper
        v-else
        v-model="wizardPage"
        use-local-header
        :get-next-page-disabled-popover="nextPageDisabled">
        <template #header-wrapper="{ position }"
                  v-if="showLogo">
            <cg-logo :inverted="!darkMode"
                     :style="{ opacity: position === 'prepend' ? 0 : 1 }" />
        </template>
        <template #title="{ page, totalPages }">
            Connect CodeGrade to Blackboard {{ page }} / {{ totalPages }}

        </template>

        <template #page-1="{ nextPage }">
            <p>
                To connect CodeGrade to blackboard first navigate to the "System
                Admin" option in the header, and navigate to the "Integrations" card an click on the
                "LTI Tool Providers" option.
            </p>

            <p>
                You should now be presented with an overview of all the tools in
                your Blackboard environment. To add CodeGrade click on the
                "Register LTI 1.3 Tool" option. If you are presented with a
                screen to add a new LTI tool,
                <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
            </p>
        </template>

        <template #page-2="{ nextPage }">
            <p>
                You should now be presented with an input for a "Client ID", for
                which you should input the following id:
                <code>{{ ltiProvider.client_id }}</code>.

                After clicking submit you should be presented with a screen
                where some information about CodeGrade is already filled in, but
                some data is still missing. Please go through each option on
                this screen and if it is present in the
                table below, input the value from the table.
            </p>

            <h5 class="text-small-uppercase">tool status</h5>

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
                    <tr>
                        <td>Tool Status</td>
                        <td>Approved</td>
                    </tr>

                    <tr>
                        <td>Tool Provider Custom Parameters</td>
                        <td>
                            <div class="copy-wrapper">
                                <pre><code>{{ customParameters }}</code></pre>
                                <cg-submit-button
                                    variant="secondary"
                                    class="copy-btn"
                                    :submit="copyCustomParameters"
                                    label="Copy" />
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>

            <h5 class="text-small-uppercase">institution policies</h5>

            <table class="table">
                <thead>
                    <tr>
                        <th>Option</th>
                        <th>Value</th>
                    </tr>
                </thead>

                <tbody>
                    <tr>
                        <td>User Fields to Send</td>
                        <td><i>All items should be checked</i></td>
                    </tr>

                    <tr>
                        <td>Allow grade service access</td>
                        <td>Yes</td>
                    </tr>

                    <tr>
                        <td>Allow Membership Service Access</td>
                        <td>Yes</td>
                    </tr>
                </tbody>
            </table>

            After inputting all these values please click "Submit" and
            <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
        </template>

        <template #page-3>
            <p>
                After submitting you should be redirected to the overview of all
                LTI tools, in which an item for CodeGrade should now be
                presented. It should have
                the <span class="text-small-uppercase text-secondary">tool type</span> "LTI 1.3
                Tool" and
                the <span class="text-small-uppercase text-secondary">status</span>
                "approved".

            </p>
            <p>
                If this is all correct please create a placement by clicking on
                chevron next to the name of the CodeGrade, and clicking on
                "Manage Placements" in the dropdown. This should load a new page
                with a "Create Placement" button, click on this button. On the
                resulting page please insert the following information.
            </p>

            <table class="table">
                <thead>
                    <tr>
                        <th>Option</th>
                        <th>Value</th>
                    </tr>
                </thead>

                <tbody>
                    <tr>
                        <td>Label</td>
                        <td>CodeGrade</td>
                    </tr>

                    <tr>
                        <td>Handle</td>
                        <td><code>cg-placement-001</code></td>
                    </tr>

                    <tr>
                        <td>Availability</td>
                        <td>Yes</td>
                    </tr>

                    <tr>
                        <td>Type</td>
                        <td>Course content tool, with the sub-option "Allows grading"</td>
                    </tr>

                    <tr>
                        <td>Icon</td>
                        <td>
                            You can download an icon
                            <a :href="secureIconUrl"
                               class="inline-link"
                               download="codegrade-logo-small-white.png"
                               target="_blank"
                               >here</a>.
                        </td>
                    </tr>

                    <tr>
                        <td>Tool Provider URL</td>
                        <td><code>{{ launchUrl }}</code></td>
                    </tr>
                </tbody>
            </table>

            <cg-submit-button
                confirm="After finalizing your configuration you cannot edit it anymore. Are you sure you want to finalize your configuration?"
                class="float-right"
                label="Finalize"
                :submit="finalizeProvider"
                @after-success="afterFinalizeProvider" />
        </template>

        <template #page-4>
            <p class="text-center">
                Your Blackboard integration has been finalized, and is now ready to use!
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
export default class BlackboardSetup extends Vue {
    @Prop({ required: true }) ltiProvider!: api.lti.NonFinalizedLTI1p3ProviderServerData;

    @Prop({ required: true }) secret!: string | null;

    @Prop({ default: false }) adminSetup!: boolean;

    wizardPage: number = 1;

    readonly darkMode!: boolean;

    clientId: string | null = this.ltiProvider.client_id;

    keySetUrl: string | null = this.ltiProvider.key_set_url;

    authTokenUrl: string | null = this.ltiProvider.auth_token_url;

    authLoginUrl: string | null = this.ltiProvider.auth_login_url;

    get showLogo(): boolean {
        return (this.$root as any).$isMediumWindow;
    }

    get redirectUrls(): readonly string[] {
        return [
            this.launchUrl,
            this.$utils.buildUrl(
                ['api', 'v1', 'lti1.3', 'launch_to_latest_submission', this.ltiProvider.id],
                {
                    baseUrl: this.$utils.getExternalUrl(),
                },
            ),
        ];
    }

    get launchUrl(): string {
        return this.$utils.buildUrl(
            ['api', 'v1', 'lti1.3', 'launch', this.ltiProvider.id],
            {
                baseUrl: this.$utils.getExternalUrl(),
            },
        );
    }

    get loginUrl(): string {
        return this.$utils.buildUrl(
            ['api', 'v1', 'lti1.3', 'login', this.ltiProvider.id],
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

    get externalHostname(): string {
        return new URL(this.$utils.getExternalUrl()).hostname;
    }

    get secureIconUrl(): string {
        return this.$utils.buildUrl(
            ['static', 'img', 'blackboard-lti-icon.png'],
        );
    }

    get customParameters(): string {
        return Object.entries(this.ltiProvider.custom_fields)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, value]) => `${key}=${value}`)
            .join('\n');
    }

    copyCustomParameters() {
        return this.$copyText(this.customParameters);
    }

    // eslint-disable-next-line class-methods-use-this
    nextPageDisabled(currentPage: number): string | null {
        if (currentPage === 3) {
            return 'Please finalize the provider';
        }
        return null;
    }

    finalizeProvider() {
        return api.lti.updateLti1p3Provider(this.ltiProvider, this.secret, {
            finalize: true,
        });
    }

    submitAdminData() {
        if (!this.clientId || !this.authTokenUrl || !this.authLoginUrl || !this.keySetUrl) {
            throw new Error('Please provide a value for every input.');
        }

        return api.lti.updateLti1p3Provider(this.ltiProvider, this.secret, {
            client_id: this.clientId,
            auth_token_url: this.authTokenUrl,
            auth_login_url: this.authLoginUrl,
            key_set_url: this.keySetUrl,
        });
    }

    afterFinalizeProvider() {
        this.wizardPage = 4;
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
