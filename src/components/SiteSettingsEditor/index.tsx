/* SPDX-License-Identifier: AGPL-3.0-only */
import * as tsx from 'vue-tsx-support';
import moment from 'moment';
import p from 'vue-strict-prop';
import { CreateElement } from 'vue';
import { ALL_SITE_SETTINGS, SiteSettings } from '@/models';
import { AssertionError, Maybe, Nothing, Either, Just, Right, Left } from '@/utils';
import { VNode } from 'vue/types/umd';
import * as api from '@/api/v1';

import * as comp from '@/components';

const numberOrError = (val: Either<Error, Maybe<number>>, onError: (err: string) => void, onNumber: (val: number) => void) => {
    val.caseOf({
        Right(maybe) {
            maybe.caseOf({
                Nothing() {
                    onError('Input is required');
                },
                Just: onNumber,
            })
        },
        Left(err) {
            onError(err.message);
        },
    });
};

type EditEvent<T> = {
    onEdit: T,
};

const BooleanEditor = tsx.componentFactoryOf<EditEvent<boolean>>().create({
    props: {
        value: p(Boolean).required,
    },

    methods: {
        emitEditEvent(newValue: boolean): void {
            tsx.emitOn(this, 'onEdit', newValue );
        },
    },

    render(h) {
        return (
            <comp.Toggle value={this.value} onInput={this.emitEditEvent} />
        );
    },
});


const StringEditor = tsx.componentFactoryOf<EditEvent<string>>().create({
    props: {
        value: p(String).required,
    },

    methods: {
        emitEditEvent(newValue: string): void {
            console.log('new string value');
            tsx.emitOn(this, 'onEdit', newValue );
        },
    },

    render(h) {
        return (
            <input class="form-control"
                   value={this.value}
                   onInput={val => this.emitEditEvent(val.target.value as string)}
            />
        );
    },
});


const TimeDeltaEditor = tsx.componentFactoryOf<EditEvent<number> & { onError: string }>().create({
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
                        const newDuration = oldDuration.clone().subtract(oldDuration[part](), part).add(newValue, part);
                        tsx.emitOn(this, 'onEdit', newDuration.asSeconds());
                    }
                );
            };
        },
    },

    render(h) {
        const duration = moment.duration(this.value * 1000);
        const opts = ['days', 'hours', 'minutes', 'seconds'] as const;
        return (
            <b-input-group>
                {opts.map((opt) => ([
                    <comp.NumberInput value={Right(Just(duration[opt]()))}
                                      onInput={this.makeEditEventEmitter(opt)}
                    />,
                    <b-input-group-append is-text>
                        {opt}
                    </b-input-group-append>,
                ]))}
            </b-input-group>
        );
    },
});

const KB = 1 << 10;
const MB = KB << 10;
const GB = MB << 10;
const POSSIBLE_UNITS = ['gb' , 'mb' , 'kb' , 'b' ] as const;
type PossibleUnit = typeof POSSIBLE_UNITS[number];
const FileSizeEditor = tsx.componentFactoryOf<EditEvent<number> & { onError: string }, {}>().create({
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
                return 'kb'
            } else {
                return 'b';
            }
        },

        unit(): PossibleUnit {
            return this.chosenUnit ?? this.computedUnit;
        },

        unitLookup(): Record<PossibleUnit, number> {
            return {
                'b': 1,
                'kb': KB,
                'mb': MB,
                'gb': GB,
            };
        },

        valueForUnit(): number {
            return this.value / this.unitLookup[this.unit]
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
            <div class="d-flex" >
                <comp.NumberInput value={Right(Just(this.valueForUnit))}
                                  onInput={this.emitEditEvent}
                />
                <b-form-select vModel={this.chosenUnit}
                               options={POSSIBLE_UNITS}
                               class="ml-3" />
            </div>
        );
    },
});

const NumberEditor = tsx.componentFactoryOf<EditEvent<number> & { onError: string }, {}>().create({
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
        return (
            <comp.NumberInput value={Right(Just(this.value))}
                              onInput={this.emitEditEvent}
            />
        );
    },
});


