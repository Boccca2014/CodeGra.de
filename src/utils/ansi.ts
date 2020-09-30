// This code is largely copied from jupyter, to match their ansi rendering as
// closely as possible. The classes applied here are style in `style.less`.
import { htmlEscape } from './typed';

/* eslint no-param-reassign: 0 */

const ANSI_COLORS = <const>[
    'ansi-color-black',
    'ansi-color-red',
    'ansi-color-green',
    'ansi-color-yellow',
    'ansi-color-blue',
    'ansi-color-magenta',
    'ansi-color-cyan',
    'ansi-color-white',
    'ansi-color-black-intense',
    'ansi-color-red-intense',
    'ansi-color-green-intense',
    'ansi-color-yellow-intense',
    'ansi-color-blue-intense',
    'ansi-color-magenta-intense',
    'ansi-color-cyan-intense',
    'ansi-color-white-intense',
];

type Color = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | number[];

function pushColoredChunk(
    chunk: string,
    fg: Color,
    bg: Color,
    bold: boolean,
    underline: boolean,
    inverse: boolean,
    addOutput: (output: string) => void,
) {
    if (chunk) {
        const classes = [];
        const styles = [];

        if (bold && typeof fg === 'number' && fg >= 0 && fg < 8) {
            fg += 8; // Bold text uses 'intense' colors
        }
        if (inverse) {
            [fg, bg] = [bg, fg];
        }

        if (typeof fg === 'number') {
            classes.push(`${ANSI_COLORS[fg]}-fg`);
        } else if (fg.length) {
            styles.push(`color: rgb(${fg})`);
        } else if (inverse) {
            classes.push('ansi-color-default-inverse-fg');
        }

        if (typeof bg === 'number') {
            classes.push(`${ANSI_COLORS[bg]}-bg`);
        } else if (bg.length) {
            styles.push(`background-color: rgb(${bg})`);
        } else if (inverse) {
            classes.push('ansi-color-default-inverse-bg');
        }

        if (bold) {
            classes.push('ansi-color-bold');
        }

        if (underline) {
            classes.push('ansi-color-underline');
        }

        if (classes.length || styles.length) {
            addOutput('<span');
            if (classes.length) {
                addOutput(` class="${classes.join(' ')}"`);
            }
            if (styles.length) {
                addOutput(` style="${styles.join('; ')}"`);
            }
            addOutput('>');
            addOutput(chunk);
            addOutput('</span>');
        } else {
            addOutput(chunk);
        }
    }
}

function getExtendedColors(numbers: number[]): Color {
    const n = numbers.pop();

    if (n === 2 && numbers.length >= 3) {
        const r = numbers.pop();
        const g = numbers.pop();
        const b = numbers.pop();
        if (r == null || g == null || b == null || [r, g, b].some(c => c < 0 || c > 255)) {
            throw new RangeError('Invalid range for RGB colors');
        }
        return [r, g, b];
    } else if (n === 5 && numbers.length >= 1) {
        // 256 colors
        const idx = numbers.pop();
        if (idx == null || idx < 0) {
            throw new RangeError('Color index must be >= 0');
        } else if (idx < 16 && idx >= 0) {
            // 16 default terminal colors
            return idx as Color;
        } else if (idx < 232) {
            // 6x6x6 color cube, see https://stackoverflow.com/a/27165165/500098
            let r = Math.floor((idx - 16) / 36);
            r = r > 0 ? 55 + r * 40 : 0;
            let g = Math.floor(((idx - 16) % 36) / 6);
            g = g > 0 ? 55 + g * 40 : 0;
            let b = (idx - 16) % 6;
            b = b > 0 ? 55 + b * 40 : 0;
            return [r, g, b];
        } else if (idx < 256) {
            // grayscale, see https://stackoverflow.com/a/27165165/500098
            const g = (idx - 232) * 10 + 8;
            return [g, g, g];
        } else {
            throw new RangeError('Color index must be < 256');
        }
    } else {
        throw new RangeError('Invalid extended color specification');
    }
}

