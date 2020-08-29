<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-alert variant="danger" show v-if="error" class="box m-0 rounded-0">
    <p style="text-align: center; font-size: 1.3em;">
        <template v-if="isCookieError">
            <p>
                We were unable to set cookies, which are necessary for CodeGrade to
                function as an LTI tool. Please allow CodeGrade to set cookies, and
                make sure that "third-party" cookies are also enabled.
            </p>

            <p v-if="cookiePostMessage">
                It might be possible to fix this automatically by clicking
                <a href="#" @click.prevent="sendPostMessage" class="inline-link">here</a>.
            </p>
        </template>
        <template v-else>
            Something went wrong during the LTI launch:
            <template v-if="errorMsg">
                {{ errorMsg }}
            </template>
            <template v-else>
                Please <a href="mailto:support@codegra.de">contact support</a>.
            </template>
        </template>
    </p>
</b-alert>
<div v-else-if="deepLinking">
    <local-header title="Creating new CodeGrade assignment" show-logo />
    <b-form-fieldset>
        <b-input-group>
            <b-input-group-prepend is-text>
                Name
                <cg-description-popover hug-text>
                    The name of the new assignment
                </cg-description-popover>
            </b-input-group-prepend>

            <input class="form-control"
                   placeholder="The name of the new assignment"
                   v-model="deepLinkAssignmentName" />
        </b-input-group>
    </b-form-fieldset>

    <b-form-fieldset>
        <b-input-group>
            <b-input-group-prepend is-text>
                Deadline
                <cg-description-popover hug-text>
                    The deadline of the new assignment
                </cg-description-popover>
            </b-input-group-prepend>

            <datetime-picker v-model="deepLinkDeadline"
                             class="assignment-deadline"
                             placeholder="The deadline of the new assignment"/>
        </b-input-group>
    </b-form-fieldset>

    <cg-submit-button :submit="createDeepLink"
                      label="Create assignment"
                      class="float-right"/>

    <form ref="deepLinkResponesForm" :action="deepLinkResponseData.url" method="POST"
          v-if="deepLinkResponseData != null">
        <input type="hidden" name="JWT" :value="deepLinkResponseData.jwt" />
    </form>
</div>
<div v-else>
    <local-header title="Opening CodeGrade" show-logo />
    <cg-loader />
</div>
</template>

<script>
import 'vue-awesome/icons/times';
import { LocalHeader, DatetimePicker } from '@/components';
import { mapActions, mapGetters } from 'vuex';
import { disablePersistance } from '@/store';
import { makeProvider } from '@/lti_providers';

import { setPageTitle } from './title';

