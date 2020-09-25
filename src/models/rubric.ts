// SPDX-License-Identifier: AGPL-3.0-only
import { store } from '@/store';
import {
    formatGrade,
    getProps,
    getUniqueId,
    toMaxNDecimals,
    setXor,
    hasAttr,
    filterMap,
    Maybe,
    Nothing,
    Just,
    AssertionError,
    parseOrKeepFloat,
    coerceToString,
    nonenumerable,
} from '@/utils/typed';
import { makeCache } from '@/utils/cache';
import { AutoTestRun, AutoTestResult } from '@/models';
import { RubricResultValidationError, RubricRowValidationError } from './errors';
import { Submission } from './submission';

enum RubricDescriptionType {
    'plain_text',
    'markdown',
}

const defaultDescriptionType: RubricDescriptionType = RubricDescriptionType.markdown;

interface RubricItemServerData {
    id: number;
    points: number;
    header: string;
    description: string;
}

interface IRubricItem<T> {
    id: T;

    points: T extends number ? number : number | '' | null;

    header: string;

    description: string;

    trackingId?: number;
}

export interface RubricItem<T = number | undefined> extends IRubricItem<T> {}
export class RubricItem<T = number | undefined> {
    static fromServerData(data: Required<RubricItemServerData>) {
        return new RubricItem({
            id: data.id,
            points: data.points,
            header: data.header,
            description: data.description,
            trackingId: undefined,
        });
    }

    static createEmpty(): RubricItem<undefined> {
        return new RubricItem({
            id: undefined,
            points: '',
            header: '',
            description: '',
            trackingId: getUniqueId(),
        });
    }

    constructor(item: IRubricItem<T>) {
        Object.assign(this, item);
        Object.freeze(this);
    }

    update<Y>(props: { id: Y } & Partial<IRubricItem<Y>>): RubricItem<Y>;

    update(props: Partial<IRubricItem<T>>): RubricItem<T>;

    update<Y>(props: Partial<IRubricItem<Y>> = {}): RubricItem<Y | T> {
        return new RubricItem(Object.assign({}, this, props));
    }

    get nonEmptyHeader() {
        return this.header || '[No name]';
    }
}

interface BaseRubricRowServerData {
    id: number;
    header: string;
    description: string;
    // eslint-disable-next-line camelcase
    description_type: keyof typeof RubricDescriptionType;
    locked: false | 'auto_test';
    items: RubricItemServerData[];
}

interface ContinuousRubricRowServerData extends BaseRubricRowServerData {
    // eslint-disable-next-line @typescript-eslint/no-use-before-define
    type: typeof ContinuousRubricRow.tag;
}

interface NormalRubricRowServerData extends BaseRubricRowServerData {
    // eslint-disable-next-line @typescript-eslint/no-use-before-define
    type: typeof NormalRubricRow.tag;
}

type RubricRowServerData = ContinuousRubricRowServerData | NormalRubricRowServerData;

interface IRubricRow<T, Y = T> {
    id: Y;
    // eslint-disable-next-line @typescript-eslint/no-use-before-define
    type: '' | keyof typeof RubricRowsTypes;
    header: string;
    description: string;
    descriptionType: RubricDescriptionType;
    locked: false | 'auto_test';
    items: RubricItem<T>[];
}

export interface RubricRow<T> extends IRubricRow<T> {}

export class RubricRow<T extends number | undefined | null> {
    static fromServerData(data: RubricRowServerData) {
        // eslint-disable-next-line @typescript-eslint/no-use-before-define
        if (!hasAttr(RubricRowsTypes, data.type)) {
            throw new ReferenceError(`Could not find specified type: ${data.type}`);
        }
        // eslint-disable-next-line @typescript-eslint/no-use-before-define
        const cls = RubricRowsTypes[data.type];
        return cls.fromServerData(data as any);
    }

    static createEmpty(): RubricRow<undefined> {
        return new RubricRow({
            id: undefined,
            type: '',
            header: '',
            description: '',
            descriptionType: defaultDescriptionType,
            locked: false,
            items: [],
        });
    }

    @nonenumerable
    protected _cache = makeCache('maxPoints', 'minPoints');

