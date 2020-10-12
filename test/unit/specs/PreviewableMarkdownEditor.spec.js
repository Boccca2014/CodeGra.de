/* SPDX-License-Identifier: AGPL-3.0-only */
import PreviewableMarkdownEditor from '@/components/PreviewableMarkdownEditor';
import { mount, createLocalVue } from '@vue/test-utils';
import BootstrapVue from 'bootstrap-vue'
import { Right, Just, Nothing } from '@/utils';

jest.mock('axios');

const localVue = createLocalVue();
localVue.use(BootstrapVue);

describe('PreviewableMarkdownEditor', () => {
    let wrapper;
    let comp;
    let mockEmit;

    async function mountComponent({ initialValue, slots, ...propsData } = {}) {
        wrapper = mount(PreviewableMarkdownEditor, {
            localVue,
            slots,
            propsData: Object.assign(
                {},
                { value: initialValue || '' },
                propsData,
            ),
        });

        comp = wrapper.vm;

        mockEmit = jest.fn();
        comp.$emit = mockEmit;
    }

    async function togglePreview() {
        const toggle = comp.$el.querySelector('.preview-toggle');
        toggle.dispatchEvent(new MouseEvent('click'));
        await comp.$nextTick();
    }

    async function setText(text) {
        const textarea = comp.$el.querySelector('textarea');
        textarea.value = text;
        textarea.dispatchEvent(new InputEvent('input'));
        await comp.$nextTick();
    }

    it('should be possible to toggle an empty editor', async () => {
        await mountComponent();
        expect(comp.$el.querySelector('textarea')).not.toBeNull();

        await togglePreview();
        expect(comp.$el.querySelector('textarea')).toBeNull();

        await togglePreview();
        expect(comp.$el.querySelector('textarea')).not.toBeNull();
    });

    it.each([
        {},
        { slots: { empty: 'message' } },
    ])('should show a message when previewing an empty editor', async (props) => {
        await mountComponent(props);
        await togglePreview();

        expect(comp.$el.querySelector('.empty')).not.toBeNull();
        expect(comp.$el.querySelector('.empty').textContent).toMatch(
            (props.slots && props.slots.empty) || 'Field is empty',
        );
    });

    it('should respect the hide-toggle prop', async () => {
        await mountComponent({ hideToggle: false });
        expect(comp.$el.querySelector('.preview-toggle')).not.toBeNull();

        await mountComponent({ hideToggle: true });
        expect(comp.$el.querySelector('.preview-toggle')).toBeNull();
    });

    it('should render markdown in the preview', async () => {
        await mountComponent({
            initialValue: `
# Heading 1
## Heading 2
### Heading 3

regular text

    code block
    second line
`,
        });
        await togglePreview();

        const markdown = comp.$el.querySelector('.inner-markdown-viewer');
        expect(markdown).not.toBeNull();

        const heading1 = markdown.querySelector('h1');
        expect(heading1.textContent).toMatch('Heading 1');

        const heading2 = markdown.querySelector('h2');
        expect(heading2.textContent).toMatch('Heading 2');

        const heading3 = markdown.querySelector('h3');
        expect(heading3.textContent).toMatch('Heading 3');

        const code = markdown.querySelector('pre');
        expect(code.textContent).toMatch('code block');
        expect(code.textContent).toMatch('second line');
    });
});
