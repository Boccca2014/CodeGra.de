<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="canvas-setup">
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
            Connect CodeGrade to Canvas {{ page }} / {{ totalPages }}

        </template>

        <template #page-1="{ nextPage }">
            <p>
                First we need to create a new "Developer Key" for CodeGrade.
            </p>

            <p>
                To do this first open Canvas and login as administrator. Now
                select the "Admin" item in the sidebar and navigate to
                "Developer Keys". A button should appear at the top left of
                your screen with the text "+ Developer Key"; click this button
                and select "LTI Key" in the appearing dropdown.
            </p>

            <p>
                A page should load to configure the new developer key. First change the configure method,
                by selecting the "Enter URL" option from the "method"
                selector. In the field for the "JSON Url" please insert the
                following url:
            </p>

            <pre><code>{{ jsonUrl }}</code></pre>

            <p>
                Now please enter the following urls in the "Redirect URIs" box:
            </p>

            <pre><code>{{ redirectUrl }}</code></pre>

            <p>
                Last, but not least, insert a name for the new key, something
                like "CodeGrade" seems appropriate. Finally click the "save"
                button at the bottom right of your screen, and
                <a href="#" @click.prevent="nextPage" class="inline-link">continue to the next step</a>.
            </p>
        </template>

        <template #page-2="{ nextPage }">
            <p>
                You should now have created the developer keys, and you should
                be back on the overview page for all the Developer keys in
                Canvas. Under the category "Details" there should be a
                relatively long number for the just created key, this is the
                "client id" for CodeGrade. Please copy it, and paste it in the
                input below.

            </p>

            <b-form-group label="Client ID">
                <b-input-group>
                    <input class="form-control" v-model="newClientId"
                           placeholder="The client id from Canvas" />
                </b-input-group>
            </b-form-group>

            <div class="d-flex mb-3 justify-content-end">
                <cg-submit-button :submit="submitClientId" />
            </div>

            <p v-if="ltiProvider.client_id">
                We received the client id, you can
                <a href="#" class="inline-link"
                   @click.prevent="nextPage">continue to the next step</a>.
            </p>
        </template>

        <template #page-3>
            <p>
                For the final step we need to add CodeGrade as an external app
                to the canvas installation.  Select the "Settings" option in the
                sidebar in Canvas, and select the "Apps" tab, and click the
                button to add an app. A modal should appear, and select "By
                Client ID" for the "Configuration Type". For the "Client ID"
                insert <code>{{ ltiProvider.client_id }}</code>.
            </p>

            <p>
                After adding the app please insert the url on which your Canvas
                instance is hosted, and click the "Finalize" button below.
            </p>

            <b-form-group :invalid-feedback="maybeWarningCanvasBaseUrl || ''"
                          label="The base url of your Canvas instance"
                          :state="maybeWarningCanvasBaseUrl == null">
                <b-input-group>
                    <input class="form-control"
                           v-model="canvasBaseUrl"
                           placeholder="https://canvas." />
                </b-input-group>
            </b-form-group>

            <div class="d-flex justify-content-end">
                <cg-submit-button
                    confirm="true"
                    label="Finalize"
                    :submit="finalizeProvider"
                    @after-success="afterFinalizeProvider">
                    <template slot="confirm">
                        After finalizing your configuration you cannot edit it
                        anymore. Are you sure you want to finalize your
                        configuration?
                    </template>
                </cg-submit-button>
            </div>
        </template>

        <template #page-4>
            <p class="text-center">
                Your Canvas integration has been finalized, and is now ready to use!
            </p>
        </template>
    </cg-wizard-wrapper>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop } from 'vue-property-decorator';

import { mapGetters } from 'vuex';
import * as api from '@/api/v1';

// @ts-ignore
import AdvancedCollapse from '@/components/AdvancedCollapse';

@Component({
    components: {
        AdvancedCollapse,
    },
    computed: {
        ...mapGetters('pref', ['darkMode']),
    },
})
export default class CanvasSetup extends Vue {
    @Prop({ required: true }) ltiProvider!: api.lti.NonFinalizedLTI1p3ProviderServerData;

    @Prop({ required: true }) secret!: string | null;

    wizardPage: number = 1;

    readonly darkMode!: boolean;

    newClientId: string | null = this.ltiProvider.client_id;

    canvasBaseUrl: string | null = null;

    get trimmedCanvasBaseUrl() {
        const base = this.canvasBaseUrl;
        if (base == null) {
            return null;
        }
        return base.replace(/\/*$/, '');
    }

    get maybeWarningCanvasBaseUrl() {
        const base = this.trimmedCanvasBaseUrl;
        if (!base) {
            return null;
        } else if (!this.$utils.isValidHttpUrl(base)) {
            return "This doesn't look like valid url.";
        }

        const url = new URL(base);
        if (url.origin !== base) {
            return `It looks like the url contains more than just a
host. This is very likely to be incorrect, so instead of "${base}" it should
probably be "${url.origin}".`;
        } else if (url.protocol !== 'https:') {
            return 'Supplying CodeGrade with non "https" urls is not secure, and we strongly advise you to use https.';
        }

        return null;
    }

    get showLogo(): boolean {
        return (this.$root as any).$isMediumWindow;
    }

    get redirectUrl(): string {
        return (['launch_to_latest_submission', 'launch'] as const).map(
            extraPath => this.$utils.buildUrl(
                ['api', 'v1', 'lti1.3', extraPath],
                {
                    baseUrl: this.$userConfig.externalUrl,
                },
            ),
        ).join('\n');
    }

    get jsonUrl(): string {
        return this.$utils.buildUrl(
            ['api', 'v1', 'lti1.3', 'providers', this.ltiProvider.id, 'config'],
            {
                baseUrl: this.$userConfig.externalUrl,
            },
        );
    }

    nextPageDisabled(currentPage: number): string | null {
        if (currentPage === 3) {
            return 'Please finalize the provider';
        } else if (currentPage === 2 && !this.ltiProvider.client_id) {
            return 'Please fill in the client id from Canvas.';
        }
        return null;
    }

    submitClientId() {
        if (!this.newClientId) {
            throw new Error('Please insert the client id');
        }

        return api.lti.updateLti1p3Provider(this.ltiProvider, this.secret, {
            client_id: this.newClientId,
        }).then(({ data }) => {
            this.$emit('update-provider', data);
        });
    }

    finalizeProvider() {
        const base = this.trimmedCanvasBaseUrl;

        if (base == null) {
            throw new Error('Please insert a base url');
        } else if (!this.$utils.isValidHttpUrl(base)) {
            throw new Error('The base url does not look like a valid url');
        }

        const authTokenUrl = `${base}/login/oauth2/token`;
        const authLoginUrl = `${base}/api/lti/authorize_redirect`;
        const keySetUrl = `${base}/api/lti/security/jwks`;

        return api.lti.updateLti1p3Provider(this.ltiProvider, this.secret, {
            auth_token_url: authTokenUrl,
            auth_login_url: authLoginUrl,
            key_set_url: keySetUrl,
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
    margin-bottom: 1rem;
    color: @color-code;
}
</style>
