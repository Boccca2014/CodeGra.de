<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="webhook-instructions">
    <div ref="copyContainer" />

    <div class="d-flex mb-2">
        <b-btn @click="showPrevBtn && page--"
               :style="{ opacity: (showPrevBtn ? 1 : 0), pointerEvents: (showPrevBtn ? 'all' : 'none') }"
               v-b-popover.top.hover="showPrevBtn ? 'Go to previous step.' : ''"
               class="prev-button">
            <icon name="arrow-left" />
        </b-btn>
        <div class="flex-grow d-flex justify-content-center">
            <h4 class="mx-3 my-0 align-self-center">
                {{ pageName }}
                ({{ page + 1 }} / {{ Object.keys(pageNames).length }})
                <small v-if="page > 0" class="ml-1">
                    ({{ providerName }})
                </small>
            </h4>
        </div>
        <b-btn @click="showNextBtn && page++"
               :style="{ opacity: (showNextBtn ? 1 : 0), pointerEvents: (showNextBtn ? 'all' : 'none') }"
               v-b-popover.top.hover="showNextBtn ? 'Go to next step.' : ''"
               class="next-button">
            <icon name="arrow-right" />
        </b-btn>
    </div>

    <div v-if="page == 0">
        <div class="logos row justify-content-center">
            <div class="github logo col-lg-5 border m-3 rounded px-5 d-flex"
                 @click="selectProvider('github')">
                <span class="align-self-center text-center">
                    <img src="/static/img/GitHub_Mark.svg" class="gh-mark mb-3" />
                    <img src="/static/img/GitHub_Logo.svg" class="gh-logo" />
                </span>
            </div>
            <div class="gitlab logo col-lg-5 border m-3 rounded d-flex"
                 @click="selectProvider('gitlab')">
                <img src="/static/img/gitlab-logo-gray-stacked-rgb.svg" class="align-self-center"/>
            </div>
        </div>
    </div>

    <div v-else-if="page == 1">
        <p>
            CodeGrade allows you to submit your work directly via Git, this is
            done by setting up a <i>webhook</i>. As a result, every time you
            push the configured branch, the content of your current branch will
            be uploaded to CodeGrade. A good practice is to set up the {{
            providerName }} CodeGrade configuration before starting to work on
            your assignment.
        </p>
        <p>
            First we need to add a <i>deploy key</i>. By adding this key you allow
            CodeGrade to access the code in your repository, which is needed for
            CodeGrade to create a submission.
        </p>

        <template v-if="provider === 'github'">
            <p>
                Start by going to the settings page of your repository. On the
                left of your screen, you will see a category named <i>"Deploy
                    Keys"</i>. Click on this option. Now click on the button named
                <i>"Add deploy key"</i>, which should be on the top right of the
                settings page.
            </p>
            <p>
                Now <a href="#" @click.prevent="copySshKey"
                       class="inline-link">copy</a> the contents of the text area
                below. Paste this content in the <i>"Key"</i> text area of the
                GitHub page. You don't need to provide a title, and write access
                is not needed either. Now press <i>"Add key"</i>.
            </p>
        </template>

        <template v-if="provider === 'gitlab'">
            <p>
                Start by going to the settings page of your repository. You can
                get there by moving your cursor over the gear icon in the
                sidebar on the left (it is the very last item) and then
                selecting the <i>"Repository"</i> item. Then expand
                the <i>"Deploy Keys"</i> category. If this category is not
                present go back to the gear icon in the sidebar and
                select <i>"CI/CD"</i>, and now expand the <i>"Deploy Keys"</i>
                category. After expanding the category you should see two input
                fields: <i>"Title"</i> and <i>"Key"</i>.
            </p>

            <p>
                Now <a href="#" @click.prevent="copySshKey" class="inline-link">copy</a>
                the contents of the text area below. Paste this in the <i>"Key"</i>
                field. Enter a title for the key (its exact value does not matter).
                Write access is not required. Now click the <i>"Add key"</i> button
                to save the key.
            </p>
        </template>

        <p>
            You can now continue to the
            <a href="#" class="inline-link" @click.prevent="page++">next step</a>.
        </p>

        <div class="border rounded p-3 copy-wrapper">
            <code class="public-key">{{ data.public_key }}</code>

            <b-btn class="copy-btn m-1 fixed" v-if="copying || copyMsg" disabled>
                <loader :scale="1" v-if="copying" />
                <template v-else>
                    {{ copyMsg }}
                </template>
            </b-btn>
            <b-btn class="copy-btn m-1"
                   v-show="!copying && !copyMsg"
                   @click="copySshKey"
                   v-b-popover.top.hover="'Copy to clipboard'">
                <icon name="clipboard" />
            </b-btn>
        </div>
    </div>

    <div v-else-if="page == 2">
        <template v-if="provider === 'github'">
            <p>
                Again navigate to the settings page of your repository, but this
                time select the <i>"Webhooks"</i> category. On this page click
                on the button <i>"Add webhook"</i>, this button should be at the
                top right of the settings page. You might be prompted for your
                GitHub password, please enter it.
            </p>

            <p>
                After entering your password you can add a webhook. First enter
                the <i>"Payload URL"</i>, which you can
                <a href="#"
                   @click.prevent="copy(webhookURL)"
                   title="Click to copy your Payload URL."
                   class="inline-link">copy</a> below.
            </p>

            <p>
                You don't need to change the <i>"Content type"</i>, all options
                are supported by CodeGrade.
            </p>

            <p>
                You do need to set the <i>"Secret"</i>, as this is used by
                CodeGrade to determine if requests to the Payload URL are
                genuine. Please
                <a href="#"
                   @click.prevent="copy(data.secret)"
                   title="Click to copy your Secret"
                   class="inline-link">copy</a> the secret from below.
            </p>

            <p>
                Now click the <i>"Add webhook"</i> button to save the
                configuration, and move on to
                <a href="#" class="inline-link" @click.prevent="page++"
                   >the next step</a>.
            </p>

            <b-form-fieldset>
                <b-input-group prepend="Payload URL" class="webhook-url">
                    <span class="form-control">{{ webhookURL }}</span>
                </b-input-group>

                <b-input-group prepend="Secret" class="mt-3 webhook-secret">
                    <span class="form-control">{{ data.secret }}</span>
                </b-input-group>
            </b-form-fieldset>
        </template>

        <template v-else-if="provider === 'gitlab'">
            <p>
                Again navigate to the settings page of your repository, but
                this time select the <i>"Integrations"</i> item after you move
                your cursor over the gear icon in the sidebar.
            </p>

            <p>
                There should be a <i>"URL"</i> and a <i>"Secret Token"</i>
                input field. First enter the <i>"URL"</i>, which you can
                <a href="#"
                   @click.prevent="copy(webhookURL)"
                   title="Click to copy your URL."
                   class="inline-link">copy</a> below.
            </p>

            <p>
                After that enter the <i>"Secret Token"</i> which you can also
                <a href="#"
                   @click.prevent="copy(data.secret)"
                   title="Click to copy your Secret Token."
                   class="inline-link">copy</a> from below.
            </p>

            <p>
                Under the <i>"Trigger"</i> section, make sure <i>"Push
                    events"</i> is selected. None of the other checkboxes have
                to be checked. Lastly, make sure <i>"SSL verification"</i>
                is checked.
            </p>

            <p>
                Now click the <i>"Add webhook"</i> button to save the configuration
                and move on to <a href="#" class="inline-link" @click.prevent="page++">
                    the next step</a>.
            </p>

            <b-form-fieldset>
                <b-input-group prepend="URL" class="webhook-url">
                    <span class="form-control">{{ webhookURL }}</span>
                </b-input-group>

                <b-input-group prepend="Secret Token" class="mt-3 webhook-secret">
                    <span class="form-control">{{ data.secret }}</span>
                </b-input-group>
            </b-form-fieldset>
        </template>

        <advanced-collapse>
            By default the Payload URL will make sure that when you push to the
            master branch a submission will be created in CodeGrade. If you want
            to use another branch to create submissions, you can change
            <code>?branch={{ data.default_branch}}</code> in the above url. For
            example <code>?branch=stable</code> will create submissions when you
            push to the <code>stable</code> branch.
            <br>
            It is also possible to specify multiple branches. For example
            <code>?branch=stable&amp;branch=master</code> will create a
            submission when you push to either <code>stable</code>
            or <code>master</code>.
        </advanced-collapse>
    </div>

    <div v-else-if="page == 3">
        <p>
            {{ providerName }} should now be successfully configured. Now, the
            content of your repository will be automatically uploaded for this
            CodeGrade assignment every time you perform a <code>git push</code>.
            You can test this by pushing to the {{ data.default_branch }}
            branch and checking if a new submission was created.
        </p>
        <p>
            A good practice is to set up the {{ providerName }} CodeGrade
            webhook in the beginning of your assignment, so every time you push
            it automatically gets uploaded to CodeGrade. If you, however, want
            to hand in your current repository, you can do this by an empty
            commit.
            You can run
            <code class="d-block p-3">git commit --allow-empty -m "Create a CodeGrade submission" &amp;&amp; git push</code>
            while the {{ data.default_branch }} branch is checked out. If you
            are using a GUI for Git that does not support empty commits, simply
            making an arbitrary change in a tracked file will allow you to
            still do a <code>git push</code>.
        </p>
        <p>
            You have now successfully setup your {{ providerName }} CodeGrade
            webhook and can close this modal. Click the button below to check
            if your {{ providerName }} submission succeeded.
        </p>

        <b-alert v-if="checkLatestResults != null"
                 show
                 :variant="checkLatestResults.sub != null ? 'success' : 'warning'"
                 dismissible
                 @dismissed="checkLatestResults = null">
            <span v-if="checkLatestResults.sub != null">
                A <router-link class="inline-link"
                               :to="submissionRoute(checkLatestResults.sub)">
                    new Git submission
                </router-link> was found!
            </span>
            <span v-else>
                Could not find a new Git submission!
            </span>
        </b-alert>

        <b-button-toolbar class="justify-content-end">
            <submit-button :submit="checkLatestSubmission"
                           label="Check for new Git submission"
                           :duration="0"
                           :wait-at-least="250"/>
        </b-button-toolbar>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/arrow-left';
