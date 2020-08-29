/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import { getErrorMessage } from '@/utils';

export default Vue.extend({
    name: 'cg-logo',
    functional: true,

    props: {
        error: {
            type: Error,
            required: true,
        },
        wrappingComponent: {
            type: String,
            default: 'b-alert',
        },
    },

    render(h, ctx) {
        return h(
            ctx.props.wrappingComponent,
            {
                attrs: ctx.data.attrs,
                class: [ctx.data.class, `${ctx.data.staticClass ?? ''} cg-error`],
                style: [ctx.data.style, ctx.data.staticStyle],
                props: {
                    show: true,
                    variant: 'danger',
                },
            },
            [getErrorMessage(ctx.props.error)],
        );
    },
});
