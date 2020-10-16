/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';
import * as stat from 'simple-statistics';

import { keys } from 'ts-transformer-keys';

import {
    flat1,
    hasAttr,
    fromEntries,
    getProps,
    deepEquals,
    mapObject,
    forEachObject,
    filterObject,
    readableFormatDate,
    unzip2,
    AssertionError,
    mapFilterObject,
    filterMap,
    Maybe,
    parseOrKeepFloat,
    mapToObject,
    nonenumerable,
} from '@/utils/typed';
import { makeCache } from '@/utils/cache';
import { defaultdict } from '@/utils/defaultdict';
import { NONEXISTENT } from '@/constants';
import { AssignmentsStore } from '@/store';

import { Assignment, Rubric, RubricItem, RubricRow, AnyUser, User } from '@/models';

function numOrNull(x: number): number | null {
    return Number.isNaN(x) ? null : x;
}

function averages(xs: number[]) {
    if (xs.length < 1) {
        return null;
    }

    return {
        mean: stat.mean(xs),
        median: stat.median(xs),
        mode: stat.mode(xs),
        stdev: xs.length < 2 ? 0 : stat.sampleStandardDeviation(xs),
    };
}

interface DataSourceValue {
    name: string;
    data: {
        [submissionId: number]: Object;
    };
}

export class DataSource<T extends DataSourceValue> {
    static sourceName = '__base_data_source';

    protected data: Readonly<T['data']>;

    private workspace: Workspace;

    static fromServerData<Y extends DataSourceValue>(dataSource: Y, workspace: Workspace) {
        if (dataSource.name !== this.sourceName) {
            throw new TypeError('Invalid DataSource type');
        }
        if (!hasAttr(dataSource, 'data')) {
            throw new TypeError('Data source without data');
        }
        return new this(dataSource.data, workspace);
    }

    constructor(data: T['data'], workspace: Workspace) {
        if (this.constructor === DataSource) {
            throw new TypeError('DataSource should not be instantiated directly');
        }
        this.data = Object.freeze(data);
        this.workspace = workspace;
    }

    get assignment(): Assignment | undefined | null {
        return getProps(this.workspace, null, 'assignment');
    }

    filter(subIds: Set<number>): this {
        const data = filterObject(this.data, (_, id) => subIds.has(parseInt(id, 10)));
        return new (this.constructor as any)(data, this.workspace);
    }
}

type RubricDataSourceInnerValue = {
    points: number;
    multiplier: number;
    // eslint-disable-next-line camelcase
    item_id: number;
};
type RubricDataSourceValue = {
    name: 'rubric_data';
    data: {
        [submissionId: number]: RubricDataSourceInnerValue[];
    };
};

export class RubricSource extends DataSource<RubricDataSourceValue> {
    static readonly sourceName = 'rubric_data';

    @nonenumerable
    private readonly _cache = makeCache(
        'rubricItems',
        'rubricRowPerItem',
        'itemsPerCat',
        'meanPerCat',
        'stdevPerCat',
        'modePerCat',
        'medianPerCat',
        'nTimesFilledPerCat',
        'scorePerCatPerSubmission',
        'totalScorePerSubmission',
        'scorePerSubmissionPerCat',
        'ritItemsPerCat',
        'rirItemsPerCat',
        'ritPerCat',
        'rirPerCat',
    );

    constructor(data: RubricDataSourceValue['data'], workspace: Workspace) {
        super(data, workspace);

        // eslint-disable-next-line
        AssertionError.assert(!!this.rubric);

        this.updateItemPoints();

        Object.freeze(this);
    }

    updateItemPoints() {
        Object.values(this.data).forEach(items => {
            items.forEach(item => {
                if (!hasAttr(item, 'points')) {
                    const rubricItem = this.rubricItems[item.item_id];
                    item.points = item.multiplier * (rubricItem.points as number);
                    Object.freeze(item);
                }
            });
            Object.freeze(items);
        });
    }

