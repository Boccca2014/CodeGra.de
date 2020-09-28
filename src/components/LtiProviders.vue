<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="lti-providers">
    <b-modal ref="blackboardModal"
             v-if="newBlackboardProvider"
             size="lg"
             no-close-on-backdrop
             no-close-on-escape
             hide-footer
             hide-header>
        <blackboard-setup
            @done="() => blackboardModal.hide()"
            :secret="null"
            :lti-provider="newBlackboardProvider"
            admin-setup />
    </b-modal>

    <b-alert variant="danger" class="m-0" show v-if="error">
        {{ error }}
        {{ $utils.getErrorMessage(error) }}
    </b-alert>
    <div v-else-if="ltiProviders != null">
        <table class="table mb-0">
            <thead>
                <tr>
                    <th>Version</th>
                    <th>For who</th>
                    <th>LMS</th>
                    <th>Finalized</th>
                    <th class="shrink" />
                </tr>
            </thead>
            <tbody>
                <tr v-for="ltiProvider in ltiProviders"
                    :key="ltiProvider.id">
                    <td class="text-small-uppercase">{{ ltiProvider.version }}</td>
                    <td>
                        <span v-if="ltiProvider.intended_use">{{ ltiProvider.intended_use }}</span>
                        <span v-else class="text-muted">Unknown</span>
                    </td>
                    <td>
                        {{ ltiProvider.lms }}
                        <template v-if="ltiProvider.version === 'lti1.3'">
                            (<code>{{ ltiProvider.iss }}</code>)
                        </template>
                    </td>
                    <td>{{ ltiProvider.finalized ? 'Yes' : 'No' }}</td>
                    <td class="shrink">
                        <template v-if="!ltiProvider.finalized">
                            <a href="#" class="inline-link"
                               @click.prevent="copyEditLink(ltiProvider)">
                                Copy edit link
                            </a>
                            <cg-description-popover hug-text>
                                This link can be used by anyone, even non
                                logged in users for as long as the setup is not
                                finalized. Please only distribute to one person!
                            </cg-description-popover>

                            <template v-if="ltiProvider.version === 'lti1.3' && ltiProvider.lms === 'Blackboard'">
                                <a href="#" class="inline-link"
                                   @click.prevent="initialSetupBlackboardProvider(ltiProvider)">
                                    Setup blackboard
                                </a>
                            </template>
                        </template>
                    </td>
                </tr>
            </tbody>
        </table>

        <div class="mt-3">
            <h6>Create a new LTI provider</h6>
            <b-form-group label="LTI version">
                <b-form-select
                    :value="newLMS && newLMS.version"
                    placeholder="LTI version"
                    @input="createNewLMS">
                    <template v-slot:first>
                        <b-form-select-option :value="null" disabled>Please select the LTI version</b-form-select-option>
                    </template>

                    <b-form-select-option value="lti1.1">
                        lti1.1
                    </b-form-select-option>
                    <b-form-select-option value="lti1.3">
                        lti1.3
                    </b-form-select-option>
                </b-form-select>
            </b-form-group>

            <b-form-group label="LMS name" v-if="newLMS">
                <b-form-select
                    :value="newLMS.name"
                    placeholder="LMS"
                    @input="setProviderName">
                    <template v-slot:first>
                        <b-form-select-option :value="null" disabled>Please select the LMS</b-form-select-option>
                    </template>

                    <b-form-select-option v-for="opt in lmsOptions"
                                          :value="opt.value"
                                          :key="opt.value">
                        {{ opt.text }}
                    </b-form-select-option>
                </b-form-select>
            </b-form-group>

            <template v-if="newLMS && newLMS.name">
                <b-form-group>
                    <label>
                        For which institution is this connection?
                        <cg-description-popover hug-text>
                            <p>
                                This value is not used internally by CodeGrade, it
                                is just for easier accounting of all providers.
                            </p>
                            <p v-if="newLMS.version === 'lti1.1'">
                                It <b>is</b> communicated to customers!
                            </p>
                        </cg-description-popover>
                    </label>
                    <input class="form-control"
                           placeholder="e.g. Universiteit van Amsterdam"
                           v-model="newLMS.forWho"/>
                </b-form-group>
            </template>

            <template v-if="newLMS && newLMS.version === 'lti1.3' && newLMS.name">
                <b-form-group>
                    <label>
                        The ISS of the new integration
                    </label>
                    <input class="form-control"
                           v-model="newLMS.iss"
                           :disabled="issDisabled"
                           :placeholder="issPlaceholder"/>
                </b-form-group>
            </template>

            <template v-if="newLMS && newLMS.name">
                <cg-submit-button :submit="submitNewProvider"
                                  @after-success="afterSubmitNewProvider"
                                  class="float-right"
                                  confirm="Are you sure you want to create a new LTI Provider?"
                                  confirm-in-modal />
            </template>
        </div>

    </div>
    <div v-else>
        <cg-loader />
    </div>
</div>
</template>

<script lang="ts">
import { Vue, Component, Ref } from 'vue-property-decorator';
import { LTI1p1ProviderNames, LTI1p1ProviderName, LTI1p3ProviderNames, LTI1p3ProviderName } from '@/lti_providers';
import { BModal } from 'bootstrap-vue';

import * as api from '@/api/v1';

import BlackboardSetup from './LtiProviderSetup/BlackboardSetup';

type NewLTI1p1 = {
    version: 'lti1.1';
    name: LTI1p1ProviderName | null;
    forWho: string | null;
};

type NewLTI1p3 = {
    version: 'lti1.3';
    name: LTI1p3ProviderName | null;
    forWho: string | null;
    iss: string | null;
};

