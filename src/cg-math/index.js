// SPDX-License-Identifier: AGPL-3.0-only
import markdownIt from 'markdown-it';
import Vue from 'vue';
import { highlightCode, htmlEscape } from '@/utils';

/* Much of this code is copied directly from jupyter with little to no
 * changes. All rights remain theirs.
 */

const MATHSPLIT = /(\$\$?|\\(?:begin|end)\{[a-z]*\*?\}|\\[{}$]|[{}]|(?:\n\s*)+|@@\d+@@|\\\\(?:\(|\)|\[|\]))/i;

const ALLOWED_EXTERNAL_URLS = /^https:\/\/(imgur.com|upload.wikimedia.org)/;
const THIS_URL = `${UserConfig.externalUrl}/static/img`;

// eslint-disable-next-line
export class CgMarkdownIt {
    constructor() {
        this.noExternalImages = false;
        this.blockedExternal = false;

        this.md = markdownIt({
            html: true,
            typographer: false,
            highlight(str, lang) {
                const inner = highlightCode(str.split('\n'), lang).join('<br>');
                return `<pre class="code-block"><code>${inner}</code></pre>`;
            },
            linkify: true,
        });
        this.md.linkify
            .set({ fuzzyLink: false })
            .add('ftp:', null)
            .add('//', null)
            .add('mailto:', null);

        // Remember old renderer, if overridden, or proxy to default renderer
        const defaultRender =
            this.md.renderer.rules.link_open ||
            ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));

        this.md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
            const token = tokens[idx];
            token.attrSet('target', '_blank');

            return defaultRender(tokens, idx, options, env, self);
        };

        const oldImage = this.md.renderer.rules.image;

        this.md.renderer.rules.image = (tokens, idx, options, env, self) => {
            const token = tokens[idx];
            const src = token.attrGet('src');

            if (this.noExternalImages && src) {
                if (!src.startsWith(THIS_URL) && !ALLOWED_EXTERNAL_URLS.test(src)) {
                    Vue.set(this, 'blockedExternal', true);
                    token.attrSet(
                        'title',
                        'External images are disallowed by default, you can enable them on top.',
                    );
                    token.attrSet('alt', 'External images are disallowed by default');
                    token.attrSet('src', `${UserConfig.externalUrl}/static/img/fa-ban.svg`);
                    token.attrSet('style', 'width: 25px; cursor: help;');
                }
            }

            if (oldImage) {
                return oldImage(tokens, idx, options, env, self);
            }
            return self.renderToken(tokens, idx, options, env, self);
        };

        this.mathBlocks = [];
    }

    insertMath(text) {
        return text.replace(/@@(\d+)@@/g, (_, n) => {
            //
            //  Replaces a math placeholder with its corresponding group.
            //  The math delimiters "\\(", "\\[", "\\)" and "\\]" are replaced
            //  removing one backslash in order to be interpreted correctly by MathJax.
            //
            const math = this.mathBlocks[parseInt(n, 10)];

            // Replace all the math group placeholders in the text
            // with the saved strings.
            if (math.substr(0, 3) === '\\\\(' && math.substr(math.length - 3) === '\\\\)') {
                return `\\(${math.substring(3, math.length - 3)}\\)`;
            } else if (math.substr(0, 3) === '\\\\[' && math.substr(math.length - 3) === '\\\\]') {
                return `\\[${math.substring(3, math.length - 3)}\\]`;
            }
            return math;
        });
    }

    use(plugin) {
        this.md.use(plugin);
    }

    processMath(i, j, preProcessFunc, blocks) {
        const block = htmlEscape(blocks.slice(i, j + 1).join(''));

        for (let innerJ = j; innerJ > i; innerJ--) {
            blocks[innerJ] = '';
        }

        blocks[i] = `@@${this.mathBlocks.length}@@`; // replace the current block text with a unique tag to find later
        this.mathBlocks.push((preProcessFunc || (x => x))(block));

        return blocks;
    }

    removeMath(text) {
        let start;
        let end;
        let last;
        let braces;

        // Except for extreme edge cases, this should catch precisely those
        // pieces of the markdown source that will later be turned into code
        // spans. While MathJax will not TeXify code spans, we still have to
        // consider them at this point; the following issue has happened several
        // times:
        //
        //  `$foo` and `$bar` are varibales.  -->  <code>$foo ` and `$bar</code> are variables.

        const hasCodeSpans = /`/.test(text);
        let deTilde = x => x;
        let innerText = text;
        if (hasCodeSpans) {
            const tilde = wholematch => wholematch.replace(/\$/g, '~D');

            innerText = text
                .replace(/~/g, '~T')
                .replace(/(^|[^\\])(`+)([^\n]*?[^`\n])\2(?!`)/gm, tilde)
                .replace(/^\s{0,3}(`{3,})(.|\n)*?\1/gm, tilde);

            deTilde = txt =>
                txt.replace(/~([TD])/g, (wholematch, character) => ({ T: '~', D: '$' }[character]));
        }

        let blocks = innerText.replace(/\r\n?/g, '\n').split(MATHSPLIT);

        for (let i = 1, m = blocks.length; i < m; i += 2) {
            const block = blocks[i];
            if (block.charAt(0) === '@') {
                // Our regex makes sure that
                // assert block.chartAt(1) === '@'

                //
                //  Things that look like our math markers will get
                //  stored and then retrieved along with the math.
                //
                blocks[i] = `@@${this.mathBlocks.length}@@`;
                this.mathBlocks.push(block);
            } else if (start) {
                //
                //  If we are in math, look for the end delimiter,
                //    but don't go past double line breaks, and
                //    and balance braces within the math.
                //
                if (block === end) {
                    if (braces) {
                        last = i;
                    } else {
                        blocks = this.processMath(start, i, deTilde, blocks);
                        start = null;
                        end = null;
                        last = null;
                    }
                } else if (block.match(/\n.*\n/)) {
                    if (last) {
                        i = last;
                        blocks = this.processMath(start, i, deTilde, blocks);
                    }
                    start = null;
                    end = null;
                    last = null;
                    braces = 0;
                } else if (block === '{') {
                    braces++;
                } else if (block === '}' && braces) {
                    braces--;
                }
            } else if (block === '$' || block === '$$') {
                start = i;
                end = block;
                braces = 0;
            } else if (block === '\\\\(' || block === '\\\\[') {
                start = i;
                end = block.slice(-1) === '(' ? '\\\\)' : '\\\\]';
                braces = 0;
            } else if (block.substr(1, 5) === 'begin') {
                start = i;
                end = `\\end${block.substr(6)}`;
                braces = 0;
            }
        }

        if (last) {
            blocks = this.processMath(start, last, deTilde, blocks);
        }

        return deTilde(blocks.join(''));
    }

    render(md, noMath = false, disallowExternalImages = false) {
        this.mathBlocks = [];
        this.noExternalImages = disallowExternalImages;
        Vue.set(this, 'blockedExternal', false);

        try {
            if (noMath) {
                return this.md.render(md);
            }
            return this.insertMath(this.md.render(this.removeMath(md)));
        } finally {
            this.mathBlocks = [];
        }
    }
}
