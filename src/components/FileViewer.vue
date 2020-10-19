<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="file-viewer"
     :class="dynamicClasses">
    <b-alert v-if="showError"
             show
             variant="danger"
             class="error mb-0">
        <template v-if="(fileData && showDiff(file) && !fileData.supportsDiff)">
            The diff for files of this type is not supported.
        </template>
        <template v-else>
            {{ error }}
        </template>
    </b-alert>

    <loader v-else-if="!dataAvailable"
            page-loader />

    <template v-else>
        <b-alert v-if="forcedFileComponent != null"
                 show
                 dismissible
                 variant="warning"
                 class="mb-0 rounded-0">
            You are viewing the source of a file that can be rendered.
            <a href="#" @click.capture.prevent.stop="forcedFileComponent = null">Click here</a>
            to show the rendered version.
        </b-alert>

        <b-alert v-if="warning"
                 show
                 dismissible
                 variant="warning"
                 class="mb-0 rounded-0">
            {{ warning }}
        </b-alert>

        <b-alert v-if="!showInlineFeedback"
                 :show="!inlineFeedbackWarningDismissed"
                 dismissible
                 @dismissed="$emit('inline-feedback-warning-dismissed')"
                 variant="warning"
                 class="mb-0 rounded-0">
            Inline feedback is currently hidden.
        </b-alert>
    </template>

    <div class="wrapper"
         :class="{ scroller: fileData && fileData.scroller }"
         v-if="!showError">
        <div v-if="showEmptyFileMessage"
             class="px-3 py-2 font-italic text-muted">
            This file is empty.
        </div>
        <template v-else-if="fileData">
            <component v-show="dataAvailable"
                       :is="fileData.component"
                       class="inner-viewer"
                       :assignment="assignment"
                       :submission="submission"
                       :file="file"
                       :file-id="fileId"
                       :file-content="fileContent"
                       :revision="revision"
                       :show-whitespace="showWhitespace"
                       :show-inline-feedback="showInlineFeedback"
                       :editable="editable"
                       @language="$emit('language', $event)"
                       :language="language"
                       :can-use-snippets="canUseSnippets"
                       @force-viewer="setForcedFileComponent"
                       @load="onLoad"
                       @loading="onLoading"
                       @error="onError"
                       @warning="onWarning"
                       :resizing="resizing"/>
        </template>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import {
    CodeViewer,
    DiffViewer,
    ImageViewer,
    IpythonViewer,
    MarkdownViewer,
    PdfViewer,
    HtmlViewer,
} from '@/components';

import Loader from './Loader';