    get rubric(): Rubric<number> {
        const rubric = this.assignment?.rubric;
        AssertionError.assert(
            rubric != null && rubric !== NONEXISTENT,
            'This assignment does not have a rubric',
        );
        return rubric;
    }

    get rowIds(): ReadonlyArray<number> {
        return this.rubric.rows.map(row => row.id);
    }

    get labels() {
        return this.rubric.rows.map(row => row.header);
    }

    get rubricItems() {
        return this._cache.get('rubricItems', () =>
            this.rubric.rows.reduce((acc: Record<string, RubricItem>, row) => {
                row.items.forEach(item => {
                    acc[item.id] = item;
                });
                return acc;
            }, {}),
        );
    }

    get rubricRowPerItem() {
        return this._cache.get('rubricRowPerItem', () =>
            this.rubric.rows.reduce((acc: Record<number, RubricRow<number>>, row) => {
                row.items.forEach(item => {
                    acc[item.id] = row;
                });
                return acc;
            }, {}),
        );
    }

    get itemsPerCat() {
        return this._cache.get('itemsPerCat', () => {
            const rowPerItem = this.rubricRowPerItem;
            return Object.values(this.data).reduce(
                (acc: Record<number, RubricDataSourceInnerValue[]>, items) => {
                    items.forEach(item => {
                        const rowId = rowPerItem[item.item_id].id;
                        acc[rowId].push(item);
                    });
                    return acc;
                },
                fromEntries(this.rowIds.map(id => [id, []])),
            );
        });
    }

    get nTimesFilledPerCat() {
        return this._cache.get('nTimesFilledPerCat', () =>
            mapObject(this.itemsPerCat, items => items.length),
        );
    }

    get meanPerCat() {
        return this._cache.get('meanPerCat', () =>
            mapObject(this.itemsPerCat, items => {
                if (items.length === 0) {
                    return null;
                } else {
                    const points = items.map(item => item.points);
                    const mean = stat.mean(points);
                    return numOrNull(mean);
                }
            }),
        );
    }

    get stdevPerCat() {
        return this._cache.get('stdevPerCat', () =>
            mapObject(this.itemsPerCat, items => {
                if (items.length < 1) {
                    return null;
                } else if (items.length === 1) {
                    return 0;
                } else {
                    const points = items.map(item => item.points);
                    const stdev = stat.sampleStandardDeviation(points);
                    return numOrNull(stdev);
                }
            }),
        );
    }

    get modePerCat() {
        return this._cache.get('modePerCat', () =>
            mapObject(this.itemsPerCat, items => {
                if (items.length === 0) {
                    return null;
                } else {
                    const mode = stat.mode(items.map(item => item.points));
                    return numOrNull(mode);
                }
            }),
        );
    }

    get medianPerCat() {
        return this._cache.get('medianPerCat', () =>
            mapObject(this.itemsPerCat, items => {
                if (items.length === 0) {
                    return null;
                } else {
                    const median = stat.median(items.map(item => item.points));
                    return numOrNull(median);
                }
            }),
        );
    }

    get scorePerCatPerSubmission() {
        return this._cache.get('scorePerCatPerSubmission', () => {
            const rowPerItem = this.rubricRowPerItem;
            return mapObject(this.data, items =>
                items.reduce((acc: Record<string, number>, item) => {
                    const rowId = rowPerItem[item.item_id].id;
                    acc[rowId] = item.points;
                    return acc;
                }, {}),
            );
        });
    }

    get totalScorePerSubmission() {
        return this._cache.get('totalScorePerSubmission', () =>
            mapFilterObject(this.scorePerCatPerSubmission, scorePerCat => {
                const score = stat.sum(Object.values(scorePerCat));
                // TODO: Figure out why score can sometimes be a `NaN` here.
                return Maybe.fromNullable(numOrNull(score));
            }),
        );
    }

