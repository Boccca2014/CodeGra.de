// Disable eslint for this line as it results in a parse error
// eslint-disable-next-line
import type * as docx from 'docx';

import { hasAttr, unzip2, flatMap1, flat1, unique } from '@/utils/typed';

type TextBlock = string;

abstract class WrapperContent {
    constructor(public readonly content: ContentBlock) {}
}

export class EmphasizedContent extends WrapperContent {
    readonly brand = 'EmphasizedContent';
}

export class BoldContent extends WrapperContent {
    readonly brand = 'BoldContent';
}

export class MonospaceContent extends WrapperContent {
    readonly brand = 'MonospaceContent';
}

// Force the content of this block to be rendered on a single line if possible
// and the document format supports it.
export class NonBreakingContent {
    readonly brand = 'NonBreakingContent';

    constructor(public readonly content: ReadonlyArray<string>) {}
}

type ContentChunk =
    | TextBlock
    | EmphasizedContent
    | BoldContent
    | MonospaceContent
    | NonBreakingContent;

export class ContentBlock {
    constructor(public readonly chunks: ReadonlyArray<ContentChunk>) {}
}

export interface CodeBlock {
    // Line number of the first line in the block.
    firstLine: number;

    // The lines of text to render.
    lines: string[];

    // Specification for lines to be highlighted.
    highlights: HighlightRange[];

    // Optional caption.
    caption?: ContentBlock;
}

interface HighlightRange {
    start: number;
    end: number;
    highlight: Highlight;
}

type HighlightID = string;

export class Highlight {
    static getHighlightId: () => HighlightID = (() => {
        let curId = 0;
        return () => `${curId++}`;
    })();

    public id: HighlightID;

    constructor(public background: Color, public foreground: Color) {
        this.id = Highlight.getHighlightId();
    }
}

export interface Color {
    red: number;
    green: number;
    blue: number;
}

export class ColumnLayout<T> {
    readonly brand = 'ColumnLayout';

    constructor(public readonly columns: ReadonlyArray<T>) {}
}

class _SubSection<T> {
    readonly brand = '_SubSection';

    constructor(
        public readonly heading: string,
        public readonly children: ReadonlyArray<T>,
    ) {}
}

export class SubSection extends _SubSection<
    DocumentContentNode
    | ColumnLayout<DocumentContentNode>
    > {}
export class ColumnSubSection extends _SubSection<DocumentContentNode> {}

export class Section {
    readonly brand = 'Section';

    constructor(
        public readonly heading: string,
        public readonly children: ReadonlyArray<
            DocumentContentNode
            | SubSection
            | ColumnLayout<DocumentContentNode | ColumnSubSection>
        >,
    ) {}
}

export class NewPage {
    readonly brand = 'NewPage';
}

export type DocumentContentNode = CodeBlock | ContentBlock | NewPage;

export type DocumentNode = DocumentContentNode | Section | ColumnLayout<DocumentContentNode>;

export class DocumentRoot {
    private constructor(public readonly children: ReadonlyArray<DocumentNode>) {}

    public addChildren(children: DocumentNode[]) {
        return new DocumentRoot([...this.children, ...children]);
    }

    static makeEmpty() {
        return new DocumentRoot([]);
    }
}

abstract class DocumentBackend {
    static backendName: string;

    static fileExtension: string;

    static mimeType: string;

    constructor(public doc: DocumentRoot) {}

    abstract renderToBuffer(): Promise<ArrayBuffer>;
}

class LatexDocument extends DocumentBackend {
    static readonly backendName = 'LaTeX';

    static readonly fileExtension = 'tex';

    static readonly mimeType = 'text/x-tex';

    private static readonly endListingRegex = new RegExp('\\\\end{lstlisting}', 'g');