    constructor(row: IRubricRow<T, T>) {
        // eslint-disable-next-line @typescript-eslint/no-use-before-define
        if (row.type && !(this instanceof RubricRowsTypes[row.type])) {
            throw new Error('You cannot make a base row with a non empty type.');
        }
        Object.assign(this, row);
        Object.freeze(this.items);

        Object.freeze(this);
    }

    get isMarkdown(): boolean {
        return this.descriptionType === RubricDescriptionType.markdown;
    }

    get minPoints(): number {
        return this._cache.get('minPoints', () => {
            const found = this.items.reduce((minFound, item) => {
                const pts: number | null | '' = item.points;
                if (pts != null && pts !== '') {
                    return Math.min(minFound, pts);
                }
                return minFound;
            }, Infinity);
            return found === Infinity ? 0 : found;
        });
    }

    get maxPoints(): number {
        return this._cache.get('maxPoints', () => {
            const maxPoints = Math.max(
                ...filterMap(
                    this.items,
                    (item): Maybe<number> => {
                        const pts: number | null | '' = item.points;
                        if (pts == null || pts === '') {
                            return Nothing;
                        } else {
                            return Just(pts);
                        }
                    },
                ),
            );

            if (maxPoints === -Infinity) {
                return 0;
            }

            return maxPoints;
        });
    }

    private update(this: RubricRow<T>, props = {}): RubricRow<T | undefined> {
        return new (this.constructor as any)(Object.assign({}, this, props));
    }

    updateItem(
        this: NormalRubricRow<T>,
        idx: number,
        prop: Exclude<keyof RubricItem, 'id'>,
        // eslint-disable-next-line no-undef
        value: RubricItem[typeof prop],
    ): NormalRubricRow<T | undefined>;

    updateItem(
        this: ContinuousRubricRow<T>,
        idx: 0,
        prop: Exclude<keyof RubricItem, 'id'>,
        // eslint-disable-next-line no-undef
        value: RubricItem[typeof prop],
    ): ContinuousRubricRow<T | undefined>;

    updateItem(
        this: RubricRow<T>,
        idx: number,
        prop: Exclude<keyof RubricItem, 'id'>,
        // eslint-disable-next-line no-undef
        value: RubricItem[typeof prop],
    ): RubricRow<T | undefined> {
        const items: RubricItem<undefined | null | number>[] = this.items.slice();
        if (idx < 0 || idx >= items.length) {
            throw new ReferenceError('Invalid index');
        }
        if (prop === 'points') {
            const pts = parseOrKeepFloat(<RubricItem[typeof prop]>value);
            items[idx] = items[idx].update({
                points: Number.isNaN(pts) ? null : pts,
            });
        } else {
            items[idx] = items[idx].update({ [prop]: value });
        }
        return this.update({ items });
    }

    setType(type: 'continuous'): ContinuousRubricRow<undefined>;

    setType(type: 'normal'): NormalRubricRow<undefined>;

    // eslint-disable-next-line @typescript-eslint/no-use-before-define
    setType<Y extends keyof typeof RubricRowsTypes>(
        type: Y,
    ): ContinuousRubricRow<undefined> | NormalRubricRow<undefined> {
        if (this.type != null && this.type !== '') {
            throw new Error(`Row type was already set and was ${this.type}`);
        }

        // eslint-disable-next-line @typescript-eslint/no-use-before-define
        const cls = RubricRowsTypes[type];
        if (cls == null) {
            throw new TypeError(`Invalid row type: ${type}`);
        }
        return cls.createEmpty();
    }

    createItem<T extends number | null | undefined>(
        this: NormalRubricRow<T>,
    ): NormalRubricRow<T | undefined>;

    createItem<T extends number | null | undefined>(this: RubricRow<T>) {
        return this.update({
            items: [...this.items, RubricItem.createEmpty()],
        });
    }

    deleteItem(idx: number) {
        if (idx < 0 || idx >= this.items.length) {
            throw new ReferenceError('Invalid index');
        }

        return this.update({
            items: this.items.slice(0, idx).concat(this.items.slice(idx + 1)),
        });
    }