    get ritItemsPerCat() {
        return this._cache.get('ritItemsPerCat', () => {
            const scoresPerSub = this.scorePerCatPerSubmission;
            const totalsPerSub = this.totalScorePerSubmission;

            return Object.entries(scoresPerSub).reduce(
                (acc: Record<string, [number, number][]>, [subId, scores]) => {
                    Object.entries(scores).forEach(([rowId, score]) => {
                        if (hasAttr(totalsPerSub, subId)) {
                            acc[rowId].push([score, totalsPerSub[subId]]);
                        }
                    });
                    return acc;
                },
                fromEntries(this.rowIds.map(id => [id, []])),
            );
        });
    }

    get rirItemsPerCat() {
        return this._cache.get('rirItemsPerCat', () =>
            mapObject(this.ritItemsPerCat, ritItems =>
                ritItems.map(([score, total]) => <const>[score, total - score]),
            ),
        );
    }

    get ritPerCat() {
        return this._cache.get('ritPerCat', () =>
            mapObject(this.ritItemsPerCat, zipped => {
                if (zipped.length < 2) {
                    return null;
                }
                const rit = stat.sampleCorrelation(...unzip2(zipped));
                return numOrNull(rit);
            }),
        );
    }

    get rirPerCat() {
        return this._cache.get('rirPerCat', () =>
            mapObject(this.rirItemsPerCat, zipped => {
                if (zipped.length < 2) {
                    return null;
                }
                const rir = stat.sampleCorrelation(...unzip2(zipped));
                return numOrNull(rir);
            }),
        );
    }
}

type InlineFeedbackDataSourceValue = {
    name: 'inline_feedback';
    data: {
        [submission: number]: {
            // eslint-disable-next-line camelcase
            total_amount: number;
        };
    };
};

export class InlineFeedbackSource extends DataSource<InlineFeedbackDataSourceValue> {
    static readonly sourceName = 'inline_feedback';

    @nonenumerable
    private readonly _cache = makeCache('entryStats', 'entriesStdev');

    constructor(data: InlineFeedbackDataSourceValue['data'], workspace: Workspace) {
        super(data, workspace);
        Object.freeze(this);
    }

    get entryStats() {
        return this._cache.get('entryStats', () => {
            const allEntries = Object.values(this.data);
            return averages(allEntries.map(x => x.total_amount));
        });
    }
}

type AnyDataSourceValue = RubricDataSourceValue | InlineFeedbackDataSourceValue;

const PossibleDataSources = <const>{
    [RubricSource.sourceName]: RubricSource,
    [InlineFeedbackSource.sourceName]: InlineFeedbackSource,
};
type PossibleDataSourceName = keyof typeof PossibleDataSources;

type PossibleDataSourcesMapping = {
    [key in PossibleDataSourceName]: InstanceType<typeof PossibleDataSources[key]>;
};

function createDataSource<T extends AnyDataSourceValue>(
    data: T,
    workspace: Workspace,
): PossibleDataSourcesMapping[T['name']] {
    if (!hasAttr(PossibleDataSources, data.name)) {
        throw new TypeError('Invalid DataSource');
    }
    // @ts-ignore
    return PossibleDataSources[data.name].fromServerData(data, workspace);
}

interface WorkspaceSubmissionServerData {
    id: number;

    // eslint-disable-next-line camelcase
    created_at: string;

    // eslint-disable-next-line camelcase
    assignee_id: number | undefined;

    grade: number | undefined;
}

interface IWorkspaceSubmission extends WorkspaceSubmissionServerData {
    createdAt: moment.Moment;
}

export interface WorkspaceSubmission extends IWorkspaceSubmission {}

export class WorkspaceSubmission {
    readonly tag = 'workspace_submission';

    static fromServerData(data: WorkspaceSubmissionServerData) {
        const props: IWorkspaceSubmission = {
            id: data.id,
            created_at: data.created_at,
            assignee_id: data.assignee_id,
            grade: data.grade,
            createdAt: moment.utc(data.created_at, moment.ISO_8601),
        };

        return new WorkspaceSubmission(props);
    }

