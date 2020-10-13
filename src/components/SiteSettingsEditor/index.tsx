/* SPDX-License-Identifier: AGPL-3.0-only */
import * as tsx from 'vue-tsx-support';
import moment from 'moment';
import p from 'vue-strict-prop';
import { CreateElement, VNode } from 'vue';

import { ALL_SITE_SETTINGS, SiteSettings } from '@/models';
import {
    AssertionError,
    Maybe,
    Nothing,
    Either,
    Just,
    Right,
    Left,
    filterMap,
    mapToObject,
    mapFilterObject,
} from '@/utils';
import { SiteSettingsStore } from '@/store';
import * as api from '@/api/v1';
import * as comp from '@/components';

// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/plus';

const numberOrError = (
    val: Either<Error, Maybe<number>>,
    onError: (err: string) => void,
    onNumber: (val: number) => void,
) => {
    val.caseOf({
        Right(maybe) {
            maybe.caseOf({
                Nothing() {
                    onError('Input is required');
                },
                Just: onNumber,
            });
        },
        Left(err) {
            onError(err.message);
        },
    });
};

type EditEvent<T> = {
    onEdit: T;
    onError: string;
};

type ListEditorEvents = {
    onRowCreated: {};
    onRowDeleted: { index: number };
    onError: string;
};

type ListEditorSlots<T> = {
    row: { index: number; value: T };
};

const NumberListEditor = tsx
    .componentFactoryOf<ListEditorEvents, ListEditorSlots<number>>()
    .create({
        props: {
            values: p.ofRoArray<number>().required,
        },

        methods: {
            emitNewRow(): void {
                tsx.emitOn(this, 'onRowCreated', {});
            },

            makeDeleteRowEmitter(index: number): () => void {
                return () => tsx.emitOn(this, 'onRowDeleted', { index });
            },
        },

        computed: {
            amountOfRows(): number {
                return this.values.length;
            },
        },

        watch: {
            amountOfRows() {
                if (this.amountOfRows === 0) {
                    tsx.emitOn(this, 'onError', 'You should have at least one value');
                }
            },
        },

        render(h: CreateElement): VNode {
            return (
                <div>
                    <ul>
                        {this.values.map((value, index) => (
                            <li class="mb-1">
                                <div class="d-flex">
                                    {this.$scopedSlots.row({ value, index })}
                                    <b-button
                                        onClick={this.makeDeleteRowEmitter(index)}
                                        class="ml-1"
                                        v-b-popover_top_hover={'Delete row'}
                                    >
                                        <Icon name="times" />
                                    </b-button>
                                </div>
                            </li>
                        ))}
                    </ul>
                    <div class="d-flex justify-content-end">
                        <div v-b-popover_top_hover={'Create row'}>
                            <b-button onClick={this.emitNewRow}>
                                <Icon name="plus" />
                            </b-button>
                        </div>
                    </div>
                </div>
            );
        },
    });

const BooleanEditor = tsx.componentFactoryOf<EditEvent<boolean>>().create({
    props: {
        value: p(Boolean).required,
    },

    methods: {
        emitEditEvent(newValue: boolean): void {
            tsx.emitOn(this, 'onEdit', newValue);
        },
    },

    render(h) {
        return <comp.Toggle value={this.value} onInput={this.emitEditEvent} />;
    },
});

const StringEditor = tsx.componentFactoryOf<EditEvent<string>>().create({
    props: {
        value: p(String).required,
    },

    methods: {
        emitEditEvent(newValue: string): void {
            if (!newValue) {
                tsx.emitOn(this, 'onError', 'The value may not be empty');
            } else {
                tsx.emitOn(this, 'onEdit', newValue);
            }
        },
    },

    render(h) {
        return (
            <input
                class="form-control"
                value={this.value}
                onInput={val => this.emitEditEvent(val.target.value as string)}
            />
        );
    },
});