import 'vue-awesome/icons/arrow-right';
import 'vue-awesome/icons/clipboard';

import Loader from './Loader';
import SubmitButton from './SubmitButton';
import AdvancedCollapse from './AdvancedCollapse';

export default {
    name: 'webhook-instructions',

    props: {
        data: {
            type: Object,
            required: true,
        },
    },

    data() {
        return {
            page: 0,
            provider: null,
            copying: false,
            copyMsg: null,
            latestSubmission: null,
            checkLatestResults: null,
        };
    },

    computed: {
        ...mapGetters('assignments', ['getAssignment']),
        ...mapGetters('submissions', ['getLatestSubmissions']),

        assignmentId() {
            return this.data.assignment_id;
        },

        courseId() {
            return this.getAssignment(this.assignmentId).mapOrDefault(
                a => a.courseId,
                null,
            );
        },

        userId() {
            return this.data.user_id;
        },

        pageNames() {
            return {
                0: 'Select Git hoster',
                1: 'Add the deploy key',
                2: 'Add the webhook',
                3: 'Test the webhook',
            };
        },

        pageName() {
            return this.pageNames[this.page];
        },

        providerName() {
            return {
                github: 'GitHub',
                gitlab: 'GitLab',
            }[this.provider];
        },

        maxPage() {
            return 3;
        },

        showPrevBtn() {
            return this.page !== 0;
        },

        showNextBtn() {
            return this.page !== 0 && this.page < this.maxPage;
        },

        webhookURL() {
            // TODO: Maybe this can/should be done using the router?
            const { host, protocol } = window.location;
            return `${protocol}//${host}/api/v1/webhooks/${this.data.id}?branch=${
                this.data.default_branch
            }`;
        },
    },

    watch: {
        data: {
            deep: true,
            immediate: true,
            handler() {
                this.page = 0;
                this.setLatestSubmission();
            },
        },

        page() {
            this.copying = false;
            this.copyMsg = null;
        },

        assignmentId: {
            immediate: true,
            handler(newValue) {
                this.loadSingleAssignment({ assignmentId: newValue });
            },
        },
    },

    methods: {
        ...mapActions('assignments', ['loadSingleAssignment']),
        ...mapActions('submissions', {
            storeLoadSubmissionsByUser: 'loadSubmissionsByUser',
        }),

        selectProvider(provider) {
            this.page = 1;
            this.provider = provider;
        },

        copySshKey() {
            this.copy(this.data.public_key);
        },

        copy(text) {
            this.copying = true;
            const req = this.$copyText(text, this.$refs.copyContainer);

            req
                .then(
                    () => {
                        this.copying = false;
                        this.copyMsg = 'Copied!';
                    },
                    e => {
                        this.copying = false;
                        this.copyMsg = this.$utils.getErrorMessage(e);
                    },
                )
                .then(() => {
                    setTimeout(() => {
                        this.copyMsg = null;
                    }, 2000);
                });
        },

        setLatestSubmission() {
            // Store the current latest submission, so we have something to compare
            // created date to in checkLatestSubmission.

            this.storeLoadSubmissionsByUser({
                assignmentId: this.assignmentId,
                userId: this.userId,
            }).then(() => {
                const latestSubmissions = this.getLatestSubmissions(this.assignmentId);
                this.latestSubmission = latestSubmissions.find(s => s.userId === this.userId);
            });
        },

        checkLatestSubmission() {
            // Get the latest submission of the user for the current webhook
            // and check if it is a git submission.

            const latestDate = this.$utils.getProps(this.latestSubmission, null, 'createdAt');

            return this.storeLoadSubmissionsByUser({
                assignmentId: this.assignmentId,
                userId: this.userId,
                force: true,
            }).then(subs => {
                const latestGitSubmission = (subs || []).find(
                    s =>
                        (s.origin === 'github' || s.origin === 'gitlab') &&
                        (latestDate == null || s.createdAt.isAfter(latestDate)),
                );

                this.checkLatestResults = {
                    sub: latestGitSubmission,
                };
            });
        },

        submissionRoute(sub) {
            return {
                name: 'submission',
                params: {
                    courseId: this.courseId,
                    assignmentId: this.assignmentId,
                    submissionId: sub.id,
                },
            };
        },
    },

    components: {
        Icon,
        Loader,
        SubmitButton,
        AdvancedCollapse,
    },
};
</script>

<style lang="less" scoped>
:not(input).form-control {
    height: auto;
}
</style>

<style lang="less">
@import '~mixins.less';

.logo {
    max-width: 20rem !important;
    user-select: none;

    &:hover {
        background: rgba(0, 0, 0, 0.05);
        cursor: pointer;
    }

    img {
        pointer-events: none;
    }

    &.gitlab img {
        width: 100%;
    }

    @{dark-mode}.github img {
        filter: invert(1);
    }

    &.github {
        padding-bottom: 2.5rem;
        padding-top: 2.5rem;
        .gh-logo {
            width: 100%;
        }
        .gh-mark {
            width: 50%;
        }
    }
}

.flex-grow {
    flex: 1 1 auto;
}

.copy-btn {
    position: absolute;
    top: 0;
    right: 0;

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

.copy-wrapper {
    position: relative;
    display: flex;
    flex-direction: column;
    max-height: 100%;
    overflow: hidden;
}

.public-key,
.webhook-url,
.webhook-secret {
    word-break: break-all;
}
</style>
