<template>
<div class="submission-limits" v-if="value != null">
    <b-form-fieldset :id="`assignment-max-submissions-${uniqueId}`"
                     :label-for="`assignment-max-submissions-${uniqueId}-input`"
                     :state="maxSubmissions.isRight()">
        <template #label>
            Maximum total amount of submissions
        </template>

        <template #invalid-feedback>
            {{ $utils.getErrorMessage(maxSubmissions.extract()) }}
        </template>

        <template #description>
            The maximum amount of submissions students will be able to make.

            <cg-description-popover hug-text>
                If you leave this value empty, or set it to 0, students will be
                able to make an infinite amount of submissions.
            </cg-description-popover>
        </template>

        <cg-number-input
            :id="`assignment-max-submissions-${uniqueId}-input`"
            :min="0"
            @input="emitValue"
            v-model="maxSubmissions"
            placeholder="Infinite"/>
    </b-form-fieldset>

    <b-form-fieldset :id="`assignment-cool-off-${uniqueId}`"
                     :label-for="`assignment-cool-off-${uniqueId}-amount-input`"
                     :state="coolOffValid">
        <template #label>
            Cool off period
        </template>

        <template #description>
            The frequency students can make submissions.

            <cg-description-popover hug-text docs-path="user/management.html#cool-off-period">
                The first input determines the amount of submissions, and the
                second the time in minutes. You can set the time to zero to
                disable this limit.
            </cg-description-popover>
        </template>

        <template #invalid-feedback>
            <div v-for="err in coolOffErrors">
                {{ $utils.getErrorMessage(err) }}
            </div>
        </template>

        <b-input-group class="cool-off-period-wrapper">
            <cg-number-input
                :id="`assignment-cool-off-${uniqueId}-amount-input`"
                class="amount-in-cool-off-period"
                name="Cool off amount"
                :min="1"
                :required="true"
                v-model="coolOffAmount"
                @input="emitValue"/>

            <b-input-group-prepend is-text>
                <template v-if="parseFloat(coolOffAmount) === 1">
                    submission
                </template>
                <template v-else>
                    submissions
                </template>
                every
            </b-input-group-prepend>

            <cg-number-input
                :id="`assignment-cool-off-${uniqueId}-period-input`"
                class="cool-off-period"
                name="Cool off period"
                :min="0"
                :step="1"
                v-model="coolOffPeriod"
                @input="emitValue"
                placeholder="0"/>

            <b-input-group-append is-text>
                <template v-if="parseFloat(coolOffPeriod) === 1">
                    minute
                </template>
                <template v-else>
                    minutes
                </template>
            </b-input-group-append>
        </b-input-group>
    </b-form-fieldset>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';

import { Either, Left, Right, Nothing } from '@/utils';
import { NumberInputValue, numberInputValue } from './NumberInput';

type MaxSubmissions = number | null;
type CoolOff = {
    period: number | null,
    amount: number | null;
};

export type SubmissionLimitValue = Either<Error, {
    maxSubmissions: MaxSubmissions,
    coolOff: CoolOff,
}>;

@Component
export default class SubmissionLimits extends Vue {
    @Prop({ required: true })
    value!: SubmissionLimitValue;

    maxSubmissions: NumberInputValue = numberInputValue(null);

    coolOffPeriod: NumberInputValue = numberInputValue(0);

    coolOffAmount: NumberInputValue = numberInputValue(1);

    readonly uniqueId: number = this.$utils.getUniqueId();

    get coolOffErrors() {
        return Either.lefts([this.coolOffAmount, this.coolOffPeriod]);
    }

    get coolOffValid() {
        return this.coolOffErrors.length === 0;
    }

    @Watch('value', { immediate: true })
    onValueChanged() {
        this.value.ifRight(value => {
            this.maxSubmissions = numberInputValue(value.maxSubmissions);
            this.coolOffPeriod = numberInputValue(value.coolOff.period);
            this.coolOffAmount = numberInputValue(value.coolOff.amount);
        });
    }

    emitValue() {
        const errors = Either.lefts([
            this.maxSubmissions,
            this.coolOffPeriod,
            this.coolOffAmount,
        ]);

        const { maxSubmissions, coolOffPeriod, coolOffAmount } = this;

        if (errors.length) {
            this.$emit('input', Left(new Error(errors.map(this.$utils.getErrorMessage).join('\n'))));
        } else {
            this.$emit('input', Right({
                maxSubmissions: maxSubmissions.orDefault(Nothing).extractNullable(),
                coolOff: {
                    period: coolOffPeriod.orDefault(Nothing).extractNullable(),
                    amount: coolOffAmount.orDefault(Nothing).extractNullable(),
                },
            }));
        }
    }
}
</script>