const TimeDeltaEditor = tsx.componentFactoryOf<EditEvent<number>>().create({
    props: {
        value: p(Number).required,
    },

    methods: {
        makeEditEventEmitter(part: 'days' | 'hours' | 'minutes' | 'seconds') {
            return (opt: Either<Error, Maybe<number>>): void => {
                numberOrError(
                    opt,
                    err => tsx.emitOn(this, 'onError', err),
                    newValue => {
                        const oldDuration = moment.duration(this.value * 1000);
                        const newDuration = oldDuration
                            .clone()
                            .subtract(this.getValue(oldDuration, part), part)
                            .add(newValue, part);

                        tsx.emitOn(this, 'onEdit', newDuration.asSeconds());
                    },
                );
            };
        },

        getValue(duration: moment.Duration, part: 'days' | 'hours' | 'minutes' | 'seconds') {
            if (part === 'days') {
                return Math.floor(duration.asDays());
            }
            return duration[part]();
        },
    },

    render(h) {
        const duration = moment.duration(this.value * 1000);
        const opts = ['days', 'hours', 'minutes', 'seconds'] as const;
        return (
            <b-input-group>
                {opts.map(opt => [
                    <comp.NumberInput
                        value={Right(Just(this.getValue(duration, opt)))}
                        onInput={this.makeEditEventEmitter(opt)}
                    />,
                    <b-input-group-append is-text>{opt}</b-input-group-append>,
                ])}
            </b-input-group>
        );
    },
});

const KB = 1 << 10;
const MB = KB << 10;
const GB = MB << 10;
const POSSIBLE_UNITS = ['gb', 'mb', 'kb', 'b'] as const;
type PossibleUnit = typeof POSSIBLE_UNITS[number];
const FileSizeEditor = tsx.componentFactoryOf<EditEvent<number>, {}>().create({
    props: {
        value: p(Number).required,
    },

    data(): { chosenUnit: null | PossibleUnit } {
        return {
            chosenUnit: null,
        };
    },

    mounted() {
        this.chosenUnit = this.computedUnit;
    },

    computed: {
        computedUnit(): PossibleUnit {
            if (this.value > GB) {
                return 'gb';
            } else if (this.value > MB) {
                return 'mb';
            } else if (this.value > KB) {
                return 'kb';
            } else {
                return 'b';
            }
        },

        unit(): PossibleUnit {
            return this.chosenUnit ?? this.computedUnit;
        },

        unitLookup(): Record<PossibleUnit, number> {
            return {
                b: 1,
                kb: KB,
                mb: MB,
                gb: GB,
            };
        },

        valueForUnit(): number {
            return this.value / this.unitLookup[this.unit];
        },
    },

    methods: {
        emitEditEvent(opt: Either<Error, Maybe<number>>): void {
            numberOrError(
                opt,
                err => tsx.emitOn(this, 'onError', err),
                val => tsx.emitOn(this, 'onEdit', val * this.unitLookup[this.unit]),
            );
        },
    },

    render(h) {
        return (
            <div class="d-flex">
                <comp.NumberInput
                    value={Right(Just(this.valueForUnit))}
                    onInput={this.emitEditEvent}
                />
                <b-form-select vModel={this.chosenUnit} options={POSSIBLE_UNITS} class="ml-3" />
            </div>
        );
    },
});

const NumberEditor = tsx.componentFactoryOf<EditEvent<number>, {}>().create({
    props: {
        value: p(Number).required,
    },

    methods: {
        emitEditEvent(opt: Either<Error, Maybe<number>>): void {
            numberOrError(
                opt,
                err => tsx.emitOn(this, 'onError', err),
                val => tsx.emitOn(this, 'onEdit', val),
            );
        },
    },

    render(h) {
        return <comp.NumberInput value={Right(Just(this.value))} onInput={this.emitEditEvent} />;
    },
});

type SettingsLookup = { [K in keyof SiteSettings]: SiteSettings[K] };
type Setting = typeof ALL_SITE_SETTINGS[number];
type PatchMap = { [K in keyof SiteSettings]: { name: K; value: SiteSettings[K] } };
type SiteSettingsEditorData = {
    settings: Maybe<Either<Error, SettingsLookup>>;
    updatedSettings: Partial<PatchMap>;
    errors: Partial<{ [K in keyof SiteSettings]: string }>;
};

