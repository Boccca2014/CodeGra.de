<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-alert show
         v-if="!proxyId && !isMyFile"
         :variant="darkMode ? '' : 'light'"
         style="overflow: auto;"
         class="html-viewer border-0">
    <div>
        <p>
            This file looks like an HTML file. We can render this file, or show its
            source.
        </p>

        <b-button-toolbar justify>
            <submit-button :submit="getIframeSrc" @success="afterGetIframeSrc" variant="outline-danger">
                Render html
            </submit-button>
            <b-btn @click="rejectWarning" variant="primary">
                {{ rejectText }}
            </b-btn>
        </b-button-toolbar>


        <advanced-collapse start-open class="html-viewer-opts mt-3">
            <b-form-group horizontal
                          label-for="allow-scripts-iframe"
                          label="Allow JavaScript execution">
                <b-form-radio-group id="allow-scripts-iframe"
                                    v-model="allowScripts"
                                    :options="yesNoOptions" />
            </b-form-group>

            <b-form-group horizontal
                          label-for="allow-remote-iframe-resources"
                          label="Allow remote resources">
                <b-form-radio-group id="allow-remote-iframe-resources"
                                    v-model="allowRemoteResources"
                                    :options="yesNoOptions" />
            </b-form-group>

            <b-form-group horizontal
                          label-for="allow-remote-scripts-iframe"
                          label="Allow 'eval' usage and loading of remote JavaScript">
                <b-form-radio-group id="allow-remote-scripts-iframe"
                                    v-model="allowRemoteScripts"
                                    :options="yesNoOptions" />
            </b-form-group>
        </advanced-collapse>
    </div>
</b-alert>
<div v-else class="flex-column d-flex-non-important html-viewer">
    <b-alert show
             dismissible
             variant="warning"
             class="mb-0 border-bottom rounded-0">
        Displayed below is a rendered html file.
        <a href="#" @click.capture.prevent.stop="rejectWarning">Click here</a> to
        show the source.
    </b-alert>
    <loader v-if="!loaded" class="pt-3"/>

    <template v-if="proxyId">
        <form target="myIframe"
              :action="iframeSrc"
              method="post"
              v-show="false"
              ref="hiddenForm">
            <input type="submit">
        </form>

        <div class="resizing-overlay"
             v-if="resizing"/>
        <iframe name="myIframe"
                src=""
                ref="iframe"
                class="border-0"
                v-if="proxyId"
                :class=" loaded ? 'flex-grow-1' : ''"
                :style="{ opacity: loaded ? 1 : 0 }"
                @load="onLoad"
                referrerpolicy="no-referrer"
                referrer="no-referrer"
                :sandbox="allowScripts ? 'allow-scripts allow-popups' : 'allow-popups'"/>
    </template>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import FloatingFeedbackButton from './FloatingFeedbackButton';
import SubmitButton from './SubmitButton';
import CodeViewer from './CodeViewer';
import Loader from './Loader';
import AdvancedCollapse from './AdvancedCollapse';

