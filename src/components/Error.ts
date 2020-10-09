/* SPDX-License-Identifier: AGPL-3.0-only */
import * as tsx from 'vue-tsx-support';
import { getErrorMessage } from '@/utils';
import p from 'vue-strict-prop';

export default tsx.component({
    name: 'cg-error',
    functional: true,

    props: {
        error: p(Error).required,
        wrappingComponent: p(String).default('b-alert'),
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
