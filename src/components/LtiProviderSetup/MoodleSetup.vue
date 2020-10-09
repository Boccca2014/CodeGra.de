<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="moodle-setup">
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
            Connect CodeGrade to Moodle {{ page }} / {{ totalPages }}

        </template>

        <template #page-1="{ nextPage }">
            <p>
                To connect CodeGrade to moodle first navigate to the "Site
                administration" item in the sidebar. Now select the "Plugins"
                tab and click on the "Manage tools" link.
            </p>

            <p>
                You should now be presented with an overview of all the tools in
                your Moodle environment. To add CodeGrade click on the
                "configure a tool manually" link. If you are presented with a screen to add a new LTI tool,
                <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
            </p>
        </template>

        <template #page-2="{ nextPage }">
            <p>
                On the page in Moodle we need to fill in quite a lot of
                information. Please click the "Expand all" link,
                and wherever possible the "Show less" links. Now we need to go
                through each option presented by Moodle, and if it is present in
                the table below please copy the value, if it is not present
                please keep the default value in Moodle.
            </p>

            <h4>Tool settings</h4>

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
                        <td>Tool name</td>
                        <td>CodeGrade</td>
                    </tr>
                    <tr>
                        <td>Tool URL</td>
                        <td><code>{{ launchUrl }}</code></td>
                    </tr>

                    <tr>
                        <td>Tool description</td>
                        <td>The complete feedback environment for computer science.</td>
                    </tr>

                    <tr>
                        <td>LTI version</td>
                        <td>LTI 1.3</td>
                    </tr>

                    <tr>
                        <td>Public key</td>
                        <td>
                            <div class="copy-wrapper">
                                <pre>{{ ltiProvider.public_key }}</pre>

                                <cg-submit-button
                                    variant="secondary"
                                    class="copy-btn"
                                    :submit="copyPublicKey"
                                    label="Copy" />
                            </div>
                        </td>
                    </tr>

                    <tr>
                        <td>Initiate login URL</td>
                        <td><code>{{ loginUrl }}</code></td>
                    </tr>

                    <tr>
                        <td> Redirection URI(s)</td>
                        <td><code>{{ redirectUrls.join('\n') }}</code></td>
                    </tr>

                    <tr>
                        <td>Custom parameters</td>
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

                    <tr>
                        <td>
                            Tool configuration usage
                            <cg-description-popover hug-text>
                                This option is not necessary for the functioning
                                of your integration, but makes it easier for
                                teacher to add new CodeGrade assignments.
                            </cg-description-popover>
                        </td>
                        <td>Show in activity chooser and as a preconfigured tool</td>
                    </tr>

                    <tr>
                        <td>Icon URL</td>
                        <td><code>{{ secureIconUrl }}</code></td>
                    </tr>

                    <tr>
                        <td>Secure icon URL</td>
                        <td><code>{{ secureIconUrl }}</code></td>
                    </tr>
                </tbody>
            </table>

            <h4>Services</h4>
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
                        <td>IMS LTI Assignment and Grade Services</td>
                        <td>Use this service for grade sync only</td>
                    </tr>
                    <tr>
                        <td>IMS LTI Names and Role Provisioning</td>
                        <td>Use this service to retrieve members' information as per privacy settings</td>
                    </tr>
                </tbody>
            </table>

            <h4>Privacy</h4>
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
                        <td>Share launcher's name with tool</td>
                        <td>Always</td>
                    </tr>
                    <tr>
                        <td>Share launcher's email with tool</td>
                        <td>Always</td>
                    </tr>

                    <tr>
                        <td>Accept grades from the tool</td>
                        <td>Always</td>
                    </tr>

                    <tr>
                        <td>Force SSL</td>
                        <td>Checked</td>
                    </tr>
                </tbody>
            </table>

            After inputting all these values please click "Save changes" in
            Moodle and
            <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
        </template>

        <template #page-3>
            <p>
                After saving, an item for CodeGrade should appear under "Tools".
                In this item please click the list icon (<icon name="list" />),
                this should open a modal, with a lot of information, please copy
                that information into the inputs below.
            </p>

            <b-form-group class="mb-3">
                <b-input-group prepend="Platform ID">
                    <input class="form-control"
                           v-model="iss" />
                </b-input-group>
            </b-form-group>

            <b-form-group class="mb-3">
                <b-input-group prepend="Client ID">
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
                <b-input-group prepend="Access token URL">
                    <input class="form-control"
                           v-model="authTokenUrl" />
                </b-input-group>
            </b-form-group>

            <b-form-group>
                <b-input-group prepend="Authentication request URL">
                    <input class="form-control"
                           v-model="authLoginUrl" />
                </b-input-group>
            </b-form-group>

            <cg-submit-button
                confirm="After finalizing your configuration you cannot edit it anymore. Are you sure you want to finalize your configuration?"
                class="float-right"
                label="Finalize"
                :submit="finalizeProvider"
                @after-success="afterFinalizeProvider" />
        </template>

        <template #page-4>
            <p class="text-center">
                Your Moodle integration has been finalized, and is now ready to use!
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
export default class MoodleSetup extends Vue {
    @Prop({ required: true }) ltiProvider!: api.lti.NonFinalizedLTI1p3ProviderServerData;

    @Prop({ required: true }) secret!: string | null;

    wizardPage: number = 1;

    readonly darkMode!: boolean;

    clientId: string | null = null;

    keySetUrl: string | null = null;

    authTokenUrl: string | null = null;

    authLoginUrl: string | null = null;

    iss: string | null = this.ltiProvider.iss;

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

    get secureIconUrl(): string {
        return this.$utils.buildUrl(
            ['static', 'favicon', 'android-chrome-512x512.png'],
            {
                baseUrl: this.$utils.getExternalUrl(),
            },
        );
    }

    get customParameters(): string {
        return Object.entries(this.ltiProvider.custom_fields)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, value]) => `${key}=${value}`)
            .join('\n');
    }

    copyPublicKey() {
        return this.$copyText(this.ltiProvider.public_key);
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
        if (!this.clientId || !this.authTokenUrl || !this.authLoginUrl || !this.keySetUrl ||
                !this.iss) {
            throw new Error('Please provide a value for every input.');
        }

        return api.lti.updateLti1p3Provider(this.ltiProvider, this.secret, {
            client_id: this.clientId,
            auth_token_url: this.authTokenUrl,
            auth_login_url: this.authLoginUrl,
            key_set_url: this.keySetUrl,
            iss: this.iss,
            finalize: true,
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