export default {
    name: 'file-viewer',

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
            default: null,
        },
        revision: {
            type: String,
            required: true,
        },
        editable: {
            type: Boolean,
            default: false,
        },
        showWhitespace: {
            type: Boolean,
            required: true,
        },
        showInlineFeedback: {
            type: Boolean,
            default: true,
        },
        language: {
            type: String,
            default: 'Default',
        },
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
        resizing: {
            type: Boolean,
            default: false,
        },
        inlineFeedbackWarningDismissed: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            loading: true,
            error: '',
            warning: '',
            forcedFileComponent: null,
            fileContent: undefined,
            loadingCode: false,
            fileTypes: [
                {
                    cond: () => this.htmlViewerEnabled(),
                    component: HtmlViewer,
                    showLanguage: false,
                    scroller: false,
                },
                {
                    cond: () => this.hasExtension('pdf'),
                    component: PdfViewer,
                    showLanguage: false,
                    scroller: false,
                    needsContent: !this.$root.isEdge,
                },
                {
                    cond: () => this.hasExtension('gif', 'jpg', 'jpeg', 'png', 'svg'),
                    component: ImageViewer,
                    showLanguage: false,
                    scroller: false,
                    needsContent: true,
                },
                {
                    cond: () => this.hasExtension('ipynb'),
                    component: IpythonViewer,
                    showLanguage: false,
                    scroller: true,
                    needsContent: true,
                },
                {
                    cond: this.showDiff,
                    component: DiffViewer,
                    showLanguage: false,
                    scroller: true,
                    needsContent: false,
                    supportsDiff: true,
                },
                {
                    cond: () => this.hasExtension('md', 'markdown'),
                    component: MarkdownViewer,
                    showLanguage: false,
                    scroller: false,
                    needsContent: true,
                },
                {
                    cond: () => true,
                    component: CodeViewer,
                    showLanguage: true,
                    scroller: true,
                    needsContent: true,
                },
            ],
        };
    },

    computed: {
        ...mapGetters('siteSettings', ['getSetting']),

        showEmptyFileMessage() {
            return (
                !this.loading &&
                    this.fileData &&
                    this.fileContent &&
                    this.fileContent.byteLength === 0
            );
        },

        fileExtension() {
            const parts = this.file.name.split('.');

            if (parts.length > 1) {
                return parts[parts.length - 1].toLowerCase();
            } else {
                return '';
            }
        },

        fileData() {
            // access file id to make sure this computed value changes when `fileId` changes.
            // eslint-disable-next-line
            const _ = this.fileId;

            if (!this.file) {
                return null;
            } else if (this.forcedFileComponent) {
                return this.fileTypes.find(ft => ft.component === this.forcedFileComponent);
            }
            return this.fileTypes.find(ft => ft.cond(this.file));
        },

        dynamicClasses() {
            if (this.showEmptyFileMessage) {
                return 'empty-file-wrapper border rounded';
            } else if (this.showError) {
                return 'rounded';
            } else if (this.fileData) {
                return `${this.fileData.component.name} border rounded ${
                    this.fileContent ? '' : 'no-data'
                }`;
            } else {
                return '';
            }
        },

        fileId() {
            let id = null;
            if (this.file) {
                id = this.file.id;
                if (this.file.ids) {
                    id = this.file.ids.find(x => x);
                }
            }

            return this.$utils.coerceToString(id);
        },

        dataAvailable() {
            return (
                this.fileData &&
                    !this.loading &&
                    (this.fileContent != null || !this.fileData.needsContent)
            );
        },

        showError() {
            return (
                this.error ||
                    (this.fileData && this.showDiff(this.file) && !this.fileData.supportsDiff)
            );
        },


        replyIdToFocus() {
            const replyId = (this.$route.query || {}).replyToFocus;
            return parseInt(replyId || '', 10);
        },
    },

    watch: {
        fileId: {
            immediate: true,
            handler(newVal, oldVal) {
                if (!newVal || oldVal === newVal) {
                    return;
                }

                this.forcedFileComponent = null;
                // Do not throw an error while the submission page is loading, i.e. the fileId
                // has not been set yet.
                if (!this.file && this.$route.params.fileId) {
                    this.onError('File not found!');
                    return;
                }

                this.loadFileContent(newVal);
            },
        },

        fileData(newVal, oldVal) {
            if (
                newVal.needsContent &&
                (oldVal == null || !oldVal.needsContent) &&
                this.fileContent == null
            ) {
                this.loadFileContent(this.fileId);
            }
        },

        replyIdToFocus: {
            immediate: true,
            handler: 'tryScrollToReplyToFocus',
        },

        dataAvailable: 'tryScrollToReplyToFocus',
    },

    methods: {
        ...mapActions('code', {
            storeLoadCode: 'loadCode',
        }),

        async tryScrollToReplyToFocus() {
            const replyId = this.replyIdToFocus;

            if (this.dataAvailable && !Number.isNaN(replyId)) {
                await this.$nextTick();
                const el = document.querySelector(`#feedback-reply-id-${replyId}`);
                if (el) {
                    el.scrollIntoView({
                        block: 'center',
                        inline: 'center',
                        behavior: 'smooth',
                    });

                    setTimeout(() => {
                        if (this.replyIdToFocus !== replyId) {
                            return;
                        }

                        this.$router.replace(Object.assign(
                            {},
                            this.$route,
                            {
                                query: Object.assign(
                                    {}, this.$route.query, { replyToFocus: undefined },
                                ),
                            },
                        ));
                    }, 30_000);
                }
            }
        },

        async loadFileContent(fileId) {
            // We are already loading this piece of code.
            if (this.loadingCode === fileId) {
                return;
            }

            this.fileContent = null;
            this.error = '';
            this.loading = true;

            if (this.fileData.needsContent) {
                if (this.fileId === fileId) {
                    this.loadingCode = fileId;
                }
                let callback = () => {};
                let content = null;

                try {
                    [content] = await Promise.all([
                        this.storeLoadCode(fileId),
                        this.$afterRerender(),
                    ]);
                    // We have to call `onLoad` manually when the content is
                    // empty, because no viewer component will be loaded to
                    // emit a `load` event.
                    if (content.byteLength === 0) {
                        callback = () => this.onLoad(fileId);
                    }
                } catch (e) {
                    callback = () =>
                        this.onError({
                            error: e,
                            fileId,
                        });
                }

                if (fileId === this.fileId) {
                    this.loadingCode = false;
                    if (content) {
                        this.fileContent = content;
                    }
                    callback();
                }
            }
        },

        onLoad(fileId) {
            if (this.fileId !== fileId) {
                return;
            }
            this.loading = false;
            this.error = '';
        },

        onLoading(fileId) {
            if (this.fileId !== fileId) {
                return;
            }

            this.loading = true;
            this.error = '';
        },

        onError(err) {
            this.setIfFileMatches('error', err);
            this.loading = false;
        },

        onWarning(warning) {
            this.setIfFileMatches('warning', warning);
        },

        setIfFileMatches(prop, err) {
            if (err.fileId) {
                if (err.fileId !== this.fileId) {
                    return;
                }
                this.$set(this, prop, this.$utils.getErrorMessage(err.error));
            } else {
                this.$set(this, prop, this.$utils.getErrorMessage(err));
            }
        },

        async setForcedFileComponent(fc) {
            this.loading = true;
            this.error = '';
            await this.$afterRerender();
            this.forcedFileComponent = fc;
            if (this.fileContent == null) {
                this.loadFileContent(this.fileId);
            }
        },

        hasExtension(...exts) {
            return exts.some(
                ext => this.fileExtension === ext || this.fileExtension === ext.toUpperCase(),
            );
        },

        showDiff(file) {
            return this.revision === 'diff' && file.ids && file.ids[0] !== file.ids[1];
        },

        htmlViewerEnabled() {
            return this.hasExtension('html', 'htm') &&
                this.revision !== 'diff' &&
                this.getSetting('RENDER_HTML_ENABLED');
        },
    },

    errorCaptured(error) {
        this.onError(error);
        return false;
    },

    components: {
        Loader,
    },
};
</script>

<style lang="less" scoped>
.file-viewer {
    overflow: hidden;
    padding: 0 !important;
    display: flex;
    flex-direction: column;

    &.html-viewer,
    &.image-viewer,
    &.markdown-viewer,
    &.pdf-viewer {
        height: 100%;
    }
}

.wrapper {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    max-height: 100%;
    width: 100%;
    overflow: hidden;

    &:not(.scroller) {
        display: flex;
        flex-direction: column;
    }
}

.scroller {
    // Fixes performance issues on scrolling because the entire
    // code viewer isn't repainted anymore.
    will-change: transform;

    overflow: auto;
}

.inner-viewer {
    min-height: 100%;
}

.loader {
    margin: 2rem 0;
}
</style>
