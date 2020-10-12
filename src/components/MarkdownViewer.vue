<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<floating-feedback-button
    :disabled="!showInlineFeedback"
    class="markdown-viewer"
    :style="{ fontSize: `${fontSize}px`}"
    :fileId="fileId"
    :line="line"
    :feedback="feedback"
    :editable="editable"
    :can-use-snippets="canUseSnippets"
    :assignment="assignment"
    :submission="submission"
    slot-description="file"
    snippet-field-above
    always-show-button
    add-space
    force-snippets-above>
    <inner-markdown-viewer v-if="data"
                           class="w-100 py-2 px-3"
                           :markdown="data"
                           :show-code-whitespace="showWhitespace"/>
</floating-feedback-button>
</template>

<script>
import { mapGetters } from 'vuex';
import decodeBuffer from '@/utils/decode';

import InnerMarkdownViewer from './InnerMarkdownViewer';
import FloatingFeedbackButton from './FloatingFeedbackButton';
import Loader from './Loader';

export default {
    name: 'markdown-viewer',

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
        showWhitespace: {
            type: Boolean,
            default: true,
        },
        showInlineFeedback: {
            type: Boolean,
            defualt: true,
        },
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
        fileContent: {
            required: true,
        },
    },

    computed: {
        ...mapGetters('pref', ['fontSize']),

        line() {
            return 0;
        },

        feedback() {
            return this.$utils.getProps(
                this.submission,
                null,
                'feedback',
                'user',
                this.fileId,
                this.line,
            );
        },

        data() {
            if (this.fileContent == null) {
                return '';
            }

            try {
                const res = decodeBuffer(this.fileContent);
                this.$emit('load', this.fileId);
                return res;
            } catch (error) {
                this.$emit('error', {
                    error,
                    fileId: this.fileId,
                });
                return '';
            }
        },
    },

    components: {
        InnerMarkdownViewer,
        FloatingFeedbackButton,
        Loader,
    },
};
</script>