    private static readonly reUnescapedLatex = /[{}\\#$%&^_~]/g;

    private static readonly reHasUnescapedLatex = RegExp(LatexDocument.reUnescapedLatex.source);

    private static readonly latexEscapes: Readonly<Record<string, string>> = Object.freeze({
        '{': '\\{',
        '}': '\\}',
        '\\': '\\textbackslash{}',
        '#': '\\#',
        $: '\\$',
        '%': '\\%',
        '&': '\\&',
        '^': '\\textasciicircum{}',
        _: '\\_',
        '~': '\\textasciitilde{}',
    });

    private static escape(input: string): string {
        if (input !== '' && LatexDocument.reHasUnescapedLatex.test(input)) {
            const map = LatexDocument.latexEscapes;
            return input.replace(LatexDocument.reUnescapedLatex, ent => map[ent]);
        }
        return input;
    }

    static make(doc: DocumentRoot): Promise<LatexDocument> {
        return Promise.resolve(new LatexDocument(doc));
    }

    constructor(public doc: DocumentRoot) {
        super(doc);
    }

    renderLines(
        el: DocumentContentNode
            | DocumentNode
            | SubSection
            | ColumnLayout<DocumentContentNode | ColumnSubSection>,
    ): [string[], Highlight[]] {
        if (el instanceof Section) {
            return this.renderSection(el);
        } else if (el instanceof SubSection) {
            return this.renderSubsection(el);
        } else if (el instanceof ColumnLayout) {
            return this.renderColumn(el);
        } else if (el instanceof ContentBlock) {
            return this.renderContentBlock(el);
        } else if (el instanceof NewPage) {
            return [['\\clearpage{}'], []];
        } else {
            return this.renderCode(el);
        }
    }

    renderToBuffer(): Promise<Uint8Array> {
        const [lines, highlights] = unzip2(this.doc.children.map(child => this.renderLines(child)));

        const base = `\\documentclass{article}
\\usepackage{listings}
\\usepackage{xcolor}
\\usepackage[T1]{fontenc}
\\usepackage[utf8]{inputenc}
\\usepackage{textcomp}
\\usepackage{paracol}
\\usepackage[margin=0.5in]{geometry}

% XXX: This may break when the package "lstlinebgrd" is updated. If compilation
% of this document fails with the error "Error: Numbers none unknown", try to
% delete everything from "START fix" to "END fix", and uncomment the line below
% this one.
%\\usepackage{lstlinebgrd}
% START Fix for incompatibility between newer versions of listings and
% lstlinebgrd
\\makeatletter
\\let\\old@lstKV@SwitchCases\\lstKV@SwitchCases
\\def\\lstKV@SwitchCases#1#2#3{}
\\makeatother
\\usepackage{lstlinebgrd}
\\makeatletter
\\let\\lstKV@SwitchCases\\old@lstKV@SwitchCases

\\lst@Key{numbers}{none}{%
    \\def\\lst@PlaceNumber{\\lst@linebgrd}%
    \\lstKV@SwitchCases{#1}%
    {none:\\\\%
     left:\\def\\lst@PlaceNumber{\\llap{\\normalfont
                \\lst@numberstyle{\\thelstnumber}\\kern\\lst@numbersep}\\lst@linebgrd}\\\\%
     right:\\def\\lst@PlaceNumber{\\rlap{\\normalfont
                \\kern\\linewidth \\kern\\lst@numbersep
                \\lst@numberstyle{\\thelstnumber}}\\lst@linebgrd}%
    }{\\PackageError{Listings}{Numbers #1 unknown}\\@ehc}}
\\makeatother
% END fix

\\definecolor{bluekeywords}{rgb}{0.13, 0.13, 1}
\\definecolor{greencomments}{rgb}{0, 0.5, 0}
\\definecolor{redstrings}{rgb}{0.9, 0, 0}
\\definecolor{graynumbers}{rgb}{0.5, 0.5, 0.5}

${this.defineColors(flat1(highlights)).join('\n')}

\\lstset{
    numbers=left,
    columns=fullflexible,
    showspaces=false,
    showtabs=false,
    breaklines=true,
    showstringspaces=false,
    breakatwhitespace=false,
    commentstyle=\\color{greencomments},
    keywordstyle=\\color{bluekeywords},
    stringstyle=\\color{redstrings},
    numberstyle=\\color{graynumbers},
    basicstyle=\\ttfamily\\footnotesize,
    xleftmargin=12pt,
    rulesepcolor=\\color{graynumbers},
    tabsize=4,
    captionpos=b,
    frame=L,
    upquote=true
}

\\begin{document}
${flat1(lines).join('\n')}
\\end{document}`;

        return Promise.resolve(new TextEncoder().encode(base));
    }

    // eslint-disable-next-line class-methods-use-this
    private defineColors(highlights: ReadonlyArray<Highlight>): string[] {
        return unique(highlights, h => h.id).reduce(
            (acc: string[], highlight) => {
                const id = highlight.id;
                const bg = highlight.background;
                const fg = highlight.foreground;
                acc.push(
                    `\\definecolor{bg-color-${id}}{RGB}{${bg.red}, ${bg.green}, ${bg.blue}}`,
                    `\\definecolor{fg-color-${id}}{RGB}{${fg.red}, ${fg.green}, ${fg.blue}}`,
                );
                return acc;
            },
            ['% Unfortunately the foreground colors are not used.'],
        );
    }

    renderContentBlock(contentBlock: ContentBlock): [[string], Highlight[]] {
        const [content, highlights] = contentBlock.chunks.reduce(
            (acc: [string[], Highlight[]], chunk) => {
                if (chunk instanceof NonBreakingContent) {
                    const b = chunk.content.join('~');
                    acc[0].push(LatexDocument.escape(b).replace(/[ \t]+/g, '~'));
                    return acc;
                } else if (chunk instanceof WrapperContent) {
                    const toWrap = this.renderContentBlock(chunk.content);
                    acc[0].push(`\\${LatexDocument.wrapperTag(chunk)}{`);
                    acc[0].push(toWrap[0][0]);
                    acc[0].push('}');
                    return [acc[0], acc[1].concat(toWrap[1])];
                } else {
                    acc[0].push(LatexDocument.escape(chunk));
                    return acc;
                }
            },
            [[], []],
        );

        return [[content.join('')], highlights];
    }

    private static wrapperTag(chunk: WrapperContent): string {
        if (chunk instanceof EmphasizedContent) {
            return 'emph';
        } else if (chunk instanceof BoldContent) {
            return 'textbf';
        } else if (chunk instanceof MonospaceContent) {
            return 'texttt';
        } else {
            throw new Error('Unsupported wrapper.');
        }
    }

    renderSection(section: Section): [string[], Highlight[]] {
        return section.children.reduce(
            (accum: [string[], Highlight[]], child): [string[], Highlight[]] => {
                const res = this.renderLines(child);
                return [accum[0].concat(res[0]), accum[1].concat(res[1])];
            },
            [[`\\section{${LatexDocument.escape(section.heading)}}`], []],
        );
    }

    renderSubsection(subsection: SubSection): [string[], Highlight[]] {
        return subsection.children.reduce(
            (accum: [string[], Highlight[]], child): [string[], Highlight[]] => {
                const res = this.renderLines(child);
                return [accum[0].concat(res[0]), accum[1].concat(res[1])];
            },
            [[`\\subsection{${LatexDocument.escape(subsection.heading)}}`], []],
        );
    }

    private renderCode(code: CodeBlock): [string[], Highlight[]] {
        // TODO: don't render caption when none given.
        let caption: string = '';
        let highlights: Highlight[] = [];
        if (code.caption != null) {
            [[caption], highlights] = this.renderContentBlock(code.caption);
        }

        return [
            [
                '\\begin{lstlisting}[',
                `    firstnumber=${code.firstLine},`,
                `    linebackgroundcolor=${this.makeHighlights(code.highlights)},`,
                `    caption = {${caption}}]`,
                ...code.lines.map(line =>
                    line.replace(LatexDocument.endListingRegex, '\\end {lstlisting}'),
                ),
                '\\end{lstlisting}',
            ],
            highlights.concat(code.highlights.map(range => range.highlight)),
        ];
    }

    private makeHighlights(ranges: HighlightRange[]): string {
        const sorted = ranges.sort((a, b) => a.end - b.end);
        return this.makeHighlightsSorted(sorted);
    }

    private makeHighlightsSorted(ranges: HighlightRange[]): string {
        // Ranges must be sorted and not overlap. Because there is no "and"
        // operator in TeX that is the only way we can guarantee that the
        // nested if-else below will work correctly.
        // TODO: Find a way to change the foreground color of specific lines.
        // Maybe simply wrapping each line in a {\color{fg-color-${id}} ...}
        // will work.

        const [cur, ...rest] = ranges;

        if (rest.length === 0) {
            return `
\\ifnum\\value{lstnumber}<${cur.end + 1}%
    \\ifnum\\value{lstnumber}>${cur.start - 1}%
        \\color{bg-color-${cur.highlight.id}}%
    \\fi%
\\fi
            `.trim();
        } else {
            return `
\\ifnum\\value{lstnumber}<${cur.end + 1}%
    \\ifnum\\value{lstnumber}>${cur.start - 1}%
        \\color{bg-color-${cur.highlight.id}}%
    \\fi%
\\else%
    ${this.makeHighlightsSorted(rest)}%
\\fi
            `.trim();
        }
    }

    renderColumn(
        column: ColumnLayout<DocumentContentNode | Section | SubSection>,
    ): [string[], Highlight[]] {
        const columns = column.columns.length;
        return column.columns.reduce(
            (acc: [string[], Highlight[]], block, index) => {
                const res = this.renderLines(block);
                acc[0] = acc[0].concat(res[0]);
                if (index !== column.columns.length - 1) {
                    acc[0].push('\\switchcolumn');
                } else {
                    acc[0].push('\\end{paracol}');
                }
                acc[1] = acc[1].concat(res[1]);
                return acc;
            },
            [[`\\begin{paracol}{${columns}}`], []],
        );
    }
}

class DocxDocument extends DocumentBackend {
    static readonly backendName = 'Docx';