export default {
    name: 'html-viewer',

    props: {
        assignment: {
            type: Object,
            required: true,
        },
        submission: {
            type: Object,
            required: true,
        },
        file: {
            type: Object,
            required: true,
        },
        fileId: {
            required: true,
        },
        revision: {
            type: String,
            required: true,
        },
        editable: {
            type: Boolean,
            required: false,
        },
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
        showInlineFeedback: {
            type: Boolean,
            default: true,
        },
        resizing: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            proxyId: null,
            loaded: 0,

            allowScripts: true,
            allowRemoteResources: true,
            allowRemoteScripts: false,

            yesNoOptions: [{ text: 'yes', value: true }, { text: 'no', value: false }],
        };
    },

    watch: {
        id: {
            immediate: true,
            handler() {
                this.setDefaultOptions();
                this.$emit('load', this.fileId);
                if (this.isMyFile) {
                    this.getIframeSrc().then(
                        data => {
                            this.afterGetIframeSrc(data);
                        },
                        err => this.$emit('error', err),
                    );
                }
            },
        },
    },

    computed: {
        ...mapGetters('feedback', ['getFeedback']),
        ...mapGetters('pref', ['darkMode']),
        ...mapGetters('user', { myId: 'id' }),
        ...mapGetters('users', ['getUser']),
        ...mapGetters('autotest', {
            allAutoTests: 'tests',
        }),

        autoTest() {
            return this.allAutoTests[this.assignment.auto_test_id];
        },

        autoTestRun() {
            return this.$utils.getProps(this.autoTest, null, 'runs', 0);
        },

        id() {
            return this.file ? this.file.id : -1;
        },

        line() {
            return 0;
        },

        isStudent() {
            return this.$utils.getProps(this.assignment, false, 'course', 'isStudent');
        },

        feedback() {
            return this.$utils.getProps(
                this.submission,
                {},
                'feedback',
                'user',
                this.id,
                this.line,
            );
        },

        currentPath() {
            const arr = [];
            let cur = this.file;
            while (cur.parent != null) {
                arr.push(cur.name);
                cur = cur.parent;
            }
            if (this.revision === 'autotest') {
                arr.pop();
            }
            arr.reverse();
            return arr.join('/');
        },

        iframeSrc() {
            const { host, protocol } = window.location;
            if (UserConfig.proxyBaseDomain) {
                return `${protocol}//${this.proxyId}.${UserConfig.proxyBaseDomain}/${
                    this.proxyId
                }/${this.currentPath}`;
            }
            return `${protocol}//${host}/api/v1/proxies/${this.proxyId}/${this.currentPath}`;
        },

        hasFeedback() {
            if (!this.showInlineFeedback || this.revision !== 'student') {
                return false;
            }
            const allFeedback = this.getFeedback(this.assignment.id, this.submission.id);
            const fileId = this.fileId;

            if (!allFeedback) {
                return false;
            }

            const feedback = allFeedback.user[fileId] || {};
            return Object.keys(feedback).length > 0;
        },

        rejectText() {
            const base = 'Show source';
            if (this.hasFeedback && this.editable) {
                return `${base}, and display and give line feedback`;
            } else if (this.hasFeedback) {
                return `${base}, and display line feedback`;
            } else if (this.editable) {
                return `${base}, and give line feedback`;
            } else {
                return `${base}`;
            }
        },

        isMyFile() {
            return this.getUser(this.myId).isEqualOrMemberOf(this.submission.user);
        },
    },

    destroyed() {
        this.$root.$emit('cg::file-tree::unfade-selected-file');
    },

    methods: {
        ...mapActions('code', {
            storeLoadCode: 'loadCode',
        }),

        setDefaultOptions() {
            this.proxyId = null;
            this.loaded = 0;
            this.allowScripts = true;
            this.allowRemoteResources = true;
            this.allowRemoteScripts = this.isMyFile;
            this.$root.$emit('cg::file-tree::unfade-selected-file');
        },

        getIframeSrc() {
            let url;
            if (this.revision === 'autotest') {
                let curFile = this.file;
                while (curFile && curFile.autoTestSuiteId == null) {
                    curFile = curFile.parent;
                }
                const suiteId = curFile.autoTestSuiteId;
                const resultId = this.autoTestRun.findResultBySubId(this.submission.id).id;
                url = `/api/v1/auto_tests/${this.assignment.auto_test_id}/runs/${
                    this.autoTestRun.id
                }/results/${resultId}/suites/${suiteId}/proxy`;
            } else {
                url = `/api/v1/submissions/${this.submission.id}/proxy`;
            }

            return this.$http
                .post(url, {
                    allow_remote_resources: this.allowRemoteResources,
                    allow_remote_scripts: this.allowRemoteScripts,
                    teacher_revision: this.revision === 'teacher',
                })
                .catch(err => {
                    if (this.isMyFile) {
                        this.$emit(
                            'error',
                            `An error occured while rendering the HTML: ${this.$utils.getErrorMessage(
                                err,
                            )}.`,
                        );
                    }
                    throw err;
                });
        },

        async afterGetIframeSrc({ data }) {
            this.proxyId = data.id;

            const hiddenForm = await this.$waitForRef('hiddenForm');
            if (hiddenForm != null) {
                hiddenForm.submit();
            }
        },

        rejectWarning() {
            this.proxyId = null;
            this.$emit('force-viewer', CodeViewer);
        },

        onLoad() {
            // Fade the filename in the file tree when jumping to another file.
            // In chromium an iframe sends two load events on the first load,
            // while Firefox only sends one. To handle this we increment `loaded`
            // only after a short while so that the second time the load event is
            // triggered in chromium it doesn't actually emit the event.
            if (this.loaded > 0) {
                this.$root.$emit('cg::file-tree::fade-selected-file');
            } else {
                const fileId = this.fileId;
                setTimeout(() => {
                    if (fileId === this.fileId) {
                        this.loaded++;
                    }
                }, 500);
            }
        },
    },

    components: {
        FloatingFeedbackButton,
        SubmitButton,
        Loader,
        AdvancedCollapse,
    },
};
</script>

<style lang="less">
.html-viewer {
    flex: 1 1 auto;
}

.html-viewer .d-flex-non-important {
    display: flex;
}

.html-viewer .html-viewer-opts .form-group {
    display: flex;

    label {
        max-width: unset;
        flex: 1;
    }

    > :last-child {
        max-width: unset;
        flex: 1;
        text-align: right;
    }
}

.resizing-overlay {
    position: absolute;
    height: 100%;
    width: 100%;
}
</style>