    constructor(props: IWorkspaceSubmission) {
        Object.assign(this, props);
        Object.freeze(this);
    }

    satisfies(filter: WorkspaceFilter) {
        const { minGrade, maxGrade, submittedAfter, submittedBefore, assignees } = filter;

        return (
            this.satisfiesGrade(minGrade, maxGrade) &&
            this.satisfiesDate(submittedAfter, submittedBefore) &&
            this.satisfiesAssignees(assignees)
        );
    }

    satisfiesGrade(minGrade: number | null, maxGrade: number | null) {
        // We do not want a submission to be in both filter A and
        // filter B if A has maxGrade=6 and B has minGrade=6, so we
        // need to check exclusively at one end. However, we need to be
        // inclusive at either 0 or the max grade for this assignment,
        // because otherwise we would drop some submissions. I chose
        // to be inclusive at the minGrade bound and exclusive at the
        // maxGrade bound because that feels more intuitive. This means
        // that a maxGrade of 9 will not contain submissions graded
        // exactly 9, but that a maxGrade of 10 _will_ include
        // submissions graded exactly 10.

        if (this.grade == null) {
            // If grade is `null` we don't want to include it if we filter on
            // `minGrade` or `maxGrade``. In the future we probably want an
            // extra option that allows users to manually filter out submissions
            // without a grade.
            return minGrade == null && maxGrade == null;
        }

        if (minGrade != null && this.grade < minGrade) {
            return false;
        }
        if (maxGrade != null) {
            if (maxGrade === 10 && this.grade === 10) {
                return true;
            }
            if (this.grade >= maxGrade) {
                return false;
            }
        }
        return true;
    }

    satisfiesDate(submittedAfter: moment.Moment | null, submittedBefore: moment.Moment | null) {
        // Same as with the grade, but we do not have a maximum value to check for.

        if (submittedAfter != null && this.createdAt.isBefore(submittedAfter)) {
            return false;
        }
        if (submittedBefore != null && !this.createdAt.isBefore(submittedBefore)) {
            return false;
        }
        return true;
    }

    satisfiesAssignees(assignees: readonly AnyUser[]) {
        if (assignees.length > 0) {
            return assignees.some(a => a.id === this.assignee_id);
        }
        return true;
    }
}

type WorkspaceSubmissionSetServerData = Record<number, readonly WorkspaceSubmissionServerData[]>;

export class WorkspaceSubmissionSet {
    static fromServerData(data: WorkspaceSubmissionSetServerData) {
        const subs = mapObject(data, ss => ss.map(WorkspaceSubmission.fromServerData));
        return new WorkspaceSubmissionSet(subs);
    }

    @nonenumerable
    private readonly _cache = makeCache(
        'allSubmissions',
        'firstSubmission',
        'lastSubmission',
        'gradeStats',
        'submissionStats',
        'submissionsPerStudent',
        'submissionIds',
        'assigneeIds',
    );

    constructor(
        public readonly submissions: { [userId: number]: ReadonlyArray<WorkspaceSubmission> },
    ) {
        forEachObject(this.submissions, sub => Object.freeze(sub));
        Object.freeze(this.submissions);
        Object.freeze(this);
    }

    get allSubmissions() {
        return this._cache.get('allSubmissions', () => flat1(Object.values(this.submissions)));
    }

    get firstSubmissionDate() {
        return this._cache.get('firstSubmission', () =>
            this.allSubmissions.reduce((first: null | moment.Moment, sub) => {
                if (first == null || first.isAfter(sub.createdAt)) {
                    return sub.createdAt;
                } else {
                    return first;
                }
            }, null),
        );
    }

    get lastSubmissionDate() {
        return this._cache.get('lastSubmission', () =>
            this.allSubmissions.reduce((last: null | moment.Moment, sub) => {
                if (last == null || last.isBefore(sub.createdAt)) {
                    return sub.createdAt;
                } else {
                    return last;
                }
            }, null),
        );
    }

