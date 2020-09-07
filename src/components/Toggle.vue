<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="toggle-container"
     :class="{ disabled, colors, inline, 'has-no-value': hasNoValue }"
     :checked="current">
    <div :id="toggleId"
         class="toggle-div">
        <div class="label label-off"
            @click="toggle(false)">
            <slot name="label-off">{{ labelOff }}</slot>
        </div>
        <div class="toggle"
             @click="toggle()"/>
        <div class="label label-on"
             @click="toggle(true)">
            <slot name="label-on">{{ labelOn }}</slot>
        </div>
    </div>
    <b-popover placement="top"
               v-if="disabled && disabledText"
               triggers="hover"
               :target="toggleId">
        {{ disabledText }}
    </b-popover>
</div>
</template>

<script>
let i = 0;

export default {
    name: 'toggle',

    props: {
        value: {
            default: false,
        },
        labelOn: {
            type: String,
            default: 'Yes',
        },
        labelOff: {
            type: String,
            default: 'No',
        },
        valueOn: {
            default: true,
        },
        valueOff: {
            default: false,
        },
        disabled: {
            default: false,
        },
        disabledText: {
            default: '',
            type: String,
        },
        colors: {
            default: true,
            type: Boolean,
        },
        inline: {
            default: false,
            type: Boolean,
        },
        hasNoValue: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            current: this.value === this.valueOn,
            toggleId: `toggle-${i++}`,
        };
    },

    watch: {
        value(to) {
            this.current = to === this.valueOn;
        },

        hasNoValue() {
            this.current = this.value === this.valueOn;
        },
    },

    methods: {
        toggle(to) {
            if (this.disabled) return;

            // Do not toggle when the value is not set and the user clicks the toggle button
            // instead of the labels.
            if (to == null && this.hasNoValue) return;

            const newState = to == null ? !this.current : to;

            if (newState !== this.current || this.hasNoValue) {
                this.current = newState;
                this.$emit('input', this.current ? this.valueOn : this.valueOff);
            }
        },
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

@unchecked-opacity: 0.5;

.toggle-container {
    cursor: default;

    &.disabled {
        cursor: not-allowed;
        opacity: 0.75;
    }

    &.inline,
    &.inline .toggle-div {
        display: inline;
    }
}

.label-off,
.label-on,
.toggle {
    display: inline-block;

    vertical-align: top;
    .toggle-container:not(.inline) & {
        vertical-align: middle;
    }

    cursor: pointer;
    .disabled & {
        cursor: not-allowed;
    }
}

.toggle {
    position: relative;
    width: 2.1rem;
    height: 1.2rem;
    margin: 0 0.5rem;
    border-radius: 0.6rem;

    background-color: @color-light-gray;
    transition: background-color @transition-duration;

    &::before {
        content: '';
        display: block;
        width: 1rem;
        height: 1rem;
        transform: translate(0.1rem, 0.1rem);
        border-radius: 50%;

        background-color: white;
        transition: transform @transition-duration;
    }
}

.label-on,
.label-off {
    transition: opacity @transition-duration;
}

.label-on {
    opacity: @unchecked-opacity;
}

.label-off {
    opacity: 1;
}

[checked] {
    &.colors .toggle {
        background-color: @color-primary;

        @{dark-mode} {
            background-color: @color-primary-darkest;
        }
    }

    .toggle::before {
        transform: translate(100%, 0.1rem);
    }

    .label-on {
        opacity: 1;
    }

    .label-off {
        opacity: @unchecked-opacity;
    }
}

.has-no-value {
    .toggle::before {
        transform: scale(0.75) translate(0.75rem, 0.15rem);
        transform-origin: center;
    }

    .label-on,
    .label-off {
        opacity: @unchecked-opacity;
    }
}
</style>