    lockMessage(autoTest: AutoTestRun, autoTestResult: AutoTestResult, rubricResult: RubricResult) {
        switch (this.locked) {
            case 'auto_test':
                return this._autoTestLockMessage(autoTest, autoTestResult, rubricResult);
            default:
                return '';
        }
    }

    _autoTestLockMessage(
        _: Object | null,
        autoTestResult: AutoTestResult,
        rubricResult: RubricResult,
    ) {
        const selectedRubricItem = getProps(
            rubricResult,
            null,
            'selected',
            coerceToString(this.id),
        );
        const autoTestPercentage = getProps(
            autoTestResult as any,
            null,
            'rubricResults',
            coerceToString(this.id),
            'percentage',
        );

        if (selectedRubricItem == null || autoTestPercentage == null) {
            let msg = 'This is an AutoTest category.';
            if (autoTestResult != null) {
                const extra = [];
                if (!autoTestResult.finished) {
                    extra.push('the test has finished running');
                }
                if (!autoTestResult.isFinal) {
                    extra.push(
                        'all hidden steps have been run, which will happen after the deadline',
                    );
                }
                if (extra.length === 0) {
                    extra.push('you have the permission to see the final grade');
                }
                msg += ` It will be filled in once ${extra.join(' and ')}.`;
            }
            return msg;
        } else {
            return `You scored ${autoTestPercentage.toFixed(
                0,
            )}% in the corresponding AutoTest category, which scores you ${toMaxNDecimals(
                selectedRubricItem.points * selectedRubricItem.multiplier,
                2,
            )} points in this rubric category. `;
        }
    }

    get nonEmptyHeader() {
        return this.header || '[No name]';
    }

    validate(prevErrors: RubricRowValidationError | null = null) {
        let errors: RubricRowValidationError;
        if (prevErrors == null) {
            errors = new RubricRowValidationError();
        } else {
            AssertionError.assert(
                prevErrors instanceof RubricRowValidationError,
                'prevErrors should be an instance of RubricRowValidationError',
            );
            errors = prevErrors;
        }

        if (this.header.length === 0) {
            errors.unnamed = true;
        }

        if (this.items.length === 0) {
            errors.categories.push(this.nonEmptyHeader);
        }

        for (let j = 0; j < this.items.length; j += 1) {
            const item = this.items[j];

            if (item.header.length === 0) {
                errors.itemHeader.push(this.nonEmptyHeader);
            }

            if (item.points == null || Number.isNaN(parseOrKeepFloat(item.points))) {
                errors.itemPoints.push(`'${this.nonEmptyHeader} - ${item.nonEmptyHeader}'`);
            }
        }

        return errors;
    }
}

export class NormalRubricRow<T extends number | undefined | null> extends RubricRow<T> {
    static readonly tag = 'normal';

    readonly type!: 'normal';

    static fromServerData(data: NormalRubricRowServerData) {
        if (data.type !== 'normal') {
            throw new TypeError('Row is not normal');
        }

        return new NormalRubricRow({
            id: data.id,
            type: data.type,
            header: data.header,
            description: data.description,
            descriptionType: RubricDescriptionType[data.description_type],
            locked: data.locked,
            items: data.items.map(item => RubricItem.fromServerData(item)),
        });
    }

    static createEmpty(): NormalRubricRow<undefined> {
        return new NormalRubricRow({
            id: undefined,
            type: 'normal',
            header: '',
            description: '',
            descriptionType: defaultDescriptionType,
            locked: false,
            items: [],
        });
    }

    _autoTestLockMessage(
        // eslint-disable-next-line camelcase
        autoTest: { grade_calculation?: 'full' | 'partial' } | null,
        autoTestResult: AutoTestResult,
        rubricResult: RubricResult,
    ) {
        // eslint-disable-next-line camelcase
        const gradeCalculation = autoTest?.grade_calculation;
        let msg = super._autoTestLockMessage(autoTest, autoTestResult, rubricResult);
        if (msg) {
            msg += ' ';
        }

        if (gradeCalculation != null) {
            const toReach = gradeCalculation === 'full' ? 'upper' : 'lower';
            msg += `You need to reach the ${toReach} bound of a rubric item to achieve its score.`;
        } else if (autoTest != null) {
            msg += 'No grade calculation method has been set yet.';
        }

        return msg;
    }
}