    get submissionIds() {
        return this._cache.get('submissionIds', () => new Set(this.allSubmissions.map(s => s.id)));
    }

    get assigneeIds() {
        return this._cache.get('assigneeIds', () =>
            this.allSubmissions.reduce((acc, sub) => {
                if (sub.assignee_id != null) {
                    acc.add(sub.assignee_id);
                }
                return acc;
            }, new Set()),
        );
    }

    binSubmissionsBy<K extends string | number>(
        f: (sub: WorkspaceSubmission) => K | null,
    ): Record<K, WorkspaceSubmission[]> {
        return this.allSubmissions.reduce<Record<K, WorkspaceSubmission[]>>(
            (acc: Record<K, WorkspaceSubmission[]>, sub: WorkspaceSubmission) => {
                const bin = f(sub);
                if (bin != null) {
                    acc[bin].push(sub);
                }
                return acc;
            },
            defaultdict(() => []),
        );
    }

    binSubmissionsByGrade(binSize = 1, maxGrade = 10) {
        return this.binSubmissionsBy(sub => {
            const { grade } = sub;
            if (grade == null) {
                return null;
            }

            // If the grade is greater than or equal to the max grade (it
            // should only really be possible for it to be equal), we need to
            // adjust it to be placed a bin earlier because there is no
            // separate bin for the maximum grade only.
            if (grade >= maxGrade) {
                const frac = maxGrade / binSize;
                const nbins = Math.ceil(frac);
                const bin = Math.floor(frac);
                return Math.min(bin, nbins - 1);
            }

            return Math.floor(grade / binSize);
        });
    }

    binSubmissionsByDate(
        range: readonly moment.Moment[],
        binSize: number,
        binUnit: moment.DurationInputArg2,
    ) {
        const [start, end] = WorkspaceSubmissionSet.getDateRange(range);
        const binStep = moment.duration(binSize, binUnit).asMilliseconds();

        if (binStep === 0) {
            return {};
        }

        const getBin = (d: moment.Moment) => {
            // We use unix timestamp for binning. Each bin starts at an integer
            // multiple of the bin size.
            // Correction term for the timezone offset.
            // utcOffset() is in seconds but we need milliseconds.
            const off = 60 * 1000 * d.utcOffset();
            return Math.floor((d.valueOf() + off) / binStep);
        };

        const binned = this.binSubmissionsBy(sub => {
            const { createdAt } = sub;

            if (
                (start != null && start.isAfter(createdAt)) ||
                (end !== null && end.isBefore(createdAt))
            ) {
                return null;
            }

            return getBin(createdAt);
        });

        const binKeys = Object.keys(binned).map(parseFloat);
        if (binKeys.length === 0) {
            return {};
        }

        const first = start == null ? stat.min(binKeys) : getBin(start);
        const last = end == null ? stat.max(binKeys) : getBin(end);

        const result: Record<
            number,
            {
                start: number;
                end: number;
                data: WorkspaceSubmission[];
            }
        > = {};

        for (let i = first; i <= last; i++) {
            const binStart = i * binStep;
            result[binStart] = {
                start: binStart,
                end: binStart + binStep - 1,
                data: binned[i],
            };
        }

        return result;
    }

    static getDateRange(range: readonly moment.Moment[]) {
        let start;
        let end;

        if (range.length === 0) {
            return [null, null];
        } else {
            [start, end] = range.map(d => moment(d));
        }

        if (end == null) {
            end = start.clone();
        }

        return [
            start
                .local()
                .hours(0)
                .minutes(0)
                .seconds(0)
                .milliseconds(0),
            end
                .local()
                .hours(23)
                .minutes(59)
                .seconds(59)
                .milliseconds(999),
        ];
    }

    get submissionCount() {
        return this.allSubmissions.length;
    }

    get studentCount() {
        return Object.keys(this.submissions).length;
    }

    get gradeStats() {
        return this._cache.get('gradeStats', () => {
            const grades = filterMap(this.allSubmissions, sub => Maybe.fromNullable(sub.grade));
            return averages(grades);
        });
    }

