/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

// @ts-ignore
import { readableFormatDate } from '@/utils';

export default tsx.component({
    functional: true,

    props: {
        date: p(Object as () => moment.Moment).validator(moment.isMoment).required,
    },

    render(h, ctx) {
        return h(
            'span',
            {
                attrs: Object.assign(
                    {
                        title: readableFormatDate(ctx.props.date),
                    },
                    ctx.data.attrs,
                ),
                class: ctx.data.staticClass,
                style: ctx.data.style,
            },
            [ctx.props.date.from(ctx.parent.$root.$now)],
        );
    },
});
