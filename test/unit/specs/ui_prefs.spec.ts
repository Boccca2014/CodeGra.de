/* SPDX-License-Identifier: AGPL-3.0-only */
import { shallowMount, createLocalVue } from '@vue/test-utils';
import BootstrapVue from 'bootstrap-vue'
import { mocked } from 'ts-jest/utils'

import '../jest';

import * as utils from '@/utils';
import * as models from '@/models';
import * as api from '@/api/v1';

import PreferredUI from '@/components/PreferredUI';
import { UIPrefsStore } from '@/store'

jest.mock('@/api/v1/ui_prefs');
const mockedApi = mocked(api.uiPrefs);

const localVue = createLocalVue();
localVue.use(BootstrapVue);

const { RubricEditorV2 } = models.UIPreference;

describe('UI preferences', () => {
    function mockOnce(name: models.UIPreference, value: null | boolean) {
        mockedApi.getUIPreferences.mockResolvedValueOnce({
            ...models.DefaultUIPreferenceMap,
            [name]: utils.Just(utils.Maybe.fromNullable(value)),
        });
    }

    beforeAll(() => {
        mockedApi.getUIPreferences
            .mockName('api.uiPrefs.getUIPreferences');

        mockedApi.patchUIPreference
            .mockName('api.uiPrefs.patchUIPreference');
    });

    beforeEach(() => {
        UIPrefsStore.commitClear();
        mockedApi.getUIPreferences
            .mockClear()
            .mockResolvedValue({ ...models.DefaultUIPreferenceMap });
        mockedApi.patchUIPreference
            .mockClear()
            .mockResolvedValue(void 0);
    });

    describe('store getters', () => {
        function makePrefs(value: null | boolean) {
            return { [RubricEditorV2]: utils.Just(utils.Maybe.fromNullable(value)) };
        }

        describe('getUIPref', () => {
            it('should return Nothing if the prefs have not been loaded', () => {
                UIPrefsStore.commitClear();

                expect(UIPrefsStore.getUIPref()(RubricEditorV2)).toBeNothing();
            });

            it.each(
                [true, false, null],
            )('should return the set value if the prefs have been loaded', (val: boolean | null) => {
                UIPrefsStore.commitUIPrefs(makePrefs(val));
                const prefValue = UIPrefsStore.getUIPref()(RubricEditorV2);

                expect(prefValue).toBeJust();
                expect(prefValue.extract()).toEqual(utils.Maybe.fromNullable(val));
            });

            it.each([
                [null, false],
                [null, true],
                [false, false],
                [false, true],
                [true, false],
                [true, true],
            ])('should return the patched value if some pref has been patched', async (fromVal, toVal) => {
                UIPrefsStore.commitUIPrefs(makePrefs(fromVal));
                UIPrefsStore.commitPatchedUIPref({ name: RubricEditorV2, value: utils.Maybe.fromNullable(toVal) });
                const prefValue = UIPrefsStore.getUIPref()(RubricEditorV2);

                expect(prefValue).toBeJust();
                expect(prefValue.extract()).toEqual(utils.Maybe.fromNullable(toVal));
            });
        });
    });

    describe('store actions', () => {
        describe('loadUIPreference', () => {
            it('should call the api', async () => {
                mockOnce(RubricEditorV2, false);
                const res = await UIPrefsStore.loadUIPreference({ preference: RubricEditorV2 });

                expect(mockedApi.getUIPreferences).toBeCalled();

                expect(res).toBeJust();
                expect(res.unsafeCoerce()).toBe(false);
            });

            it('should not call the api twice', async () => {
                mockOnce(RubricEditorV2, true);
                const res1 = await UIPrefsStore.loadUIPreference({ preference: RubricEditorV2 });
                const res2 = await UIPrefsStore.loadUIPreference({ preference: RubricEditorV2 });

                expect(mockedApi.getUIPreferences).toBeCalledTimes(1);

                expect(res1).toBeJust();
                expect(res2).toBeJust();
                expect(res1.extract()).toBe(res2.extract());
            });

            it.each(
                [true, false, null],
            )('should update the store', async (val) => {
                mockOnce(RubricEditorV2, val);

                await UIPrefsStore.loadUIPreference({ preference: RubricEditorV2 });
                const storePrefs = UIPrefsStore.getUIPref()(RubricEditorV2);

                expect(storePrefs).toBeJust();
                expect(storePrefs.unsafeCoerce().extractNullable()).toBe(val);
            });

            it('should return Nothing if the pref was not present in the response', async () => {
                const res = await UIPrefsStore.loadUIPreference({ preference: RubricEditorV2 });
                expect(mockedApi.getUIPreferences).toBeCalled();
                expect(res).toBeNothing();
            });
        });

        describe('patchUIPreference', () => {
            it.each([
                [null, false],
                [null, true],
                [false, false],
                [false, true],
                [true, false],
                [true, true],
            ])('should call the api', async (fromVal, toVal) => {
                mockOnce(RubricEditorV2, fromVal);

                await UIPrefsStore.loadUIPreference({ preference: RubricEditorV2 });
                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: toVal,
                });

                expect(mockedApi.patchUIPreference).toBeCalled();
            });

            it('should call the api each time', async () => {
                await UIPrefsStore.loadUIPreference({ preference: RubricEditorV2 });
                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: false,
                });
                // Even when the value is the same the store should be called
                // again.
                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: false,
                });

                expect(mockedApi.patchUIPreference).toBeCalledTimes(2);
            });

            it('should update the store', async () => {
                await UIPrefsStore.loadUIPreference({ preference: RubricEditorV2 });
                let storePref = UIPrefsStore.getUIPref()(RubricEditorV2);
                expect(storePref).toBeJust();
                expect(storePref.unsafeCoerce()).toBeNothing();

                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: false,
                });
                storePref = UIPrefsStore.getUIPref()(RubricEditorV2);
                expect(storePref).toBeJust();
                expect(storePref.join().extract()).toBe(false);

                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: true,
                });
                storePref = UIPrefsStore.getUIPref()(RubricEditorV2);
                expect(storePref.join().extract()).toBe(true);
            });

            it('should update the store even if preferences were not loaded', async () => {
                let storePref = UIPrefsStore.getUIPref()(RubricEditorV2);
                expect(storePref).toBeNothing();

                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: false,
                });
                storePref = UIPrefsStore.getUIPref()(RubricEditorV2);

                expect(storePref).toBeJust();
                expect(storePref.join().extract()).toBe(false);
            });
        });
    });

    describe('PreferredUI.tsx', () => {
        let wrapper: ReturnType<typeof shallowMount>;
        let comp: typeof wrapper['vm'];

        async function mount(initialValue: null | boolean, propsData = {}) {
            mockOnce(RubricEditorV2, initialValue);

            wrapper = shallowMount(PreferredUI, {
                localVue,
                propsData: Object.assign({}, {
                    prefName: RubricEditorV2,
                    componentName: 'rubric editor',
                }, propsData),
                slots: {
                    ifUnset: 'unset',
                    ifFalse: 'false',
                    ifTrue: 'true',
                },
            });

            comp = wrapper.vm;
            await comp.$nextTick();
        }

        it.each([
            [null, /unset/],
            [false, /false/],
            [true, /true/],
        ])('should render the correct slot', async (val, toMatch) => {
            await mount(val);

            expect(comp.$el.textContent).toMatch(toMatch);
        });

        it('should not render the switcher at the bottom when no value is set', async () => {
            await mount(null);

            expect(comp.$el.querySelector('.ui-switcher')).toBeNull();
        });

        it.each(
            [true, false],
        )('should render the switcher at the bottom when a value is set', async (val) => {
            await mount(val);

            expect(comp.$el.querySelector('.ui-switcher')).not.toBeNull();
        });
    });
});
