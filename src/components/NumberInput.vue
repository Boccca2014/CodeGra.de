<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<input v-model="userInput"
       @keydown.down="decValue"
       @keydown.up="incValue"
       class="number-input form-control"
       :name="name"
       type="tel"/>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import { Either, Left, Right, Maybe, Nothing } from '@/utils';

export type NumberInputValue = Either<Error, Maybe<number>>

export function numberInputValue(x: number | null) {
    return Right(Maybe.fromNullable(x));
}

@Component
export default class NumberInput extends Vue {
    _tsx!: tsx.DeclareProps<Pick<NumberInput, any>>;

    @Prop({ required: true })
    value!: NumberInputValue;

    // The <input>'s "type" attribute _must_ be "tel", so we have a prop named
    // "type" to prevent the <input>'s "type" attribute to be overridden, while
    // still allowing to set other <input> attributes on the component.
    @Prop({ type: String, default: 'tel' })
    type!: string;

    @Prop({ type: Number, default: 1 })
    step!: number;

    @Prop({ type: Number, default: -Infinity })
    min!: number;

    @Prop({ type: Number, default: Infinity })
    max!: number;

    @Prop({ type: String, default: 'Value' })
    name!: string;

    @Prop({ type: Boolean, default: false })
    required!: boolean;

    userInput: string = '';

    @Watch('value', { immediate: true })
    onValueChanged() {
        this.value.ifRight(maybeValue => {
            const value = maybeValue.extractNullable();
            if (value == null) {
                this.userInput = '';
            } else if (value !== this.internalValue.orDefault(Nothing).extractNullable()) {
                this.userInput = value.toString(10);
            }
        });
    }

    @Watch('userInput', { immediate: true })
    emitValue() {
        this.$emit('input', this.internalValue);
    }

    get internalValue(): NumberInputValue {
        const parsed = this.$utils.parseOrKeepFloat(this.userInput);

        if (!this.userInput) {
            if (this.required) {
                return Left(new Error(`${this.name} may not be empty.`));
            } else {
                return numberInputValue(null);
            }
        } else if (Number.isNaN(parsed)) {
            return Left(new Error(`${this.name} is not a number.`));
        } else if (parsed < this.min) {
            return Left(new Error(`${this.name} should be greater than or equal to ${this.min}.`));
        } else if (parsed > this.max) {
            return Left(new Error(`${this.name} should be less than or equal to ${this.max}.`));
        } else {
            return numberInputValue(parsed);
        }
    }

    decValue() {
        this.maybeUpdate(v => v - this.step);
    }

    incValue() {
        this.maybeUpdate(v => v + this.step);
    }

    maybeUpdate(f: (v: number) => number) {
        this.internalValue.ifRight(maybeValue => maybeValue.ifJust(value => {
            const newValue = Math.max(this.min, Math.min(this.max, f(value)));
            this.userInput = newValue.toString(10);
        }));
    }
}
</script>

<style lang="less" scoped>
input {
    text-align: right;
}
</style>