export class ContinuousRubricRow<T extends number | undefined | null> extends RubricRow<T> {
    static readonly tag = 'continuous';

    readonly type!: 'continuous';

    static fromServerData(data: ContinuousRubricRowServerData): ContinuousRubricRow<number> {
        if (data.type !== 'continuous') {
            throw new TypeError('Row is not continuous');
        }

        return new ContinuousRubricRow({
            id: data.id,
            type: data.type,
            header: data.header,
            description: data.description,
            descriptionType: RubricDescriptionType[data.description_type],
            locked: data.locked,
            items: data.items.map(item => RubricItem.fromServerData(item)),
        });
    }

    static createEmpty(): ContinuousRubricRow<undefined> {
        return new ContinuousRubricRow({
            id: undefined,
            type: 'continuous',
            header: '',
            description: '',
            descriptionType: defaultDescriptionType,
            locked: false,
            items: [RubricItem.createEmpty().update({ header: 'Continuous' })],
        });
    }

    // eslint-disable-next-line class-methods-use-this
    get minPoints() {
        return 0;
    }

    validate(prevErrors: RubricRowValidationError | null = null) {
        const errors = super.validate(prevErrors);

        if ((this.items[0].points ?? 0) <= 0) {
            errors.continuous.push(this.nonEmptyHeader);
        }

        return errors;
    }
}

const RubricRowsTypes = <const>{
    [NormalRubricRow.tag]: NormalRubricRow,
    [ContinuousRubricRow.tag]: ContinuousRubricRow,
};

type RubricServerData = RubricRowServerData[];

export class Rubric<T extends number | undefined | null> {
    static fromServerData(data: RubricServerData) {
        const rows = (data || []).map(row => {
            row.items.sort((x, y) => x.points - y.points);
            return RubricRow.fromServerData(row);
        });

        return new Rubric(rows);
    }

    @nonenumerable
    private _cache = makeCache('maxPoints', 'rowsById');

    constructor(public readonly rows: ReadonlyArray<RubricRow<T>>) {
        this.rows = Object.freeze(rows);

        Object.freeze(this);
    }

    get maxPoints() {
        return this._cache.get('maxPoints', () =>
            this.rows.reduce((acc, row) => acc + row.maxPoints, 0),
        );
    }

    get rowsById() {
        return this._cache.get('rowsById', () =>
            this.rows.reduce((acc: Record<string, RubricRow<T>>, row) => {
                if (row.id != null) {
                    acc[<number>row.id] = row;
                }
                return acc;
            }, {}),
        );
    }

    getItemIds() {
        return this.rows.reduce((acc: Record<string, string>, row) => {
            row.items.forEach(item => {
                if (item.id != null) {
                    acc[<number>item.id] = `${row.nonEmptyHeader} - ${item.nonEmptyHeader}`;
                }
            });
            return acc;
        }, {});
    }

    createRow() {
        const rows = [...this.rows, RubricRow.createEmpty()];
        return new Rubric(rows);
    }

    deleteRow(idx: number) {
        if (idx < 0 || idx >= this.rows.length) {
            throw new ReferenceError('Invalid index');
        }

        const rows = this.rows.slice(0, idx).concat(this.rows.slice(idx + 1));
        return new Rubric(rows);
    }

    updateRow(idx: number, rowData: RubricRow<T>) {
        if (!(rowData instanceof RubricRow)) {
            throw new TypeError('Rubric rows must be of type RubricRow');
        }

        const rows = this.rows.slice();
        rows[idx] = rowData;
        return new Rubric(rows);
    }

    // eslint-disable-next-line class-methods-use-this
    setRows(rows: ReadonlyArray<RubricRow<T>>) {
        return new Rubric(rows);
    }
}

export interface RubricResultItemServerData extends RubricItemServerData {
    multiplier: number;
}

interface RubricResultServerData {
    rubrics: RubricRowServerData[];
    selected: RubricResultItemServerData[];
}

