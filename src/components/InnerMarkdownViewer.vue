<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="inner-markdown-viewer"
     :class="{'show-whitespace': showCodeWhitespace}"
     v-html="html">
</div>
</template>

<script>
import { CgMarkdownIt } from '@/cg-math';
import markdownItSanitizer from 'markdown-it-sanitizer';

export default {
    name: 'inner-markdown-viewer',

    props: {
        markdown: {
            type: String,
            required: true,
        },

        showCodeWhitespace: {
            type: Boolean,
            default: true,
        },

        disableMath: {
            type: Boolean,
            default: false,
        },

        blockExternalImages: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        const md = new CgMarkdownIt();
        md.use(markdownItSanitizer);

        return {
            md,
        };
    },

    computed: {
        html() {
            return this.md.render(this.markdown, this.disableMath, this.blockExternalImages);
        },

        blockedExternal() {
            return this.md.blockedExternal;
        },
    },

    watch: {
        html: {
            async handler() {
                if (!this.disableMath) {
                    // Make sure html is rendered before we kick MathJax.
                    await this.$nextTick();
                    window.MathJax.Hub.Queue(['Typeset', window.MathJax.Hub, this.$el]);
                }
            },
            immediate: true,
        },

        blockedExternal: {
            immediate: true,
            handler() {
                this.$emit('blocked-external', {
                    blocked: this.blockedExternal,
                });
            },
        },
    },
};
</script>

<style lang="less">
@import '~mixins.less';

.inner-markdown-viewer {
    white-space: wrap;
    word-wrap: break-word;
    word-break: break-word;

    h1 {
        font-size: 2.5em;
    }

    h2 {
        font-size: 2em;
    }

    h3 {
        font-size: 1.75em;
    }

    h4 {
        font-size: 1.5em;
    }

    h5 {
        font-size: 1.25em;
    }

    h6 {
        font-size: 1em;
    }

    pre {
        padding: 0.5rem 1rem;
        background-color: @color-lightest-gray;
        border-radius: 0.25rem;
        font-size: 100%;
        white-space: pre-wrap;
        word-wrap: break-word;
        word-break: break-word;
        hyphens: auto;

        @{dark-mode} {
            color: @text-color-dark;
            background-color: fade(@color-primary-darker, 50%);
        }
    }

    img,
    .MathJax_SVG svg {
        max-width: 100%;

        @media @media-large {
            max-width: 30rem;
        }
    }

    a {
        color: @color-inline-link !important;
    }
}
</style>