    get submissionStats() {
        return this._cache.get('submissionStats', () => {
            const subsPerStudent = Object.values(this.submissions)
                .filter(s => s.length > 0)
                .map(s => s.length);
            return averages(subsPerStudent);
        });
    }

    get submissionsPerStudent() {
        return this._cache.get('submissionsPerStudent', () => {
            const subsPerStudent = Object.values(this.submissions)
                .filter(s => s.length > 0)
                .map(s => s.length);
            return subsPerStudent.reduce(
                (acc: Record<number, number>, nSubs) => {
                    // XXX: This can probably be replaced with "acc[nSubs]++;"
                    // but I got a lot of errors, and at the time I thought they
                    // were related to that line. I don't get them anymore when
                    // using that expression, though... Needs further investigation!
                    const amt = acc[nSubs];
                    acc[nSubs] = amt + 1;
                    return acc;
                },
                defaultdict(() => 0),
            );
        });
    }

    filter(filter: WorkspaceFilter) {
        let filtered = filter.onlyLatestSubs ? this.getLatestSubmissions() : this.submissions;

        filtered = mapObject(filtered, subs => subs.filter(s => s.satisfies(filter)));

        filtered = filterObject(filtered, subs => subs.length > 0);

        return new WorkspaceSubmissionSet(filtered);
    }

    getLatestSubmissions() {
        return mapObject(this.submissions, subs => {
            const [first, ...rest] = subs;
            const latest = rest.reduce((a, b) => (a.createdAt.isAfter(b.createdAt) ? a : b), first);
            return latest == null ? [] : [latest];
        });
    }
}
type IWorkspaceFilterInput = {
    onlyLatestSubs?: boolean;
    minGrade?: null | number | string;
    maxGrade?: null | number | string;
    submittedAfter?: null | moment.Moment | string;
    submittedBefore?: null | moment.Moment | string;
    assignees?: ReadonlyArray<number | AnyUser>;
};

const WORKSPACE_FILTER_DEFAULT_PROPS: Required<IWorkspaceFilterInput> = {
    onlyLatestSubs: true,
    minGrade: null,
    maxGrade: null,
    submittedAfter: null,
    submittedBefore: null,
    assignees: <readonly AnyUser[]>[],
};

type IWorkspaceFilter = {
    onlyLatestSubs: boolean;
    minGrade: null | number;
    maxGrade: null | number;
    submittedAfter: null | moment.Moment;
    submittedBefore: null | moment.Moment;
    assignees: ReadonlyArray<AnyUser>;
};

export interface WorkspaceFilter extends IWorkspaceFilter {}

export class WorkspaceFilter {
    @nonenumerable
    private readonly _cache = makeCache('string');

    constructor(props: IWorkspaceFilterInput | IWorkspaceFilter) {
        // First check that the given ``props`` object doesn't contain extra
        // keys.
        Object.keys(props).forEach(key => {
            if (!hasAttr(WORKSPACE_FILTER_DEFAULT_PROPS, key)) {
                throw new Error(`Invalid filter: ${key}`);
            }
        });

        const maybeFloat = (x?: string | number | null) => {
            const f = parseOrKeepFloat(x);
            return Number.isNaN(f) ? null : f;
        };

        const maybeMoment = (x?: moment.Moment | null | string): moment.Moment | null => {
            if (x == null) {
                return null;
            }
            const m = moment.utc(x, moment.ISO_8601);
            return m.isValid() ? m : null;
        };

        // Now go over
        keys<IWorkspaceFilter>().forEach(key => {
            if (hasAttr(props, key)) {
                switch (key) {
                    case 'minGrade':
                    case 'maxGrade':
                        this[key] = maybeFloat(props[key]);
                        break;
                    case 'submittedAfter':
                    case 'submittedBefore':
                        this[key] = maybeMoment(props[key]);
                        break;
                    case 'assignees':
                        this[key] = (props[key] ?? []).map((assignee: number | AnyUser) => {
                            if (typeof assignee === 'number') {
                                const user = User.findUserById(assignee);
                                AssertionError.assert(
                                    user != null,
                                    'The specified assignee was not found',
                                );
                                return user;
                            }
                            return assignee;
                        });
                        break;
                    default:
                        this[key] = props[key] ?? true;
                }
            } else {
                const defaultValue = WORKSPACE_FILTER_DEFAULT_PROPS[key];
                this[key] = defaultValue;
            }
        });

        Object.freeze(this);
    }