function ansispan(str: string): string {
    // eslint-disable-next-line no-control-regex
    const ansiRe = /\x1b\[(.*?)([@-~])/g;
    let fg: Color = [];
    let bg: Color = [];
    let bold = false;
    let underline = false;
    let inverse = false;
    const out: string[] = [];
    const numbers: number[] = [];
    let start = 0;

    str += '\x1b[m'; // Ensure markup for trailing text
    let match;
    // eslint-disable-next-line no-cond-assign
    while ((match = ansiRe.exec(str)) != null) {
        if (match[2] === 'm') {
            const items = match[1].split(';');
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item === '') {
                    numbers.push(0);
                } else if (item.search(/^\d+$/) !== -1) {
                    numbers.push(parseInt(item, 10));
                } else {
                    // Ignored: Invalid color specification
                    numbers.length = 0;
                    break;
                }
            }
        } else {
            // Ignored: Not a color code
        }
        const chunk = str.substring(start, match.index);
        pushColoredChunk(chunk, fg, bg, bold, underline, inverse, out.push.bind(out));
        start = ansiRe.lastIndex;

        numbers.reverse();
        while (numbers.length > 0) {
            const n = numbers.pop();
            switch (n) {
                case 0:
                    fg = [];
                    bg = fg;
                    bold = false;
                    underline = false;
                    inverse = false;
                    break;
                case 1:
                case 5:
                    bold = true;
                    break;
                case 4:
                    underline = true;
                    break;
                case 7:
                    inverse = true;
                    break;
                case 21:
                case 22:
                    bold = false;
                    break;
                case 24:
                    underline = false;
                    break;
                case 27:
                    inverse = false;
                    break;
                case 30:
                case 31:
                case 32:
                case 33:
                case 34:
                case 35:
                case 36:
                case 37:
                    fg = (n - 30) as Color;
                    break;
                case 38:
                    try {
                        fg = getExtendedColors(numbers);
                    } catch (e) {
                        numbers.length = 0;
                    }
                    break;
                case 39:
                    fg = [];
                    break;
                case 40:
                case 41:
                case 42:
                case 43:
                case 44:
                case 45:
                case 46:
                case 47:
                    bg = (n - 40) as Color;
                    break;
                case 48:
                    try {
                        bg = getExtendedColors(numbers);
                    } catch (e) {
                        numbers.length = 0;
                    }
                    break;
                case 49:
                    bg = [];
                    break;
                case 90:
                case 91:
                case 92:
                case 93:
                case 94:
                case 95:
                case 96:
                case 97:
                    fg = (n - 90 + 8) as Color;
                    break;
                case 100:
                case 101:
                case 102:
                case 103:
                case 104:
                case 105:
                case 106:
                case 107:
                    bg = (n - 100 + 8) as Color;
                    break;
                default:
                // Unknown codes are ignored
            }
        }
    }
    return out.join('');
}

// Remove chunks that should be overridden by the effect of
// carriage return characters
function fixCarriageReturn(txt: string): string {
    txt = txt.replace(/\r+\n/gm, '\n'); // \r followed by \n --> newline

    while (txt.search(/\r[^$]/g) > -1) {
        // @ts-ignore
        const base = txt.match(/^(.*)\r+/m)[1];
        // @ts-ignore
        let insert = txt.match(/\r+(.*)$/m)[1];
        insert += base.slice(insert.length, base.length);
        txt = txt.replace(/\r+.*$/m, '\r').replace(/^.*\r/m, insert);
    }

    return txt;
}

// Remove characters that are overridden by backspace characters
function fixBackspace(txt: string): string {
    let tmp = txt;
    do {
        txt = tmp;
        // Cancel out anything-but-newline followed by backspace
        // eslint-disable-next-line no-control-regex
        tmp = txt.replace(/[^\n]\x08/gm, '');
    } while (tmp.length < txt.length);

    return txt;
}

// Remove characters overridden by backspace and carriage return
function fixOverwrittenChars(txt: string): string {
    return fixCarriageReturn(fixBackspace(txt));
}

// Transform ANSI color escape codes into HTML <span> tags with CSS
// classes such as 'ansi-green-intense-fg'.
// The actual colors used are set in the CSS file.
// This is supposed to have the same behavior as nbconvert.filters.ansi2html()
export function ansiToHTML(txt: string): string {
    const cleaned = htmlEscape(fixOverwrittenChars(txt));

    // color ansi codes (and remove non-color escape sequences)
    return ansispan(cleaned);
}