export default {
    name: 'lti-launch-page',

    data() {
        return {
            error: false,
            errorMsg: false,
            originalException: null,
            deepLinkBlobId: null,
            deepLinkDeadline: null,
            deepLinkAssignmentName: null,
            deepLinkResponseData: null,
            deepLinkAuthToken: null,
        };
    },

    mounted() {
        this.secondStep(true);
    },

    computed: {
        ...mapGetters('assignments', ['getAssignment']),
        ...mapGetters('user', { myUserId: 'id' }),
        ...mapGetters('submissions', ['getSubmissionsByUser']),

        isCookieError() {
            return this.$utils.getProps(this.originalException, null, 'code') === 'LTI1_3_COOKIE_ERROR';
        },

        cookiePostMessage() {
            return this.$utils.getProps(this.originalException, null, 'lms_capabilities', 'cookie_post_message');
        },

        deepLinking() {
            return this.deepLinkBlobId != null;
        },
    },

    methods: {
        ...mapActions('user', ['logout', 'updateAccessToken']),
        ...mapActions('assignments', ['loadSingleAssignment']),
        ...mapActions('submissions', ['forceLoadSubmissions']),
        ...mapActions('plagiarism', { clearPlagiarismCases: 'clear' }),

        secondStep(first) {
            this.$inLTI = true;

            setPageTitle('LTI is launching, please wait');

            this.$http
                .post('/api/v1/lti/launch/2?extended', {
                    jwt_token: this.$route.query.jwt,
                    blob_id: this.$route.query.blob_id,
                })
                .then(async response => {
                    this.$utils.WarningHeader.fromResponse(response).messages.forEach(warning => {
                        this.$root.$emit('cg::app::toast', {
                            tag: `LTIWarning-${warning.code}`,
                            title: 'Warning',
                            message: warning.text,
                        });
                    });
                    const { data } = response;
                    if (data.version !== 'v1_1' && data.version !== 'v1_3') {
                        return this.$utils.AssertionError.assertNever(
                            data.version,
                            `Unknown LTI version (${data.version}) encountered.`,
                        );
                    }

                    switch (data.data.type) {
                    case 'deep_link':
                        return this.handleLTIDeepLink(data.data);
                    case 'normal_result':
                        return this.handleLTI(data.data);
                    default:
                        return this.$utils.AssertionError.assertNever(
                            data.data.type,
                            `Unknown LTI data type (${data.data.type}) encountered.`,
                        );
                    }
                })
                .catch(err => {
                    if (first && this.$utils.getProps(err, null, 'response', 'status') === 401) {
                        return this.logout().then(() => this.secondStep(false));
                    }
                    this.errorMsg = this.$utils.getErrorMessage(err, null);
                    this.originalException = this.$utils.getProps(err, null, 'response', 'data', 'original_exception');
                    this.error = true;

                    return null;
                });
        },

        async handleLTIDeepLink(data) {
            this.deepLinkBlobId = data.deep_link_blob_id;
            this.deepLinkAuthToken = data.auth_token;
        },

        async handleLTI(data) {
            this.$ltiProvider = makeProvider(data.course.lti_provider);

            if (data.access_token) {
                await this.logout();
                disablePersistance();
                await this.updateAccessToken(data.access_token);
            } else {
                this.clearPlagiarismCases();
            }


            await this.loadSingleAssignment({
                assignmentId: data.assignment.id,
                courseId: data.course.id,
            });
            this.$LTIAssignmentId = data.assignment.id;

            if (data.new_role_created) {
                this.$root.$emit('cg::app::toast', {
                    tag: 'LTINewRoleCreated',
                    title: 'New role created',
                    message: `You do not have any permissions yet, please ask your teacher to enable them for your role "${
                        data.new_role_created
                    }".`,
                });
            }

            if (data.updated_email) {
                this.$root.$emit('cg::app::toast', {
                    tag: 'LTIEmailUpdated',
                    title: 'Email was updated',
                    message: `Your email was updated to "${
                        data.updated_email
                    }" which is the email registered with your ${data.custom_lms_name}.`,
                });
            }

            if (this.$route.query.redirect && this.$route.query.redirect.startsWith('/')) {
                return this.$router.replace(this.$route.query.redirect);
            } else if (this.$utils.parseBool(this.$route.query.goto_latest_submission, false)) {
                const assignment = this.getAssignment(data.assignment.id).extract();
                if (!assignment || !assignment.course.isStudent) {
                    return this.doDefaultRedirect(data);
                }

                await this.forceLoadSubmissions({
                    assignmentId: assignment.id,
                    courseId: assignment.courseId,
                });
                const subs = this.getSubmissionsByUser(assignment.id, this.myUserId, {
                    includeGroupSubmissions: true,
                });

                if (!subs || subs.length === 0) {
                    return this.doDefaultRedirect(data);
                }

                return this.$router.replace({
                    name: 'submission',
                    params: {
                        courseId: assignment.courseId,
                        assignmentId: assignment.id,
                        submissionId: subs[subs.length - 1].id,
                    },
                });
            } else {
                return this.doDefaultRedirect(data);
            }
        },

        doDefaultRedirect(data) {
            return this.$router.replace({
                name: 'assignment_submissions',
                params: {
                    courseId: data.assignment.course.id,
                    assignmentId: data.assignment.id,
                },
            });
        },

        sendPostMessage() {
            const { host, protocol } = window.location;
            window.parent.postMessage({
                messageType: this.cookiePostMessage,
                data: this.$utils.buildUrl(
                    ['api', 'v1', 'lti1.3', 'launch'],
                    { host, protocol },
                ),
            }, '*');
        },

        createDeepLink() {
            if (!this.deepLinkAssignmentName || !this.deepLinkDeadline) {
                throw new Error('Please insert a name and deadline for the new assignment');
            }

            return this.$http.post(
                this.$utils.buildUrl(['api', 'v1', 'lti1.3', 'deep_link', this.deepLinkBlobId]),
                {
                    name: this.deepLinkAssignmentName,
                    deadline: this.deepLinkDeadline,
                    auth_token: this.deepLinkAuthToken,
                },
            ).then(async ({ data }) => {
                this.deepLinkResponseData = data;
                await this.$afterRerender();
                return this.$refs.deepLinkResponesForm.submit();
            });
        },
    },

    components: {
        LocalHeader,
        DatetimePicker,
    },
};
</script>

<style lang="less" scoped>
.box {
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>
