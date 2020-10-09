/* SPDX-License-Identifier: AGPL-3.0-only */
import { VNode, CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import * as api from '@/api/v1';
import { makeProvider, LTIProvider } from '@/lti_providers';

// @ts-ignore
import LocalHeader from '../LocalHeader';
// @ts-ignore
import SubmitButton from '../SubmitButton';

type Info = {
    option: string;
    value: string;
};

export default tsx.component({
    props: {
        ltiProvider: p.ofType<api.lti.NonFinalizedLTI1p1ProviderServerData>().required,
        secret: p(String).required,
    },

    data(): { finalized: boolean } {
        return {
            finalized: false,
        };
    },

    methods: {
        getInfo(): Info[] {
            switch (this.ltiProvider.lms) {
                case 'Canvas':
                    return this.getCanvasInfo();
                case 'BrightSpace':
                    return this.getBrightspaceInfo();
                case 'Blackboard':
                    return this.getBlackboardInfo();
                case 'Moodle':
                    return this.getMoodleInfo();
                case 'Open edX':
                case 'Sakai':
                    return this.getGenericInfo();
                default:
                    return this.$utils.AssertionError.assertNever(this.ltiProvider.lms);
            }
        },

        getCanvasInfo(): Info[] {
            return [
                { option: 'Name', value: 'CodeGrade' },
                {
                    option: 'Config URL',
                    value: this.$utils.buildUrl(
                        ['api', 'v1', 'lti'],
                        {
                            baseUrl: this.$utils.getExternalUrl(),
                            query: { lms: 'Canvas' },
                            addTrailingSlash: true,
                        },
                    ),
                },
                { option: 'Consumer key', value: this.ltiProvider.lms_consumer_key },
                { option: 'Shared Secret', value: this.ltiProvider.lms_consumer_secret },

            ];
        },

        getBrightspaceInfo(): Info[] {
            return [
                { option: 'Name', value: 'CodeGrade' },
                { option: 'Launch point', value: this.$utils.getExternalUrl() },
                { option: 'Consumer key', value: this.ltiProvider.lms_consumer_key },
                { option: 'Shared Secret', value: this.ltiProvider.lms_consumer_secret },
                {
                    option: 'CodeGrade URL for assignments',
                    value: this.$utils.buildUrl(
                        ['api', 'v1', 'lti', 'launch', '1'],
                        { baseUrl: this.$utils.getExternalUrl() },
                    ),
                },
            ];
        },

        getBlackboardInfo(): Info[] {
            return [
                { option: 'Name', value: 'CodeGrade' },
                {
                    option: 'Launch URL',
                    value: this.$utils.buildUrl(
                        ['api', 'v1', 'lti', 'launch', '1'],
                        { baseUrl: this.$utils.getExternalUrl() },
                    ),
                },
                { option: 'Consumer key (Provider Key)', value: this.ltiProvider.lms_consumer_key },
                { option: 'Shared Secret (Provider Secret)', value: this.ltiProvider.lms_consumer_secret },
                {
                    option: 'Optional icon',
                    value: this.$utils.buildUrl(
                        ['static', 'img', 'blackboard-lti-icon.png'],
                        { baseUrl: this.$utils.getExternalUrl() },
                    ),
                },
            ];
        },

        getMoodleInfo(): Info[] {
            return [
                { option: 'Name', value: 'CodeGrade' },
                {
                    option: 'Common Cartridge URL',
                    value: this.$utils.buildUrl(
                        ['api', 'v1', 'lti'],
                        {
                            baseUrl: this.$utils.getExternalUrl(),
                            query: { lms: 'Moodle' },
                            addTrailingSlash: true,
                        },
                    ),
                },
                { option: 'Consumer key (Provider Key)', value: this.ltiProvider.lms_consumer_key },
                { option: 'Shared secret (Provider Secret)', value: this.ltiProvider.lms_consumer_secret },
                {
                    option: 'Optional icon',
                    value: this.$utils.buildUrl(
                        ['static', 'favicon', 'android-chrome-512x512.png'],
                        { baseUrl: this.$utils.getExternalUrl() },
                    ),
                },
            ];
        },

        getGenericInfo(): Info[] {
            return [
                { option: 'Name', value: 'CodeGrade' },
                { option: 'Consumer key', value: this.ltiProvider.lms_consumer_key },
                { option: 'Shared secret', value: this.ltiProvider.lms_consumer_secret },
            ];
        },

        finalize(): Promise<unknown> {
            return api.lti.finalizeLti1p1Provider(this.ltiProvider, this.secret);
        },

        afterFinalize(): void {
            this.finalized = true;
        },
    },

    computed: {
        ltiProviderModel(): LTIProvider {
            return makeProvider(this.ltiProvider);
        },

        title(): string {
            return `Connect CodeGrade to ${this.ltiProviderModel.lms}`;
        },

        finalizeConfirm(): string {
            return `
            After finalizing your configuration you cannot edit it anymore. Are
            you sure you want to finalize your configuration?
            `;
        }
    },

    render(h: CreateElement): VNode {
        return (
            <div class="lti1p1-provider">
                <LocalHeader title={this.title} show-logo />

                <p>
                    To add CodeGrade as an LTI 1.1 connection to your LMS we
                    need to insert the data below into the LMS.
                </p>
                <p>
                    Please note that the consumer key and shared secret should
                    both be kept secret, as anybody with access to these values
                    will be able to change assignment settings.
                </p>

                <table class="table">
                    <thead>
                        <tr>
                            <th>Option</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {this.getInfo().map(info => (
                            <tr>
                                <td>{info.option}</td>
                                <td><code>{info.value}</code></td>
                            </tr>
                        ))}
                    </tbody>
                </table>

                <p>
                    After inserting these values please click the finalize
                    button below. This will enable the integration, please note
                    that after finalizing you will no longer be able to access
                    this wizard.
                </p>

                <div class="d-flex mb-3 justify-content-end">
                    <SubmitButton submit={this.finalize}
                                  label="Finalize"
                                  confirm={this.finalizeConfirm}
                                  onAfter-success={this.afterFinalize} />
                </div>

                {this.$utils.ifOrEmpty(
                    this.finalized,
                    () => (
                        <p>
                            You have finalized the provider and it is ready to use.
                        </p>
                    ),
                )}
            </div>
        );
    },
});
