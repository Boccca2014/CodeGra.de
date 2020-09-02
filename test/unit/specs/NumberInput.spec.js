/* SPDX-License-Identifier: AGPL-3.0-only */
import NumberInput from '@/components/NumberInput';
import { shallowMount, createLocalVue } from '@vue/test-utils';
import BootstrapVue from 'bootstrap-vue'
import { Right, Just, Nothing } from '@/utils';

jest.mock('axios');

const localVue = createLocalVue();
localVue.use(BootstrapVue);

describe('NumberInput.vue', () => {
    let wrapper;
    let comp;
    let mockEmit;

    async function mount({ initialValue, ...propsData } = {}) {
        wrapper = shallowMount(NumberInput, {
            localVue,
            propsData: Object.assign({}, {
                value: Right(Nothing),
            }, propsData),
        });

        comp = wrapper.vm;

        if (initialValue != null) {
            await setText(initialValue);
        }

        // This must happen after the above
        mockEmit = jest.fn();

        comp.$emit = mockEmit;
    }

    async function setText(text) {
        comp.$el.value = text;
        comp.$el.dispatchEvent(new InputEvent('input'));
        await comp.$nextTick();
    }

    async function pressDownKey() {
        comp.$el.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'ArrowDown',
            code: 'ArrowDown',
            keyCode: 40,
        }));
        await comp.$nextTick();
    }

    async function pressUpKey() {
        comp.$el.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'ArrowUp',
            code: 'ArrowUp',
            keyCode: 38,
        }));
        await comp.$nextTick();
    }

    function expectEmpty(result) {
        expect(result.isRight()).toBeTrue();
        expect(result.extract().isNothing()).toBeTrue();
    }

    function expectError(result, message = undefined) {
        expect(result.isLeft()).toBeTrue();
        expect(result.extract()).toBeInstanceOf(Error);

        if (message != null) {
            expect(result.extract().message).toMatch(message);
        }
    }

    function expectValue(result, value = undefined) {
        expect(result.isRight()).toBeTrue();
        expect(result.extract().isJust()).toBeTrue();

        if (value != null) {
            expect(result.extract().extract()).toBe(value);
        }
    }

    beforeEach(() => mount());

    it.each([
        ['0', 0],
        ['+0', 0],
        ['-0', -0],
        ['1', 1],
        ['+1', 1],
        ['-1', -1],
        ['0.1', 0.1],
        ['+0.1', 0.1],
        ['-0.1', -0.1],
        ['.25', 0.25],
        ['+.25', 0.25],
        ['-.25', -0.25],
        ['3.', 3],
        ['+3.', 3],
        ['-3.', -3],
        ['5e2', 5e2],
        ['5e2', 5E2],
    ])('should accept "%s" and emit value "%d"', async (text, expected) => {
        await setText(text);

        expect(mockEmit).toBeCalledTimes(1);
        expectValue(mockEmit.mock.calls[0][1], expected);
    });

    it('should accept empty input if the "required" prop is not set', async () => {
        // Setting empty text only doesn't work because it isn't registered as
        // a change to the input value because the input starts
        // await setText('abc');
        await mount({ initialValue: 'abc' });
        await setText('');

        expect(mockEmit).toBeCalledTimes(1);
        expectEmpty(mockEmit.mock.calls[0][1]);
    });

    it('should not accept empty input if the "required" prop is set', async () => {
        await mount({ initialValue: 'abc', required: true });
        await setText('');

        expect(mockEmit).toBeCalledTimes(1);
        expectError(mockEmit.mock.calls[0][1], 'may not be empty');
    });

    it.each([
        ['1', '1.', 1],
        ['1.', '1.0', 1],
        ['1.1', '1.10', 1.1],
    ])('should not rewrite its value when changing from "%s" to "%s"', async (first, second, expected) => {
        await setText(first);
        await setText(second);

        expect(comp.$el.value).toBe(second);
        expect(mockEmit).toBeCalledTimes(2);
        expectValue(mockEmit.mock.calls[0][1], expected);
        expectValue(mockEmit.mock.calls[1][1], expected);
    });

    it.each([
        ['-20', -10],
        ['-10', 0],
        ['-5', 10],
        ['0', 10],
        ['5', 10],
    ])('should not accept number "%s" less than its "min" prop "%d"', async (value, min) => {
        await mount({ min });
        await setText(value);

        expect(comp.$el.value).toBe(value);
        expect(mockEmit).toBeCalledTimes(1);
        expectError(mockEmit.mock.calls[0][1], 'should be greater than or equal to');
    });

    it.each([
        ['-5', -10],
        ['0', -10],
        ['5', -10],
        ['10', 0],
        ['20', 10],
    ])('should not accept number "%s" greater than its "max" prop "%d"', async (value, max) => {
        await mount({ max });
        await setText(value);

        expect(comp.$el.value).toBe(value);
        expect(mockEmit).toBeCalledTimes(1);
        expectError(mockEmit.mock.calls[0][1], 'should be less than or equal to');
    });

    it.each([
        '-',
        '5a',
        'abc',
        '..3',
        '3.4.5',
    ])('should not rewrite its value for non-numeric input "%s"', async (text) => {
        await setText(text);

        expect(comp.$el.value).toBe(text);
        expect(mockEmit).toBeCalledTimes(1);
        expectError(mockEmit.mock.calls[0][1], 'is not a number');
    });

    it('should use its name in error messages', async () => {
        await mount({ name: 'MyName', required: true, min: 0, max: 1 });
        await setText('abc');
        await setText('-1');
        await setText('2');
        await setText('');

        expect(mockEmit).toBeCalledTimes(4);
        for (let [_, result] of mockEmit.mock.calls) {
            expectError(result, /^MyName/);
        }
    });

    it.each([
        'tel',
        'text',
        'number',
        'password',
        'datetime',
    ])('should have the "tel" type even if passed type="%s"', async (type) => {
        await mount({ type });

        expect(comp.$el.type).toBe('tel');
    });

    it.each([
        -10,
        -1,
        1,
        10,
    ])('should decrement with its configured step "%d" when the down key is pressed', async (step) => {
        await mount({ step, initialValue: '0' });

        await pressDownKey();
        expect(comp.$el.value).toBe((-step).toString(10));

        await pressDownKey();
        expect(comp.$el.value).toBe((-2 * step).toString(10));

        expect(mockEmit).toBeCalledTimes(2);
        expectValue(mockEmit.mock.calls[0][1], -step);
        expectValue(mockEmit.mock.calls[1][1], -2 * step);
    });

    it.each([
        -10,
        -1,
        1,
        10,
    ])('should increment with its configured step "%d" when the up key is pressed', async (step) => {
        await mount({ step, initialValue: '0' });

        await pressUpKey();
        expect(comp.$el.value).toBe(step.toString(10));

        await pressUpKey();
        expect(comp.$el.value).toBe((2 * step).toString(10));

        expect(mockEmit).toBeCalledTimes(2);
        expectValue(mockEmit.mock.calls[0][1], step);
        expectValue(mockEmit.mock.calls[1][1], 2 * step);
    });

    it('should do nothing when the step is 0', async () => {
        await mount({ step: 0, initialValue: '0' });

        await pressUpKey();
        expect(comp.$el.value).toBe('0');

        await pressUpKey();
        expect(comp.$el.value).toBe('0');

        await pressDownKey();
        expect(comp.$el.value).toBe('0');

        await pressDownKey();
        expect(comp.$el.value).toBe('0');

        expect(mockEmit).toBeCalledTimes(0);
    });

    it.each([
        '',
        'abc',
        '5a',
    ])('should do nothing when the up or down keys are pressed with value "%s"', async (initialValue) => {
        await mount({ initialValue });

        await pressUpKey();
        expect(comp.$el.value).toBe(initialValue);

        await pressUpKey();
        expect(comp.$el.value).toBe(initialValue);

        await pressDownKey();
        expect(comp.$el.value).toBe(initialValue);

        await pressDownKey();
        expect(comp.$el.value).toBe(initialValue);

        expect(mockEmit).toBeCalledTimes(0);
    });
});