    static readonly fileExtension = 'docx';

    static readonly mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

    private codeBlockIndex: number = 0;

    static async make(doc: DocumentRoot): Promise<DocxDocument> {
        const docxType = await import('docx');
        return new DocxDocument(doc, docxType);
    }

    constructor(public readonly doc: DocumentRoot, private readonly docxType: typeof docx) {
        super(doc);
    }

    async renderToBuffer(): Promise<ArrayBuffer> {
        const doc = new this.docxType.Document({
            numbering: {
                config: [...this.codeBlockNumberings()],
            },
        });

        this.doc.children.forEach(child => this.renderDocument(child, doc));

        const blob = await this.docxType.Packer.toBlob(doc);
        return blob.arrayBuffer();
    }

    renderDocument(child: DocumentNode, document: docx.Document) {
        if (child instanceof Section) {
            this.renderSection(child, document);
        } else {
            document.addSection({
                children: this.renderElement(child),
            });
        }
    }

    private codeBlockNumberings(): ReadonlyArray<Readonly<{
        levels: docx.ILevelsOptions[];
        reference: string;
    }>> {
        return this.getCodeBlocks().map((block, i) => ({
            levels: [
                {
                    level: 0,
                    format: 'decimal',
                    start: block.firstLine,
                    text: '%1',
                    alignment: this.docxType.AlignmentType.END,
                    style: {
                        paragraph: {
                            indent: { left: 720, hanging: 260 },
                        },
                    },
                },
            ],
            reference: `decimal-ordered-${i}`,
        }));
    }

