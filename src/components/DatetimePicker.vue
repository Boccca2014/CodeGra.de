<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<flat-pickr
    class="form-control datetime-picker"
    :value="value"
    :config="internalConfig"
    @on-change="$emit('on-change', $event)"
    @on-close="$emit('on-close', $event)"
    @on-open="$emit('on-open', $event)"
    />
</template>

<script>
import flatPickr from 'vue-flatpickr-component';
import confirmDatePlugin from 'flatpickr/dist/plugins/confirmDate/confirmDate';

import moment from 'moment';

export default {
    name: 'datetime-picker',
    props: {
        value: {},
        config: {
            type: Object,
            default: () => ({}),
        },
    },

    computed: {
        internalConfig() {
            return Object.assign(
                {},
                {
                    enableTime: true,
                    plugins: [
                        confirmDatePlugin({
                            showAlways: true,
                            confirmIcon: '',
                            confirmText: 'Close',
                        }),
                    ],
                    minuteIncrement: 1,
                    time_24hr: true,
                    onChange: this.emitDate,
                    onClose: this.emitDate,
                    defaultHour: 23,
                    defaultMinute: 59,
                },
                this.config,
            );
        },
    },

    methods: {
        emitDate(selectedDates) {
            if (!selectedDates.length) {
                return;
            }
            const dateToString = date => moment(date).format();

            if (this.internalConfig.mode === 'multiple') {
                this.$emit('input', selectedDates.map(dateToString));
            } else {
                this.$emit('input', dateToString(selectedDates[0]));
            }
        },
    },

    components: {
        flatPickr,
    },
};
</script>

<style lang="less">
@import '~mixins.less';

.datetime-picker {
    &.flatpickr-input:not(:disabled) {
        background-color: white;
    }
    &:disabled {
        cursor: not-allowed !important;
    }

    &.flatpickr-input {
        .default-form-control-colors;
    }
}
</style>

<style src="flatpickr/dist/flatpickr.css"/>

<style src="flatpickr/dist/plugins/confirmDate/confirmDate.css"/>
