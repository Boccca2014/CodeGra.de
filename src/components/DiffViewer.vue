<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="diff-viewer" v-if="diffOnly">
    <div v-for="(part, i) in changedParts"
         :key="`part-${i}-line-${part[0]}`">
        <hr v-if="i !== 0"
            class="m-0">
        <ol :class="{ 'show-whitespace': showWhitespace }"
            class="diff-part rounded"
            :start="part[0] + 1"
            :style="{
                paddingLeft: `${3 + Math.log10(lines.length) * 2/3}em`,
                fontSize: `${fontSize}px`,
            }">
            <li v-for="line in range(part[0], part[1])"
                :key="line"
                :class="lines[line].cls">
                <code v-html="lines[line].txt"/>
            </li>
        </ol>
    </div>
</div>
<div class="diff-viewer" v-else>
    <ol :class="{ 'show-whitespace': showWhitespace }"
        class="diff-part only scroller rounded"
        :style="{
            paddingLeft: `${3 + Math.log10(lines.length) * 2/3}em`,
            fontSize: `${fontSize}px`,
        }">
        <li v-for="(line, i) in lines"
            :key="i"
            :class="line.cls">
            <code v-html="line.txt"/>
        </li>
    </ol>
</div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/cog';
import DiffMatchPatch from 'diff-match-patch';

import { last, range } from '@/utils';
import { visualizeWhitespace } from '@/utils/visualize';

import decodeBuffer from '@/utils/decode';

import FeedbackArea from './FeedbackArea';
import Loader from './Loader';
import Toggle from './Toggle';

export default {
    name: 'diff-viewer',

    props: {
        file: {
            type: Object,
            required: true,
        },
        fileId: {
            type: String,
            required: true,
        },
        showWhitespace: {
            type: Boolean,
            default: true,
        },
        diffOnly: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            code: '',
            lines: [],
            canUseSnippets: false,
            range,
        };
    },

    watch: {
        fileId: {
            immediate: true,
            handler(id) {
                if (id) {
                    this.getCode(this.fileId);
                }
            },
        },
    },

    methods: {
        ...mapActions('code', {
            storeLoadCode: 'loadCode',
        }),

        getCode(fileId) {
            let error = '';

            const promises = this.file.ids.map(id => {
                if (id) {
                    return this.storeLoadCode(id);
                } else {
                    return Promise.resolve(new ArrayBuffer(0));
                }
            });

            Promise.all(promises)
                .then(
                    ([orig, rev]) => {
                        let origCode;
                        let revCode;
                        try {
                            origCode = decodeBuffer(orig);
                            revCode = decodeBuffer(rev);
                        } catch (e) {
                            error = 'This file cannot be displayed';
                            return;
                        }

                        if (fileId === this.fileId) {
                            this.diffCode(origCode, revCode);
                        }
                    },
                    err => {
                        error = err;
                    },
                )
                .then(() => {
                    if (error) {
                        this.$emit('error', {
                            error,
                            fileId,
                        });
                    } else {
                        this.$emit('load', fileId);
                    }
                });
        },

        diffCode(origCode, revCode) {
            const ADDED = 1;
            const REMOVED = -1;

            // This was copied from the diff-match-patch repository
            function diffText(text1, text2) {
                const dmp = new DiffMatchPatch();
                // eslint-disable-next-line no-underscore-dangle
                const { chars1, chars2, lineArray } = dmp.diff_linesToChars_(text1, text2);
                const diffs = dmp.diff_main(chars1, chars2, false);
                // eslint-disable-next-line no-underscore-dangle
                dmp.diff_charsToLines_(diffs, lineArray);
                return diffs;
            }

            const diff = diffText(origCode, revCode);
            const lines = [];

            diff.forEach(([state, text]) => {
                let cls = '';
                if (state === ADDED) {
                    cls = 'added';
                } else if (state === REMOVED) {
                    cls = 'removed';
                }
                text.split('\n').forEach((txt, i) => {
                    // Merge lines. The diff output will be:
                    // [[0, 'hello\n\n']], [-1, 'bye'], [1, 'thomas']]
                    // When diffing: `hello
                    //
                    // bye`
                    // with `hello
                    //
                    // thomas`
                    //
                    // And the output should be `hello
                    //
                    // - bye
                    // + thomas`
                    //
                    // Without this merging the output will contain an extra newline.
                    const line = { txt, cls };
                    if (i === 0 && lines.length > 0 && last(lines).txt === '') {
                        lines[lines.length - 1] = line;
                    } else {
                        lines.push(line);
                    }
                });
            });

            lines.forEach(line => {
                line.txt = this.$utils.htmlEscape(line.txt);
            });

            if (lines.length < 5000) {
                lines.forEach(line => {
                    line.txt = visualizeWhitespace(line.txt);
                });
            }

            this.lines = lines;
        },
    },

    computed: {
        ...mapGetters('pref', ['contextAmount', 'fontSize']),

        changedParts() {
            const res = [];
            const end = this.lines.length;

            this.lines.forEach((line, i) => {
                const startLine = Math.max(i - this.contextAmount, 0);
                const endLine = Math.min(i + this.contextAmount + 1, end);

                if (line.cls !== '') {
                    if (res.length === 0) {
                        res.push([startLine, endLine]);
                    } else if (last(res)[1] > startLine - 2) {
                        last(res)[1] = endLine;
                    } else {
                        res.push([startLine, endLine]);
                    }
                }
            });

            return res;
        },
    },

    components: {
        Icon,
        FeedbackArea,
        Loader,
        Toggle,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.diff-viewer {
    position: relative;
    padding: 0;
    background: rgb(248, 248, 248);

    @{dark-mode} {
        background: @color-primary-darker;
    }
}

ol {
    overflow-x: visible;
    background: @linum-bg;
    margin: 0;
    padding: 0;
    font-family: monospace;
    font-size: small;

    .diff-part only & {
        min-height: 5em;
    }

    @{dark-mode} {
        background: @color-primary-darkest;
        color: @color-secondary-text-lighter;
    }
}

li {
    position: relative;
    padding-left: 0.75em;
    padding-right: 0.75em;
    background-color: lighten(@linum-bg, 1%);
    border-left: 1px solid darken(@linum-bg, 5%);
    cursor: text;

    @{dark-mode} {
        background: @color-primary-darker;
        border-left: 1px solid darken(@color-primary-darkest, 5%);
    }

    &.added {
        background-color: @color-diff-added-light !important;

        @{dark-mode} {
            background-color: @color-diff-added-dark !important;
        }
    }

    &.removed {
        background-color: @color-diff-removed-light !important;

        @{dark-mode} {
            background-color: @color-diff-removed-dark !important;
        }
    }
}

code {
    color: @color-secondary-text;
    background: transparent;
    white-space: pre-wrap;
    font-size: 100%;

    @{dark-mode} {
        color: rgb(131, 148, 150);
    }

    li.added & {
        color: black !important;
    }

    li.removed & {
        color: black !important;
    }
}

.loader {
    margin-top: 2.5em;
    margin-bottom: 3em;
}

.diff-part {
    z-index: 100;
}
</style>

<style lang="less">
@import '~mixins.less';

.diff-viewer {
    .whitespace {
        opacity: 0;

        @{dark-mode} {
            color: @color-secondary-text;
        }
    }

    .show-whitespace .whitespace {
        opacity: 1;
    }
}
</style>
