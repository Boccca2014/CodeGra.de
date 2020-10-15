interface SearchOptions {
    // TODO: More options? Regex searching? Accept if an object matches some
    // terms but not all?
    caseInsensitive: boolean;
}

interface SearchTerm<K> {
    // Keys to search on.
    keys: ReadonlyArray<K>;
    // Search query.
    q: string;
}

// Type that defines an object that contains all keys in K, where K is
// a distinct union over strings, and requires the values of those keys to be
// of type string. Other keys are allowed and can be of any type.
type SearchRecord<K extends string> = Record<K, string> & Record<string, any>;

export class Search<K extends string> {
    private static defaultOptions: SearchOptions = {
        caseInsensitive: true,
    };

    private options: SearchOptions;

    constructor(private keys: ReadonlyArray<K>, options?: Partial<SearchOptions>) {
        this.options = Object.assign({}, Search.defaultOptions, options);
    }

    search<R extends SearchRecord<K>>(query: string, items: ReadonlyArray<R>): R[] {
        // TODO: More intelligent splitting of terms. Allow quoting to
        // represent a term containing whitespace? Search all keys except one/a
        // few?
        const terms = query
            .split(/\s+/)
            .filter(x => x)
            .map(t => this.makeTerm(t));

        return items.filter(item =>
            terms.every(term =>
                term.keys.some(key => {
                    const val = this.prepareTerm(String(item[key] ?? ''));
                    return val.indexOf(term.q) !== -1;
                }),
            ),
        );
    }

    private makeTerm(query: string): SearchTerm<K> {
        const colon = query.indexOf(':');
        if (colon !== -1) {
            // We get the key in this roundabout way to make typescript happy,
            // because this way it can infer that the key is actually one of
            // the searcher's allowed keys.
            const sliced = query.slice(0, colon);
            const key = this.keys.find(k => k === sliced);

            if (key != null) {
                return {
                    keys: [key],
                    q: this.prepareTerm(query.slice(colon + 1)),
                };
            }
        }

        return {
            keys: this.keys,
            q: this.prepareTerm(query),
        };
    }

    private prepareTerm(str: string): string {
        if (this.options.caseInsensitive) {
            return str.toLocaleLowerCase();
        } else {
            return str;
        }
    }
}
