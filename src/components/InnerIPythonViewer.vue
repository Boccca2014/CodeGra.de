<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="inner-ipython-viewer p-3">
    <div v-for="(cell, i) in outputCells"
        :key="`output-cell-${i}`"
        :style="{ fontSize: `${fontSize}px` }"
        class="output-cell">
        <hr v-if="i > 0"/>

        <span class="input-data-prompt"
              v-if="cell.cell_type === 'code'">
            In [{{ cell.execution_count || 1 }}]:
        </span>

        <div class="inner-output-cell">
            <span v-if="cell.cell_type === 'markdown'"
                  class="markdown-wrapper">
                <floating-feedback-button
                    :disabled="withoutFeedback"
                    :fileId="fileId"
                    :line="cell.feedback_offset"
                    :feedback="feedback[cell.feedback_offset]"
                    :assignment="assignment"
                    :submission="submission"
                    :editable="editable"
                    no-resize
                    :can-use-snippets="canUseSnippets"
                    force-snippets-above>
                    <inner-markdown-viewer
                        :markdown="cell.source"
                        :show-code-whitespace="showWhitespace"/>
                </floating-feedback-button>
            </span>
            <div v-else-if="cell.cell_type === 'code'">
                <inner-code-viewer
                    class="code border rounded p-0"
                    :assignment="assignment"
                    :submission="submission"
                    :code-lines="cell.source"
                    :feedback="feedback"
                    :linter-feedback="{}"
                    :show-whitespace="showWhitespace"
                    :show-inline-feedback="!withoutFeedback"
                    :can-use-snippets="canUseSnippets"
                    :line-feedback-offset="cell.feedback_offset"
                    :file-id="fileId"
                    empty-file-message="Cell is empty"
                    :editable="editable"
                    :warn-no-newline="false"/>
                <div v-for="out in cell.outputs"
                     :key="`cell-output-${out.feedback_offset}`"
                     class="result-cell">
                    <span class="output-data-prompt">
                        Out [{{ cell.execution_count || 1}}]:
                    </span>
                    <floating-feedback-button
                        :disabled="withoutFeedback"
                        :class="{'feedback-editable-output': editable}"
                        :assignment="assignment"
                        :submission="submission"
                        :fileId="fileId"
                        :line="out.feedback_offset"
                        :feedback="feedback[out.feedback_offset]"
                        :editable="editable"
                        no-resize
                        :can-use-snippets="canUseSnippets">
                        <div class="inner-result-cell">
                            <span v-if="out.output_type === 'execute_result' || out.output_type === 'display_data'"
                                  class="mime-output">
                                <img v-if="outputData(out, ['png', 'image/png'])" :src="'data:image/png;base64,' + outputData(out, ['png', 'image/png'])"/>
                                <img v-else-if="outputData(out, ['jpeg', 'image/jpeg'])" :src="'data:image/jpeg;base64,' + outputData(out, ['jpeg', 'image/jpeg'])"/>
                                <span v-else-if="outputData(out, ['text/markdown'])">
                                    <inner-markdown-viewer :markdown="outputData(out, ['text/markdown'])"
                                                           :show-code-whitespace="showWhitespace"/>
                                </span>
                                <span v-else-if="outputData(out, ['text', 'text/plain'])">
                                    <pre>{{ outputData(out, ['text', 'text/plain']) }}</pre>
                                </span>
                                <span v-else>
                                    <b style="color: red;">Unsupported output</b>
                                </span>
                            </span>
                            <pre v-else-if="out.output_type === 'stream'">{{ maybeJoinArray(out.text) }}</pre>
                            <pre v-else-if="out.output_type === 'error'">{{ maybeJoinArray(out.traceback) }}</pre>
                            <span v-else style="color: red;">
                                <b>Unknown output type:</b> {{ out.output_type }}
                            </span>
                        </div>
                    </floating-feedback-button>
                </div>
            </div>
        </div>
    </div>
</div>
</template>

<script>
import { mapGetters } from 'vuex';

import InnerMarkdownViewer from './InnerMarkdownViewer';
import InnerCodeViewer from './InnerCodeViewer';
import FloatingFeedbackButton from './FloatingFeedbackButton';

export default {
    name: 'inner-ipython-viewer',

    props: {
        assignment: {
            type: Object,
            required: true,
        },
        submission: {
            type: Object,
            required: true,
        },
        fileId: {
            type: String,
            required: true,
        },
        editable: {
            type: Boolean,
            required: false,
        },
        withoutFeedback: {
            type: Boolean,
            default: false,
        },
        showWhitespace: {
            type: Boolean,
            required: true,
        },
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
        outputCells: {
            type: Array,
            required: true,
        },
    },

    computed: {
        ...mapGetters('pref', ['fontSize']),

        feedback() {
            return this.$utils.getProps(this.submission, {}, 'feedback', 'user', this.fileId);
        },
    },

    methods: {
        outputData(output, types) {
            for (let i = 0; i < types.length; ++i) {
                // nbformat v3 does not have a `data` key with the props we are interested in,
                // but instead has those keys directly on the output object.
                const data = this.$utils.getProps(output, output, 'data');
                if (data[types[i]]) {
                    return this.maybeJoinArray(data[types[i]]);
                }
            }
            return null;
        },

        maybeJoinArray(txt) {
            if (Array.isArray(txt)) {
                return txt.join('');
            }
            return txt;
        },
    },

    components: {
        InnerCodeViewer,
        InnerMarkdownViewer,
        FloatingFeedbackButton,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.inner-ipython-viewer {
    position: relative;
}

.output-cell {
    &:not(:last-child) {
        margin-bottom: 20px;
    }

    .code {
        padding-right: 0;
        overflow-x: hidden;
    }

    .inner-markdown-viewer,
    .inner-result-cell {
        width: 100%;
    }

    .inner-result-cell pre {
        padding: 0.6em 2rem;
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: @border-radius;

        @{dark-mode} {
            background: @color-primary-darkest;
            color: @color-secondary-text-lighter;
        }
    }

    .input-data-prompt,
    .output-data-prompt {
        font-family: monospace;
        color: rgb(153, 153, 153);
        width: 7em;
        margin-left: -10px;
        overflow-x: visible;
        display: block;
    }

    .output-data-prompt {
        margin-top: 10px;
        margin-bottom: 5px;
    }
}

pre {
    margin-bottom: 0;
    font-size: 100%;
    white-space: pre-wrap;
    word-wrap: break-word;
    word-break: break-word;
    hyphens: auto;
}

.mime-output {
    overflow-x: auto;
}

.inner-result-cell img {
    max-width: 100%;
}

.inner-output-cell {
    position: relative;
}
</style>
