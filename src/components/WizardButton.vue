<script lang="ts">
import Vue, { VNodeData } from 'vue';

import 'vue-awesome/icons/file-o';

import * as utils from '@/utils';

type ButtonSize = 'small' | 'medium' | 'large';

function isButtonSize(value: any): value is ButtonSize {
    return typeof value === 'string' && ['small', 'medium', 'large'].includes(value);
}

const ICON_SCALES: Record<ButtonSize, number> = Object.freeze(<const>{
    small: 3,
    medium: 4,
    large: 6,
});

const FILE_ICON_SCALES: Record<ButtonSize, number> = Object.freeze(<const>{
    small: 1.5,
    medium: 2,
    large: 2,
});

export default Vue.component('wizard-button', {
    functional: true,

    props: {
        icon: {
            type: String,
            required: true,
        },
        isFileIcon: {
            type: Boolean,
            default: false,
        },
        label: {
            type: String,
            default: '',
        },
        size: {
            type: String,
            default: 'medium',
        },
        popover: {
            type: String,
            default: '',
        },
    },

    render(h, ctx) {
        utils.AssertionError.assert(
            isButtonSize(ctx.props.size),
            `Invalid button size: ${ctx.props.size}`,
        );

        const slots = ctx.slots();

        let icon;
        if (ctx.props.isFileIcon) {
            icon = h(
                'div',
                {
                    class: 'file-icon',
                },
                [
                    h('fa-icon', {
                        attrs: {
                            name: 'file-o',
                            scale: ICON_SCALES[ctx.props.size],
                        },
                    }),
                    h('fa-icon', {
                        attrs: {
                            name: ctx.props.icon,
                            scale: FILE_ICON_SCALES[ctx.props.size],
                        },
                        class: 'center',
                    }),
                ],
            );
        } else {
            icon = h('fa-icon', {
                attrs: {
                    name: ctx.props.icon,
                    scale: ICON_SCALES[ctx.props.size],
                },
            });
        }

        const label = h(
            'div',
            {
                class: ctx.props.size === 'small' ? 'pt-1' : 'pt-2',
            },
            [slots.default || ctx.props.label],
        );

        const wizardBtn = h(
            'b-button',
            {
                attrs: ctx.data.attrs,
                class: {
                    'wizard-button': true,
                    [ctx.props.size]: true,
                },
                // Pass all event listeners on to the button, not the wrapper div.
                on: ctx.listeners,
            },
            [icon, label],
        );

        const wrapperArgs: VNodeData = {
            class: `wizard-button-container ${ctx.data.staticClass || ''} ${ctx.data.class || ''}`,
            style: Object.assign({}, ctx.data.staticStyle, ctx.data.style),
        };

        if (ctx.props.popover) {
            wrapperArgs.directives = [
                {
                    name: 'b-popover',
                    value: ctx.props.popover,
                    modifiers: {
                        top: true,
                        hover: true,
                    },
                },
            ];
        }

        return h('div', wrapperArgs, [wizardBtn]);
    },
});
</script>

<!-- Can't use scoped style here because when a functional component has
     a scoped style it will only set its own `data-v-XXX` attribute and it will
     not use its parent's one
     https://github.com/vuejs/vue-loader/issues/1136 -->
<style lang="less">
@import '~mixins.less';

.wizard-button {
    &.small {
        width: 8rem;
        height: 8rem;
        padding: 1.75rem 0.5rem;
    }

    &.medium {
        width: 10rem;
        height: 10rem;
        padding: 2rem 0.5rem;
    }

    &.large {
        width: 14rem;
        height: 14rem;
        padding: 3rem 0.5rem;
    }

    &.btn-danger {
        color: @color-danger;
        background-color: fade(@color-danger, 25%) !important;

        &:hover {
            background-color: fade(@color-danger, 35%) !important;
        }
    }
}

.file-icon {
    position: relative;

    .center {
        position: absolute;
        top: 60%;
        left: 50%;
        transform: translate(-50%, -50%);
    }
}
</style>
