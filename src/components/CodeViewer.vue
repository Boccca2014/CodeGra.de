<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="code-viewer">
    <inner-code-viewer
        :assignment="assignment"
        :submission="submission"
        :code-lines="codeLines"
        :feedback="feedback"
        :gutter-comments="gutterComments"
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

import * as models from '@/models';

import { cmpNoCase, highlightCode } from '@/utils';
import '@/polyfills';
import decodeBuffer from '@/utils/decode';
import { DefaultMap } from '@/utils/defaultdict';

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
        qualityComments: {
            type: Array,
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

            if (!this.$userConfig.features.linters || !feedback || !this.studentMode) {
                return {};
            }

            return feedback.linter[fileId] || {};
        },

        gutterComments() {
            const { linterFeedback, qualityComments } = this;
            const comments = new DefaultMap(() => []);

            for (const line of Object.keys(linterFeedback)) {
                const forLine = comments.get(line);
                for (const comment of linterFeedback[line]) {
                    const model = models.QualityComment.fromServerData({
                        step_id: null,
                        result_id: null,
                        file_id: this.fileId,
                        severity: models.QualityCommentSeverity.old_linter,
                        code: comment[1].code,
                        origin: comment[0],
                        msg: comment[1].msg,
                        line: comment[1].line,
                        column: { start: 1 },
                    });
                    forLine.push(model);
                }
                comments.get(line).push(...linterFeedback[line]);
            }

            for (const comment of qualityComments) {
                const lines = comment.line;
                for (let line = lines.start; line <= lines.end; line++) {
                    comments.get(line - 1).push(comment);
                }
            }

            return Object.fromEntries(comments.entries());
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
                if (lang !== null) {
                    this.$emit('language', lang);
                    this.selectedLanguage = lang;
                } else {
                    this.selectedLanguage = 'Default';
                }
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
