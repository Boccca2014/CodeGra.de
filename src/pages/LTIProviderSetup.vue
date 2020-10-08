<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="lti-provider-setup">
    <b-alert v-if="error"
             variant="danger"
             class="my-3"
             show>
        {{ $utils.getErrorMessage(error) }}
    </b-alert>
    <lti-provider-setup v-else-if="ltiProvider"
                        @update-provider="ltiProvider = $event"
                        :secret="setupSecret"
                        :lti-provider="ltiProvider" />
    <cg-loader page-loader class="h-100" v-else />
</div>
</template>

<script lang="ts">
import { Vue, Component, Watch } from 'vue-property-decorator';

import LtiProviderSetup from '@/components/LtiProviderSetup';

import * as api from '@/api/v1';

@Component({ components: { LtiProviderSetup } })
export default class LTIProviderSetup extends Vue {
    error: Error | null = null;

    get ltiProviderId(): string {
        return this.$route.params.ltiProviderId;
    }

    get setupSecret(): string | null {
        return this.$route.query.setupSecret ?? null;
    }

    ltiProvider: api.lti.LTIProviderServerData | null = null;

    @Watch('ltiProviderId', { immediate: true })
    onLtiProviderIdChange() {
        this.load();
    }

    async load() {
        this.ltiProvider = null;
        try {
            this.ltiProvider = (await api.lti.getLtiProvider(
                this.ltiProviderId,
                this.setupSecret,
            )).data;
        } catch (e) {
            this.error = e;
        }
    }
}
</script>
