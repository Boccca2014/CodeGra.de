import { getProps, sortBy, withSentry, AssertionError, Just, Nothing } from '@/utils';
import decodeBuffer from '@/utils/decode';
import { Maybe } from 'purify-ts/Maybe';

function mapHTMLCollection<T>(
    collection: HTMLCollection,
    mapper: (node: Element, index: number) => T,
): T[] {
    return Array.from(collection, mapper);
}

function getAttribute<Y extends string | number>(
    node: Element,
    name: string,
    dflt: Y | null = null,
): string | Y {
    const attr = node.getAttribute(name);
    if (dflt == null) {
        AssertionError.assert(attr != null, `Attribute ${name} not found in ${node.outerHTML}`);
        return attr;
    } else {
        return attr ?? dflt;
    }
}

const fontAwesomeIconMap = <const>{
    success: { icon: 'check', cls: 'text-success' },
    failure: { icon: 'times', cls: 'text-danger' },
    skipped: { icon: 'ban', cls: 'text-muted' },
    error: { icon: 'exclamation', cls: 'text-danger' },
    unknown: { icon: 'question', cls: 'text-danger' },
};

type CGJunitCaseState = keyof typeof fontAwesomeIconMap;

function isValidState(state: string): state is CGJunitCaseState {
    return state in fontAwesomeIconMap;
}

class CGJunitCase {
    public readonly content: Maybe<ReadonlyArray<string>> = Nothing;

    public readonly stdout: Maybe<ReadonlyArray<string>> = Nothing;

    public readonly stderr: Maybe<ReadonlyArray<string>> = Nothing;

    public readonly state: CGJunitCaseState;

    public readonly message: Maybe<string> = Nothing;

    constructor(
        children: ReadonlyArray<Element>,
        public readonly name: string,
        public readonly classname: string,
        public readonly time: number,
        public readonly weight: number,
    ) {
        const getText = (node: Element) => {
            const content = node.textContent?.split('\n');
            if (content != null && content.length > 0) {
                return Just(content);
            }
            return Nothing;
        };

        let state: CGJunitCaseState | undefined;

        for (const child of children) {
            const tagName = child.tagName;
            if (isValidState(tagName)) {
                state = state ?? tagName;
                this.message = Just(getAttribute<string>(child, 'message'));
                this.content = getText(child);
            } else if (tagName === 'system-out') {
                this.stdout = getText(child);
            } else if (tagName === 'system-err') {
                this.stderr = getText(child);
            } else {
                state = state ?? 'unknown';
            }
        }
        this.state = state ?? 'success';

        Object.freeze(this);
    }

    static fromXml(node: Element) {
        const children = node.hasChildNodes() ? Array.from(node.children) : [];

        return new CGJunitCase(
            children,
            getAttribute(node, 'name'),
            getAttribute(node, 'classname'),
            parseFloat(getAttribute(node, 'time')),
            parseFloat(getAttribute(node, 'weight', '1.0')),
        );
    }

    get fontAwesomeIcon() {
        return fontAwesomeIconMap[this.state];
    }
}

class CGJunitSuite {
    public failures: number;

    public errors: number;

    public skipped: number;

    public successful: number;

    public runTests: number;

    public totalTests: number;

    constructor(public cases: CGJunitCase[], public name: string, public weight: number) {
        this.totalTests = cases.reduce((acc, c) => acc + c.weight, 0);
        this.failures = 0.0;
        this.errors = 0.0;
        this.skipped = 0.0;
        this.successful = 0.0;

        cases.forEach(c => {
            const caseWeight = c.weight;
            switch (c.state) {
                case 'failure':
                    this.failures += caseWeight;
                    break;
                case 'error':
                    this.errors += caseWeight;
                    break;
                case 'skipped':
                    this.errors += caseWeight;
                    break;
                case 'success':
                    this.successful += caseWeight;
                    break;
                default:
                    AssertionError.typeAssert<'unknown'>(c.state);
            }
        });
        this.runTests = this.totalTests - this.skipped;

        Object.freeze(this.cases);
        Object.freeze(this);
    }

    static fromXml(node: Element) {
        const suiteName: string = getAttribute(node, 'name');
        const cases = mapHTMLCollection(node.children, CGJunitCase.fromXml);
        const errors = parseInt(getAttribute(node, 'errors'), 10);
        const failures = parseInt(getAttribute(node, 'failures'), 10);
        const skipped = parseInt(getAttribute(node, 'skipped', '0'), 10);
        const tests = parseInt(getAttribute(node, 'tests'), 10);

        function countCases(state: CGJunitCaseState): number {
            return cases.reduce((acc, c) => acc + (c.state === state ? 1 : 0), 0);
        }

        AssertionError.assert(
            tests === cases.length,
            'The amount of cases does not match the found "tests" attributes',
        );
        AssertionError.assert(
            errors === countCases('error'),
            'Amount of errors does not match the found "errors" attribute',
        );
        AssertionError.assert(
            failures === countCases('failure'),
            'Amount of failures does not match the found "failures" attribute',
        );
        AssertionError.assert(
            skipped === countCases('skipped'),
            'Amount of skipped cases does not match the found "skipped" attribute',
        );

        return new CGJunitSuite(cases, suiteName, parseFloat(getAttribute(node, 'weight', '1.0')));
    }
}

export class CGJunit {
    suites: ReadonlyArray<CGJunitSuite>;

    constructor(public id: string, suites: CGJunitSuite[]) {
        this.suites = sortBy(suites, x => [x.failures <= 0]);

        Object.freeze(this.suites);
        Object.freeze(this);
    }

    static fromXml(id: string, xml: ArrayBuffer): CGJunit {
        const rootNodes = CGJunit.parseXML(xml);

        return new CGJunit(id, mapHTMLCollection(rootNodes, CGJunitSuite.fromXml));
    }

    private static parseXML(xml: ArrayBuffer): HTMLCollection {
        const xmlDoc = new DOMParser().parseFromString(decodeBuffer(xml), 'text/xml');

        CGJunit.maybeRaiseParserError(xmlDoc);

        let rootNodes = xmlDoc.children;
        if (rootNodes.length === 1 && rootNodes[0].tagName === 'testsuites') {
            rootNodes = rootNodes[0].children;
        }

        return rootNodes;
    }

    private static maybeRaiseParserError(xmlDoc: Document): void {
        // The <parsererror> element might be nested in some other elements, so
        // use querySelector to find it.
        const perr = xmlDoc.querySelector('parsererror');

        if (perr != null) {
            withSentry(Sentry => {
                Sentry.captureMessage('Could not parse as XML');
            });
            throw new Error(getProps(perr, undefined, 'textContent'));
        }
    }
}