    private getCodeBlocks(): CodeBlock[] {
        function getBlocks(
            els: ReadonlyArray<
                DocumentNode | SubSection | ColumnLayout<DocumentContentNode | ColumnSubSection
                >>,
        ): CodeBlock[] {
            return els.reduce((acc: CodeBlock[], el): CodeBlock[] => {
                if (el instanceof Section) {
                    return acc.concat(getBlocks(el.children));
                } else if (el instanceof SubSection) {
                    return acc.concat(getBlocks(el.children));
                } else if (el instanceof ColumnLayout) {
                    return acc.concat(getBlocks(el.columns));
                } else if (el instanceof ContentBlock || el instanceof NewPage) {
                    return acc;
                } else {
                    return acc.concat(el);
                }
            }, []);
        }

        return getBlocks(this.doc.children);
    }

    renderSection(el: Section, doc: docx.Document): void {
        doc.addSection({
            margins: {
                left: 360,
                right: 360,
                top: 360,
                bottom: 0,
            },
            headers: {
                default: new this.docxType.Header({
                    children: [new this.docxType.Paragraph(el.heading)],
                }),
            },
            children: flatMap1(el.children, child => this.renderElement(child)),
        });
    }

    renderElement(
        el: DocumentContentNode | SubSection | ColumnLayout<DocumentContentNode | ColumnSubSection>,
    ): (docx.Paragraph | docx.Table)[] {
        if (el instanceof SubSection) {
            return this.renderSubSection(el);
        } else if (el instanceof ColumnLayout) {
            return this.renderColumn(el);
        } else if (el instanceof ContentBlock) {
            return [new this.docxType.Paragraph({ children: this.renderContentBlock(el) })];
        } else if (el instanceof NewPage) {
            return this.renderNewPage();
        } else {
            return this.renderCode(el);
        }
    }

    renderSubSection(el: SubSection): (docx.Paragraph | docx.Table)[] {
        return [
            new this.docxType.Paragraph({
                text: el.heading,
                heading: this.docxType.HeadingLevel.HEADING_3,
            }),
            ...flatMap1(el.children, child => this.renderElement(child)),
        ];
    }

