/* SPDX-License-Identifier: AGPL-3.0-only */
import SnippetManager from '@/components/SnippetManager';
import { shallowMount, createLocalVue } from '@vue/test-utils';
import VDebounce from 'vue-debounce';
import Vuex from 'vuex';
import BootstrapVue from 'bootstrap-vue'
import router from '@/router';

jest.mock('axios');

const localVue = createLocalVue();
localVue.use(Vuex);
localVue.use(BootstrapVue);
localVue.use(VDebounce);

const snippets = [
    { id: 1, key: 'key_abc', value: 'value_abc' },
    { id: 2, key: 'key_def', value: 'value_def' },
    { id: 3, key: 'duplicate', value: 'duplicate' },
];

describe('SnippetManager.vue', () => {
    let allSnippets;
    let store;
    let wrapper;
    let comp;
    let mockRefresh;
    let mockAdd;
    let mockUpdate;
    let mockRemove;
    let mockPut;
    let mockPatch;
    let mockDelete;

    function cloneSnippets() {
        const ret = {};
        for (let snippet of snippets) {
            ret[snippet.key] = Object.assign({}, snippet);
        }
        return ret;
    }

    function newSnippetId() {
        const ids = Object.values(allSnippets).map(s => s.id);
        return Math.max(...ids) + 1;
    }

    beforeEach(() => {
        allSnippets = cloneSnippets();
        mockRefresh = jest.fn(() => Promise.resolve(true));
        mockAdd = jest.fn();
        mockUpdate = jest.fn();
        mockRemove = jest.fn();
        mockPut = jest.fn(
            snip => Promise.resolve({
                data: Object.assign({}, snip, {
                    id: newSnippetId(),
                }),
            }),
        );
        mockPatch = jest.fn(
            snip => Promise.resolve({ data: {} }),
        );
        mockDelete = jest.fn(() => Promise.resolve({ data: {} }));

        store = new Vuex.Store({
            modules: {
                user: {
                    state: {
                        snippets: allSnippets,
                    },
                    getters: {
                        snippets: () => allSnippets,
                    },
                    actions: {
                        refreshSnippets: mockRefresh,
                        addSnippet: mockAdd,
                        updateSnippet: mockUpdate,
                        deleteSnippet: mockRemove,
                    },
                    namespaced: true,
                },
            },
        });

        wrapper = shallowMount(SnippetManager, {
            router,
            store,
            localVue,
            mocks: {
                $http: {
                    put: mockPut,
                    patch: mockPatch,
                    delete: mockDelete,
                },
            },
        });

        comp = wrapper.vm;
    });

    it('should not be null', () => {
        expect(comp).not.toBe(null);
    });

    describe('saveSnippets', () => {
        it('should add the snippet to the store snippets and to the end of filteredSnippets', async () => {
            const new_snip = {
                key: 'aaa',
                value: 'aaa',
            };

            const num_snips = comp.filteredSnippets.length;

            comp.editingSnippet = new_snip;
            await comp.saveSnippet();

            expect(mockPut).toBeCalledTimes(1);
            expect(mockPatch).toBeCalledTimes(0);

            const snips = comp.filteredSnippets;
            expect(snips.length).toBe(num_snips + 1);
            expect(snips[num_snips].key).toBe(new_snip.key);
            expect(snips[num_snips].value).toBe(new_snip.value);
        });

        it('should not do a request if the snippet has not changed', async () => {
            comp.editingSnippet = comp.snippets[0];

            await comp.saveSnippet();

            expect(mockPut).toBeCalledTimes(0);
            expect(mockPatch).toBeCalledTimes(0);
        });

        async function expectFail(snippet) {
            comp.editingSnippet = snippet;

            let caught = 0;
            try {
                await comp.saveSnippet();
            } catch (e) {
                caught = 1;
            }

            expect(caught).toBe(1);
            expect(mockPut).toBeCalledTimes(0);
            expect(mockPatch).toBeCalledTimes(0);
        }

        it('should fail when the key is empty', async () => {
            await expectFail({ key: '', value: 'not empty' });
        });

        it('should fail when the key contains whitespace', async () => {
            await expectFail({ key: 'key with spaces', value: 'not empty' });
        });

        it('should fail when the value is empty', async () => {
            await expectFail({ key: 'key', value: '' });
        });
    });

    describe('deleteSnippet', () => {
        it('it should remove the snippet from the store and from filteredSnippets', async () => {
            const snip = comp.snippets[0];
            const num_snips = comp.snippets.length;

            await comp.deleteSnippet(snip).then(
                comp.afterDeleteSnippet,
            );

            expect(mockDelete).toBeCalledTimes(1);
            expect(comp.snippets.length).toBe(num_snips - 1);
        });
    });

    describe('filteredSnippets', () => {
        it('should be sorted and contain all snippets in the store', () => {
            const snips = comp.filteredSnippets;
            const keys = Object.keys(allSnippets).sort();

            expect(snips.length).toBe(keys.length);
            for (let i = 0; i < keys.length; i++) {
                expect(snips[i].key).toBe(keys[i]);
            }
        });
    });

    describe('filter', () => {
        it('should filter by key', async () => {
            comp.filter = 'key_abc';

            await comp.$nextTick();
            await comp.$nextTick();

            const snips = comp.filteredSnippets;

            expect(snips.length).toBe(1);
            expect(snips[0].key).toBe('key_abc');
        });

        it('should filter by key', async () => {
            comp.filter = 'value_abc';

            await comp.$nextTick();
            await comp.$nextTick();

            const snips = comp.filteredSnippets;

            expect(snips.length).toBe(1);
            expect(snips[0].key).toBe('key_abc');
        });
    });
});