@Component({ components: { BlackboardSetup } })
export default class LtiProviders extends Vue {
    error: Error | null = null;

    ltiProviders: api.lti.LTIProviderServerData[] | null = null;

    newLMS: NewLTI1p1 | NewLTI1p3 | null = null;

    newBlackboardProvider: api.lti.LTI1p3ProviderServerData | null = null;

    @Ref() readonly blackboardModal!: BModal;

    mounted() {
        this.load();
    }

    async load() {
        this.ltiProviders = null;
        this.error = null;

        try {
            this.ltiProviders = (await api.lti.getAllLtiProviders()).data;
        } catch (e) {
            this.error = e;
        }
    }

    // eslint-disable-next-line class-methods-use-this
    get lmsOptions() {
        if (this.newLMS == null) {
            return [];
        }
        switch (this.newLMS.version) {
        case 'lti1.1':
            return LTI1p1ProviderNames.map(cur => ({ value: cur, text: cur }));
        case 'lti1.3':
            return LTI1p3ProviderNames.map(cur => ({ value: cur, text: cur }));
        default:
            return this.$utils.AssertionError.assertNever(this.newLMS);
        }
    }

    get issDisabled(): boolean {
        if (this.newLMS == null || this.newLMS.version === 'lti1.1') {
            return true;
        }

        const name = this.newLMS.name;
        switch (name) {
        case 'Brightspace':
        case 'Moodle':
        case 'Canvas':
        case null:
            return false;
        case 'Blackboard':
            return true;
        default:
            return this.$utils.AssertionError.assertNever(name);
        }
    }

    get issPlaceholder(): string {
        if (this.newLMS == null || this.newLMS.version === 'lti1.1') {
            return '';
        }

        const name = this.newLMS.name;
        switch (name) {
        case 'Brightspace':
        case 'Moodle':
        case 'Blackboard':
            return 'The ISS for the new provider, this is the url on which the LMS is hosted.';
        case null:
        case 'Canvas':
            return '';
        default:
            return this.$utils.AssertionError.assertNever(name);
        }
    }

    createNewLMS(version: 'lti1.1' | 'lti1.3') {
        switch (version) {
            case 'lti1.1': {
                this.newLMS = {
                    version,
                    forWho: null,
                    name: null,
                };
                break;
            }
            case 'lti1.3': {
                this.newLMS = {
                    version,
                    forWho: null,
                    name: null,
                    iss: null,
                };
                break;
            }
            default: this.$utils.AssertionError.assertNever(version);
        }
    }

    setProviderName(name: LTI1p3ProviderName | LTI1p1ProviderName | null): void {
        this.$utils.AssertionError.assert(this.newLMS != null);

        switch (this.newLMS.version) {
            case 'lti1.1': {
                this.$utils.AssertionError.assert(
                    name == null || LTI1p1ProviderNames.find(k => k === name) === name,
                );
                this.newLMS.name = name;
                break;
            }

            case 'lti1.3': {
                this.$utils.AssertionError.assert(
                    name == null || LTI1p3ProviderNames.find(k => k === name) === name,
                );
                this.newLMS.name = name;

                switch (name) {
                    case 'Canvas':
                        this.newLMS.iss = 'https://canvas.instructure.com';
                        break;
                    case 'Blackboard':
                        this.newLMS.iss = 'https://blackboard.com';
                        break;
                    case null:
                    case 'Moodle':
                    case 'Brightspace':
                        this.newLMS.iss = null;
                        break;
                    default:
                        this.$utils.AssertionError.assertNever(name);
                    }

                break;
            }

            default: this.$utils.AssertionError.assertNever(this.newLMS);
        }
    }

    submitNewProvider() {
        // This can never happen because of the template structure.
        this.$utils.AssertionError.assert(this.newLMS != null);

        switch (this.newLMS.version) {
            case 'lti1.1': {
                if (!this.newLMS.name || !this.newLMS.forWho) {
                    throw new Error('Please make sure that no fields are empty.');
                }

                return this.$http.post('/api/v1/lti/providers/', {
                    lti_version: 'lti1.1',
                    lms: this.newLMS.name,
                    intended_use: this.newLMS.forWho,
                });
            }

            case 'lti1.3': {
                if (!this.newLMS.iss || !this.newLMS.name || !this.newLMS.forWho) {
                    throw new Error('Please make sure that no fields are empty.');
                }

                return this.$http.post('/api/v1/lti/providers/', {
                    lti_version: 'lti1.3',
                    iss: this.newLMS.iss,
                    lms: this.newLMS.name,
                    intended_use: this.newLMS.forWho,
                });
            }

            default: return this.$utils.AssertionError.assertNever(this.newLMS);
        }
    }

    async afterSubmitNewProvider({ data }: { data: api.lti.NonFinalizedLTI1p3ProviderServerData }) {
        this.newLMS = null;

        if (this.ltiProviders == null) {
            await this.load();
        } else {
            this.ltiProviders.push(data);
        }

        if (data.lms === 'Blackboard') {
            this.initialSetupBlackboardProvider(data);
        }
    }

    async initialSetupBlackboardProvider(prov: api.lti.NonFinalizedLTI1p3ProviderServerData) {
        this.newBlackboardProvider = prov;
        await this.$nextTick();
        this.blackboardModal.show();
    }

    copyEditLink(ltiProvider: api.lti.LTI1p3ProviderServerData) {
        this.$utils.AssertionError.assert(!ltiProvider.finalized);

        this.$copyText(this.$utils.buildUrl(
            ['lti_providers', ltiProvider.id, 'setup'],
            {
                baseUrl: this.$userConfig.externalUrl,
                query: {
                    setupSecret: ltiProvider.edit_secret ?? '',
                },
            },
        ));
    }
}
</script>
