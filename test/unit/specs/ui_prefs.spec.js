/* SPDX-License-Identifier: AGPL-3.0-only */
import { shallowMount, createLocalVue } from '@vue/test-utils';
import BootstrapVue from 'bootstrap-vue'

import * as utils from '@/utils';
import * as models from '@/models';
import * as api from '@/api/v1';

import PreferredUI from '@/components/PreferredUI';
import { UIPrefsStore } from '@/store'

jest.mock('@/api/v1/ui_prefs');

const localVue = createLocalVue();
localVue.use(BootstrapVue);

const { RubricEditorV2 } = models.UIPreference;

describe('UI preferences', () => {
    function mockOnce(name, value) {
        api.uiPrefs.getUIPreferences.mockResolvedValueOnce({
            data: { [name]: utils.Maybe.fromNullable(value) },
        });
    }

    beforeAll(() => {
        api.uiPrefs.getUIPreferences
            .mockName('api.uiPrefs.getUIPreferences');

        api.uiPrefs.patchUIPreference
            .mockName('api.uiPrefs.patchUIPreference');
    });

    beforeEach(() => {
        UIPrefsStore.commitClear();
        api.uiPrefs.getUIPreferences
            .mockClear()
            .mockResolvedValue({ data: { [RubricEditorV2]: utils.Nothing } });
        api.uiPrefs.patchUIPreference
            .mockClear()
            .mockResolvedValue({ data: null });
    });

    describe('store getters', () => {
        function makePrefs(value) {
            return { [RubricEditorV2]: utils.Maybe.fromNullable(value) };
        }

        describe('uiPrefs', () => {
            it('should return Nothing if the prefs have not been loaded', () => {
                UIPrefsStore.commitClear();

                expect(UIPrefsStore.uiPrefs().isNothing()).toBeTrue();
            });

            it.each(
                [ true, false, null ],
            )('should return the mapping of prefs when the prefs have been loaded', (val) => {
                UIPrefsStore.commitUIPrefs(makePrefs(val));
                const storePrefs = UIPrefsStore.uiPrefs();

                expect(storePrefs).toBeJust();
                expect(storePrefs.extract()).toHaveProperty(RubricEditorV2);
                expect(storePrefs.extract()[RubricEditorV2].extractNullable()).toBe(val);
            });
        });

        describe('getUIPref', () => {
            it('should return Nothing if the prefs have not been loaded', () => {
                UIPrefsStore.commitClear();

                expect(UIPrefsStore.getUIPref()(RubricEditorV2)).toBeNothing();
            });

            it.each(
                [ true, false, null ],
            )('should return the set value if the prefs have been loaded', (val) => {
                UIPrefsStore.commitUIPrefs(makePrefs(val));
                const prefValue = UIPrefsStore.getUIPref()(RubricEditorV2);

                expect(prefValue.extractNullable()).toBe(val);
            });

            it.each([
                [ null, false ],
                [ null, true ],
                [ false, false ],
                [ false, true ],
                [ true, false ],
                [ true, true ],
            ])('should return the patched value if some pref has been patched', async (fromVal, toVal) => {
                UIPrefsStore.commitUIPrefs(makePrefs(fromVal));
                UIPrefsStore.commitPatchedUIPref({ name: RubricEditorV2, value: toVal });
                const prefValue = UIPrefsStore.getUIPref()(RubricEditorV2);

                expect(prefValue.extract()).toBe(toVal);
            });
        });
    });

    describe('store actions', () => {
        describe('loadUIPreferences', () => {
            it('should call the api', async () => {
                const res = await UIPrefsStore.loadUIPreferences();

                expect(api.uiPrefs.getUIPreferences).toBeCalled();

                expect(res).toBeJust();
                expect(res.extract()).toHaveProperty(RubricEditorV2);
                expect(res.extract()[RubricEditorV2]).toBeNothing();
            });

            it('should not call the api twice', async () => {
                const res1 = await UIPrefsStore.loadUIPreferences();
                const res2 = await UIPrefsStore.loadUIPreferences();

                expect(api.uiPrefs.getUIPreferences).toBeCalledTimes(1);

                expect(res1).toBeJust();
                expect(res2).toBeJust();
                expect(res1.extract()).toBe(res2.extract());
            });

            it.each(
                [ true, false, null ],
            )('should update the store', async (val) => {
                mockOnce(RubricEditorV2, val);

                await UIPrefsStore.loadUIPreferences();
                const storePrefs = UIPrefsStore.uiPrefs();

                expect(storePrefs).toBeJust();
                expect(storePrefs.extract()).toHaveProperty(RubricEditorV2);
                expect(storePrefs.extract()[RubricEditorV2].extractNullable()).toBe(val);
            });
        });

        describe('patchUIPreference', () => {
            it.each([
                [ null, false ],
                [ null, true ],
                [ false, false ],
                [ false, true ],
                [ true, false ],
                [ true, true ],
            ])('should call the api', async (fromVal, toVal) => {
                mockOnce(RubricEditorV2, fromVal);

                await UIPrefsStore.loadUIPreferences();
                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: toVal,
                });

                expect(api.uiPrefs.patchUIPreference).toBeCalled();
            });

            it('should call the api each time', async () => {
                await UIPrefsStore.loadUIPreferences();
                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: false
                });
                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: true
                });

                expect(api.uiPrefs.patchUIPreference).toBeCalledTimes(2);
            });

            it('should update the store', async () => {
                await UIPrefsStore.loadUIPreferences();
                let storePrefs = UIPrefsStore.uiPrefs();
                expect(storePrefs.extract()[RubricEditorV2]).toBeNothing();

                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: false,
                });
                storePrefs = UIPrefsStore.uiPrefs();
                expect(storePrefs.extract()[RubricEditorV2].extract()).toBeFalse();

                await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: true,
                });
                storePrefs = UIPrefsStore.uiPrefs();
                expect(storePrefs.extract()[RubricEditorV2].extract()).toBeTrue();
            });

            it('should update the store even if preferences were not loaded', async () => {
                let storePrefs = UIPrefsStore.uiPrefs();
                expect(storePrefs).toBeNothing();

                const res = await UIPrefsStore.patchUIPreference({
                    name: RubricEditorV2,
                    value: false,
                });
                storePrefs = UIPrefsStore.uiPrefs();

                expect(storePrefs).toBeJust();
                expect(storePrefs.extract()[RubricEditorV2].extract()).toBeFalse();
            });
        });
    });

    describe('PreferredUI.tsx', () => {
        let wrapper;
        let comp;

        async function mount(initialValue, propsData = {}) {
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
            [ null, /unset/ ],
            [ false, /false/ ],
            [ true, /true/ ],
        ])('should render the correct slot', async (val, toMatch) => {
            await mount(val);

            expect(comp.$el.textContent).toMatch(toMatch);
        });

        it('should not render the switcher at the bottom when no value is set', async () => {
            await mount(null);

            expect(comp.$el.querySelector('.ui-switcher')).toBeNull();
        });

        it.each(
            [ true, false ],
        )('should render the switcher at the bottom when a value is set', async (val) => {
            await mount(val);

            expect(comp.$el.querySelector('.ui-switcher')).not.toBeNull();
        });
    });
});
