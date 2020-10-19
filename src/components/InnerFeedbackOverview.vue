<template>
<div class="inner-feedback-viewer">
    <template v-if="fileIds.length === 0">
        <slot name="no-feedback" />
    </template>

    <template v-else-if="error != null">
        <slot name="error" :error="error" />
    </template>

    <div v-for="id in fileIds"
               v-else
               v-bind="fileWrapperProps"
               :key="id"
               class="inner-inline-feedback-file">
        <slot name="header"
              :file="getFileProp(id)" />

        <component :is="partsWrapperComponent"
                   :id="`inner-feedback-overview-file-${id}`"
                   v-b-visible="visible => onFileVisible(id, visible)"
                   class="parts-wrapper">
            <slot name="disabled-file"
                  :file="getFileProp(id)"
                  :fileType="disabledFileType(id)"
                  :userFeedback="feedback.user[id]"
                  v-if="disabledFileType(id)" />

            <div v-else-if="codeLines[id] == null">
                <cg-loader :scale="2"/>
            </div>
            <div v-else
                 v-for="(part, i) in getParts(id)"
                 :key="`file-${id}-line-${part[0]}`">
                <slot name="code"
                      :file="getFileProp(id)"
                      :userFeedback="feedback.user[id] || {}"
                      :linterFeedback="feedback.linter[id]"
                      :chunk="{ start: part[0], end: part[1], content: codeLines[id], idx: i }" />
            </div>
        </component>
    </div>
</div>
</template>


<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';

import { mapActions } from 'vuex';
import decodeBuffer from '@/utils/decode';

import * as models from '@/models';

const KNOWN_EXTENSIONS: Record<string, { name: string, singleLine: boolean }> = Object.freeze({
    ipynb: {
        name: 'IPython notebooks',
        singleLine: false,
    },
    md: {
        name: 'markdown files',
        singleLine: true,
    },
    markdown: {
        name: 'markdown files',
        singleLine: true,
    },
    svg: {
        name: 'images',
        singleLine: true,
    },
    gif: {
        name: 'images',
        singleLine: true,
    },
    jpeg: {
        name: 'images',
        singleLine: true,
    },
    jpg: {
        name: 'images',
        singleLine: true,
    },
    png: {
        name: 'images',
        singleLine: true,
    },
    pdf: {
        name: 'PDF files',
        singleLine: true,
    },
});

@Component({
    methods: {
        ...mapActions('code', { storeLoadCode: 'loadCode' }),
    },
})
export default class InnerFeedbackOverview extends Vue {
    @Prop({ required: true }) fileWrapperProps!: Record<string, object>;

    @Prop({ required: true }) partsWrapperComponent!: string;

    @Prop({ required: true }) assignment!: models.Assignment;

    @Prop({ required: true }) submission!: models.Submission;

    @Prop({ required: true }) feedback!: models.Feedback;

    @Prop({ required: true }) fileTree!: models.FileTree;

    @Prop({ required: true }) shouldRenderThread!: (thread: models.FeedbackLine) => boolean;

    @Prop({ required: true }) contextLines!: number;

    @Prop({ default: () => null }) onFileVisible!: (fileId: string, visible: boolean) => unknown;

    private storeLoadCode!: (fileId: string) => Promise<ArrayBuffer>;

    private codeLines: Record<string, string[]> = {};

    private error: Error | null = null;

    get submissionId() {
        return this.submission.id;
    }

    @Watch('submissionId')
    onSubmissionChange() {
        this.codeLines = {};
        this.loadCode();
    }

    get fileIds() {
        return Object.keys(this.feedback?.user ?? {}).filter(
            fileId => Object.values(this.feedback.user[fileId] ?? {}).some(
                thread => this.shouldRenderThread(thread),
            ),
        ).sort((a, b) => a.localeCompare(b));
    }

    get nonDisabledFileIds() {
        return this.fileIds.filter(id => !this.disabledFileType(id));
    }

    getFileLink(fileId: string) {
        const revision = this.fileTree.getRevision(fileId);
        const newQuery = Object.assign({}, this.$route.query, {
            revision,
        });

        return {
            name: 'submission_file',
            params: {
                courseId: this.assignment.courseId,
                assignmentId: this.assignment.id,
                submissionId: this.submission.id,
                fileId,
            },
            query: newQuery,
            hash: '#code',
        };
    }

    disabledFileType(fileId: string) {
        const file = this.fileTree.flattened[fileId];
        if (!file) {
            return false;
        }
        return KNOWN_EXTENSIONS[this.$utils.getExtension(file) ?? ''];
    }

    @Watch('nonDisabledFileIds', { immediate: true })
    async loadCode() {
        if (this.fileIds.length === 0) {
            this.codeLines = {};
            return Promise.resolve();
        }

        if (this.codeLines == null) {
            this.codeLines = {};
        }

        const unloadedIds = this.nonDisabledFileIds.filter(id => this.codeLines[id] == null);
        return unloadedIds.map(async id => {
            const code = await this.loadCodeWithSettings(id);
            if (code != null) {
                this.$set(this.codeLines, id, code);
            }
        });
    }

    highlightCode(codeLines: string[], language: string, filePath: string): string[] {
        let lang = language;
        if (lang === 'Default') {
            lang = this.$utils.getExtension(filePath) ?? filePath;
        }
        return this.$utils.highlightCode(codeLines, lang, 1000);
    }

    getCode(fileId: string, selectedLanguage: string): Promise<ReadonlyArray<string> | null> {
        return this.storeLoadCode(fileId).then(
            rawCode => {
                let code;
                try {
                    code = decodeBuffer(rawCode);
                } catch (e) {
                    return [];
                }
                return this.highlightCode(
                    code.split('\n'),
                    selectedLanguage,
                    this.fileTree.flattened[fileId],
                );
            },
            err => {
                this.error = err;
                return null;
            },
        );
    }

    async loadCodeWithSettings(fileId: string): Promise<ReadonlyArray<string> | null> {
        const val: string | null = await this.$hlanguageStore.getItem(`${fileId}`);
        let selectedLanguage;

        if (val !== null) {
            selectedLanguage = val;
        } else {
            selectedLanguage = 'Default';
        }
        return this.getCode(fileId, selectedLanguage);
    }

    getFileProp(id: string) {
        return {
            id,
            name: this.fileTree.flattened[id],
            link: this.getFileLink(id),
            disabled: this.disabledFileType(id),
        };
    }

    getParts(fileId: string): ReadonlyArray<[number, number]> {
        const last = this.$utils.last;
        const lines = this.codeLines[fileId];
        const feedback = this.feedback.user[fileId];

        const ret = Object.entries(feedback).reduce(
            (res: [number, number][], [lineStr, thread]) => {
                if (!this.shouldRenderThread(thread)) {
                    return res;
                }

                const line = parseFloat(lineStr);
                const startLine = Math.max(line - this.contextLines, 0);
                const endLine = Math.min(line + this.contextLines + 1, lines.length);

                if (res.length === 0 || last(last(res)) <= startLine - 2) {
                    res.push([startLine, endLine]);
                } else {
                    last(res)[1] = endLine;
                }

                return res;
            },
            [],
        );

        return ret;
    }
}
</script>