export default tsx.component({
    name: 'site-settings-editor',

    data(): SiteSettingsEditorData {
        return {
            settings: Nothing,
            updatedSettings: {},
            errors: {},
        };
    },

    methods: {
        setUpdatedSetting<K extends keyof PatchMap>(item: { name: K; value: SettingsLookup[K] }) {
            // Yeah I know..., this casts shouldn't really be necessary as this
            // is the exact shape of the items in PatchMap.
            this.$utils.vueSet(this.updatedSettings, item.name, (item as unknown) as PatchMap[K]);
        },

        renderGroup(
            h: CreateElement,
            groupName: string,
            items: readonly Setting[],
            settings: SettingsLookup,
        ): VNode {
            const header = this.$utils.ifOrEmpty(!!groupName, () => <h4>{groupName}</h4>);

            return (
                <div>
                    {header}
                    {items.map(item => this.renderItem(h, item, settings))}
                </div>
            );
        },

        renderItem(h: CreateElement, item: Setting, settings: SettingsLookup): VNode {
            return (
                <b-form-group
                    state={!(item.name in this.errors)}
                    invalid-feedback={this.errors[item.name] ?? ''}
                >
                    <div slot="label">
                        <code>{item.name}</code>
                    </div>
                    <div slot="description">
                        <comp.InnerMarkdownViewer markdown={item.doc} class="mb-n3" />
                    </div>
                    {this.renderEditor(h, item, settings)}
                </b-form-group>
            );
        },

        renderEditor(h: CreateElement, item: Setting, settings: SettingsLookup): VNode {
            const updatedSettings = this.updatedSettings;

            if (item.list) {
                AssertionError.typeAssert<'number'>(item.typ);
                AssertionError.typeAssert<readonly number[]>(settings[item.name]);

                const rowSlot = ({ value, index }: { value: number; index: number }) =>
                    this.renderFormattedNumber(
                        h,
                        value,
                        item.format,
                        (newItem: number) => {
                            const newValue = settings[item.name].slice();
                            if (newItem !== newValue[index]) {
                                newValue[index] = newItem;
                                this.getUpdater(item)(newValue);
                            }
                        },
                        this.getErrorSetter(item),
                    );

                const onRowCreated = () => {
                    this.getUpdater(item)([...settings[item.name].slice(), 0]);
                };

                const onRowDeleted = ({ index }: { index: number }) => {
                    const newValue = settings[item.name].slice();
                    newValue.splice(index, 1);
                    this.getUpdater(item)(newValue);
                };

                return (
                    <NumberListEditor
                        values={settings[item.name]}
                        scopedSlots={{
                            row: rowSlot,
                        }}
                        onError={this.getErrorSetter(item)}
                        onRowCreated={onRowCreated}
                        onRowDeleted={onRowDeleted}
                    />
                );
            }

            switch (item.typ) {
                case 'number':
                    return this.renderFormattedNumber(
                        h,
                        settings[item.name],
                        item.format,
                        this.getUpdater(item),
                        this.getErrorSetter(item),
                    );
                case 'string':
                    return (
                        <StringEditor
                            value={settings[item.name]}
                            onEdit={this.getUpdater(item)}
                            onError={this.getErrorSetter(item)}
                        />
                    );
                case 'boolean':
                    return (
                        <BooleanEditor value={settings[item.name]} onEdit={this.getUpdater(item)} />
                    );
                default:
                    return AssertionError.assertNever(item);
            }
        },

        renderFormattedNumber(
            h: CreateElement,
            value: number,
            format: 'timedelta' | 'filesize' | '',
            onEdit: (val: number) => void,
            onError: (val: string) => void,
        ) {
            if (format === 'timedelta') {
                return <TimeDeltaEditor value={value} onEdit={onEdit} onError={onError} />;
            } else if (format === 'filesize') {
                return <FileSizeEditor value={value} onEdit={onEdit} onError={onError} />;
            }
            return <NumberEditor value={value} onEdit={onEdit} onError={onError} />;
        },

        getErrorSetter<T extends keyof SettingsLookup>({ name }: { name: T }) {
            return (error: string) => {
                this.$utils.vueSet(this.errors, name, error);
            };
        },

        getUpdater<T extends keyof SiteSettings>({ name }: { name: T }) {
            return (value: SettingsLookup[T]) => {
                this.$utils.vueDelete(this.errors, name);
                const newObj = { name, value };

                this.settings.orDefault(Left(new Error('Settings not yet available'))).caseOf({
                    Right: originalValues => {
                        if (originalValues[name] === newObj.value) {
                            this.$utils.vueDelete(this.updatedSettings, name);
                        } else {
                            this.setUpdatedSetting(newObj);
                        }
                    },
                    Left: () => this.setUpdatedSetting(newObj),
                });
            };
        },

        renderSaveButton(h: CreateElement, oldSettings: SettingsLookup): VNode {
            return (
                <div
                    class={{
                        'sticky-save-bar': !this.$utils.isEmpty(this.updatedSettings),
                        'd-flex': true,
                        'justify-content-end': true,
                    }}
                >
                    <div
                        v-b-popover_top_hover={this.submitDisabledMessage ?? ''}
                        class="button-wrapper"
                    >
                        <comp.SubmitButton
                            submit={this.saveChanges}
                            onAfter-success={this.afterSaveChanges}
                            disabled={this.submitDisabled}
                            confirmInModal={true}
                            confirm="yes"
                        >
                            <template slot="confirm">
                                {this.renderConfirmMessage(h, oldSettings)}
                            </template>
                            Save changes
                        </comp.SubmitButton>
                    </div>
                </div>
            );
        },

        renderConfirmMessage(h: CreateElement, oldSettings: SettingsLookup): VNode {
            return (
                <div>
                    Are sure you want to save the following changes?
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Setting</th>
                                <th>Old value</th>
                                <th>New value</th>
                            </tr>
                        </thead>

                        <tbody>
                            {filterMap(ALL_SITE_SETTINGS, ({ name }) =>
                                Maybe.fromNullable(this.updatedSettings[name]),
                            ).map(({ name, value: newValue }) => (
                                <tr>
                                    <td>
                                        <code>{name}</code>
                                    </td>
                                    <td>{oldSettings[name].toString()}</td>
                                    <td>{newValue.toString()}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            );
        },

        maybeRenderSettings(h: CreateElement): VNode {
            return this.settings.caseOf({
                Just: settings =>
                    settings.caseOf({
                        Left: err => <comp.CgError error={err} />,
                        Right: lookup => {
                            const currentValues = mapToObject(
                                filterMap(Object.values(this.updatedSettings), Maybe.fromNullable),
                                s => [s.name, s.value],
                                { ...lookup },
                            );

                            const byGroup = this.$utils.groupBy(
                                ALL_SITE_SETTINGS,
                                el => el.group ?? '',
                            );
                            const groups = this.$utils.sortBy(
                                Array.from(byGroup.entries()),
                                ([group]) => [group],
                                { reverse: true },
                            );
                            return (
                                <div>
                                    {groups.map(([groupName, items]) =>
                                        this.renderGroup(h, groupName, items, currentValues),
                                    )}
                                    {this.renderSaveButton(h, lookup)}
                                </div>
                            );
                        },
                    }),
                Nothing: () => <comp.Loader />,
            });
        },

        saveChanges() {
            const newValues = filterMap(ALL_SITE_SETTINGS, ({ name }) =>
                Maybe.fromNullable(this.updatedSettings[name]),
            );
            return SiteSettingsStore.updateSettings({ data: newValues });
        },

        afterSaveChanges(data: SiteSettings) {
            this.updatedSettings = {};
            this.settings = Just(Right(data));
        },
    },

    computed: {
        submitDisabledMessage(): string | null {
            if (!this.$utils.isEmpty(this.errors)) {
                return 'Some values are invalid';
            } else if (this.$utils.isEmpty(this.updatedSettings)) {
                return 'No values changed';
            }
            return null;
        },

        submitDisabled(): boolean {
            return this.submitDisabledMessage != null;
        },
    },

    mounted() {
        api.siteSettings.getAll().then(
            settings => {
                this.settings = Just(Right(settings));
            },
            err => {
                this.settings = Just(Left(err));
            },
        );
    },

    render(h) {
        return <div class="site-settings-editor">{this.maybeRenderSettings(h)}</div>;
    },
});
