<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="code-viewer">
    <inner-code-viewer
        :assignment="assignment"
        :submission="submission"
        :code-lines="codeLines"
        :feedback="feedback"
        :linter-feedback="linterFeedback"
        :show-whitespace="showWhitespace"
        :show-inline-feedback="showInlineFeedback"
        :can-use-snippets="canUseSnippets"
        :file-id="fileId"/>
</div>
</template>

<script>
import { listLanguages } from 'highlightjs';
import { mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/cog';

import { cmpNoCase, highlightCode } from '@/utils';
import '@/polyfills';
import decodeBuffer from '@/utils/decode';

import InnerCodeViewer from './InnerCodeViewer';
import Toggle from './Toggle';

export default {
    name: 'code-viewer',

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
            type: String,
            required: true,
        },
        language: {
            type: String,
            default: 'Default',
        },
        revision: {
            type: String,
            required: true,
        },
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
        showWhitespace: {
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
    },

    computed: {
        ...mapGetters('pref', ['fontSize']),
        ...mapGetters('feedback', ['getFeedback']),

        canSeeAssignee() {
            return this.$utils.getProps(
                this.assignment,
                false,
                'course',
                'permissions',
                'can_see_assignee',
            );
        },

        extension() {
            const fileParts = this.file.name.split('.');
            return fileParts.length > 1 ? fileParts[fileParts.length - 1] : null;
        },

        studentMode() {
            return this.revision === 'student';
        },

        isLargeFile() {
            return this.rawCodeLines && this.rawCodeLines.length > 5000;
        },

        feedback() {
            const feedback = this.getFeedback(this.assignment.id, this.submission.id);
            const fileId = this.fileId;

            if (!feedback || !this.studentMode) {
                return {};
            }

            return feedback.user[fileId] || {};
        },

        linterFeedback() {
            const feedback = this.submission.feedback;
            const fileId = this.fileId;

            if (!feedback || !this.studentMode) {
                return {};
            }

            return feedback.linter[fileId] || {};
        },

        rawCodeLines() {
            if (this.fileContent == null) {
                return [];
            }
            let code;
            try {
                code = decodeBuffer(this.fileContent);
            } catch (e) {
                this.$emit('error', {
                    error: 'This file cannot be displayed',
                    fileId: this.fileId,
                });
                return [];
            }

            return Object.freeze(code.split(/\r?\n/));
        },

        codeLines() {
            const language = this.selectedLanguage;
            if (this.rawCodeLines.length === 0 || language == null) {
                return [];
            }
            const lang = language === 'Default' ? this.extension : language;

            const res = Object.freeze(highlightCode(this.rawCodeLines, lang));
            this.emitLoad(this.fileId);
            return res;
        },
    },

    data() {
        const languages = listLanguages();
        languages.push('plain');
        languages.sort(cmpNoCase);
        languages.unshift('Default');

        return {
            selectedLanguage: 'Default',
            languages,
        };
    },

    watch: {
        fileId: {
            immediate: true,
            handler() {
                this.loadSettings();
            },
        },

        language(lang) {
            if (this.selectedLanguage === lang) {
                return;
            }
            this.selectedLanguage = lang;
        },
    },

    methods: {
        loadSettings() {
            this.selectedLanguage = null;
            return this.$hlanguageStore.getItem(this.fileId).then(lang => {
                if (lang != null) {
                    this.$emit('language', lang);
                    this.selectedLanguage = lang;
                } else {
                    this.selectedLanguage = 'Default';
                }
            }, () => {
                this.selectedLanguage = 'Default';
            });
        },

        async emitLoad(fileId) {
            if (this.fileId === fileId) {
                this.$emit('load', fileId);

                await this.$nextTick();
            }
        },
    },

    components: {
        Icon,
        Toggle,
        InnerCodeViewer,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.code-viewer {
    position: relative;
    padding: 0;
}
</style>
