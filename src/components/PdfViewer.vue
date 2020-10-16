<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<floating-feedback-button
    :disabled="!showInlineFeedback"
    v-if="pdfURL"
    @feedback-shown="onFeedbackChange"
    class="pdf-viewer"
    :fileId="id"
    :line="line"
    :feedback="feedback"
    :assignment="assignment"
    :submission="submission"
    :editable="editable"
    :can-use-snippets="canUseSnippets"
    slot-description="pdf"
    snippet-field-above
    always-show-button
    :visible-without-hover="$root.isEdge"
    add-space
    force-snippets-above
    button-position="bottom-right">
    <template v-slot:default="slotProps">
        <div class="p-relative d-flex flex-grow flex-column h-100">
            <div class="resize-div" v-if="resizing || slotProps.resizing" />
            <object :data="pdfURL"
                    type="application/pdf"
                    width="100%"
                    height="100%"
                    v-if="pdfURL !== ''">
                <b-alert class="mb-0 flex-grow" variant="danger" show>
                    Your browser doesn't support the PDF viewer. Please download
                    the PDF <a class="alert-link" :href="pdfURL">here</a>.
                </b-alert>
            </object>
        </div>
    </template>
</floating-feedback-button>
</template>

<script>
import FloatingFeedbackButton from './FloatingFeedbackButton';

export default {
    name: 'pdf-viewer',

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
        fileContent: {
            required: true,
        },
        resizing: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            pdfURL: '',
        };
    },

    watch: {
        fileContent: {
            immediate: true,
            handler() {
                this.embedPdf(this.id);
            },
        },

        id() {
            if (this.$root.isEdge) {
                this.embedPdf(this.id);
            }
        },
    },

    computed: {
        id() {
            return this.file ? this.file.id : -1;
        },

        line() {
            return 0;
        },

        feedback() {
            return this.$utils.getProps(
                this.submission,
                null,
                'feedback',
                'user',
                this.id,
                this.line,
            );
        },
    },

    methods: {
        async embedPdf(fileId) {
            this.pdfURL = '';

            let pdfURL;

            if (this.$root.isEdge) {
                await this.$http.get(`/api/v1/code/${this.id}?type=file-url`).then(
                    ({ data }) => {
                        pdfURL = `/api/v1/files/${
                            data.name
                        }?not_as_attachment&mime=application/pdf`;
                    },
                    err => {
                        this.$emit('error', {
                            error: `An error occured while loading the PDF: ${this.$utils.getErrorMessage(
                                err,
                            )}.`,
                            fileId,
                        });
                    },
                );
            } else if (this.fileContent == null) {
                return;
            } else {
                const blob = new Blob([this.fileContent], { type: 'application/pdf' });
                pdfURL = this.$utils.coerceToString(URL.createObjectURL(blob));
            }

            if (this.id === fileId && pdfURL) {
                this.pdfURL = pdfURL;
                this.$emit('load', fileId);
            }
        },

        async onFeedbackChange() {
            if (!this.$root.isEdge) {
                return;
            }

            this.pdfUrl = '';
            this.$emit('loading', this.id);
            this.embedPdf(this.id);
        },
    },

    components: {
        FloatingFeedbackButton,
    },
};
</script>

<style lang="less" scoped>
.pdf-viewer {
    padding: 0 !important;
    height: 100%;
    min-height: 100%;
}

object {
    display: block;
    flex: 1 1 100%;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
}

.resize-div {
    position: absolute;
    height: 100%;
    width: 100%;
}
</style>

<style lang="less">
.pdf-viewer.floating-feedback-button {
    flex: 1 1 100%;

    > .content {
        display: flex;
        flex-direction: column;
    }
}

.pdf-viewer.floating-feedback-button .feedback-area-wrapper {
    flex: unset;
}
</style>