type SettingsLookup = { [K in keyof SiteSettings]: SiteSettings[K] };
type Setting = typeof ALL_SITE_SETTINGS[number];
type SiteSettingsEditorData = {
    settings: Maybe<Either<Error, SettingsLookup>>,
    updatedSettings: Partial<SettingsLookup>,
    errors: Partial<{ [ K in keyof SiteSettings]: string}>,
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
        renderGroup(h: CreateElement, groupName: string, items: readonly Setting[], settings: SettingsLookup): VNode {
            const header = this.$utils.ifOrEmpty(!!groupName, () => (
                <h4>{groupName}</h4>
            ));
            return (
                <div>
                    {header}
                    {items.map(item => this.renderItem(h, item, settings))}
                </div>
            )
        },

        renderItem(h: CreateElement, item: Setting, settings: SettingsLookup): VNode {
            return (
                <b-form-group state={!(item.name in this.errors)}
                              invalid-feedback={this.errors[item.name] ?? ''}>
                    <div slot="label">
                        <code>{item.name}</code>
                    </div>
                    <div slot="description">
                        <comp.InnerMarkdownViewer markdown={item.doc} class="mb-n3" />
                    </div>
                    {this.renderEditor(h, item, settings)}
                </b-form-group>
            )
        },

        renderEditor(h: CreateElement, item: Setting, settings: SettingsLookup): VNode {
            const updatedSettings = this.updatedSettings;
            function lookup<T extends keyof SettingsLookup>({ name }: { name: T }): SettingsLookup[T] {
                return {...settings, ...updatedSettings}[name];
            };
            if (item.list) {
                return <div></div>;
            }

            switch (item.typ) {
                case 'number':
                    if (item.format === 'timedelta') {
                        return <TimeDeltaEditor value={lookup(item)}
                                                onEdit={this.getUpdater(item)}
                                                onError={this.getErrorSetter(item)} />;
                    } else if (item.format === 'filesize') {
                        return <FileSizeEditor value={lookup(item)}
                                               onEdit={this.getUpdater(item)}
                                               onError={this.getErrorSetter(item)} />;
                    }
                    return <NumberEditor value={lookup(item)}
                                         onEdit={this.getUpdater(item)}
                                         onError={this.getErrorSetter(item)} />;
                case 'string':
                    return <StringEditor value={lookup(item)}
                                         onEdit={this.getUpdater(item)} />;
                case 'boolean':
                    return <BooleanEditor value={lookup(item)}
                                          onEdit={this.getUpdater(item)} />;
                default:
                    AssertionError.assertNever(item);
            }
        },

        getErrorSetter<T extends keyof SettingsLookup>({ name }: { name: T }) {
            return (error: string) => {
                this.$utils.vueSet(this.errors, name, error);
            };
        },

        getUpdater<T extends keyof SettingsLookup>({ name }: { name: T }) {
            return (newValue: SettingsLookup[T]) => {
                this.$utils.vueDelete(this.errors, name);

                this.settings.orDefault(Left(new Error('Settings not yet available'))).caseOf({
                    Right: originalValues => {
                        if (originalValues[name] === newValue) {
                            this.$utils.vueDelete(this.updatedSettings, name);
                        } else {
                            this.$utils.vueSet(this.updatedSettings, name, newValue);
                        }
                    },
                    Left: () => this.$utils.vueSet(this.updatedSettings, name, newValue),
                })
            };
        },

        renderSaveButton(h: CreateElement): VNode {
            return (
                <div  class={{
                    'sticky-save-bar': !this.$utils.isEmpty(this.updatedSettings),
                    'd-flex': true,
                    'justify-content-end': true
                }}>
                    <div v-b-popover_top_hover={this.submitDisabledMessage ?? ''}>
                        <comp.SubmitButton submit={this.saveChanges}
                                           disabled={this.submitDisabled}>
                            Save changes
                        </comp.SubmitButton>
                    </div>
                </div>
            );
        },

        maybeRenderSettings(h: CreateElement): VNode {
            return this.settings.caseOf({
                Just: settings => settings.caseOf({
                    Left: err => (
                        <comp.CgError error={err} />
                    ),
                    Right: lookup => {
                        const byGroup = this.$utils.groupBy(ALL_SITE_SETTINGS, el => el.group ?? '');
                        const groups = this.$utils.sortBy(
                            Array.from(byGroup.entries()),
                            ([group]) => [group],
                            { reverse: true },
                        );
                        return (
                            <div>
                                {groups.map(([groupName, items]) => this.renderGroup(h, groupName, items, lookup))}
                                {this.renderSaveButton(h)}
                            </div>
                        );
                    }

                }),
                Nothing: () => {
                    return <comp.Loader />;
                },
            });
        },

        saveChanges() {
            return {};
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
        api.siteSettings.getAll().then(settings => {
            if ('AUTO_TEST_HEARTBEAT_MAX_MISSED' in settings) {
                this.settings = Just(Right(settings));
            } else {
                this.settings = Just(Left(new Error('Only got frontend settings.')));
            }
        }, err => {
            this.settings = Just(Left(err));
        });
    },

    render(h) {
        return (
            <div class="site-settings-editor">
                {this.maybeRenderSettings(h)}
            </div>
        );
    },
});