    renderColumn(
        el: ColumnLayout<DocumentContentNode | ColumnSubSection>,
    ): docx.Table[] {
        const width = 100 / el.columns.length;
        const getBorder = () => ({
            style: this.docxType.BorderStyle.NONE,
            color: '000000',
            size: 1,
        });

        const getBorders = () => ({
            top: getBorder(),
            bottom: getBorder(),
            left: getBorder(),
            right: getBorder(),
        });

        const table = new this.docxType.Table({
            rows: [
                new this.docxType.TableRow({
                    children: el.columns.map(child => new this.docxType.TableCell({
                        children: this.renderElement(child),
                        width: {
                            size: width,
                            type: this.docxType.WidthType.PERCENTAGE,
                        },
                        borders: getBorders(),
                    })),
                }),
            ],
            borders: getBorders(),
            width: { size: 100, type: this.docxType.WidthType.PERCENTAGE },
            columnWidths: el.columns.map(() => width),
            layout: this.docxType.TableLayoutType.FIXED,
        });
        return [table];
    }

    renderContentBlock(el: ContentBlock, opts: docx.IRunOptions = {}): docx.TextRun[] {
        return flatMap1(el.chunks, chunk => this.renderContentChunk(chunk, opts));
    }

    renderContentChunk(el: ContentChunk, opts: docx.IRunOptions): docx.TextRun[] {
        const childOpts = (key: string, value: any) => Object.assign({}, opts, { [key]: value });

        if (el instanceof EmphasizedContent) {
            return this.renderContentBlock(el.content, childOpts('italics', true));
        } else if (el instanceof BoldContent) {
            return this.renderContentBlock(el.content, childOpts('bold', true));
        } else if (el instanceof MonospaceContent) {
            return this.renderContentBlock(el.content, childOpts('font', { name: 'Courier new' }));
        } else if (el instanceof NonBreakingContent) {
            // TODO: Try to make this non-breaking.
            return el.content.map(str => new this.docxType.TextRun(childOpts('text', str)));
        } else {
            return [new this.docxType.TextRun(childOpts('text', el))];
        }
    }

    // eslint-disable-next-line class-methods-use-this
    renderNewPage(): docx.Paragraph[] {
        return [new this.docxType.Paragraph({ pageBreakBefore: true })];
    }

    // eslint-disable-next-line class-methods-use-this
    renderCode(el: CodeBlock): docx.Paragraph[] {
        const shadings: { [lnum: number]: string } = {};
        const colors: { [lnum: number]: string } = {};
        el.highlights.forEach(hl => {
            for (let i = hl.start; i <= hl.end; i++) {
                shadings[i] = DocxDocument.colorToString(hl.highlight.background);
                colors[i] = DocxDocument.colorToString(hl.highlight.foreground);
            }
        });

        const start = el.firstLine;
        const blockIdx = this.codeBlockIndex++;

        const pars = el.lines.map((line, offset) => {
            const lnum = start + offset;
            return new this.docxType.Paragraph({
                numbering: {
                    reference: `decimal-ordered-${blockIdx}`,
                    level: 0,
                },
                children: [
                    new this.docxType.TextRun({
                        text: line,
                        size: 18, // This is 9 point
                        font: { name: 'Courier New' },
                        color: colors[lnum] ?? '000000',
                        shading: {
                            type: this.docxType.ShadingType.SOLID,
                            fill: 'fill',
                            color: shadings[lnum] ?? 'FFFFFF',
                        },
                    }),
                ],
            });
        });

        if (el.caption != null) {
            pars.push(
                new this.docxType.Paragraph({
                    alignment: this.docxType.AlignmentType.CENTER,
                    spacing: {
                        before: 200,
                        after: 200,
                    },
                    children: this.renderContentBlock(el.caption),
                }),
            );
        }

        return pars;
    }

    static colorToString(color: Color): string {
        const toHex = (x: number) => {
            const s = x.toString(16);
            return s.length === 1 ? `0${s}` : s;
        };
        return `${toHex(color.red)}${toHex(color.green)}${toHex(color.blue)}`;
    }
}

export const backends = {
    [LatexDocument.backendName]: LatexDocument,
    [DocxDocument.backendName]: DocxDocument,
} as const;

export async function render(
    backendName: keyof typeof backends,
    document: DocumentRoot,
): Promise<ArrayBuffer> {
    if (!hasAttr(backends, backendName)) {
        // eslint-disable-next-line @typescript-eslint/restrict-template-expressions
        throw new Error(`Invalid backend: ${backendName} `);
    }
    const backend = await backends[backendName].make(document);
    return backend.renderToBuffer();
}