export class RubricResult {
    static fromServerData(submissionId: number, data: RubricResultServerData) {
        const rowOfItem = data.rubrics.reduce((acc: Record<string, number>, row) => {
            row.items.forEach(item => {
                acc[item.id] = row.id;
            });
            return acc;
        }, {});

        const selected = data.selected.reduce(
            (acc: Record<string, RubricResultItemServerData>, item) => {
                const rowId = rowOfItem[item.id];
                acc[rowId] = item;
                return acc;
            },
            {},
        );

        return new RubricResult(submissionId, selected);
    }

    private _cache = makeCache('points');

    constructor(
        public submissionId: number,
        public selected: Record<string, RubricResultItemServerData>,
    ) {
        this.submissionId = submissionId;
        this.selected = Object.freeze(selected);

        Object.freeze(this);
    }

    get points() {
        return this._cache.get('points', () => {
            if (Object.values(this.selected).length === 0) {
                return null;
            } else {
                return Object.values(this.selected).reduce((acc, item) => {
                    if (typeof item.multiplier !== 'number') {
                        return acc;
                    }
                    const multiplier = Math.max(0, Math.min(item.multiplier, 1));
                    return acc + item.points * multiplier;
                }, 0);
            }
        });
    }

    get submission(): Submission {
        return store.getters['submissions/getSingleSubmission'](this.submissionId);
    }

    get assignment() {
        return getProps(this.submission, null, 'assignment');
    }

    get rubric(): Rubric<number> | null {
        const id = this.submission?.assignmentId;
        return id == null ? null : store.getters['rubrics/rubrics'][id];
    }

    get maxPoints(): Maybe<number> {
        return Maybe.fromNullable(
            // eslint-disable-next-line camelcase
            this.assignment?.fixed_max_rubric_points,
        ).alt(Maybe.fromNullable(this.rubric?.maxPoints));
    }

    get grade(): string | null {
        const points = this.points;
        const maxPoints = this.maxPoints.extractNullable();
        if (points == null || maxPoints == null) {
            return null;
        } else {
            const grade = (10 * points) / maxPoints;
            return formatGrade(Math.max(0, Math.min(grade, 10)));
        }
    }

    diffSelected(other: RubricResult) {
        const ownIds = new Set(Object.values(this.selected).map(x => x.id));
        const otherIds = new Set(Object.values(other.selected).map(x => x.id));

        return setXor(ownIds, otherIds);
    }

    toggleItem(rowId: number, item: RubricItem & { id: number; points: number }) {
        const selected = Object.assign({}, this.selected);
        const selectedItem = selected[rowId];

        if (selectedItem && selectedItem.id === item.id) {
            delete selected[rowId];
        } else {
            selected[rowId] = Object.assign({}, item, {
                multiplier: 1,
            });
        }

        return new RubricResult(this.submissionId, selected);
    }

    setMultiplier(
        rowId: number,
        item: RubricItem & { id: number; points: number },
        multiplier: number,
    ) {
        const selected = Object.assign({}, this.selected);
        const selectedItem = selected[rowId];

        if (selectedItem && selectedItem.id !== item.id) {
            throw new Error(
                `Item id should not change! Expected ${selectedItem.id} but got ${item.id}.`,
            );
        } else if (multiplier == null) {
            delete selected[rowId];
        } else {
            selected[rowId] = Object.assign({}, item, {
                multiplier: Number(multiplier),
            });
        }

        return new RubricResult(this.submissionId, selected);
    }

    validate() {
        if (this.rubric == null) {
            throw new ReferenceError('Rubric not found.');
        }

        const errors = new RubricResultValidationError();
        const rows = this.rubric.rowsById;

        Object.entries(this.selected).forEach(([rowId, item]) => {
            const row = rows[rowId];
            if (item.multiplier != null && (item.multiplier < 0 || item.multiplier > 1)) {
                errors.multipliers.push(row.nonEmptyHeader);
            }
        });

        return errors;
    }

    // eslint-disable-next-line class-methods-use-this
    clearSelected() {
        return new RubricResult(this.submissionId, {});
    }
}
