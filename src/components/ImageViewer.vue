<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<floating-feedback-button
    :disabled="!showInlineFeedback"
    v-if="imgURL"
    class="image-viewer"
    :fileId="id"
    :line="line"
    :feedback="feedback"
    :assignment="assignment"
    :submission="submission"
    :editable="editable"
    :can-use-snippets="canUseSnippets"
    slot-description="image"
    snippet-field-above
    always-show-button
    add-space
    force-snippets-above>
    <img :src="imgURL"
         class="img"
         :title="name"
         @error="imgError"
         @load="imgLoaded"/>
</floating-feedback-button>
</template>

<script>
import FloatingFeedbackButton from './FloatingFeedbackButton';

export default {
    name: 'image-viewer',

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
        fileId: {
            type: String,
            required: true,
        },
        editable: {
            type: Boolean,
            default: false,
        },
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
        revision: {
            type: String,
            required: true,
        },
        showInlineFeedback: {
            type: Boolean,
            default: true,
        },
        fileContent: {
            required: true,
        },
    },

    computed: {
        id() {
            return this.file && (this.file.id || this.file.ids[0] || this.file.ids[1]);
        },

        name() {
            return this.file ? this.file.name : '';
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

        imgURL() {
            if (this.fileContent == null) {
                return '';
            }
            const blob = new Blob([this.fileContent], { type: this.getMimeType() });
            return URL.createObjectURL(blob);
        },
    },

    methods: {
        getMimeType() {
            const ext = this.name.split('.').reverse()[0];
            const types = {
                gif: 'image/gif',
                jpg: 'image/jpeg',
                jpeg: 'image/jpeg',
                png: 'image/png',
                svg: 'image/svg+xml',
            };
            return types[ext];
        },

        imgLoaded() {
            this.$emit('load', this.id);
        },

        imgError() {
            this.$emit('error', {
                error: 'The image can not be displayed.',
                fileId: this.fileId,
            });
        },
    },

    components: {
        FloatingFeedbackButton,
    },
};
</script>

<style lang="less" scoped>
.image-viewer {
    padding: 0;

    .img {
        display: inline-block;
        max-height: 100%;
        max-width: 100%;
    }
}
</style>

<style lang="less">
.image-viewer.floating-feedback-button .content-wrapper {
    display: block;
    min-height: 5rem;
    text-align: center;

    /* Checkerboard pattern. */
    background-size: 1rem;
    background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyIDIi PjxyZWN0IGZpbGw9IiNmNGY0ZjQiIHg9IjAiIHk9IjAiIHdpZHRoPSIxIiBoZWlnaHQ9IjEiLz48 cmVjdCBmaWxsPSIjZjRmNGY0IiB4PSIxIiB5PSIxIiB3aWR0aD0iMSIgaGVpZ2h0PSIxIi8+PC9z dmc+Cg==');
}

.image-viewer .Pane {
    overflow: visible;
}
</style>
