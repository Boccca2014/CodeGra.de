/* SPDX-License-Identifier: AGPL-3.0-only */
import { VNode, CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import {
    CGIPythonCodeCellOutput,
    IPythonMimeData,
    IPythonV4MimeDataString,
    IPythonDisplayDataOutput,
    IPythonExecuteResultOuput,
    IPythonV3MimeDataString,
} from '@/utils/ipython';
import { AssertionError } from '@/utils';

import AnsiColoredText from './AnsiColoredText';
// @ts-ignore
import InnerMarkdownViewer from './InnerMarkdownViewer';

const maybeJoin = (txt: undefined | string | string[], joiner: string = ''): string => {
    if (Array.isArray(txt)) {
        return txt.join(joiner);
    }
    return txt ?? '';
};

const renderPdf = (h: CreateElement): VNode => (
    <span>
        <b>CodeGrade doesn't support PDF output for IPython notebooks at this time</b>
    </span>
);

const renderLatex = (h: CreateElement, data: string): VNode => (
    // This is not totally correct, but I can't think of a better easy solution
    // for the moment.
    <InnerMarkdownViewer markdown={data} showCodeWhitespace={false} />
);

const renderConsole = (h: CreateElement, text: string): VNode => <AnsiColoredText text={text} />;

const renderMimeType = (
    h: CreateElement,
    mimebundle: IPythonMimeData,
    showCodeWhitespace: boolean,
): VNode => {
    if (mimebundle.data) {
        for (const typ of IPythonV4MimeDataString) {
            const rawData = mimebundle.data[typ];
            if (rawData == null) {
                // eslint-disable-next-line no-continue
                continue;
            }

            const data = maybeJoin(rawData);
            switch (typ) {
                case 'text/latex':
                    return renderLatex(h, data);
                case 'text/markdown':
                    return (
                        <InnerMarkdownViewer
                            markdown={data}
                            showCodeWhitespace={showCodeWhitespace}
                        />
                    );
                case 'image/png':
                case 'image/jpeg':
                case 'image/gif': {
                    return <img src={`data:${typ};base64,${data}`} />;
                }
                case 'application/pdf':
                    return renderPdf(h);
                case 'text/plain':
                    return renderConsole(h, data);
                default:
                    AssertionError.typeAssert<never>(typ);
            }
        }
    } else {
        for (const typ of IPythonV3MimeDataString) {
            const rawData = mimebundle[typ];
            if (rawData == null) {
                // eslint-disable-next-line no-continue
                continue;
            }

            const data = maybeJoin(rawData);
            switch (typ) {
                case 'latex':
                    return renderLatex(h, data);
                case 'markdown':
                    return (
                        <InnerMarkdownViewer
                            markdown={data}
                            showCodeWhitespace={showCodeWhitespace}
                        />
                    );
                case 'png':
                case 'jpeg':
                case 'gif': {
                    return <img src={`data:image/${typ};base64,${data}`} />;
                }
                case 'pdf':
                    return renderPdf(h);
                case 'text':
                    return renderConsole(h, data);
                default:
                    AssertionError.typeAssert<never>(typ);
            }
        }
    }

    return (
        <span>
            <b style="color: red;">Unrecognized output.</b>
        </span>
    );
};

const renderExecuteResult = (
    h: CreateElement,
    cell: IPythonExecuteResultOuput,
    showCodeWhitespace: boolean,
) => renderMimeType(h, cell, showCodeWhitespace);

const renderDisplayData = (
    h: CreateElement,
    cell: IPythonDisplayDataOutput,
    showCodeWhitespace: boolean,
) => renderMimeType(h, cell, showCodeWhitespace);

export default tsx.component({
    name: 'inner-ipython-output-cell',
    functional: true,

    props: {
        cell: p.ofType<CGIPythonCodeCellOutput>().required,
        showCodeWhitespace: p(Boolean).required,
    },

    render(h, ctx): VNode {
        const { cell, showCodeWhitespace } = ctx.props;
        switch (cell.output_type) {
            case 'stream': {
                return renderConsole(h, maybeJoin(cell.text));
            }
            case 'pyout':
            case 'execute_result': {
                return renderExecuteResult(h, cell, showCodeWhitespace);
            }
            case 'pyerr':
            case 'error': {
                return renderConsole(h, maybeJoin(cell.traceback, '\n'));
            }
            case 'display_data': {
                return renderDisplayData(h, cell, showCodeWhitespace);
            }
            default:
                AssertionError.typeAssert<never>(cell);
                return (
                    <span style="color: red;" class="pt-1">
                        <b>Unknown output type:</b>
                        {(cell as any).output_type}
                    </span>
                );
        }
    },
});