    static get emptyFilter() {
        return new WorkspaceFilter(WORKSPACE_FILTER_DEFAULT_PROPS);
    }

    update<T extends keyof IWorkspaceFilter>(key: T, value: IWorkspaceFilter[T]) {
        return new WorkspaceFilter(Object.assign({}, this, { [key]: value }));
    }

    split(props: {
        grade?: number | string;
        latest: boolean;
        assignees?: AnyUser[];
        date?: null | moment.Moment | string;
    }) {
        const { minGrade, maxGrade, submittedAfter, submittedBefore } = this;

        const { latest, assignees } = props;
        const grade = parseOrKeepFloat(props.grade);
        // moment(undefined) gives a valid moment, so we must convert it to
        // null first.
        const date = props.date == null ? moment.invalid() : moment(props.date);

        let result: readonly WorkspaceFilter[] = [this];

        if (!Number.isNaN(grade)) {
            if (minGrade != null && minGrade >= grade) {
                throw new Error('Selected grade is less than or equal to the old "Min grade".');
            }
            if (maxGrade != null && maxGrade <= grade) {
                throw new Error('Selected grade is greater than or equal to the old "Min grade".');
            }
            result = flat1(
                result.map(f => [f.update('maxGrade', grade), f.update('minGrade', grade)]),
            );
        }

        if (date.isValid()) {
            if (submittedAfter != null && !submittedAfter.isBefore(date)) {
                throw new Error('Selected date is before the old "Submitted after".');
            }
            if (submittedBefore != null && !submittedBefore.isAfter(date)) {
                throw new Error('Selected date is after the old "Submitted before".');
            }
            result = flat1(
                result.map(f => [
                    f.update('submittedBefore', date),
                    f.update('submittedAfter', date),
                ]),
            );
        }

        if (latest) {
            result = flat1(
                result.map(f => [
                    f.update('onlyLatestSubs', false),
                    f.update('onlyLatestSubs', true),
                ]),
            );
        }

        if (assignees != null && assignees.length > 0) {
            result = flat1(assignees.map(a => result.map(f => f.update('assignees', [a]))));
        }

        return result;
    }

    toString() {
        return this._cache.get('string', () => {
            const parts = [];

            if (this.onlyLatestSubs) {
                parts.push('Latest');
            } else {
                parts.push('All');
            }

            if (this.minGrade != null && this.maxGrade != null) {
                parts.push(`${this.minGrade} <= Grade < ${this.maxGrade}`);
            } else if (this.minGrade != null) {
                parts.push(`Grade >= ${this.minGrade}`);
            } else if (this.maxGrade != null) {
                parts.push(`Grade < ${this.maxGrade}`);
            }

            if (this.submittedAfter != null) {
                parts.push(`After ${readableFormatDate(this.submittedAfter)}`);
            }

            if (this.submittedBefore != null) {
                parts.push(`Before ${readableFormatDate(this.submittedBefore)}`);
            }

            parts.push(...this.assignees.map(a => a.name));

            return parts.join(', ');
        });
    }

    serialize() {
        const defaults = WorkspaceFilter.emptyFilter;

        return keys<IWorkspaceFilter>().reduce((acc: Partial<IWorkspaceFilterInput>, key) => {
            if (deepEquals(this[key], defaults[key])) {
                return acc;
            }
            if (key === 'submittedAfter' || key === 'submittedBefore') {
                const val = this[key];
                if (val != null) {
                    acc[key] = val.toISOString();
                }
            } else if (key === 'assignees') {
                const val = this[key];
                if (val != null) {
                    acc[key] = val.map(a => a.id);
                }
            } else {
                // @ts-ignore
                acc[key] = this[key];
            }
            return acc;
        }, {});
    }

    static deserialize(data: IWorkspaceFilterInput) {
        return new WorkspaceFilter(data);
    }
}

export class WorkspaceFilterResult {
    public readonly submissions: WorkspaceSubmissionSet;

    private readonly dataSources: Partial<PossibleDataSourcesMapping>;

    constructor(public workspace: Workspace, public filter: WorkspaceFilter) {
        this.submissions = workspace.submissions.filter(filter);

        const subIds = this.submissions.submissionIds;
        this.dataSources = Object.freeze(
            mapObject(workspace.dataSources, ds => ds?.filter(subIds)),
        );

        Object.freeze(this);
    }

    get assignment(): Assignment | undefined {
        return this.workspace.assignment;
    }

    getSource<T extends PossibleDataSourceName>(sourceName: T) {
        return this.dataSources[sourceName];
    }
}

interface WorkspaceServerData {
    id: number;
    // eslint-disable-next-line camelcase
    assignment_id: number;
    // eslint-disable-next-line camelcase
    data_sources: PossibleDataSourceName[];
    // eslint-disable-next-line camelcase
    student_submissions: WorkspaceSubmissionSetServerData;
}

const WORKSPACE_SERVER_DATA_TO_COPY: ReadonlyArray<'id' | 'assignment_id'> = Object.freeze([
    'id',
    'assignment_id',
]);

interface WorkspaceProps {
    id: number;
    // eslint-disable-next-line camelcase
    assignment_id: number;
    submissions: WorkspaceSubmissionSet;
}

interface IWorkspace extends WorkspaceProps {
    dataSources: Partial<PossibleDataSourcesMapping>;
}

export interface Workspace extends IWorkspace {}

export class Workspace {
    static fromServerData(workspace: WorkspaceServerData, sources: (AnyDataSourceValue | null)[]) {
        const props: WorkspaceProps = mapToObject(
            WORKSPACE_SERVER_DATA_TO_COPY,
            prop => [prop, workspace[prop]],
            {
                id: -1,
                assignment_id: -1,
                submissions: WorkspaceSubmissionSet.fromServerData(workspace.student_submissions),
            },
        );

        const self = new Workspace(props);
        const dataSources: Partial<PossibleDataSourcesMapping> = mapToObject(
            workspace.data_sources,
            (srcName, i) => {
                const source = sources[i];
                if (source == null || source.name !== srcName) {
                    throw new Error(`Did not receive data for source: ${srcName}`);
                }
                if (!hasAttr(PossibleDataSources, srcName)) {
                    throw new TypeError('Invalid DataSource');
                }

                return [srcName, createDataSource(source, self)];
            },
        );
        // eslint-disable-next-line no-underscore-dangle
        self._setSources(dataSources);

        return self;
    }

    constructor(props: WorkspaceProps, sources: PossibleDataSourcesMapping | null = null) {
        Object.assign(this, props);
        this.dataSources = {};
        Object.freeze(this);

        if (sources != null) {
            this._setSources(sources);
        }
    }

    _setSources(dataSources: Partial<PossibleDataSourcesMapping>) {
        Object.assign(this.dataSources, dataSources);
        Object.freeze(this.dataSources);
    }

    hasSource(sourceName: PossibleDataSourceName) {
        return hasAttr(this.dataSources, sourceName);
    }

    getSource<T extends PossibleDataSourceName>(sourceName: T) {
        return this.dataSources[sourceName];
    }

    get assignment(): Assignment | undefined {
        return AssignmentsStore.getAssignment()(this.assignment_id).extract();
    }

    filter(filters: readonly WorkspaceFilter[]) {
        return filters.map(filter => new WorkspaceFilterResult(this, filter));
    }
}
